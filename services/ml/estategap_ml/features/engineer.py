"""Feature engineering pipeline for price-model training."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
import logging
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from estategap_ml.config import CONFIG_DIR

from .encoders import condition_encoder, energy_cert_encoder
from .config import CountryFeatureConfig
from .zone_stats import ZoneStats


LOGGER = logging.getLogger(__name__)


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
        "area_m2",
        "zone_median_price_eur_m2",
        "dist_to_center_km",
        "dist_to_transit_km",
        "property_type_encoded",
        "is_new_construction",
        "energy_cert_encoded",
        "has_elevator",
        "community_fees_monthly",
        "orientation_encoded",
        "ape_rating",
        "omi_zone_min_price_eur_m2",
        "omi_zone_max_price_eur_m2",
        "dpe_rating",
        "dvf_median_transaction_price_eur_m2",
        "pieces_count",
        "council_tax_band_encoded",
        "epc_rating",
        "leasehold_flag",
        "land_registry_last_price_gbp_m2",
        "hoa_fees_monthly_usd",
        "lot_size_m2",
        "tax_assessed_value_usd",
        "school_rating",
        "zestimate_reference_usd",
    ]

    def __init__(
        self,
        zone_stats: dict[UUID, ZoneStats],
        city_stats: dict[str, ZoneStats],
        country_stats: ZoneStats,
        country: str = "ES",
    ) -> None:
        self.zone_stats = zone_stats
        self.city_stats = city_stats
        self.country_stats = country_stats
        self.country = country.upper()
        self.feature_config = self._load_feature_config(self.country)
        self.features = list(self.feature_config.all_features)
        self.encoding_rules = dict(self.feature_config.encoding_rules)

    @staticmethod
    def _load_feature_config(country: str) -> CountryFeatureConfig:
        config_path = CONFIG_DIR / f"features_{country.lower()}.yaml"
        try:
            return CountryFeatureConfig.from_yaml(config_path)
        except FileNotFoundError:
            LOGGER.warning("feature_config_fallback", extra={"country": country, "path": str(config_path)})
            return CountryFeatureConfig.from_yaml(CONFIG_DIR / "features_base.yaml")

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
        frame["area_m2"] = frame["built_area_m2"]
        frame["zone_median_price_eur_m2"] = frame["zone_median_price_m2"]
        frame["dist_to_center_km"] = pd.to_numeric(frame["dist_metro_m"], errors="coerce") / 1000.0
        transit_distances = pd.concat(
            [
                pd.to_numeric(frame["dist_metro_m"], errors="coerce"),
                pd.to_numeric(frame["dist_train_m"], errors="coerce"),
            ],
            axis=1,
        )
        frame["dist_to_transit_km"] = transit_distances.min(axis=1, skipna=True) / 1000.0
        property_type_lookup = {value: index + 1 for index, value in enumerate(self.PROPERTY_TYPE_CATEGORIES)}
        frame["property_type_encoded"] = (
            frame["property_type"].fillna("other").astype(str).str.lower().map(property_type_lookup).fillna(0.0)
        )
        frame["is_new_construction"] = frame["condition"].fillna("").astype(str).str.lower().eq("new").astype(float)
        frame["energy_cert_encoded"] = self._encode_series(frame["energy_cert"], "energy_cert")
        frame["has_elevator"] = frame["has_lift"].fillna(False).astype(float)
        frame["community_fees_monthly"] = pd.to_numeric(frame["community_fees_eur"], errors="coerce")
        frame["orientation_encoded"] = self._encode_series(frame["orientation"], "orientation")
        frame["ape_rating"] = self._encode_series(frame["ape_rating"], "ape_rating")
        frame["dpe_rating"] = self._encode_series(frame["dpe_rating"], "dpe_rating")
        frame["council_tax_band_encoded"] = self._encode_series(frame["council_tax_band"], "council_tax_band")
        frame["epc_rating"] = self._encode_series(frame["epc_rating"], "epc_rating")
        frame["leasehold_flag"] = (
            frame["tenure"].fillna("").astype(str).str.contains("leasehold", case=False).astype(float)
        )
        frame["land_registry_last_price_gbp_m2"] = np.where(
            frame["built_area_m2"].fillna(0) > 0,
            pd.to_numeric(frame["uk_lr_last_price_gbp"], errors="coerce")
            / frame["built_area_m2"].replace(0, np.nan),
            np.nan,
        )
        frame["dvf_median_transaction_price_eur_m2"] = pd.to_numeric(
            frame["dvf_median_price_m2"], errors="coerce"
        )
        frame["pieces_count"] = pd.to_numeric(frame["bedrooms"], errors="coerce").fillna(0.0) + 1.0
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
            "orientation",
            "ape_rating",
            "dpe_rating",
            "council_tax_band",
            "epc_rating",
            "tenure",
            "uk_lr_last_price_gbp",
            "omi_zone_min_price_eur_m2",
            "omi_zone_max_price_eur_m2",
            "dvf_median_price_m2",
            "hoa_fees_monthly_usd",
            "lot_size_m2",
            "tax_assessed_value_usd",
            "school_rating",
            "zestimate_reference_usd",
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

    def _encode_series(self, series: pd.Series, rule_name: str) -> pd.Series:
        rule = self.encoding_rules.get(rule_name)
        categories = rule.categories if rule is not None else []
        if not categories:
            return pd.Series(np.nan, index=series.index, dtype="float64")
        mapping = {str(category).lower(): index + 1 for index, category in enumerate(categories)}
        normalized = series.fillna("").astype(str).str.lower()
        return normalized.map(mapping).fillna(0.0)

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
