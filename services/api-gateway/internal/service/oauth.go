package service

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"time"

	"github.com/estategap/libs/models"
	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"golang.org/x/oauth2"
)

const oauthStateTTL = 10 * time.Minute

var ErrInvalidOAuthState = errors.New("invalid oauth state")

type OAuthService struct {
	redisClient  *redis.Client
	oauth2Config *oauth2.Config
	usersRepo    *repository.UsersRepo
	authService  *AuthService
	httpClient   *http.Client
}

func NewOAuthService(
	redisClient *redis.Client,
	oauth2Config *oauth2.Config,
	usersRepo *repository.UsersRepo,
	authService *AuthService,
) *OAuthService {
	return &OAuthService{
		redisClient:  redisClient,
		oauth2Config: oauth2Config,
		usersRepo:    usersRepo,
		authService:  authService,
		httpClient:   &http.Client{Timeout: 10 * time.Second},
	}
}

func (s *OAuthService) BeginFlow(ctx context.Context) (string, string, error) {
	state := uuid.NewString()
	if err := s.redisClient.Set(ctx, "oauth:state:"+state, "1", oauthStateTTL).Err(); err != nil {
		return "", "", err
	}

	url := s.oauth2Config.AuthCodeURL(
		state,
		oauth2.AccessTypeOffline,
		oauth2.SetAuthURLParam("prompt", "consent"),
	)
	return url, state, nil
}

func (s *OAuthService) HandleCallback(ctx context.Context, code, state string) (*TokenPair, *models.User, error) {
	ok, err := s.consumeState(ctx, state)
	if err != nil {
		return nil, nil, err
	}
	if !ok {
		return nil, nil, ErrInvalidOAuthState
	}

	token, err := s.oauth2Config.Exchange(ctx, code)
	if err != nil {
		return nil, nil, err
	}

	userInfo, err := s.fetchGoogleUserInfo(ctx, token.AccessToken)
	if err != nil {
		return nil, nil, err
	}

	user, err := s.findOrCreateUser(ctx, userInfo)
	if err != nil {
		return nil, nil, err
	}
	if userID, idErr := userUUID(user); idErr == nil {
		_ = s.usersRepo.UpdateLastLogin(ctx, userID)
	}

	pair, err := s.authService.IssueTokenPair(ctx, user)
	if err != nil {
		return nil, nil, err
	}
	return pair, user, nil
}

func (s *OAuthService) consumeState(ctx context.Context, state string) (bool, error) {
	result, err := s.redisClient.GetDel(ctx, "oauth:state:"+state).Result()
	if err != nil {
		if errors.Is(err, redis.Nil) {
			return false, nil
		}
		return false, err
	}
	return result != "", nil
}

func (s *OAuthService) findOrCreateUser(ctx context.Context, info googleUserInfo) (*models.User, error) {
	if user, err := s.usersRepo.GetUserByOAuth(ctx, "google", info.Sub); err == nil {
		return user, nil
	} else if !errors.Is(err, repository.ErrNotFound) {
		return nil, err
	}

	if user, err := s.usersRepo.GetUserByEmail(ctx, info.Email); err == nil {
		userID, idErr := userUUID(user)
		if idErr != nil {
			return nil, idErr
		}
		if err := s.usersRepo.LinkOAuth(ctx, userID, "google", info.Sub); err != nil {
			return nil, err
		}
		return s.usersRepo.GetUserByID(ctx, userID)
	} else if !errors.Is(err, repository.ErrNotFound) {
		return nil, err
	}

	return s.usersRepo.CreateOAuthUser(ctx, info.Email, "google", info.Sub, info.Name, info.Picture)
}

func (s *OAuthService) fetchGoogleUserInfo(ctx context.Context, accessToken string) (googleUserInfo, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, "https://www.googleapis.com/oauth2/v3/userinfo", nil)
	if err != nil {
		return googleUserInfo{}, err
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return googleUserInfo{}, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return googleUserInfo{}, fmt.Errorf("google userinfo returned %d", resp.StatusCode)
	}

	var info googleUserInfo
	if err := json.NewDecoder(resp.Body).Decode(&info); err != nil {
		return googleUserInfo{}, err
	}
	if info.Email == "" || info.Sub == "" {
		return googleUserInfo{}, errors.New("google userinfo missing subject or email")
	}
	return info, nil
}

type googleUserInfo struct {
	Sub     string `json:"sub"`
	Email   string `json:"email"`
	Name    string `json:"name"`
	Picture string `json:"picture"`
}
