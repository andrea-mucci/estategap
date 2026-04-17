//go:build integration

package consumer

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	sharedbroker "github.com/estategap/libs/broker"
	"github.com/estategap/testhelpers"
	"github.com/estategap/services/alert-dispatcher/internal/dispatcher"
	"github.com/estategap/services/alert-dispatcher/internal/metrics"
	"github.com/estategap/services/alert-dispatcher/internal/model"
	"github.com/estategap/services/alert-dispatcher/internal/repository"
	senderpkg "github.com/estategap/services/alert-dispatcher/internal/sender"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/testcontainers/testcontainers-go/modules/postgres"
)

type successSender struct{}

func (successSender) Send(_ context.Context, _ model.NotificationEvent, _ *model.UserChannelProfile) (model.DeliveryResult, error) {
	now := time.Now().UTC()
	return model.DeliveryResult{Success: true, DeliveredAt: &now}, nil
}

func TestConsumerCreatesSingleHistoryRecordPerEvent(t *testing.T) {
	ctx := context.Background()

	bootstrapAddr, cleanup := testhelpers.StartKafkaContainer(t)
	defer cleanup()

	pgContainer, err := postgres.Run(ctx, "postgres:16-alpine",
		postgres.WithDatabase("estategap"),
		postgres.WithUsername("postgres"),
		postgres.WithPassword("postgres"),
	)
	if err != nil {
		t.Fatalf("start postgres container: %v", err)
	}
	defer testcontainers.TerminateContainer(pgContainer)

	dsn, err := pgContainer.ConnectionString(ctx, "sslmode=disable")
	if err != nil {
		t.Fatalf("postgres dsn: %v", err)
	}

	primaryPool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatalf("connect postgres: %v", err)
	}
	defer primaryPool.Close()

	replicaPool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatalf("connect replica postgres: %v", err)
	}
	defer replicaPool.Close()

	_, _ = primaryPool.Exec(ctx, `
		CREATE TABLE users (
			id UUID PRIMARY KEY,
			email TEXT NOT NULL,
			preferred_language TEXT NOT NULL DEFAULT 'en',
			telegram_chat_id BIGINT NULL,
			push_subscription_json TEXT NULL,
			phone_e164 TEXT NULL,
			webhook_secret TEXT NULL
		)
	`)
	_, _ = primaryPool.Exec(ctx, `
		CREATE TABLE alert_history (
			id UUID PRIMARY KEY,
			event_id UUID NULL,
			rule_id UUID NOT NULL,
			listing_id UUID NULL,
			channel TEXT NOT NULL,
			delivery_status TEXT NOT NULL,
			attempt_count SMALLINT NOT NULL,
			error_detail TEXT NULL,
			delivered_at TIMESTAMPTZ NULL,
			triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
		)
	`)
	_, _ = primaryPool.Exec(ctx, `CREATE UNIQUE INDEX uq_alert_history_event_channel ON alert_history (event_id, channel) WHERE event_id IS NOT NULL`)
	_, _ = primaryPool.Exec(ctx, `INSERT INTO users (id, email) VALUES ('11111111-1111-1111-1111-111111111111', 'user@example.com')`)

	kafkaBroker, err := sharedbroker.NewKafkaBroker(sharedbroker.KafkaConfig{Brokers: []string{bootstrapAddr}})
	if err != nil {
		t.Fatalf("create kafka broker: %v", err)
	}
	defer func() { _ = kafkaBroker.Close() }()

	userRepo := repository.NewUserRepo(primaryPool, replicaPool)
	historyRepo := repository.NewHistoryRepo(primaryPool, replicaPool)
	dispatcherSvc := dispatcher.New(map[string]senderpkg.Sender{
		model.ChannelEmail: successSender{},
	}, historyRepo, userRepo, metrics.New())
	consumerSvc := New(kafkaBroker, dispatcherSvc, metrics.New(), 1)

	runCtx, cancel := context.WithCancel(ctx)
	defer cancel()
	go func() {
		_ = consumerSvc.Start(runCtx, 1)
	}()

	event := model.NotificationEvent{
		EventID: "22222222-2222-2222-2222-222222222222",
		UserID:  "11111111-1111-1111-1111-111111111111",
		RuleID:  "33333333-3333-3333-3333-333333333333",
		Channel: model.ChannelEmail,
	}
	payload, _ := json.Marshal(event)
	if err := kafkaBroker.Publish(ctx, "alerts-notifications", event.UserID, payload); err != nil {
		t.Fatalf("publish first event: %v", err)
	}
	if err := kafkaBroker.Publish(ctx, "alerts-notifications", event.UserID, payload); err != nil {
		t.Fatalf("publish duplicate event: %v", err)
	}

	deadline := time.Now().Add(20 * time.Second)
	for time.Now().Before(deadline) {
		var count int
		if err := primaryPool.QueryRow(ctx, `SELECT COUNT(*) FROM alert_history WHERE event_id = $1::uuid`, event.EventID).Scan(&count); err == nil && count == 1 {
			return
		}
		time.Sleep(500 * time.Millisecond)
	}

	t.Fatalf("timed out waiting for exactly one alert_history record")
}
