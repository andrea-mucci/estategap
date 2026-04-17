package grpc

import (
	"context"
	"crypto/tls"
	"os"
	"strings"

	estategapv1 "github.com/estategap/libs/proto/estategap/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
)

type MLClient struct {
	conn   *grpc.ClientConn
	client estategapv1.MLScoringServiceClient
}

func NewMLClient(target string) (*MLClient, error) {
	conn, err := grpc.Dial(target, grpc.WithTransportCredentials(transportCredentials(target)))
	if err != nil {
		return nil, err
	}
	return &MLClient{
		conn:   conn,
		client: estategapv1.NewMLScoringServiceClient(conn),
	}, nil
}

func (c *MLClient) ScoreListing(ctx context.Context, req *estategapv1.ScoreListingRequest) (*estategapv1.ScoreListingResponse, error) {
	return c.client.ScoreListing(ctx, req)
}

func (c *MLClient) Close() error {
	return c.conn.Close()
}

func transportCredentials(target string) credentials.TransportCredentials {
	if os.Getenv("CLUSTER_ENVIRONMENT") == "production" || strings.HasSuffix(target, ":443") {
		return credentials.NewTLS(&tls.Config{MinVersion: tls.VersionTLS12})
	}
	return insecure.NewCredentials()
}
