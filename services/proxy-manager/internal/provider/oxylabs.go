package provider

import "net/url"

type OxylabsAdapter struct{}

func (OxylabsAdapter) Name() string {
	return "oxylabs"
}

func (OxylabsAdapter) BuildProxyURL(username, password, endpoint, sessionID string) string {
	user := username
	if sessionID != "" {
		user = user + "-sessid-" + sessionID
	}
	return (&url.URL{
		Scheme: "http",
		User:   url.UserPassword(user, password),
		Host:   endpoint,
	}).String()
}
