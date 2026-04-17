package provider

import "testing"

func TestNewProvider(t *testing.T) {
	t.Parallel()

	cases := []struct {
		name        string
		provider    string
		username    string
		password    string
		endpoint    string
		sessionID   string
		expectedURL string
	}{
		{
			name:        "brightdata without session",
			provider:    "brightdata",
			username:    "user",
			password:    "pass",
			endpoint:    "zproxy.example.com:22225",
			expectedURL: "http://user:pass@zproxy.example.com:22225",
		},
		{
			name:        "brightdata with session",
			provider:    "brightdata",
			username:    "user",
			password:    "pass",
			endpoint:    "zproxy.example.com:22225",
			sessionID:   "abc123",
			expectedURL: "http://user-session-abc123:pass@zproxy.example.com:22225",
		},
		{
			name:        "smartproxy without session",
			provider:    "smartproxy",
			username:    "user",
			password:    "pass",
			endpoint:    "gate.smartproxy.com:7000",
			expectedURL: "http://user:pass@gate.smartproxy.com:7000",
		},
		{
			name:        "smartproxy with session",
			provider:    "smartproxy",
			username:    "user",
			password:    "pass",
			endpoint:    "gate.smartproxy.com:7000",
			sessionID:   "abc123",
			expectedURL: "http://user-sessid-abc123:pass@gate.smartproxy.com:7000",
		},
		{
			name:        "oxylabs without session",
			provider:    "oxylabs",
			username:    "user",
			password:    "pass",
			endpoint:    "pr.oxylabs.io:7777",
			expectedURL: "http://user:pass@pr.oxylabs.io:7777",
		},
		{
			name:        "oxylabs with session",
			provider:    "oxylabs",
			username:    "user",
			password:    "pass",
			endpoint:    "pr.oxylabs.io:7777",
			sessionID:   "abc123",
			expectedURL: "http://user-sessid-abc123:pass@pr.oxylabs.io:7777",
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()

			adapter, err := NewProvider(tc.provider)
			if err != nil {
				t.Fatalf("NewProvider() error = %v", err)
			}

			if got := adapter.BuildProxyURL(tc.username, tc.password, tc.endpoint, tc.sessionID); got != tc.expectedURL {
				t.Fatalf("BuildProxyURL() = %q, want %q", got, tc.expectedURL)
			}
		})
	}
}
