package middleware

import (
	"context"
	"errors"
	"net/http"
	"strings"

	"github.com/golang-jwt/jwt/v5"
	"github.com/redis/go-redis/v9"
)

var (
	ErrMissingToken     = errors.New("missing token")
	ErrInvalidToken     = errors.New("invalid token")
	ErrExpiredToken     = errors.New("expired token")
	ErrBlacklistedToken = errors.New("blacklisted token")
)

type AccessTokenClaims struct {
	Email string `json:"email"`
	Tier  string `json:"tier"`
	jwt.RegisteredClaims
}

func ExtractToken(r *http.Request) string {
	if token := strings.TrimSpace(r.URL.Query().Get("token")); token != "" {
		return token
	}

	header := strings.TrimSpace(r.Header.Get("Authorization"))
	if len(header) < 7 || !strings.EqualFold(header[:7], "Bearer ") {
		return ""
	}
	return strings.TrimSpace(header[7:])
}

func ValidateToken(tokenStr, jwtSecret string, redisClient *redis.Client) (*AccessTokenClaims, error) {
	if strings.TrimSpace(tokenStr) == "" {
		return nil, ErrMissingToken
	}

	claims := &AccessTokenClaims{}
	parsed, err := jwt.ParseWithClaims(tokenStr, claims, func(t *jwt.Token) (any, error) {
		if t.Method.Alg() != jwt.SigningMethodHS256.Alg() {
			return nil, ErrInvalidToken
		}
		return []byte(jwtSecret), nil
	})
	if err != nil {
		switch {
		case errors.Is(err, jwt.ErrTokenExpired):
			return nil, ErrExpiredToken
		default:
			return nil, ErrInvalidToken
		}
	}
	if !parsed.Valid {
		return nil, ErrInvalidToken
	}

	if claims.ID != "" && redisClient != nil {
		blacklisted, err := redisClient.Exists(context.Background(), "blacklist:"+claims.ID).Result()
		if err != nil {
			return nil, ErrInvalidToken
		}
		if blacklisted > 0 {
			return nil, ErrBlacklistedToken
		}
	}

	return claims, nil
}

func Reason(err error) string {
	switch {
	case errors.Is(err, ErrMissingToken):
		return "missing token"
	case errors.Is(err, ErrExpiredToken):
		return "expired token"
	case errors.Is(err, ErrBlacklistedToken):
		return "blacklisted token"
	default:
		return "invalid signature"
	}
}
