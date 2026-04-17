package provider

import (
	"net/url"
)

type BrightDataAdapter struct{}

func (BrightDataAdapter) Name() string {
	return "brightdata"
}

func (BrightDataAdapter) BuildProxyURL(username, password, endpoint, sessionID string) string {
	user := username
	if sessionID != "" {
		user = user + "-session-" + sessionID
	}
	return (&url.URL{
		Scheme: "http",
		User:   url.UserPassword(user, password),
		Host:   endpoint,
	}).String()
}
