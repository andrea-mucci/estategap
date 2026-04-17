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
	grpcclient "github.com/estategap/services/api-gateway/internal/grpc"
	"github.com/estategap/services/api-gateway/internal/handler"
	gatewaymw "github.com/estategap/services/api-gateway/internal/middleware"
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

	usersRepo := repository.NewUsersRepo(primaryPool, replicaPool)
	listingsRepo := repository.NewListingsRepo(replicaPool)
	dashboardRepo := repository.NewDashboardRepo(replicaPool, cacheClient)
	zonesRepo := repository.NewZonesRepo(primaryPool, replicaPool, cacheClient)
	referenceRepo := repository.NewReferenceRepo(replicaPool, cacheClient)
	alertRulesRepo := repository.NewAlertRulesRepo(primaryPool, replicaPool)
	subsRepo := repository.NewSubscriptionsRepo(primaryPool, replicaPool)
	portfolioRepo := repository.NewPortfolioRepo(primaryPool, replicaPool)
	adminRepo := repository.NewAdminRepo(primaryPool, replicaPool, redisClient)

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

	grpcTimeout := time.Duration(cfg.GRPCTimeoutSeconds) * time.Second
	mlClient, err := grpcclient.NewMLClient(grpcclient.MLClientConfig{
		Target:      cfg.GRPCMLScorerAddr,
		Timeout:     grpcTimeout,
		CBThreshold: cfg.GRPCCBThreshold,
		CBWindow:    time.Duration(cfg.GRPCCBWindowSeconds) * time.Second,
		CBCooldown:  time.Duration(cfg.GRPCCBCooldownSeconds) * time.Second,
	})
	if err != nil {
		return err
	}
	defer mlClient.Close()

	chatClient, err := grpcclient.NewChatClient(grpcclient.ChatClientConfig{
		Target:  cfg.GRPCChatAddr,
		Timeout: grpcTimeout,
	})
	if err != nil {
		return err
	}
	defer chatClient.Close()

	healthHandler := handler.NewHealthHandler(primaryPool, redisClient)
	authHandler := handler.NewAuthHandler(authService, usersRepo)
	googleOAuthHandler := handler.NewGoogleOAuthHandler(oauthService)
	dashboardHandler := handler.NewDashboardHandler(dashboardRepo, usersRepo)
	listingsHandler := handler.NewListingsHandler(listingsRepo, usersRepo, cacheClient)
	zonesHandler := handler.NewZonesHandler(zonesRepo, cacheClient)
	referenceHandler := handler.NewReferenceHandler(referenceRepo)
	docsHandler := handler.NewDocsHandler()
	mlHandler := handler.NewMLHandler(mlClient, listingsRepo, grpcTimeout)
	alertRulesHandler := handler.NewAlertRulesHandler(alertRulesRepo, cacheClient)
	subscriptionsHandler := handler.NewSubscriptionsHandler(stripeService, subsRepo, usersRepo, redisClient)
	portfolioHandler := handler.NewPortfolioHandler(portfolioRepo)
	adminHandler := handler.NewAdminHandler(adminRepo, redisClient)
	meExportHandler := handler.NewMeExportHandler(usersRepo, alertRulesRepo, portfolioRepo, redisClient)
	meDeleteHandler := handler.NewMeDeleteHandler(usersRepo, authService, redisClient)
	dataRemovalRequestHandler := handler.NewDataRemovalRequestHandler()

	go worker.StartDowngradeWorker(ctx, redisClient, usersRepo)

	router := chi.NewRouter()
	router.Use(gatewaymw.CORS(cfg.AllowedOrigins))
	router.Use(gatewaymw.CSP(gatewaymw.CSPConfig{
		ReportOnly: cfg.CSPReportOnly,
		ReportURI:  cfg.CSPReportURI,
	}))
	router.Use(gatewaymw.RequestLogger())
	router.Use(gatewaymw.MetricsMiddleware())

	router.Get("/api/openapi.json", docsHandler.ServeOpenAPISpec)
	router.Get("/api/docs", http.RedirectHandler("/api/docs/", http.StatusMovedPermanently).ServeHTTP)
	router.Get("/api/docs/*", docsHandler.ServeSwaggerUI)
	router.Get("/healthz", healthHandler.Healthz)
	router.Get("/readyz", healthHandler.Readyz)
	router.Handle("/metrics", promhttp.Handler())

	authenticator := gatewaymw.Authenticator(cfg.JWTSecret, redisClient)
	rateLimiter := gatewaymw.RateLimiter(redisClient)
	authRateLimiter := gatewaymw.AuthRateLimitMiddleware(redisClient)

	router.Route("/v1/auth", func(r chi.Router) {
		r.Use(authRateLimiter)
		mountAuthRoutes(r, authHandler, googleOAuthHandler, authenticator, rateLimiter)
	})

	router.Route("/api/v1/auth", func(r chi.Router) {
		r.Use(authRateLimiter)
		mountAuthRoutes(r, authHandler, googleOAuthHandler, authenticator, rateLimiter)
	})

	router.Post("/v1/data-removal-requests", dataRemovalRequestHandler.ServeHTTP)
	router.Post("/api/v1/data-removal-requests", dataRemovalRequestHandler.ServeHTTP)

	router.Route("/v1", func(r chi.Router) {
		r.Post("/webhooks/stripe", subscriptionsHandler.StripeWebhook)

		r.Group(func(r chi.Router) {
			r.Use(authenticator)
			r.Use(gatewaymw.RequireAuth)
			r.Use(rateLimiter)

			mountAuthenticatedV1Routes(r, dashboardHandler, listingsHandler, zonesHandler, referenceHandler, mlHandler, alertRulesHandler, subscriptionsHandler, portfolioHandler, adminHandler, meExportHandler, meDeleteHandler)
		})
	})

	router.Route("/api/v1", func(r chi.Router) {
		r.Post("/webhooks/stripe", subscriptionsHandler.StripeWebhook)

		r.Group(func(r chi.Router) {
			r.Use(authenticator)
			r.Use(gatewaymw.RequireAuth)
			r.Use(rateLimiter)

			mountAuthenticatedV1Routes(r, dashboardHandler, listingsHandler, zonesHandler, referenceHandler, mlHandler, alertRulesHandler, subscriptionsHandler, portfolioHandler, adminHandler, meExportHandler, meDeleteHandler)
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
