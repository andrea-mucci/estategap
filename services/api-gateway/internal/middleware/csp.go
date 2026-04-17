package middleware

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"net/http"
	"strings"
)

type cspContextKey string

const cspNonceKey cspContextKey = "csp_nonce"

type CSPConfig struct {
	ReportOnly bool
	ReportURI  string
}

func CSP(cfg CSPConfig) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			nonce, err := randomNonce()
			if err == nil {
				r = r.WithContext(context.WithValue(r.Context(), cspNonceKey, nonce))
				w.Header().Set("X-CSP-Nonce", nonce)
			}

			directives := []string{
				"default-src 'self'",
				"script-src 'self' 'nonce-" + nonce + "'",
				"style-src 'self' 'nonce-" + nonce + "' https://fonts.googleapis.com",
				"font-src 'self' https://fonts.gstatic.com",
				"img-src 'self' data: blob: https://tiles.openfreemap.org https://demotiles.maplibre.org https://api.maptiler.com",
				"connect-src 'self' https://api.estategap.com wss://api.estategap.com",
				"frame-ancestors 'none'",
				"base-uri 'self'",
				"object-src 'none'",
			}
			if reportURI := strings.TrimSpace(cfg.ReportURI); reportURI != "" {
				directives = append(directives, "report-uri "+reportURI)
			}

			headerName := "Content-Security-Policy"
			if cfg.ReportOnly {
				headerName = "Content-Security-Policy-Report-Only"
			}

			w.Header().Set(headerName, strings.Join(directives, "; "))
			next.ServeHTTP(w, r)
		})
	}
}

func CSPNonce(ctx context.Context) string {
	value, _ := ctx.Value(cspNonceKey).(string)
	return value
}

func randomNonce() (string, error) {
	buf := make([]byte, 16)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	return base64.StdEncoding.EncodeToString(buf), nil
}
