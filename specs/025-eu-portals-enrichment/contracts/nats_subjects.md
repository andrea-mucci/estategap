# Contract: NATS Subject Extensions

**Feature**: 025-eu-portals-enrichment  
**Interface type**: NATS JetStream publish/subscribe subjects

---

## New Publish Subjects (Spider Workers → Pipeline)

Following the existing pattern `scraped.listings.{country}.{portal}`:

| Subject | Publisher | Consumer |
|---------|-----------|---------|
| `scraped.listings.IT.immobiliare` | ImmobiliareSpider | Normalizer (feature 012) |
| `scraped.listings.IT.idealista` | IdealistaITSpider | Normalizer |
| `scraped.listings.FR.seloger` | SeLogerSpider | Normalizer |
| `scraped.listings.FR.leboncoin` | LeBonCoinSpider | Normalizer |
| `scraped.listings.FR.bienici` | BienIciSpider | Normalizer |
| `scraped.listings.GB.rightmove` | RightmoveSpider | Normalizer |
| `scraped.listings.NL.funda` | FundaSpider | Normalizer |

## Enriched Output Subjects (Pipeline → Downstream)

Following the existing pattern `enriched.listings.{country}`:

| Subject | Publisher | Notes |
|---------|-----------|-------|
| `enriched.listings.IT` | EnricherService | Includes OMI enrichment fields |
| `enriched.listings.FR` | EnricherService | Includes DVF enrichment fields |
| `enriched.listings.GB` | EnricherService | Includes Land Registry fields |
| `enriched.listings.NL` | EnricherService | Includes BAG enrichment fields |

These subjects already exist in the NATS JetStream config as wildcards (`enriched.listings.*`). No new stream configuration is required — the new country subjects are automatically matched.

## Scraper Command Messages

Existing command subject `scraper.commands.{country}.{portal}` handles dispatch. No new subjects required — the scrape orchestrator (feature 010) dispatches by country+portal tuple, which now includes the 7 new portals after spider registration.
