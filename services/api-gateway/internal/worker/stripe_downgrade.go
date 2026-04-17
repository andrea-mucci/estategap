package worker

import (
	"context"
	"log/slog"
	"strconv"
	"time"

	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
)

const stripePendingDowngradesKey = "stripe:pending_downgrades"

func StartDowngradeWorker(ctx context.Context, redisClient *redis.Client, usersRepo *repository.UsersRepo) {
	ticker := time.NewTicker(60 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			slog.Info("stripe downgrade worker stopped")
			return
		case <-ticker.C:
			now := time.Now().Unix()
			items, err := redisClient.ZRangeByScoreWithScores(ctx, stripePendingDowngradesKey, &redis.ZRangeBy{
				Min: "0",
				Max: strconv.FormatInt(now, 10),
			}).Result()
			if err != nil {
				slog.Error("failed to load pending Stripe downgrades", "error", err)
				continue
			}

			for _, item := range items {
				member, ok := item.Member.(string)
				if !ok {
					slog.Error("invalid Stripe downgrade queue member", "member", item.Member)
					continue
				}

				userID, err := uuid.Parse(member)
				if err != nil {
					slog.Error("invalid Stripe downgrade user id", "member", member, "error", err)
					if remErr := redisClient.ZRem(ctx, stripePendingDowngradesKey, member).Err(); remErr != nil {
						slog.Error("failed to remove invalid Stripe downgrade member", "member", member, "error", remErr)
					}
					continue
				}

				if err := usersRepo.DowngradeToFree(ctx, userID); err != nil {
					slog.Error("failed to downgrade expired Stripe subscription", "user_id", userID.String(), "error", err)
					continue
				}
				if err := redisClient.ZRem(ctx, stripePendingDowngradesKey, member).Err(); err != nil {
					slog.Error("failed to remove processed Stripe downgrade member", "user_id", userID.String(), "error", err)
					continue
				}

				slog.Info("downgraded Stripe subscriber to free", "user_id", userID.String())
			}
		}
	}
}
