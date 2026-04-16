FROM golang:1.23-alpine AS builder

WORKDIR /build

COPY go.work go.work.sum ./
COPY libs/pkg libs/pkg
COPY services/scrape-orchestrator services/scrape-orchestrator

RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /app ./services/scrape-orchestrator/cmd

FROM gcr.io/distroless/static:nonroot

COPY --from=builder /app /app

USER nonroot:nonroot
ENTRYPOINT ["/app"]
