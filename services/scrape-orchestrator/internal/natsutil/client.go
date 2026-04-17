package natsutil

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/nats-io/nats.go"
)

type Client struct {
	mu   sync.RWMutex
	url  string
	conn *nats.Conn
	js   nats.JetStreamContext
}

func New(url string) (*Client, error) {
	conn, js, err := connect(url)
	if err != nil {
		return nil, err
	}

	return &Client{
		url:  url,
		conn: conn,
		js:   js,
	}, nil
}

func (c *Client) Publish(subject string, payload []byte) error {
	c.mu.RLock()
	js := c.js
	c.mu.RUnlock()

	if js == nil {
		if err := c.reconnect(); err != nil {
			return err
		}
		c.mu.RLock()
		js = c.js
		c.mu.RUnlock()
	}

	_, err := js.Publish(subject, payload)
	if err == nil {
		return nil
	}

	if reconnectErr := c.reconnect(); reconnectErr != nil {
		return fmt.Errorf("publish %s: %w (reconnect failed: %v)", subject, err, reconnectErr)
	}

	c.mu.RLock()
	js = c.js
	c.mu.RUnlock()
	_, err = js.Publish(subject, payload)
	return err
}

func (c *Client) Ping(ctx context.Context) error {
	c.mu.RLock()
	conn := c.conn
	c.mu.RUnlock()
	if conn == nil {
		return errors.New("nats connection is not initialized")
	}
	return conn.FlushWithContext(ctx)
}

func (c *Client) Drain() error {
	c.mu.RLock()
	conn := c.conn
	c.mu.RUnlock()
	if conn == nil {
		return nil
	}
	return conn.Drain()
}

func (c *Client) Close() {
	c.mu.RLock()
	conn := c.conn
	c.mu.RUnlock()
	if conn != nil {
		conn.Close()
	}
}

func (c *Client) reconnect() error {
	conn, js, err := connect(c.url)
	if err != nil {
		return err
	}

	c.mu.Lock()
	old := c.conn
	c.conn = conn
	c.js = js
	c.mu.Unlock()

	if old != nil {
		old.Close()
	}

	return nil
}

func connect(url string) (*nats.Conn, nats.JetStreamContext, error) {
	conn, err := nats.Connect(
		url,
		nats.Name("scrape-orchestrator"),
		nats.MaxReconnects(-1),
		nats.ReconnectWait(2*time.Second),
		nats.Timeout(5*time.Second),
	)
	if err != nil {
		return nil, nil, err
	}

	js, err := conn.JetStream()
	if err != nil {
		conn.Close()
		return nil, nil, err
	}

	return conn, js, nil
}
