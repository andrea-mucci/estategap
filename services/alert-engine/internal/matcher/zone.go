package matcher

import (
	"context"

	"github.com/estategap/services/alert-engine/internal/cache"
	"github.com/estategap/services/alert-engine/internal/model"
	"github.com/jackc/pgx/v5/pgxpool"
)

func InAnyZone(ctx context.Context, listing model.ScoredListingEvent, zoneIDs []string, rules *cache.RuleCache, db *pgxpool.Pool) (bool, error) {
	if len(zoneIDs) == 0 {
		return true, nil
	}

	candidates := make([]string, 0, len(zoneIDs))
	for _, zoneID := range zoneIDs {
		zone, ok := rules.GetZone(zoneID)
		if !ok {
			continue
		}
		if listing.Lat < zone.BBoxMinLat || listing.Lat > zone.BBoxMaxLat {
			continue
		}
		if listing.Lon < zone.BBoxMinLon || listing.Lon > zone.BBoxMaxLon {
			continue
		}
		candidates = append(candidates, zoneID)
	}
	if len(candidates) == 0 {
		return false, nil
	}

	rows, err := db.Query(ctx, `
		SELECT id
		FROM zones
		WHERE id = ANY($1::uuid[])
		  AND ST_Contains(COALESCE(geometry, bbox), ST_SetSRID(ST_MakePoint($2, $3), 4326))
		LIMIT 1
	`, candidates, listing.Lon, listing.Lat)
	if err != nil {
		return false, err
	}
	defer rows.Close()

	return rows.Next(), rows.Err()
}
