"""Training-data export and split helpers."""

from __future__ import annotations

from collections.abc import Sequence

import asyncpg
import numpy as np
import pandas as pd


async def export_training_data(country: str, dsn: str, limit: int | None = None) -> pd.DataFrame:
    """Export the denormalised training dataset for one country."""

    country_code = country.upper()
    conn = await asyncpg.connect(dsn)
    try:
        available_columns = {
            row["column_name"]
            for row in await conn.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'listings'
                """
            )
        }
        final_price_exists = "final_price_eur" in available_columns
        def _select(column: str, *, alias: str | None = None, cast: str = "TEXT") -> str:
            resolved_alias = alias or column
            if column in available_columns:
                return f"{column} AS {resolved_alias}" if alias else column
            return f"NULL::{cast} AS {resolved_alias}"

        limit_sql = "LIMIT $2" if limit is not None else ""
        target_select = (
            "COALESCE(final_price_eur, asking_price_eur) AS final_price_eur"
            if final_price_exists
            else "NULL::NUMERIC AS final_price_eur"
        )
        query = f"""
            SELECT
                id,
                country,
                city,
                zone_id,
                ST_Y(location::geometry) AS lat,
                ST_X(location::geometry) AS lon,
                asking_price_eur,
                {target_select},
                price_per_m2_eur,
                built_area_m2,
                usable_area_m2,
                bedrooms,
                bathrooms,
                floor_number,
                total_floors,
                has_lift,
                parking_spaces,
                property_type,
                property_category,
                energy_rating AS energy_cert,
                condition,
                year_built AS building_year,
                {_select("community_fees_monthly", alias="community_fees_eur", cast="NUMERIC")},
                images_count AS photo_count,
                days_on_market,
                published_at AS listed_at,
                status,
                dist_metro_m,
                dist_train_m,
                dist_beach_m,
                data_completeness,
                {_select("orientation")},
                {_select("ape_rating")},
                {_select("council_tax_band")},
                {_select("epc_rating")},
                {_select("tenure")},
                {_select("uk_lr_last_price_gbp", cast="NUMERIC")},
                {_select("omi_price_min_eur_m2", alias="omi_zone_min_price_eur_m2", cast="NUMERIC")},
                {_select("omi_price_max_eur_m2", alias="omi_zone_max_price_eur_m2", cast="NUMERIC")},
                {_select("dvf_median_price_m2", cast="NUMERIC")},
                {_select("hoa_fees_monthly_usd", cast="NUMERIC")},
                {_select("lot_size_m2", cast="NUMERIC")},
                {_select("tax_assessed_value_usd", cast="NUMERIC")},
                {_select("school_rating", cast="NUMERIC")},
                {_select("zestimate_reference_usd", cast="NUMERIC")}
            FROM listings
            WHERE country = $1
              AND (status IN ('sold', 'delisted') OR days_on_market > 30)
              AND asking_price_eur IS NOT NULL
              AND built_area_m2 > 0
            ORDER BY created_at DESC
            {limit_sql}
        """
        rows = await conn.fetch(query, country_code, *([limit] if limit is not None else []))
    finally:
        await conn.close()

    frame = pd.DataFrame([dict(row) for row in rows])
    if frame.empty:
        return frame
    if "country" in frame.columns:
        frame["country"] = frame["country"].astype(str).str.lower()
    return frame


def stratified_split(
    df: pd.DataFrame,
    stratify_col: str,
    ratios: Sequence[float] = (0.70, 0.15, 0.15),
    rare_threshold: int = 50,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split a dataframe into train/val/test partitions with rare-strata fallback."""

    if len(ratios) != 3 or not np.isclose(sum(ratios), 1.0):
        msg = "ratios must contain three values that sum to 1.0"
        raise ValueError(msg)
    if df.empty:
        return df.copy(), df.copy(), df.copy()

    rng = np.random.default_rng(random_state)
    frame = df.copy()
    frame["_stratum"] = frame[stratify_col].fillna("other").astype(str)
    counts = frame["_stratum"].value_counts()
    rare = counts[counts < rare_threshold].index
    frame.loc[frame["_stratum"].isin(rare), "_stratum"] = "other"

    train_parts: list[pd.DataFrame] = []
    val_parts: list[pd.DataFrame] = []
    test_parts: list[pd.DataFrame] = []

    for _, group in frame.groupby("_stratum", sort=False):
        shuffled = group.iloc[rng.permutation(len(group))]
        n_rows = len(shuffled)
        train_end = max(1, int(round(n_rows * ratios[0])))
        val_end = train_end + int(round(n_rows * ratios[1]))
        if val_end >= n_rows and n_rows >= 3:
            val_end = n_rows - 1
        train_parts.append(shuffled.iloc[:train_end])
        val_parts.append(shuffled.iloc[train_end:val_end])
        test_parts.append(shuffled.iloc[val_end:])

    def _finalise(parts: list[pd.DataFrame]) -> pd.DataFrame:
        if not parts:
            return df.iloc[0:0].copy()
        result = pd.concat(parts).drop(columns="_stratum").reset_index(drop=True)
        return result

    return _finalise(train_parts), _finalise(val_parts), _finalise(test_parts)
