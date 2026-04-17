package db

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type Portal struct {
	Name            string
	Country         string
	ScrapeFrequency time.Duration
	SearchURLs      []string
}

type Querier interface {
	QueryPortals(ctx context.Context) ([]Portal, error)
	Ping(ctx context.Context) error
}

type Client struct {
	pool *pgxpool.Pool
}

func New(ctx context.Context, url string) (*Client, error) {
	pool, err := pgxpool.New(ctx, url)
	if err != nil {
		return nil, err
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, err
	}
	return &Client{pool: pool}, nil
}

func (c *Client) QueryPortals(ctx context.Context) ([]Portal, error) {
	rows, err := c.pool.Query(ctx, `
		SELECT
			name,
			country,
			COALESCE(EXTRACT(epoch FROM scrape_frequency)::bigint, 0) AS scrape_frequency_seconds,
			COALESCE(search_urls, ARRAY[]::text[]) AS search_urls
		FROM portals
		WHERE enabled = true
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var portals []Portal
	for rows.Next() {
		var portal Portal
		var seconds int64
		if err := rows.Scan(&portal.Name, &portal.Country, &seconds, &portal.SearchURLs); err != nil {
			return nil, err
		}
		if strings.TrimSpace(portal.Name) == "" {
			return nil, fmt.Errorf("portal row missing name")
		}
		portal.Country = strings.ToUpper(strings.TrimSpace(portal.Country))
		portal.ScrapeFrequency = time.Duration(seconds) * time.Second
		portals = append(portals, portal)
	}

	if rows.Err() != nil {
		return nil, rows.Err()
	}

	return portals, nil
}

func (c *Client) Ping(ctx context.Context) error {
	return c.pool.Ping(ctx)
}

func (c *Client) Close() {
	if c != nil && c.pool != nil {
		c.pool.Close()
	}
}
