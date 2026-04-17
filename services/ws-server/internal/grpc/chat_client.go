package grpcclient

import (
	"context"
	"encoding/json"
	"io"
	"strings"
	"time"

	estategapv1 "github.com/estategap/libs/proto/estategap/v1"
	"github.com/estategap/services/ws-server/internal/metrics"
	"github.com/estategap/services/ws-server/internal/protocol"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

type ChatClient struct {
	client estategapv1.AIChatServiceClient
}

func New(cc *grpc.ClientConn) *ChatClient {
	return &ChatClient{client: estategapv1.NewAIChatServiceClient(cc)}
}

func (c *ChatClient) OpenChatStream(ctx context.Context, userID, tier, sessionID, message, countryCode string, sendFn func([]byte)) error {
	started := time.Now()
	statusLabel := "ok"
	defer func() {
		metrics.GRPCStreamDurationSeconds.WithLabelValues(statusLabel).Observe(time.Since(started).Seconds())
	}()

	callCtx, cancel := context.WithTimeout(ctx, 5*time.Minute)
	defer cancel()
	callCtx = metadata.AppendToOutgoingContext(
		callCtx,
		"x-user-id", userID,
		"x-subscription-tier", tier,
	)

	stream, err := c.client.Chat(callCtx, grpc.WaitForReady(true))
	if err != nil {
		statusLabel = "open_error"
		sendMappedError(sendFn, sessionID, err, false)
		return err
	}

	if err := stream.Send(&estategapv1.ChatRequest{
		ConversationId: sessionID,
		UserMessage:    message,
		CountryCode:    countryCode,
	}); err != nil {
		statusLabel = "send_error"
		sendMappedError(sendFn, sessionID, err, false)
		return err
	}
	if err := stream.CloseSend(); err != nil {
		statusLabel = "close_send_error"
		sendMappedError(sendFn, sessionID, err, false)
		return err
	}

	seenChunk := false
	for {
		resp, err := stream.Recv()
		if err == nil {
			seenChunk = true
			if forwardErr := c.forwardResponse(sessionID, resp, sendFn); forwardErr != nil {
				statusLabel = "encode_error"
				sendMappedError(sendFn, sessionID, forwardErr, seenChunk)
				return forwardErr
			}
			continue
		}
		if err == io.EOF {
			return nil
		}

		statusLabel = grpcStatusLabel(err, seenChunk)
		sendMappedError(sendFn, sessionID, err, seenChunk)
		return err
	}
}

func (c *ChatClient) forwardResponse(sessionID string, resp *estategapv1.ChatResponse, sendFn func([]byte)) error {
	conversationID := resp.GetConversationId()
	if conversationID == "" {
		conversationID = sessionID
	}

	chunk := strings.TrimSpace(resp.GetChunk())
	switch {
	case strings.HasPrefix(chunk, "{\"chips\":"):
		var wrapper struct {
			Chips protocol.ChipsPayload `json:"chips"`
		}
		if err := json.Unmarshal([]byte(chunk), &wrapper); err != nil {
			return err
		}
		return sendEnvelope(sendFn, "chips", conversationID, wrapper.Chips)
	case strings.HasPrefix(chunk, "{\"image_carousel\":"):
		var wrapper struct {
			Carousel protocol.ImageCarouselPayload `json:"image_carousel"`
		}
		if err := json.Unmarshal([]byte(chunk), &wrapper); err != nil {
			return err
		}
		return sendEnvelope(sendFn, "image_carousel", conversationID, wrapper.Carousel)
	case strings.HasPrefix(chunk, "{\"criteria_summary\":"):
		var wrapper struct {
			Summary protocol.CriteriaSummaryPayload `json:"criteria_summary"`
		}
		if err := json.Unmarshal([]byte(chunk), &wrapper); err != nil {
			return err
		}
		return sendEnvelope(sendFn, "criteria_summary", conversationID, wrapper.Summary)
	default:
		if err := sendEnvelope(sendFn, "text_chunk", conversationID, protocol.TextChunkPayload{
			Text:           resp.GetChunk(),
			ConversationID: conversationID,
			IsFinal:        resp.GetIsFinal(),
		}); err != nil {
			return err
		}
		if !resp.GetIsFinal() || len(resp.GetListingIds()) == 0 {
			return nil
		}

		listings := make([]protocol.SearchListing, 0, len(resp.GetListingIds()))
		for _, listingID := range resp.GetListingIds() {
			listings = append(listings, protocol.SearchListing{ListingID: listingID})
		}
		return sendEnvelope(sendFn, "search_results", conversationID, protocol.SearchResultsPayload{
			ConversationID: conversationID,
			TotalCount:     len(listings),
			Listings:       listings,
		})
	}
}

func sendEnvelope(sendFn func([]byte), messageType, sessionID string, payload any) error {
	raw, err := protocol.MarshalEnvelope(messageType, sessionID, payload)
	if err != nil {
		return err
	}
	sendFn(raw)
	return nil
}

func sendMappedError(sendFn func([]byte), sessionID string, err error, seenChunk bool) {
	payload := protocol.ErrorPayload{
		Code:    "ai_unavailable",
		Message: "ai-chat is unavailable",
	}

	if seenChunk {
		payload = protocol.ErrorPayload{
			Code:    "stream_error",
			Message: "chat stream interrupted",
		}
	} else {
		switch status.Code(err) {
		case codes.ResourceExhausted:
			payload = protocol.ErrorPayload{Code: "ai_limit_exceeded", Message: "ai-chat limit exceeded"}
		case codes.NotFound:
			payload = protocol.ErrorPayload{Code: "conversation_not_found", Message: "conversation not found"}
		case codes.Internal, codes.Unavailable, codes.Unauthenticated:
			payload = protocol.ErrorPayload{Code: "ai_unavailable", Message: "ai-chat is unavailable"}
		}
	}

	if raw, marshalErr := protocol.MarshalEnvelope("error", sessionID, payload); marshalErr == nil {
		sendFn(raw)
	}
}

func grpcStatusLabel(err error, seenChunk bool) string {
	if seenChunk {
		return "stream_error"
	}
	switch status.Code(err) {
	case codes.ResourceExhausted:
		return "resource_exhausted"
	case codes.NotFound:
		return "not_found"
	case codes.Internal:
		return "internal"
	case codes.Unavailable:
		return "unavailable"
	case codes.Unauthenticated:
		return "unauthenticated"
	default:
		return "error"
	}
}
