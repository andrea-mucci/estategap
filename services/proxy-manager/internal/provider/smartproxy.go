package provider

import "net/url"

type SmartProxyAdapter struct{}

func (SmartProxyAdapter) Name() string {
	return "smartproxy"
}

func (SmartProxyAdapter) BuildProxyURL(username, password, endpoint, sessionID string) string {
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
