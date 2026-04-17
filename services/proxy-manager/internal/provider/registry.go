package provider

import (
	"fmt"
	"strings"
)

type Registry struct{}

func (Registry) New(name string) (ProxyProvider, error) {
	return NewProvider(name)
}

func NewProvider(name string) (ProxyProvider, error) {
	switch strings.ToLower(strings.TrimSpace(name)) {
	case "brightdata":
		return BrightDataAdapter{}, nil
	case "smartproxy":
		return SmartProxyAdapter{}, nil
	case "oxylabs":
		return OxylabsAdapter{}, nil
	default:
		return nil, fmt.Errorf("unsupported proxy provider %q", name)
	}
}
