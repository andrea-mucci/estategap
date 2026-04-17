package timeutil

import (
	"os"
	"strconv"
	"strings"
	"time"
)

func Now() time.Time {
	return nowFunc()
}

func nowFunc() time.Time {
	raw := strings.TrimSpace(os.Getenv("NOW_OVERRIDE"))
	if raw == "" {
		return time.Now().UTC()
	}
	ts, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		return time.Now().UTC()
	}
	return time.Unix(ts, 0).UTC()
}
