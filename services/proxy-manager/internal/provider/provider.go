package provider

type ProxyProvider interface {
	BuildProxyURL(username, password, endpoint, sessionID string) string
	Name() string
}

type ProviderRegistry interface {
	New(name string) (ProxyProvider, error)
}
