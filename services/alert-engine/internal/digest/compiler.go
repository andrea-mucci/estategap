package digest

import (
	"context"
	"log/slog"
	"time"

	"github.com/estategap/services/alert-engine/internal/cache"
	"github.com/estategap/services/alert-engine/internal/model"
	"github.com/estategap/services/alert-engine/internal/publisher"
	"github.com/estategap/services/alert-engine/internal/repository"
	"github.com/redis/go-redis/v9"
)

type Compiler struct {
	redis       *redis.Client
	buffer      *Buffer
	repo        *repository.Repo
	publisher   *publisher.Publisher
	historyRepo *repository.HistoryRepo
	cache       *cache.RuleCache
}

func NewCompiler(redisClient *redis.Client, buffer *Buffer, repo *repository.Repo, publisherClient *publisher.Publisher, historyRepo *repository.HistoryRepo, rules *cache.RuleCache) *Compiler {
	return &Compiler{
		redis:       redisClient,
		buffer:      buffer,
		repo:        repo,
		publisher:   publisherClient,
		historyRepo: historyRepo,
		cache:       rules,
	}
}

func (c *Compiler) Compile(ctx context.Context, frequency string) error {
	frequency = model.NormalizeFrequency(frequency)
	var cursor uint64

	for {
		keys, nextCursor, err := c.redis.Scan(ctx, cursor, "alerts:digest:*:"+frequency, 100).Result()
		if err != nil {
			return err
		}

		for _, key := range keys {
			if err := c.compileKey(ctx, key, frequency); err != nil {
				return err
			}
		}

		cursor = nextCursor
		if cursor == 0 {
			return nil
		}
	}
}

func (c *Compiler) StartHourly(ctx context.Context) error {
	return c.runTicker(ctx, time.Hour, model.FrequencyHourly)
}

func (c *Compiler) StartDaily(ctx context.Context) error {
	return c.runTicker(ctx, 24*time.Hour, model.FrequencyDaily)
}

func (c *Compiler) runTicker(ctx context.Context, interval time.Duration, frequency string) error {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return nil
		case <-ticker.C:
			if err := c.Compile(ctx, frequency); err != nil {
				slog.Error("digest compilation failed", "frequency", frequency, "error", err)
			}
		}
	}
}

func (c *Compiler) compileKey(ctx context.Context, key, expectedFrequency string) error {
	userID, ruleID, frequency, err := ParseKey(key)
	if err != nil {
		return err
	}
	if frequency != expectedFrequency {
		return nil
	}

	rule, ok := c.cache.FindRule(ruleID)
	if !ok || rule.UserID != userID || model.NormalizeFrequency(rule.Frequency) != frequency {
		_, _, flushErr := c.buffer.Flush(ctx, key, 20)
		return flushErr
	}

	memberIDs, totalMatches, err := c.buffer.Flush(ctx, key, 20)
	if err != nil {
		return err
	}
	if len(memberIDs) == 0 {
		return nil
	}

	listingIDs := make([]string, 0, len(memberIDs))
	for _, memberID := range memberIDs {
		if memberID == "" {
			continue
		}
		listingIDs = append(listingIDs, memberID)
	}
	if len(listingIDs) == 0 {
		return nil
	}

	summaries, err := c.repo.FetchListingSummaries(ctx, listingIDs)
	if err != nil {
		return err
	}

	type digestBatch struct {
		countryCode string
		listings    []publisher.DigestListing
	}

	batches := make(map[string]*digestBatch)
	for _, listingID := range listingIDs {
		summary, ok := summaries[listingID]
		if !ok {
			continue
		}
		countryCode := summary.CountryCode
		if countryCode == "" {
			countryCode = rule.CountryCode
		}
		countryCode = model.NormalizeCountryCode(countryCode)
		if countryCode == "" {
			continue
		}

		batch, ok := batches[countryCode]
		if !ok {
			batch = &digestBatch{countryCode: countryCode}
			batches[countryCode] = batch
		}

		batch.listings = append(batch.listings, publisher.DigestListing{
			ListingID: listingID,
			DealScore: summary.DealScore,
			DealTier:  summary.DealTier,
			Title:     summary.Title,
			PriceEUR:  summary.PriceEUR,
			AreaM2:    summary.AreaM2,
			Bedrooms:  summary.Bedrooms,
			City:      summary.City,
			ImageURL:  summary.ImageURL,
		})
	}
	if len(batches) == 0 {
		return nil
	}

	for _, batch := range batches {
		for _, channel := range rule.Channels {
			total := len(batch.listings)
			if totalMatches > total && len(batches) == 1 {
				total = totalMatches
			}

			event := publisher.NotificationEvent{
				EventID:      model.NewEventID(),
				UserID:       rule.UserID,
				RuleID:       rule.ID,
				RuleName:     rule.Name,
				CountryCode:  batch.countryCode,
				Channel:      channel.Type,
				WebhookURL:   channel.WebhookURL,
				Frequency:    frequency,
				IsDigest:     true,
				TotalMatches: &total,
				Listings:     batch.listings,
				TriggeredAt:  time.Now().UTC(),
			}
			if err := c.publisher.PublishNotification(ctx, event); err != nil {
				return err
			}
			for _, digestListing := range batch.listings {
				if err := c.historyRepo.InsertHistory(ctx, rule.ID, digestListing.ListingID, channel.Type); err != nil {
					slog.Warn("failed to persist digest history", "rule_id", rule.ID, "listing_id", digestListing.ListingID, "channel", channel.Type, "error", err)
				}
			}
		}
	}

	return nil
}
