package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	sharedlogger "github.com/estategap/libs/logger"
	cachepkg "github.com/estategap/services/api-gateway/internal/cache"
	"github.com/estategap/services/api-gateway/internal/config"
	"github.com/estategap/services/api-gateway/internal/db"
	"github.com/estategap/services/api-gateway/internal/handler"
	gatewaymw "github.com/estategap/services/api-gateway/internal/middleware"
	"github.com/estategap/services/api-gateway/internal/natsutil"
	"github.com/estategap/services/api-gateway/internal/redisclient"
	"github.com/estategap/services/api-gateway/internal/repository"
	"github.com/estategap/services/api-gateway/internal/service"
	"github.com/estategap/services/api-gateway/internal/worker"
	"github.com/go-chi/chi/v5"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
)

func main() {
	if err := run(); err != nil {
		slog.Error("api gateway exited", "error", err)
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}

	slog.SetDefault(sharedlogger.New(cfg.LogLevel))

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	primaryPool, err := db.NewPrimaryPool(ctx, cfg.DBPrimaryURL)
	if err != nil {
		return err
	}
	defer primaryPool.Close()

	replicaPool, err := db.NewReplicaPool(ctx, cfg.DBReplicaURL)
	if err != nil {
		return err
	}
	defer replicaPool.Close()

	redisClient, err := redisclient.New(cfg.RedisURL)
	if err != nil {
		return err
	}
	defer func() { _ = redisClient.Close() }()
	cacheClient := cachepkg.NewClient(redisClient)

	natsConn, err := natsutil.Connect(cfg.NATSURL)
	if err != nil {
		return err
	}
	defer natsConn.Close()

	usersRepo := repository.NewUsersRepo(primaryPool, replicaPool)
	listingsRepo := repository.NewListingsRepo(replicaPool)
	zonesRepo := repository.NewZonesRepo(replicaPool, cacheClient)
	referenceRepo := repository.NewReferenceRepo(replicaPool, cacheClient)
	alertsRepo := repository.NewAlertsRepo(primaryPool, replicaPool)
	subsRepo := repository.NewSubscriptionsRepo(primaryPool, replicaPool)

	authService := service.NewAuthService(cfg.JWTSecret, redisClient)
	stripeService := service.NewStripeService(cfg)
	oauthService := service.NewOAuthService(
		redisClient,
		&oauth2.Config{
			ClientID:     cfg.GoogleClientID,
			ClientSecret: cfg.GoogleClientSecret,
			RedirectURL:  cfg.GoogleRedirectURL,
			Scopes:       []string{"openid", "email", "profile"},
			Endpoint:     google.Endpoint,
		},
		usersRepo,
		authService,
	)

	healthHandler := handler.NewHealthHandler(primaryPool, redisClient, natsConn)
	authHandler := handler.NewAuthHandler(authService, usersRepo)
	googleOAuthHandler := handler.NewGoogleOAuthHandler(oauthService)
	listingsHandler := handler.NewListingsHandler(listingsRepo, usersRepo)
	zonesHandler := handler.NewZonesHandler(zonesRepo)
	referenceHandler := handler.NewReferenceHandler(referenceRepo)
	alertsHandler := handler.NewAlertsHandler(alertsRepo)
	subscriptionsHandler := handler.NewSubscriptionsHandler(stripeService, subsRepo, usersRepo, redisClient)

	go worker.StartDowngradeWorker(ctx, redisClient, usersRepo)

	router := chi.NewRouter()
	router.Use(gatewaymw.CORS(cfg.AllowedOrigins))
	router.Use(gatewaymw.RequestLogger())
	router.Use(gatewaymw.MetricsMiddleware())

	router.Get("/healthz", healthHandler.Healthz)
	router.Get("/readyz", healthHandler.Readyz)
	router.Handle("/metrics", promhttp.Handler())

	authenticator := gatewaymw.Authenticator(cfg.JWTSecret, redisClient)
	rateLimiter := gatewaymw.RateLimiter(redisClient)

	router.Route("/v1/auth", func(r chi.Router) {
		r.Post("/register", authHandler.Register)
		r.Post("/login", authHandler.Login)
		r.Post("/refresh", authHandler.Refresh)
		r.Get("/google", googleOAuthHandler.Redirect)
		r.Get("/google/callback", googleOAuthHandler.Callback)

		r.Group(func(r chi.Router) {
			r.Use(authenticator)
			r.Use(gatewaymw.RequireAuth)
			r.Use(rateLimiter)
			r.Post("/logout", authHandler.Logout)
			r.Get("/me", authHandler.Me)
		})
	})

	router.Route("/v1", func(r chi.Router) {
		r.Post("/webhooks/stripe", subscriptionsHandler.StripeWebhook)

		r.Group(func(r chi.Router) {
			r.Use(authenticator)
			r.Use(gatewaymw.RequireAuth)
			r.Use(rateLimiter)

			mountAuthenticatedV1Routes(r, listingsHandler, zonesHandler, referenceHandler, alertsHandler, subscriptionsHandler)
		})
	})

	server := &http.Server{
		Addr:              ":" + cfg.Port,
		Handler:           router,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	errCh := make(chan error, 1)
	go func() {
		slog.Info("server started", "addr", server.Addr)
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
		}
	}()

	select {
	case <-ctx.Done():
	case err := <-errCh:
		return err
	}

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	return server.Shutdown(shutdownCtx)
}
