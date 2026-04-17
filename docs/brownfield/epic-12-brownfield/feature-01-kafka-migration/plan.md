# Feature: NATS JetStream → Apache Kafka Migration

## /plan prompt

```
Implement the Kafka migration with these technical decisions:

## Broker Abstraction — Go (pkg/broker/)

```go
// pkg/broker/broker.go
type Message struct {
    Key     string
    Value   []byte
    Headers map[string]string
    Topic   string
}

type MessageHandler func(ctx context.Context, msg Message) error

type Publisher interface {
    Publish(ctx context.Context, topic string, key string, value []byte) error
    PublishWithHeaders(ctx context.Context, topic string, key string, value []byte, headers map[string]string) error
    Close() error
}

type Subscriber interface {
    Subscribe(ctx context.Context, topics []string, group string, handler MessageHandler) error
    Close() error
}

type Broker interface {
    Publisher
    Subscriber
}
```

## Kafka Implementation — Go (pkg/broker/kafka/)

```go
// pkg/broker/kafka/kafka.go
type Config struct {
    Brokers       []string
    TopicPrefix   string  // "estategap."
    SASLUsername   string
    SASLPassword   string
    TLSEnabled    bool
    MaxRetries    int     // 3
    DeadLetterTopic string // "estategap.dead-letter"
}

// KafkaBroker implements broker.Broker
type KafkaBroker struct {
    writer *kafka.Writer      // segmentio/kafka-go
    config Config
}

func (b *KafkaBroker) Publish(ctx context.Context, topic, key string, value []byte) error {
    return b.writer.WriteMessages(ctx, kafka.Message{
        Topic: b.config.TopicPrefix + topic,
        Key:   []byte(key),
        Value: value,
    })
}
```

- Use `kafka.NewWriter` with `Balancer: &kafka.Hash{}` for consistent key-based partitioning
- Consumer: `kafka.NewReader` with `GroupID`, `MinBytes: 1e3`, `MaxBytes: 10e6`, `CommitInterval: 1s`
- Dead letter: on handler error after MaxRetries, publish to DLT with headers: `x-original-topic`, `x-error`, `x-retry-count`, `x-timestamp`

## Kafka Implementation — Python (libs/common/broker/kafka/)

```python
# libs/common/broker/kafka_broker.py
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

class KafkaBroker:
    def __init__(self, config: KafkaConfig):
        self.config = config
        self.producer = AIOKafkaProducer(
            bootstrap_servers=config.brokers,
            key_serializer=lambda k: k.encode(),
            value_serializer=lambda v: v,
        )
        
    async def publish(self, topic: str, key: str, value: bytes) -> None:
        full_topic = f"{self.config.topic_prefix}{topic}"
        await self.producer.send_and_wait(full_topic, value=value, key=key)
    
    async def subscribe(self, topics: list[str], group: str, handler) -> None:
        full_topics = [f"{self.config.topic_prefix}{t}" for t in topics]
        consumer = AIOKafkaConsumer(
            *full_topics,
            bootstrap_servers=self.config.brokers,
            group_id=group,
            enable_auto_commit=False,  # Manual commit for at-least-once
        )
        await consumer.start()
        try:
            async for msg in consumer:
                try:
                    await handler(Message(key=msg.key, value=msg.value, topic=msg.topic))
                    await consumer.commit()
                except Exception as e:
                    await self._handle_failure(msg, e)
        finally:
            await consumer.stop()
```

## Topic Init Job (helm/estategap/templates/kafka-topics-init.yaml)

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: estategap-kafka-topics-init
  annotations:
    "helm.sh/hook": pre-install,pre-upgrade
    "helm.sh/hook-weight": "-5"
spec:
  template:
    spec:
      containers:
        - name: kafka-topics
          image: bitnami/kafka:3.7
          command: ["/bin/bash", "-c"]
          args:
            - |
              TOPICS="raw-listings:10:7 normalized-listings:10:7 enriched-listings:10:7 scored-listings:10:7 alerts-triggers:5:3 alerts-notifications:5:3 scraper-commands:5:1 price-changes:5:7 dead-letter:3:30"
              for SPEC in $TOPICS; do
                IFS=: read -r NAME PARTS RETENTION <<< "$SPEC"
                kafka-topics.sh --bootstrap-server {{ .Values.kafka.brokers }} \
                  --create --if-not-exists \
                  --topic {{ .Values.kafka.topicPrefix }}${NAME} \
                  --partitions ${PARTS} \
                  --config retention.ms=$((RETENTION * 86400000))
              done
      restartPolicy: Never
```

## Service Migration Order

1. **libs/**: Create broker abstraction + Kafka implementation (Go + Python)
2. **spider-workers**: Replace NATS publish with Kafka publish
3. **pipeline**: Replace all NATS consumers/publishers
4. **ml-scorer**: Replace NATS consumer/publisher
5. **scrape-orchestrator**: Replace NATS publisher
6. **alert-engine**: Replace NATS consumers
7. **alert-dispatcher**: Replace NATS consumer
8. **ws-server**: Replace NATS subscriber for real-time notifications
9. **Cleanup**: Remove all NATS code, configs, Helm templates, dependencies

## Consumer Lag Metrics

```go
// Exposed by each consumer service
kafkaConsumerLag = prometheus.NewGaugeVec(prometheus.GaugeOpts{
    Name: "estategap_kafka_consumer_lag",
    Help: "Kafka consumer group lag per topic partition",
}, []string{"group", "topic", "partition"})
```

Calculated by comparing `HighWaterMark` from consumer stats with current offset.

## Helm Values — Kafka Section

```yaml
kafka:
  brokers: "kafka-bootstrap.kafka.svc.cluster.local:9092"
  topicPrefix: "estategap."
  sasl:
    enabled: false
    username: ""
    password: ""
    mechanism: "PLAIN"          # PLAIN, SCRAM-SHA-256, SCRAM-SHA-512
    credentialsSecret: ""       # K8s Secret name (overrides username/password)
  tls:
    enabled: false
    caSecret: ""                # K8s Secret with ca.crt
  consumer:
    maxRetries: 3
    retryBackoffMs: 1000
  deadLetter:
    enabled: true
    topic: "estategap.dead-letter"
    retentionDays: 30
```

## Test Adaptation

- Testcontainers: replace NATS container with `testcontainers-kafka` (Go) / `testcontainers` Kafka module (Python)
- E2E tests on kind: deploy a single-node Kafka (Strimzi operator or Bitnami Helm chart) in the test cluster
- All existing NATS integration tests rewritten for Kafka with same assertions
```
