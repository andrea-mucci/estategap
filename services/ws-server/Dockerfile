FROM golang:1.23-alpine AS builder

WORKDIR /workspace

RUN apk add --no-cache git

COPY go.work go.work.sum ./
COPY libs/pkg ./libs/pkg
COPY services/ws-server ./services/ws-server

WORKDIR /workspace/services/ws-server

RUN go mod download
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-w -s" -o /out/ws-server ./cmd

FROM gcr.io/distroless/static-debian12

COPY --from=builder /out/ws-server /app/ws-server

EXPOSE 8081

USER nonroot:nonroot
ENTRYPOINT ["/app/ws-server"]
