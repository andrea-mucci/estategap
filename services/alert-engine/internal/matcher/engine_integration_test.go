//go:build integration

package matcher_test

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/estategap/services/alert-engine/internal/cache"
	"github.com/estategap/services/alert-engine/internal/dedup"
	"github.com/estategap/services/alert-engine/internal/matcher"
	"github.com/estategap/services/alert-engine/internal/metrics"
	"github.com/estategap/services/alert-engine/internal/model"
	"github.com/estategap/services/alert-engine/internal/repository"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
)

func TestEngineMatchIntegration(t *testing.T) {
	ctx := context.Background()

	postgresC, pgDSN := startPostgres(t, ctx)
	defer func() { _ = postgresC.Terminate(ctx) }()

	redisC, redisURL := startRedis(t, ctx)
	defer func() { _ = redisC.Terminate(ctx) }()

	primaryPool, err := pgxpool.New(ctx, pgDSN)
	if err != nil {
		t.Fatalf("create primary pool: %v", err)
	}
	defer primaryPool.Close()

	replicaPool, err := pgxpool.New(ctx, pgDSN)
	if err != nil {
		t.Fatalf("create replica pool: %v", err)
	}
	defer replicaPool.Close()

	rdb := redis.NewClient(&redis.Options{Addr: redisURL})
	defer func() { _ = rdb.Close() }()

	userID := "550e8400-e29b-41d4-a716-446655440001"
	ruleID := "550e8400-e29b-41d4-a716-446655440002"
	zoneID := "550e8400-e29b-41d4-a716-446655440003"
	listingID := "550e8400-e29b-41d4-a716-446655440004"

	mustExec(t, ctx, primaryPool, `
		CREATE EXTENSION IF NOT EXISTS postgis;
		CREATE TABLE zones (
			id UUID PRIMARY KEY,
			country_code CHAR(2) NOT NULL,
			geometry geometry(MULTIPOLYGON, 4326),
			bbox geometry(POLYGON, 4326)
		);
		CREATE TABLE alert_rules (
			id UUID PRIMARY KEY,
			user_id UUID NOT NULL,
			name VARCHAR(255) NOT NULL,
			zone_ids UUID[] NOT NULL,
			category VARCHAR(50) NOT NULL,
			filter JSONB NOT NULL DEFAULT '{}'::jsonb,
			channels JSONB NOT NULL DEFAULT '[]'::jsonb,
			frequency VARCHAR(10) NOT NULL DEFAULT 'instant',
			is_active BOOLEAN NOT NULL DEFAULT TRUE
		);
	`)

	mustExec(t, ctx, primaryPool, fmt.Sprintf(`
		INSERT INTO zones (id, country_code, geometry, bbox)
		VALUES (
			'%s',
			'ES',
			ST_GeomFromText('MULTIPOLYGON(((-3.75 40.40,-3.75 40.45,-3.68 40.45,-3.68 40.40,-3.75 40.40)))', 4326),
			ST_GeomFromText('POLYGON((-3.75 40.40,-3.75 40.45,-3.68 40.45,-3.68 40.40,-3.75 40.40))', 4326)
		);
		INSERT INTO alert_rules (id, user_id, name, zone_ids, category, filter, channels, frequency, is_active)
		VALUES (
			'%s',
			'%s',
			'Test rule',
			ARRAY['%s']::uuid[],
			'residential',
			'{"price_max":500000,"deal_tier_max":2}'::jsonb,
			'[{"type":"email"}]'::jsonb,
			'instant',
			TRUE
		);
	`, zoneID, ruleID, userID, zoneID))

	registry := metrics.New()
	repo := repository.New(primaryPool, replicaPool)
	ruleCache := cache.New(registry)
	if err := ruleCache.Load(ctx, repo); err != nil {
		t.Fatalf("load cache: %v", err)
	}

	dedupStore := dedup.New(rdb, registry)
	engine := matcher.New(ruleCache, replicaPool, dedupStore, 0, registry)

	listing := model.ScoredListingEvent{
		ListingID:    listingID,
		CountryCode:  "ES",
		Lat:          40.42,
		Lon:          -3.70,
		PropertyType: "residential",
		PriceEUR:     320000,
		AreaM2:       95,
		DealScore:    0.87,
		DealTier:     1,
	}

	matches, err := engine.Match(ctx, listing)
	if err != nil {
		t.Fatalf("engine match: %v", err)
	}
	if len(matches) != 1 {
		t.Fatalf("expected 1 match, got %d", len(matches))
	}

	if err := dedupStore.MarkSent(ctx, userID, listingID); err != nil {
		t.Fatalf("mark sent: %v", err)
	}

	sent, err := dedupStore.IsSent(ctx, userID, listingID)
	if err != nil {
		t.Fatalf("dedup lookup: %v", err)
	}
	if !sent {
		t.Fatal("expected listing to be marked as sent")
	}
}

func startPostgres(t *testing.T, ctx context.Context) (testcontainers.Container, string) {
	t.Helper()

	container, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: testcontainers.ContainerRequest{
			Image:        "postgis/postgis:16-3.4",
			ExposedPorts: []string{"5432/tcp"},
			Env: map[string]string{
				"POSTGRES_PASSWORD": "postgres",
				"POSTGRES_USER":     "postgres",
				"POSTGRES_DB":       "estategap",
			},
			WaitingFor: wait.ForLog("database system is ready to accept connections").WithOccurrence(2).WithStartupTimeout(60 * time.Second),
		},
		Started: true,
	})
	if err != nil {
		t.Fatalf("start postgres container: %v", err)
	}

	host, err := container.Host(ctx)
	if err != nil {
		t.Fatalf("postgres host: %v", err)
	}
	port, err := container.MappedPort(ctx, "5432")
	if err != nil {
		t.Fatalf("postgres port: %v", err)
	}

	return container, fmt.Sprintf("postgres://postgres:postgres@%s:%s/estategap?sslmode=disable", host, port.Port())
}

func startRedis(t *testing.T, ctx context.Context) (testcontainers.Container, string) {
	t.Helper()

	container, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: testcontainers.ContainerRequest{
			Image:        "redis:7-alpine",
			ExposedPorts: []string{"6379/tcp"},
			WaitingFor:   wait.ForListeningPort("6379/tcp").WithStartupTimeout(30 * time.Second),
		},
		Started: true,
	})
	if err != nil {
		t.Fatalf("start redis container: %v", err)
	}

	host, err := container.Host(ctx)
	if err != nil {
		t.Fatalf("redis host: %v", err)
	}
	port, err := container.MappedPort(ctx, "6379")
	if err != nil {
		t.Fatalf("redis port: %v", err)
	}

	return container, fmt.Sprintf("%s:%s", host, port.Port())
}

func mustExec(t *testing.T, ctx context.Context, pool *pgxpool.Pool, query string) {
	t.Helper()
	if _, err := pool.Exec(ctx, query); err != nil {
		t.Fatalf("exec query: %v", err)
	}
}
