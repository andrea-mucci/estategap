from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import asyncpg
import boto3
import redis


ROOT_DIR = Path(__file__).resolve().parent
COUNTRY_DATA = (
    ("ES", "Spain", "EUR"),
    ("IT", "Italy", "EUR"),
    ("FR", "France", "EUR"),
    ("PT", "Portugal", "EUR"),
    ("GB", "United Kingdom", "GBP"),
)
PORTALS = {
    "ES": ("idealista", "https://www.idealista.com", "FixtureSpider"),
    "IT": ("immobiliare", "https://www.immobiliare.it", "FixtureSpider"),
    "FR": ("seloger", "https://www.seloger.com", "FixtureSpider"),
    "PT": ("imovirtual", "https://www.imovirtual.com", "FixtureSpider"),
    "GB": ("rightmove", "https://www.rightmove.co.uk", "FixtureSpider"),
}


def _load_json(relative_path: str) -> Any:
    return json.loads((ROOT_DIR / relative_path).read_text(encoding="utf-8"))


def _env(name: str, default: str) -> str:
    value = os.getenv(name, default)
    return value if value.startswith("http") or "://" not in default else value


async def ensure_reference_data(conn: asyncpg.Connection) -> None:
    await conn.executemany(
        """
        INSERT INTO countries (code, name, currency)
        VALUES ($1, $2, $3)
        ON CONFLICT (code) DO UPDATE
        SET name = EXCLUDED.name,
            currency = EXCLUDED.currency,
            updated_at = NOW()
        """,
        COUNTRY_DATA,
    )
    await conn.executemany(
        """
        INSERT INTO portals (name, country_code, base_url, spider_class, enabled)
        VALUES ($1, $2, $3, $4, TRUE)
        ON CONFLICT (name, country_code) DO UPDATE
        SET base_url = EXCLUDED.base_url,
            spider_class = EXCLUDED.spider_class,
            enabled = TRUE,
            updated_at = NOW()
        """,
        [(name, country, base_url, spider_class) for country, (name, base_url, spider_class) in PORTALS.items()],
    )


async def insert_users(conn: asyncpg.Connection, users: list[dict[str, Any]]) -> None:
    rows = [
        (
            user["id"],
            user["email"],
            user["password_hash"],
            user["display_name"],
            user["subscription_tier"],
            user["preferred_currency"],
            user["allowed_countries"],
            user["alert_limit"],
            user["email_verified"],
            user["preferred_language"],
            user["created_at"],
            user["updated_at"],
        )
        for user in users
    ]
    await conn.executemany(
        """
        INSERT INTO users (
            id,
            email,
            password_hash,
            display_name,
            subscription_tier,
            preferred_currency,
            allowed_countries,
            alert_limit,
            email_verified,
            preferred_language,
            created_at,
            updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7::char(2)[], $8, $9, $10, $11, $12)
        ON CONFLICT (id) DO UPDATE
        SET email = EXCLUDED.email,
            display_name = EXCLUDED.display_name,
            subscription_tier = EXCLUDED.subscription_tier,
            preferred_currency = EXCLUDED.preferred_currency,
            allowed_countries = EXCLUDED.allowed_countries,
            alert_limit = EXCLUDED.alert_limit,
            preferred_language = EXCLUDED.preferred_language,
            updated_at = EXCLUDED.updated_at
        """,
        rows,
    )


async def insert_zones(conn: asyncpg.Connection, zones: list[dict[str, Any]]) -> None:
    rows = [
        (
            zone["id"],
            zone["name"],
            zone.get("name_local"),
            zone["country_code"],
            zone["level"],
            zone.get("parent_id"),
            zone["geometry_wkt"],
            zone["bbox_wkt"],
            zone.get("population"),
            zone.get("area_km2"),
            zone["slug"],
            zone.get("osm_id"),
            zone["created_at"],
            zone["updated_at"],
        )
        for zone in zones
    ]
    await conn.executemany(
        """
        INSERT INTO zones (
            id,
            name,
            name_local,
            country_code,
            level,
            parent_id,
            geometry,
            bbox,
            population,
            area_km2,
            slug,
            osm_id,
            created_at,
            updated_at
        )
        VALUES (
            $1,
            $2,
            $3,
            $4,
            $5,
            $6,
            ST_GeomFromText($7, 4326),
            ST_GeomFromText($8, 4326),
            $9,
            $10,
            $11,
            $12,
            $13,
            $14
        )
        ON CONFLICT (id) DO UPDATE
        SET name = EXCLUDED.name,
            name_local = EXCLUDED.name_local,
            parent_id = EXCLUDED.parent_id,
            geometry = EXCLUDED.geometry,
            bbox = EXCLUDED.bbox,
            population = EXCLUDED.population,
            area_km2 = EXCLUDED.area_km2,
            slug = EXCLUDED.slug,
            osm_id = EXCLUDED.osm_id,
            updated_at = EXCLUDED.updated_at
        """,
        rows,
    )


async def insert_alerts(conn: asyncpg.Connection, alerts: list[dict[str, Any]]) -> None:
    rows = [
        (
            alert["id"],
            alert["user_id"],
            alert["name"],
            alert["zone_ids"],
            alert["category"],
            json.dumps(alert["filter"]),
            json.dumps(alert["channels"]),
            alert["frequency"],
            alert["is_active"],
            alert["created_at"],
            alert["updated_at"],
        )
        for alert in alerts
    ]
    await conn.executemany(
        """
        INSERT INTO alert_rules (
            id,
            user_id,
            name,
            zone_ids,
            category,
            filter,
            channels,
            frequency,
            is_active,
            created_at,
            updated_at
        )
        VALUES ($1, $2, $3, $4::uuid[], $5, $6::jsonb, $7::jsonb, $8, $9, $10, $11)
        ON CONFLICT (id) DO UPDATE
        SET name = EXCLUDED.name,
            zone_ids = EXCLUDED.zone_ids,
            category = EXCLUDED.category,
            filter = EXCLUDED.filter,
            channels = EXCLUDED.channels,
            frequency = EXCLUDED.frequency,
            is_active = EXCLUDED.is_active,
            updated_at = EXCLUDED.updated_at
        """,
        rows,
    )


async def insert_listings(conn: asyncpg.Connection, listings: list[dict[str, Any]]) -> None:
    rows = [
        (
            listing["id"],
            listing["country"],
            listing["source"],
            listing["source_id"],
            listing["source_url"],
            listing["address"],
            listing["district"],
            listing["city"],
            listing["region"],
            listing["postal_code"],
            listing["zone_id"],
            listing["asking_price"],
            listing["currency"],
            listing["asking_price_eur"],
            listing["price_per_m2_eur"],
            listing["property_category"],
            listing["property_type"],
            listing["built_area_m2"],
            listing["bedrooms"],
            listing["bathrooms"],
            listing["status"],
            listing["description_orig"],
            listing["images_count"],
            listing["published_at"],
            listing["first_seen_at"],
            listing["last_seen_at"],
            listing["created_at"],
            listing["updated_at"],
            listing["deal_score"],
            listing["deal_tier"],
            listing["lon"],
            listing["lat"],
        )
        for listing in listings
    ]
    await conn.executemany(
        """
        INSERT INTO listings (
            id,
            country,
            source,
            source_id,
            source_url,
            address,
            district,
            city,
            region,
            postal_code,
            zone_id,
            asking_price,
            currency,
            asking_price_eur,
            price_per_m2_eur,
            property_category,
            property_type,
            built_area_m2,
            bedrooms,
            bathrooms,
            status,
            description_orig,
            images_count,
            published_at,
            first_seen_at,
            last_seen_at,
            created_at,
            updated_at,
            deal_score,
            deal_tier,
            location
        )
        VALUES (
            $1,
            $2,
            $3,
            $4,
            $5,
            $6,
            $7,
            $8,
            $9,
            $10,
            $11,
            $12,
            $13,
            $14,
            $15,
            $16,
            $17,
            $18,
            $19,
            $20,
            $21,
            $22,
            $23,
            $24,
            $25,
            $26,
            $27,
            $28,
            $29,
            $30,
            ST_SetSRID(ST_MakePoint($31, $32), 4326)
        )
        ON CONFLICT (source, source_id, country) DO UPDATE
        SET source_url = EXCLUDED.source_url,
            address = EXCLUDED.address,
            district = EXCLUDED.district,
            city = EXCLUDED.city,
            region = EXCLUDED.region,
            postal_code = EXCLUDED.postal_code,
            zone_id = EXCLUDED.zone_id,
            asking_price = EXCLUDED.asking_price,
            currency = EXCLUDED.currency,
            asking_price_eur = EXCLUDED.asking_price_eur,
            price_per_m2_eur = EXCLUDED.price_per_m2_eur,
            property_category = EXCLUDED.property_category,
            property_type = EXCLUDED.property_type,
            built_area_m2 = EXCLUDED.built_area_m2,
            bedrooms = EXCLUDED.bedrooms,
            bathrooms = EXCLUDED.bathrooms,
            status = EXCLUDED.status,
            description_orig = EXCLUDED.description_orig,
            images_count = EXCLUDED.images_count,
            published_at = EXCLUDED.published_at,
            last_seen_at = EXCLUDED.last_seen_at,
            updated_at = EXCLUDED.updated_at,
            deal_score = EXCLUDED.deal_score,
            deal_tier = EXCLUDED.deal_tier,
            location = EXCLUDED.location
        """,
        rows,
    )


async def insert_conversations(conn: asyncpg.Connection, conversations: list[dict[str, Any]]) -> None:
    for conversation in conversations:
        await conn.execute(
            """
            INSERT INTO ai_conversations (
                id,
                user_id,
                language,
                criteria_state,
                turn_count,
                status,
                model_used,
                created_at,
                updated_at
            )
            VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9)
            ON CONFLICT (id) DO UPDATE
            SET criteria_state = EXCLUDED.criteria_state,
                turn_count = EXCLUDED.turn_count,
                status = EXCLUDED.status,
                model_used = EXCLUDED.model_used,
                updated_at = EXCLUDED.updated_at
            """,
            conversation["conversation_id"],
            conversation["user_id"],
            conversation.get("language", "en"),
            json.dumps(conversation.get("criteria_state", {})),
            len(conversation["messages"]),
            conversation.get("status", "active"),
            conversation.get("model_used", "fake-llm-provider"),
            conversation["created_at"],
            conversation["updated_at"],
        )

        for message in conversation["messages"]:
            await conn.execute(
                """
                INSERT INTO ai_messages (
                    conversation_id,
                    role,
                    content,
                    criteria_snapshot,
                    visual_refs,
                    tokens_used,
                    created_at
                )
                SELECT $1, $2, $3, $4::jsonb, $5::jsonb, $6, $7
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM ai_messages
                    WHERE conversation_id = $1
                      AND role = $2
                      AND content = $3
                      AND created_at = $7
                )
                """,
                conversation["conversation_id"],
                message["role"],
                message["content"],
                json.dumps(message.get("criteria_snapshot", {})),
                json.dumps(message.get("visual_refs", [])),
                message.get("tokens_used", 32),
                message["created_at"],
            )


async def insert_model_versions(conn: asyncpg.Connection, bucket: str, countries: list[str]) -> None:
    rows = [
        (
            country,
            f"{country.lower()}_fixture_v1",
            f"s3://{bucket}/models/{country.lower()}_fixture_v1.onnx",
            json.dumps(["built_area_m2", "bedrooms", "bathrooms"]),
            json.dumps({"mape_national": 0.08, "mae": 17500}),
        )
        for country in countries
    ]
    await conn.executemany(
        """
        INSERT INTO model_versions (
            country_code,
            algorithm,
            version_tag,
            artifact_path,
            feature_names,
            metrics,
            status,
            trained_at,
            promoted_at,
            created_at
        )
        VALUES ($1, 'linear-regression', $2, $3, $4::jsonb, $5::jsonb, 'active', NOW(), NOW(), NOW())
        ON CONFLICT (country_code, version_tag) DO UPDATE
        SET artifact_path = EXCLUDED.artifact_path,
            feature_names = EXCLUDED.feature_names,
            metrics = EXCLUDED.metrics,
            status = 'active',
            promoted_at = NOW()
        """,
        rows,
    )


def ensure_bucket(s3_client: Any, bucket: str) -> None:
    existing = {item["Name"] for item in s3_client.list_buckets().get("Buckets", [])}
    if bucket not in existing:
        s3_client.create_bucket(Bucket=bucket)


def upload_fixture_assets(s3_client: Any, model_bucket: str, fixture_bucket: str) -> None:
    ensure_bucket(s3_client, model_bucket)
    ensure_bucket(s3_client, fixture_bucket)

    for country in ("es", "it", "fr", "pt", "gb"):
        model_path = ROOT_DIR / "ml-models" / f"{country}.onnx"
        if not model_path.exists():
            raise FileNotFoundError(f"Missing ONNX artifact: {model_path}. Run tests/fixtures/ml-models/generate.py first.")
        s3_client.put_object(Bucket=model_bucket, Key=f"models/{country}_fixture_v1.onnx", Body=model_path.read_bytes())

        listings_path = ROOT_DIR / "listings" / f"{country}.json"
        s3_client.put_object(Bucket=fixture_bucket, Key=f"listings/{country}.json", Body=listings_path.read_bytes())


async def summarize_counts(conn: asyncpg.Connection) -> dict[str, int]:
    return {
        "users": await conn.fetchval("SELECT COUNT(*) FROM users"),
        "listings": await conn.fetchval("SELECT COUNT(*) FROM listings"),
        "zones": await conn.fetchval("SELECT COUNT(*) FROM zones"),
        "alert_rules": await conn.fetchval("SELECT COUNT(*) FROM alert_rules"),
        "ai_conversations": await conn.fetchval("SELECT COUNT(*) FROM ai_conversations"),
        "model_versions": await conn.fetchval("SELECT COUNT(*) FROM model_versions"),
    }


async def main() -> None:
    started = time.perf_counter()
    pg_dsn = os.getenv("PG_DSN", "postgresql://app:app@localhost:5432/estategap")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    minio_endpoint = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
    minio_access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    model_bucket = os.getenv("MINIO_MODEL_BUCKET", "ml-models")
    fixture_bucket = os.getenv("FIXTURE_MINIO_BUCKET", "fixtures")

    users = _load_json("users.json")
    alerts = _load_json("alerts.json")
    zones = [
        zone
        for relative_path in ("zones/es.json", "zones/it.json", "zones/fr.json", "zones/pt.json", "zones/gb.json")
        for zone in _load_json(relative_path)
    ]
    listings = [
        listing
        for relative_path in ("listings/es.json", "listings/it.json", "listings/fr.json", "listings/pt.json", "listings/gb.json")
        for listing in _load_json(relative_path)
    ]
    conversations = [_load_json("conversations/sample_01.json")]

    pool = await asyncpg.create_pool(pg_dsn, min_size=1, max_size=4, command_timeout=30)
    redis_client = redis.from_url(redis_url, decode_responses=True)
    s3_client = boto3.client(
        "s3",
        endpoint_url=minio_endpoint,
        aws_access_key_id=minio_access_key,
        aws_secret_access_key=minio_secret_key,
    )

    async with pool.acquire() as conn:
        await ensure_reference_data(conn)
        await insert_users(conn, users)
        await insert_zones(conn, zones)
        await insert_alerts(conn, alerts)
        await insert_listings(conn, listings)
        await insert_conversations(conn, conversations)
        await insert_model_versions(conn, model_bucket, [country for country, _, _ in COUNTRY_DATA])
        counts = await summarize_counts(conn)

    upload_fixture_assets(s3_client, model_bucket, fixture_bucket)
    redis_client.set("test:mode", "1")
    redis_client.set("fixtures:loaded_at", str(int(time.time())))

    await pool.close()
    redis_client.close()

    elapsed = time.perf_counter() - started
    summary = " ".join(f"{key}={value}" for key, value in counts.items())
    print(f"Seed load complete in {elapsed:.2f}s {summary}")


if __name__ == "__main__":
    asyncio.run(main())
