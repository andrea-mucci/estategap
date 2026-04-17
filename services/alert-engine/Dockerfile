FROM golang:1.23 AS builder

WORKDIR /src

COPY go.work go.work.sum ./
COPY libs/pkg libs/pkg
COPY services/alert-engine services/alert-engine

RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /out/alert-engine ./services/alert-engine/cmd

FROM gcr.io/distroless/static-debian12:nonroot

EXPOSE 8080

COPY --from=builder --chown=nonroot:nonroot /out/alert-engine /app

USER nonroot:nonroot
ENTRYPOINT ["/app"]
