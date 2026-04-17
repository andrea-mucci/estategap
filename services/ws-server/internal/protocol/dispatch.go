package protocol

import (
	"context"
	"encoding/json"
)

import "github.com/estategap/services/ws-server/internal/metrics"

type ChatStreamer interface {
	OpenChatStream(ctx context.Context, userID, tier, sessionID, message, countryCode string, sendFn func([]byte)) error
}

type Connection interface {
	UserID() string
	Tier() string
	Context() context.Context
	Enqueue([]byte) bool
}

func Dispatch(c Connection, env Envelope, chatClient ChatStreamer) {
	metrics.MessagesReceivedTotal.WithLabelValues(env.Type).Inc()

	switch env.Type {
	case "chat_message":
		var payload ChatMessagePayload
		if err := json.Unmarshal(env.Payload, &payload); err != nil || payload.UserMessage == "" {
			sendError(c, env.SessionID, "invalid_message", "invalid chat_message payload")
			return
		}
		go func() {
			_ = chatClient.OpenChatStream(
				c.Context(),
				c.UserID(),
				c.Tier(),
				env.SessionID,
				payload.UserMessage,
				payload.CountryCode,
				func(raw []byte) {
					_ = c.Enqueue(raw)
				},
			)
		}()
	case "image_feedback":
		var payload ImageFeedbackPayload
		if err := json.Unmarshal(env.Payload, &payload); err != nil {
			sendError(c, env.SessionID, "invalid_message", "invalid image_feedback payload")
			return
		}
		forwardPayload(c, env, chatClient, env.Payload)
	case "criteria_confirm":
		var payload CriteriaConfirmPayload
		if err := json.Unmarshal(env.Payload, &payload); err != nil {
			sendError(c, env.SessionID, "invalid_message", "invalid criteria_confirm payload")
			return
		}
		forwardPayload(c, env, chatClient, env.Payload)
	default:
		sendError(c, env.SessionID, "invalid_message", "unknown message type")
	}
}

func forwardPayload(c Connection, env Envelope, chatClient ChatStreamer, payload []byte) {
	go func() {
		_ = chatClient.OpenChatStream(
			c.Context(),
			c.UserID(),
			c.Tier(),
			env.SessionID,
			string(payload),
			"",
			func(raw []byte) {
				_ = c.Enqueue(raw)
			},
		)
	}()
}

func sendError(c Connection, sessionID, code, message string) {
	payload, err := MarshalEnvelope("error", sessionID, ErrorPayload{
		Code:    code,
		Message: message,
	})
	if err != nil {
		return
	}
	_ = c.Enqueue(payload)
}
