package service

import (
	"context"
	"errors"
	"time"

	"github.com/estategap/libs/models"
	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"golang.org/x/crypto/bcrypt"
)

const (
	accessTokenTTL  = 15 * time.Minute
	refreshTokenTTL = 7 * 24 * time.Hour
)

var ErrInvalidRefreshToken = errors.New("invalid refresh token")

type TokenPair struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	ExpiresIn    int    `json:"expires_in"`
}

type AccessTokenClaims struct {
	Email string `json:"email"`
	Tier  string `json:"tier"`
	jwt.RegisteredClaims
}

type AuthService struct {
	jwtSecret   []byte
	redisClient *redis.Client
}

func NewAuthService(jwtSecret string, redisClient *redis.Client) *AuthService {
	return &AuthService{
		jwtSecret:   []byte(jwtSecret),
		redisClient: redisClient,
	}
}

func (s *AuthService) HashPassword(plain string) (string, error) {
	hashed, err := bcrypt.GenerateFromPassword([]byte(plain), 12)
	if err != nil {
		return "", err
	}
	return string(hashed), nil
}

func (s *AuthService) CheckPassword(hash, plain string) bool {
	return bcrypt.CompareHashAndPassword([]byte(hash), []byte(plain)) == nil
}

func (s *AuthService) IssueAccessToken(user *models.User) (string, error) {
	userID, err := userUUID(user)
	if err != nil {
		return "", err
	}

	now := time.Now().UTC()
	claims := AccessTokenClaims{
		Email: user.Email,
		Tier:  string(user.SubscriptionTier),
		RegisteredClaims: jwt.RegisteredClaims{
			Subject:   userID.String(),
			ID:        uuid.NewString(),
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(now.Add(accessTokenTTL)),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString(s.jwtSecret)
}

func (s *AuthService) IssueRefreshToken(ctx context.Context, userID uuid.UUID) (string, error) {
	token := uuid.NewString()
	if err := s.redisClient.Set(ctx, refreshKey(token), userID.String(), refreshTokenTTL).Err(); err != nil {
		return "", err
	}
	return token, nil
}

func (s *AuthService) RevokeRefreshToken(ctx context.Context, token string) error {
	return s.redisClient.Del(ctx, refreshKey(token)).Err()
}

func (s *AuthService) ResolveRefreshToken(ctx context.Context, token string) (uuid.UUID, error) {
	value, err := s.redisClient.Get(ctx, refreshKey(token)).Result()
	if err != nil {
		if errors.Is(err, redis.Nil) {
			return uuid.Nil, ErrInvalidRefreshToken
		}
		return uuid.Nil, err
	}
	id, err := uuid.Parse(value)
	if err != nil {
		return uuid.Nil, err
	}
	return id, nil
}

func (s *AuthService) ConsumeRefreshToken(ctx context.Context, token string) (uuid.UUID, error) {
	value, err := s.redisClient.GetDel(ctx, refreshKey(token)).Result()
	if err != nil {
		if errors.Is(err, redis.Nil) {
			return uuid.Nil, ErrInvalidRefreshToken
		}
		return uuid.Nil, err
	}
	id, err := uuid.Parse(value)
	if err != nil {
		return uuid.Nil, err
	}
	return id, nil
}

func (s *AuthService) BlacklistAccessToken(ctx context.Context, jti string, ttl time.Duration) error {
	if ttl <= 0 {
		return nil
	}
	return s.redisClient.Set(ctx, blacklistKey(jti), "1", ttl).Err()
}

func (s *AuthService) IsBlacklisted(ctx context.Context, jti string) (bool, error) {
	count, err := s.redisClient.Exists(ctx, blacklistKey(jti)).Result()
	return count > 0, err
}

func (s *AuthService) ParseAccessToken(token string) (*AccessTokenClaims, error) {
	claims := &AccessTokenClaims{}
	parsed, err := jwt.ParseWithClaims(token, claims, func(t *jwt.Token) (any, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, errors.New("unexpected signing method")
		}
		return s.jwtSecret, nil
	})
	if err != nil {
		return nil, err
	}
	if !parsed.Valid {
		return nil, errors.New("invalid token")
	}
	return claims, nil
}

func (s *AuthService) RemainingTokenTTL(token string) (time.Duration, error) {
	claims, err := s.ParseAccessToken(token)
	if err != nil {
		return 0, err
	}
	if claims.ExpiresAt == nil {
		return 0, nil
	}
	return time.Until(claims.ExpiresAt.Time), nil
}

func (s *AuthService) IssueTokenPair(ctx context.Context, user *models.User) (*TokenPair, error) {
	userID, err := userUUID(user)
	if err != nil {
		return nil, err
	}
	accessToken, err := s.IssueAccessToken(user)
	if err != nil {
		return nil, err
	}
	refreshToken, err := s.IssueRefreshToken(ctx, userID)
	if err != nil {
		return nil, err
	}
	return &TokenPair{
		AccessToken:  accessToken,
		RefreshToken: refreshToken,
		ExpiresIn:    int(accessTokenTTL.Seconds()),
	}, nil
}

func refreshKey(token string) string {
	return "refresh:" + token
}

func blacklistKey(jti string) string {
	return "blacklist:" + jti
}

func userUUID(user *models.User) (uuid.UUID, error) {
	if !user.ID.Valid {
		return uuid.Nil, errors.New("user has invalid id")
	}
	return uuid.UUID(user.ID.Bytes), nil
}
