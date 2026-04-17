module github.com/estategap/services/alert-dispatcher

go 1.23

require (
	github.com/aws/aws-sdk-go-v2 v1.32.2
	github.com/aws/aws-sdk-go-v2/config v1.28.1
	github.com/aws/aws-sdk-go-v2/service/ses v1.29.6
	github.com/estategap/libs v0.0.0
	github.com/estategap/testhelpers v0.0.0
	github.com/go-chi/chi/v5 v5.2.1
	github.com/go-telegram-bot-api/telegram-bot-api/v5 v5.5.1
	github.com/google/uuid v1.6.0
	github.com/jackc/pgx/v5 v5.7.1
	github.com/prometheus/client_golang v1.20.5
	github.com/redis/go-redis/v9 v9.7.0
	github.com/segmentio/kafka-go v0.4.47
	github.com/shopspring/decimal v1.4.0
	github.com/spf13/viper v1.19.0
	github.com/stretchr/testify v1.9.0
	github.com/twilio/twilio-go v1.23.10
	golang.org/x/oauth2 v0.22.0
	golang.org/x/sync v0.10.0
)

replace github.com/estategap/libs => ../../libs/pkg
