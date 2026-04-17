FROM golang:1.23-alpine AS builder

WORKDIR /workspace

RUN apk add --no-cache git

COPY go.work ./
COPY libs/pkg ./libs/pkg
COPY services/api-gateway ./services/api-gateway

WORKDIR /workspace/services/api-gateway

RUN go mod download
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-w -s" -o /out/api-gateway ./cmd

FROM gcr.io/distroless/static-debian12

COPY --from=builder /out/api-gateway /app/api-gateway

USER nonroot:nonroot
ENTRYPOINT ["/app/api-gateway"]
