package worker

import (
	"context"
	"log/slog"

	"github.com/estategap/services/alert-engine/internal/dedup"
	"github.com/estategap/services/alert-engine/internal/matcher"
	"github.com/estategap/services/alert-engine/internal/model"
	"github.com/estategap/services/alert-engine/internal/repository"
	routepkg "github.com/estategap/services/alert-engine/internal/router"
)

type Processor struct {
	engine      *matcher.Engine
	router      *routepkg.Router
	repo        *repository.Repo
	historyRepo *repository.HistoryRepo
	dedup       *dedup.Dedup
}

func NewProcessor(engine *matcher.Engine, router *routepkg.Router, repo *repository.Repo, historyRepo *repository.HistoryRepo, dedupStore *dedup.Dedup) *Processor {
	return &Processor{
		engine:      engine,
		router:      router,
		repo:        repo,
		historyRepo: historyRepo,
		dedup:       dedupStore,
	}
}

func (p *Processor) HandleScoredListing(ctx context.Context, listing model.ScoredListingEvent) error {
	matches, err := p.engine.Match(ctx, listing)
	if err != nil {
		return err
	}
	if len(matches) == 0 {
		return nil
	}

	summaries, err := p.repo.FetchListingSummaries(ctx, []string{listing.ListingID})
	if err != nil {
		slog.Warn("failed to enrich listing summary from repository", "listing_id", listing.ListingID, "error", err)
	} else if summary, ok := summaries[listing.ListingID]; ok {
		listing = listing.WithSummary(summary)
	}

	for _, rule := range matches {
		switch model.NormalizeFrequency(rule.Frequency) {
		case model.FrequencyHourly, model.FrequencyDaily:
			if err := p.router.RouteDigest(ctx, rule, listing); err != nil {
				return err
			}
			if err := p.markSent(ctx, rule.UserID, listing.ListingID); err != nil {
				slog.Warn("failed to mark digest notification as sent", "rule_id", rule.ID, "listing_id", listing.ListingID, "error", err)
			}
		default:
			channels, err := p.router.RouteInstant(ctx, rule, listing)
			if err != nil {
				return err
			}
			if len(channels) == 0 {
				continue
			}
			if err := p.markSent(ctx, rule.UserID, listing.ListingID); err != nil {
				slog.Warn("failed to mark instant notification as sent", "rule_id", rule.ID, "listing_id", listing.ListingID, "error", err)
			}
			for _, channel := range channels {
				if err := p.historyRepo.InsertHistory(ctx, rule.ID, listing.ListingID, channel); err != nil {
					slog.Warn("failed to persist alert history", "rule_id", rule.ID, "listing_id", listing.ListingID, "channel", channel, "error", err)
				}
			}
		}
	}

	return nil
}

func (p *Processor) HandlePriceChange(ctx context.Context, event model.PriceChangeEvent) error {
	if event.NewPriceEUR >= event.OldPriceEUR {
		return nil
	}

	userIDs, err := p.historyRepo.ListUsersForListing(ctx, event.ListingID)
	if err != nil {
		return err
	}

	for _, userID := range userIDs {
		if err := p.dedup.ClearSent(ctx, userID, event.ListingID); err != nil {
			slog.Warn("failed to clear dedup entry after price drop", "user_id", userID, "listing_id", event.ListingID, "error", err)
		}
	}

	return nil
}

func (p *Processor) markSent(ctx context.Context, userID, listingID string) error {
	if p.dedup == nil {
		return nil
	}
	return p.dedup.MarkSent(ctx, userID, listingID)
}
