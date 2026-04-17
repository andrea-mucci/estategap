package broker

import "context"

// Message is the canonical event envelope for broker-delivered messages.
type Message struct {
	Key     string
	Value   []byte
	Headers map[string]string
	Topic   string
}

// MessageHandler is invoked for every consumed message.
type MessageHandler func(context.Context, Message) error

// Publisher publishes events to a named topic.
type Publisher interface {
	Publish(ctx context.Context, topic string, key string, value []byte) error
	PublishWithHeaders(ctx context.Context, topic string, key string, value []byte, headers map[string]string) error
	Close() error
}

// Subscriber consumes events from one or more topics as a named group.
type Subscriber interface {
	Subscribe(ctx context.Context, topics []string, group string, handler MessageHandler) error
	Close() error
}

// Broker combines Publisher and Subscriber behaviours.
type Broker interface {
	Publisher
	Subscriber
}
