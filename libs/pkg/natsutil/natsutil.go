package natsutil

import (
	"github.com/nats-io/nats.go"
)

// Connect establishes a connection to a NATS server at the given URL.
func Connect(url string) (*nats.Conn, error) {
	return nats.Connect(url)
}

// EnsureStream creates or updates a JetStream stream with the given config.
func EnsureStream(js nats.JetStreamContext, cfg *nats.StreamConfig) error {
	_, err := js.StreamInfo(cfg.Name)
	if err != nil {
		_, err = js.AddStream(cfg)
		return err
	}
	_, err = js.UpdateStream(cfg)
	return err
}
