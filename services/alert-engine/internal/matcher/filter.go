package matcher

import (
	"strings"

	"github.com/estategap/services/alert-engine/internal/model"
)

func Evaluate(filter model.RuleFilter, listing model.ScoredListingEvent) bool {
	if filter.HasUnsupportedFields() {
		return false
	}

	if len(filter.PropertyTypes) > 0 && !containsString(filter.PropertyTypes, listing.PropertyType) {
		return false
	}
	if filter.PriceMin != nil && listing.PriceEUR < *filter.PriceMin {
		return false
	}
	if filter.PriceMax != nil && listing.PriceEUR > *filter.PriceMax {
		return false
	}
	if filter.AreaMin != nil && listing.AreaM2 < *filter.AreaMin {
		return false
	}
	if filter.AreaMax != nil && listing.AreaM2 > *filter.AreaMax {
		return false
	}
	if filter.BedroomsMin != nil {
		if listing.Bedrooms == nil || *listing.Bedrooms < *filter.BedroomsMin {
			return false
		}
	}
	if filter.BedroomsMax != nil {
		if listing.Bedrooms == nil || *listing.Bedrooms > *filter.BedroomsMax {
			return false
		}
	}
	if filter.DealTierMax != nil && listing.DealTier > *filter.DealTierMax {
		return false
	}
	if len(filter.Features) > 0 && !containsAll(listing.Features, filter.Features) {
		return false
	}

	return true
}

func containsString(haystack []string, needle string) bool {
	needle = strings.ToLower(strings.TrimSpace(needle))
	for _, item := range haystack {
		if strings.ToLower(strings.TrimSpace(item)) == needle {
			return true
		}
	}
	return false
}

func containsAll(haystack, needles []string) bool {
	if len(needles) == 0 {
		return true
	}

	available := make(map[string]struct{}, len(haystack))
	for _, item := range haystack {
		available[strings.ToLower(strings.TrimSpace(item))] = struct{}{}
	}

	for _, needle := range needles {
		if _, ok := available[strings.ToLower(strings.TrimSpace(needle))]; !ok {
			return false
		}
	}

	return true
}
