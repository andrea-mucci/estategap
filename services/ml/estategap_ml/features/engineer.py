"""Feature engineering pipeline for price-model training."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .encoders import condition_encoder, energy_cert_encoder
from .zone_stats import ZoneStats


class FeatureEngineer(BaseEstimator, TransformerMixin):
    """A scikit-learn compatible feature engineering transformer."""

    PROPERTY_TYPE_CATEGORIES = [
        "apartment",
        "house",
        "studio",
        "penthouse",
        "duplex",
        "other",
    ]
    OPTIONAL_COMPLETENESS_COLUMNS = [
        "usable_area_m2",
        "bedrooms",
        "bathrooms",
        "floor_number",
        "total_floors",
        "has_lift",
        "parking_spaces",
        "energy_cert",
        "condition",
        "building_year",
        "dist_metro_m",
        "dist_train_m",
        "dist_beach_m",
        "photo_count",
    ]
    NUMERIC_COLUMNS = [
        "lat",
        "lon",
        "dist_metro_m",
        "dist_train_m",
        "dist_beach_m",
        "zone_median_price_m2",
        "zone_listing_density",
        "zone_avg_income",
        "built_area_m2",
        "usable_area_m2",
        "bedrooms",
        "bathrooms",
        "floor_number",
        "total_floors",
        "has_lift",
        "parking_spaces",
        "building_age_years",
        "community_fees_eur",
        "month_sin",
        "month_cos",
        "usable_built_ratio",
        "price_per_m2_eur",
        "photo_count",
        "has_photos",
        "data_completeness",
        "has_energy_cert",
    ]

    def __init__(
        self,
        zone_stats: dict[UUID, ZoneStats],
        city_stats: dict[str, ZoneStats],
        country_stats: ZoneStats,
    ) -> None:
        self.zone_stats = zone_stats
        self.city_stats = city_stats
        self.country_stats = country_stats

    def fit(self, df: pd.DataFrame, y: Any = None) -> "FeatureEngineer":
        prepared = self.prepare_frame(df)
        self._fit_source_frame_ = df.copy()
        self.preprocessor_ = ColumnTransformer(
            transformers=[
                (
                    "numeric",
                    Pipeline([("imputer", SimpleImputer(strategy="median"))]),
                    self.NUMERIC_COLUMNS,
                ),
                (
                    "energy",
                    Pipeline(
                        [
                            ("imputer", SimpleImputer(strategy="most_frequent")),
                            ("encoder", energy_cert_encoder()),
                        ]
                    ),
                    ["energy_cert"],
                ),
                (
                    "condition",
                    Pipeline(
                        [
                            ("imputer", SimpleImputer(strategy="most_frequent")),
                            ("encoder", condition_encoder()),
                        ]
                    ),
                    ["condition"],
                ),
                (
                    "property_type",
                    Pipeline(
                        [
                            ("imputer", SimpleImputer(strategy="most_frequent")),
                            (
                                "onehot",
                                OneHotEncoder(
                                    sparse_output=False,
                                    handle_unknown="ignore",
                                    categories=[self.PROPERTY_TYPE_CATEGORIES],
                                ),
                            ),
                        ]
                    ),
                    ["property_type"],
                ),
            ],
            remainder="drop",
        )
        self.preprocessor_.fit(prepared)
        self._fit_feature_frame_ = prepared.copy()
        feature_names = self.preprocessor_.get_feature_names_out()
        self.feature_names_out_ = [name.split("__", maxsplit=1)[-1] for name in feature_names]
        self.training_dataset_ref_ = datetime.now(tz=UTC).isoformat()
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        if not hasattr(self, "preprocessor_"):
            msg = "FeatureEngineer must be fitted before transform()."
            raise ValueError(msg)
        prepared = self.prepare_frame(df)
        matrix = self.preprocessor_.transform(prepared)
        if hasattr(matrix, "toarray"):
            matrix = matrix.toarray()
        output = np.asarray(matrix, dtype=np.float32)
        if np.isnan(output).any() or np.isinf(output).any():
            msg = "FeatureEngineer produced NaN or Inf values."
            raise ValueError(msg)
        return output

    def prepare_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        frame = df.copy()
        frame = self._normalise_columns(frame)
        if frame.empty:
            for column in self.NUMERIC_COLUMNS + ["energy_cert", "condition", "property_type"]:
                if column not in frame.columns:
                    frame[column] = pd.Series(dtype="float64")
            return frame
        frame["property_type"] = frame["property_type"].fillna("other").astype(str).str.lower()
        frame.loc[
            ~frame["property_type"].isin(self.PROPERTY_TYPE_CATEGORIES),
            "property_type",
        ] = "other"
        frame["city"] = frame["city"].fillna("unknown").astype(str)
        resolved = frame.apply(self._resolve_zone_stats, axis=1, result_type="expand")
        resolved.columns = [
            "zone_median_price_m2",
            "zone_listing_density",
            "zone_avg_income",
        ]
        frame = pd.concat([frame, resolved], axis=1)
        frame["usable_built_ratio"] = np.where(
            frame["built_area_m2"].fillna(0) > 0,
            frame["usable_area_m2"].fillna(0) / frame["built_area_m2"].replace(0, np.nan),
            0.0,
        )
        frame["usable_built_ratio"] = frame["usable_built_ratio"].replace([np.inf, -np.inf], 0.0).fillna(0.0)
        frame["price_per_m2_eur"] = frame["price_per_m2_eur"].where(
            frame["price_per_m2_eur"].notna(),
            frame["asking_price_eur"].fillna(0) / frame["built_area_m2"].replace(0, np.nan),
        )
        frame["price_per_m2_eur"] = frame["price_per_m2_eur"].replace([np.inf, -np.inf], np.nan)
        listed_at = pd.to_datetime(frame["listed_at"], utc=True, errors="coerce")
        months = listed_at.dt.month.fillna(1).astype(int)
        frame["month_sin"] = np.sin(2.0 * np.pi * ((months - 3) / 12.0))
        frame["month_cos"] = np.cos(2.0 * np.pi * ((months - 3) / 12.0))
        current_year = datetime.now(tz=UTC).year
        frame["building_age_years"] = current_year - frame["building_year"].fillna(current_year)
        frame["has_energy_cert"] = frame["energy_cert"].notna().astype(float)
        frame["has_photos"] = (frame["photo_count"].fillna(0) > 0).astype(float)
        completeness = frame[self.OPTIONAL_COMPLETENESS_COLUMNS].notna().sum(axis=1)
        frame["data_completeness"] = completeness / float(len(self.OPTIONAL_COMPLETENESS_COLUMNS))
        for column in self.NUMERIC_COLUMNS:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame

    def _normalise_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        aliases = {
            "energy_rating": "energy_cert",
            "year_built": "building_year",
            "images_count": "photo_count",
            "published_at": "listed_at",
        }
        df = df.rename(columns={key: value for key, value in aliases.items() if key in df.columns})
        for required in (
            "asking_price_eur",
            "built_area_m2",
            "bedrooms",
            "bathrooms",
            "floor_number",
            "total_floors",
            "condition",
            "energy_cert",
            "building_year",
            "photo_count",
            "community_fees_eur",
            "property_type",
            "city",
            "lat",
            "lon",
            "dist_metro_m",
            "dist_train_m",
            "dist_beach_m",
            "price_per_m2_eur",
            "usable_area_m2",
            "parking_spaces",
            "has_lift",
            "listed_at",
        ):
            if required not in df.columns:
                df[required] = np.nan
        return df

    def _resolve_zone_stats(self, row: pd.Series) -> tuple[float, int, float | None]:
        zone_id = row.get("zone_id")
        if zone_id in self.zone_stats:
            stats = self.zone_stats[zone_id]
        else:
            city_key = str(row.get("city", "unknown")).strip().lower()
            stats = self.city_stats.get(city_key, self.country_stats)
        return (
            float(stats.median_price_m2),
            int(stats.listing_density),
            stats.avg_income,
        )

    def get_feature_names_out(self, input_features: Iterable[str] | None = None) -> list[str]:
        if not hasattr(self, "feature_names_out_"):
            msg = "FeatureEngineer must be fitted before requesting feature names."
            raise ValueError(msg)
        return list(self.feature_names_out_)
