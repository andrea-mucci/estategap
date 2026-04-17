package broker

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/segmentio/kafka-go"
	"github.com/segmentio/kafka-go/sasl/plain"
)

const (
	defaultTopicPrefix = "estategap."
	defaultMaxRetries  = 3
	deadLetterTopic    = "dead-letter"
	errorHeaderLimit   = 512
)

// KafkaConfig configures the shared Kafka broker.
type KafkaConfig struct {
	Brokers     []string
	TopicPrefix string
	MaxRetries  int
	TLSEnabled  bool
	SASLUser    string
	SASLPass    string
}

// KafkaBroker implements the Broker interface with kafka-go.
type KafkaBroker struct {
	cfg     KafkaConfig
	dialer  *kafka.Dialer
	mu      sync.RWMutex
	writers map[string]*kafka.Writer
	readers map[*kafka.Reader]struct{}
}

// NewKafkaBroker constructs a Kafka-backed broker with lazy producers.
func NewKafkaBroker(cfg KafkaConfig) (*KafkaBroker, error) {
	brokers := make([]string, 0, len(cfg.Brokers))
	for _, broker := range cfg.Brokers {
		trimmed := strings.TrimSpace(broker)
		if trimmed != "" {
			brokers = append(brokers, trimmed)
		}
	}
	if len(brokers) == 0 {
		return nil, errors.New("kafka broker requires at least one bootstrap server")
	}

	normalized := KafkaConfig{
		Brokers:     brokers,
		TopicPrefix: normalizeTopicPrefix(cfg.TopicPrefix),
		MaxRetries:  cfg.MaxRetries,
		TLSEnabled:  cfg.TLSEnabled,
		SASLUser:    strings.TrimSpace(cfg.SASLUser),
		SASLPass:    cfg.SASLPass,
	}
	if normalized.MaxRetries < 1 {
		normalized.MaxRetries = defaultMaxRetries
	}

	dialer := &kafka.Dialer{
		Timeout:   10 * time.Second,
		DualStack: true,
	}
	if normalized.TLSEnabled {
		dialer.TLS = &tls.Config{
			MinVersion: tls.VersionTLS12,
		}
	}
	if normalized.SASLUser != "" || normalized.SASLPass != "" {
		dialer.SASLMechanism = plain.Mechanism{
			Username: normalized.SASLUser,
			Password: normalized.SASLPass,
		}
	}

	return &KafkaBroker{
		cfg:     normalized,
		dialer:  dialer,
		writers: make(map[string]*kafka.Writer),
		readers: make(map[*kafka.Reader]struct{}),
	}, nil
}

// Dialer exposes the configured Kafka dialer for health checks.
func (b *KafkaBroker) Dialer() *kafka.Dialer {
	return b.dialer
}

// TopicName resolves a short topic name to its fully-qualified Kafka topic.
func (b *KafkaBroker) TopicName(topic string) string {
	return b.topicName(topic)
}

// Publish writes a message to a Kafka topic without custom headers.
func (b *KafkaBroker) Publish(ctx context.Context, topic string, key string, value []byte) error {
	return b.PublishWithHeaders(ctx, topic, key, value, nil)
}

// PublishWithHeaders writes a message to a Kafka topic with string headers.
func (b *KafkaBroker) PublishWithHeaders(
	ctx context.Context,
	topic string,
	key string,
	value []byte,
	headers map[string]string,
) error {
	writer := b.writerForTopic(topic)
	if err := writer.WriteMessages(ctx, kafka.Message{
		Key:     []byte(key),
		Value:   append([]byte(nil), value...),
		Headers: headersToKafka(headers),
	}); err != nil {
		return fmt.Errorf("publish kafka message to %s: %w", b.topicName(topic), err)
	}
	return nil
}

// NewReader creates and tracks a kafka-go reader for the given topic/group pair.
func (b *KafkaBroker) NewReader(topic string, group string) (*kafka.Reader, error) {
	shortTopic := strings.TrimSpace(topic)
	if shortTopic == "" {
		return nil, errors.New("kafka reader requires a topic")
	}
	if strings.TrimSpace(group) == "" {
		return nil, errors.New("kafka reader requires a consumer group")
	}

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:        b.cfg.Brokers,
		GroupID:        strings.TrimSpace(group),
		Topic:          b.topicName(shortTopic),
		MinBytes:       1e3,
		MaxBytes:       10e6,
		CommitInterval: time.Second,
		StartOffset:    kafka.LastOffset,
		Dialer:         b.dialer,
	})

	b.mu.Lock()
	b.readers[reader] = struct{}{}
	b.mu.Unlock()

	return reader, nil
}

// Subscribe consumes all provided topics concurrently until the context is cancelled.
func (b *KafkaBroker) Subscribe(
	ctx context.Context,
	topics []string,
	group string,
	handler MessageHandler,
) error {
	if len(topics) == 0 {
		return errors.New("kafka subscription requires at least one topic")
	}

	subCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	errCh := make(chan error, len(topics))
	var wg sync.WaitGroup

	for _, topic := range topics {
		reader, err := b.NewReader(topic, group)
		if err != nil {
			return err
		}
		wg.Add(1)
		go func(rd *kafka.Reader) {
			defer wg.Done()
			if err := b.ConsumeReader(subCtx, rd, group, handler); err != nil && !errors.Is(err, context.Canceled) {
				errCh <- err
			}
		}(reader)
	}

	done := make(chan struct{})
	go func() {
		wg.Wait()
		close(done)
	}()

	select {
	case <-ctx.Done():
		<-done
		return nil
	case err := <-errCh:
		cancel()
		<-done
		return err
	case <-done:
		return nil
	}
}

// ConsumeReader drains a single reader and applies retry + dead-letter handling.
func (b *KafkaBroker) ConsumeReader(
	ctx context.Context,
	reader *kafka.Reader,
	group string,
	handler MessageHandler,
) error {
	defer func() {
		_ = reader.Close()
		b.mu.Lock()
		delete(b.readers, reader)
		b.mu.Unlock()
	}()

	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			if errors.Is(err, context.Canceled) || ctx.Err() != nil {
				return nil
			}
			return fmt.Errorf("fetch kafka message: %w", err)
		}

		envelope := Message{
			Key:     string(msg.Key),
			Value:   append([]byte(nil), msg.Value...),
			Headers: kafkaHeadersToMap(msg.Headers),
			Topic:   msg.Topic,
		}

		var handlerErr error
		for attempt := 1; attempt <= b.cfg.MaxRetries; attempt++ {
			handlerErr = handler(ctx, envelope)
			if handlerErr == nil {
				if err := reader.CommitMessages(ctx, msg); err != nil {
					return fmt.Errorf("commit kafka message: %w", err)
				}
				break
			}

			if attempt == b.cfg.MaxRetries {
				if err := b.publishDeadLetter(ctx, envelope, handlerErr, attempt, group); err != nil {
					return err
				}
				if err := reader.CommitMessages(ctx, msg); err != nil {
					return fmt.Errorf("commit dead-lettered kafka message: %w", err)
				}
			}
		}
	}
}

func (b *KafkaBroker) publishDeadLetter(
	ctx context.Context,
	message Message,
	handlerErr error,
	retryCount int,
	service string,
) error {
	headers := make(map[string]string, len(message.Headers)+5)
	for key, value := range message.Headers {
		headers[key] = value
	}
	headers["x-original-topic"] = message.Topic
	headers["x-error"] = truncateString(handlerErr.Error(), errorHeaderLimit)
	headers["x-retry-count"] = strconv.Itoa(retryCount)
	headers["x-timestamp"] = time.Now().UTC().Format(time.RFC3339)
	headers["x-service"] = strings.TrimSpace(service)

	if err := b.PublishWithHeaders(ctx, deadLetterTopic, message.Key, message.Value, headers); err != nil {
		return fmt.Errorf("publish dead-letter message: %w", err)
	}
	return nil
}

// Close stops all readers and writers owned by the broker.
func (b *KafkaBroker) Close() error {
	b.mu.Lock()
	defer b.mu.Unlock()

	var closeErr error
	for reader := range b.readers {
		if err := reader.Close(); err != nil && closeErr == nil {
			closeErr = err
		}
	}
	b.readers = make(map[*kafka.Reader]struct{})

	for topic, writer := range b.writers {
		if err := writer.Close(); err != nil && closeErr == nil {
			closeErr = err
		}
		delete(b.writers, topic)
	}

	return closeErr
}

func (b *KafkaBroker) writerForTopic(topic string) *kafka.Writer {
	fullTopic := b.topicName(topic)

	b.mu.RLock()
	writer, ok := b.writers[fullTopic]
	b.mu.RUnlock()
	if ok {
		return writer
	}

	b.mu.Lock()
	defer b.mu.Unlock()
	if writer, ok := b.writers[fullTopic]; ok {
		return writer
	}

	writer = &kafka.Writer{
		Addr:         kafka.TCP(b.cfg.Brokers...),
		Topic:        fullTopic,
		Balancer:     &kafka.Hash{},
		BatchSize:    100,
		BatchTimeout: 10 * time.Millisecond,
		Async:        false,
		Transport: &kafka.Transport{
			TLS:         b.dialer.TLS,
			SASL:        b.dialer.SASLMechanism,
			ClientID:    "estategap",
			IdleTimeout: 30 * time.Second,
		},
	}
	b.writers[fullTopic] = writer
	return writer
}

func (b *KafkaBroker) topicName(topic string) string {
	trimmed := strings.TrimSpace(topic)
	if strings.HasPrefix(trimmed, b.cfg.TopicPrefix) {
		return trimmed
	}
	return b.cfg.TopicPrefix + trimmed
}

func kafkaHeadersToMap(headers []kafka.Header) map[string]string {
	result := make(map[string]string, len(headers))
	for _, header := range headers {
		result[header.Key] = string(header.Value)
	}
	return result
}

func headersToKafka(headers map[string]string) []kafka.Header {
	if len(headers) == 0 {
		return nil
	}

	keys := make([]string, 0, len(headers))
	for key := range headers {
		keys = append(keys, key)
	}
	sort.Strings(keys)

	result := make([]kafka.Header, 0, len(headers))
	for _, key := range keys {
		result = append(result, kafka.Header{
			Key:   key,
			Value: []byte(headers[key]),
		})
	}
	return result
}

func normalizeTopicPrefix(prefix string) string {
	trimmed := strings.TrimSpace(prefix)
	if trimmed == "" {
		return defaultTopicPrefix
	}
	if strings.HasSuffix(trimmed, ".") {
		return trimmed
	}
	return trimmed + "."
}

func truncateString(value string, limit int) string {
	if limit <= 0 || len(value) <= limit {
		return value
	}
	return value[:limit]
}
