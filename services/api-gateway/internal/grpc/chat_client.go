package grpc

import (
	"context"

	estategapv1 "github.com/estategap/libs/proto/estategap/v1"
	"google.golang.org/grpc"
)

type ChatClient struct {
	conn   *grpc.ClientConn
	client estategapv1.AIChatServiceClient
}

func NewChatClient(target string) (*ChatClient, error) {
	conn, err := grpc.Dial(target, grpc.WithTransportCredentials(transportCredentials(target)))
	if err != nil {
		return nil, err
	}
	return &ChatClient{
		conn:   conn,
		client: estategapv1.NewAIChatServiceClient(conn),
	}, nil
}

func (c *ChatClient) StreamChat(ctx context.Context, req *estategapv1.ChatRequest) (estategapv1.AIChatService_ChatClient, error) {
	stream, err := c.client.Chat(ctx)
	if err != nil {
		return nil, err
	}
	if req != nil {
		if err := stream.Send(req); err != nil {
			return nil, err
		}
	}
	return stream, nil
}

func (c *ChatClient) Close() error {
	return c.conn.Close()
}
