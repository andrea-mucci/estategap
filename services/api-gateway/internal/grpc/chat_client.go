package grpc

import (
	"context"
	"time"

	estategapv1 "github.com/estategap/libs/proto/estategap/v1"
	"google.golang.org/grpc"
)

type ChatClientConfig struct {
	Target  string
	Timeout time.Duration
}

type ChatClient struct {
	conn    *grpc.ClientConn
	client  estategapv1.AIChatServiceClient
	timeout time.Duration
}

type timedChatStream struct {
	estategapv1.AIChatService_ChatClient
	cancel context.CancelFunc
}

func NewChatClient(cfg ChatClientConfig) (*ChatClient, error) {
	conn, err := grpc.NewClient(cfg.Target, clientDialOptions(cfg.Target)...)
	if err != nil {
		return nil, err
	}
	return &ChatClient{
		conn:    conn,
		client:  estategapv1.NewAIChatServiceClient(conn),
		timeout: cfg.Timeout,
	}, nil
}

func (c *ChatClient) StreamChat(ctx context.Context, req *estategapv1.ChatRequest) (estategapv1.AIChatService_ChatClient, error) {
	callCtx := ctx
	cancel := func() {}
	if c.timeout > 0 {
		callCtx, cancel = context.WithTimeout(ctx, c.timeout)
	}

	stream, err := c.client.Chat(callCtx)
	if err != nil {
		cancel()
		return nil, err
	}
	if req != nil {
		if err := stream.Send(req); err != nil {
			cancel()
			return nil, err
		}
	}
	return &timedChatStream{
		AIChatService_ChatClient: stream,
		cancel:                   cancel,
	}, nil
}

func (c *ChatClient) Close() error {
	return c.conn.Close()
}

func (s *timedChatStream) CloseSend() error {
	err := s.AIChatService_ChatClient.CloseSend()
	if s.cancel != nil {
		s.cancel()
	}
	return err
}
