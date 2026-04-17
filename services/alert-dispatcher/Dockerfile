FROM golang:1.23-alpine AS builder

WORKDIR /src

COPY go.work go.work.sum ./
COPY libs/pkg libs/pkg
COPY services/alert-dispatcher services/alert-dispatcher

RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /out/alert-dispatcher ./services/alert-dispatcher/cmd

FROM gcr.io/distroless/static-debian12:nonroot

EXPOSE 8081

COPY --from=builder --chown=nonroot:nonroot /out/alert-dispatcher /app

USER nonroot:nonroot
ENTRYPOINT ["/app"]
