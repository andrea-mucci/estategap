package repository

import (
	"fmt"
	"time"
)

func parseRFC3339Millis(value string) (time.Time, error) {
	layouts := []string{time.RFC3339Nano, "2006-01-02T15:04:05.000Z"}
	for _, layout := range layouts {
		if parsed, err := time.Parse(layout, value); err == nil {
			return parsed, nil
		}
	}
	return time.Time{}, fmt.Errorf("invalid time %q", value)
}
