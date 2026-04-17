"""Model loading and hot-reload support for the scorer service."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from estategap_ml import logger

from .metrics import SCORER_ACTIVE_MODEL_VERSION, SCORER_MODEL_RELOAD_TOTAL
from .shap_explainer import ShapExplainer


@dataclass(slots=True)
class ModelBundle:
    """Loaded artefacts required to score one country."""

    country_code: str
    version_tag: str
    session_point: Any
    session_q05: Any
    session_q95: Any
    lgb_booster: Any
    feature_engineer: Any
    input_name: str
    feature_names: list[str]
    confidence: str
    transfer_learned: bool
    base_country: str | None
    loaded_at: datetime


def _derive_paths(base: Path) -> tuple[Path, Path, Path, Path, Path]:
    stem = base.with_suffix("")
    return (
        base,
        stem.with_name(f"{stem.name}_q05").with_suffix(".onnx"),
        stem.with_name(f"{stem.name}_q95").with_suffix(".onnx"),
        stem.with_suffix(".lgb"),
        stem.with_name(f"{stem.name}_feature_engineer").with_suffix(".joblib"),
    )


def _download_s3_object(s3_client: Any, bucket: str, key: str, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    s3_client.download_file(bucket, key, str(target))
    return target


def _materialize_artifacts(version_tag: str, artifact_path: str, bucket: str, s3_client: Any) -> tuple[Path, ...]:
    parsed = urlparse(artifact_path)
    if parsed.scheme == "s3":
        bucket_name = parsed.netloc or bucket
        base_key = parsed.path.lstrip("/")
        local_dir = Path("/tmp") / version_tag
        point_key = base_key
        q05_key = base_key.replace(".onnx", "_q05.onnx")
        q95_key = base_key.replace(".onnx", "_q95.onnx")
        lgb_key = base_key.replace(".onnx", ".lgb")
        fe_key = base_key.replace(".onnx", "_feature_engineer.joblib")
        return (
            _download_s3_object(s3_client, bucket_name, point_key, local_dir / Path(point_key).name),
            _download_s3_object(s3_client, bucket_name, q05_key, local_dir / Path(q05_key).name),
            _download_s3_object(s3_client, bucket_name, q95_key, local_dir / Path(q95_key).name),
            _download_s3_object(s3_client, bucket_name, lgb_key, local_dir / Path(lgb_key).name),
            _download_s3_object(s3_client, bucket_name, fe_key, local_dir / Path(fe_key).name),
        )

    base_path = Path(artifact_path)
    if not base_path.exists():
        base_path = Path("/tmp") / artifact_path
    return _derive_paths(base_path)


def download_bundle(
    version_tag: str,
    artifact_path: str,
    bucket: str,
    *,
    country_code: str,
    feature_names: list[str] | None = None,
    confidence: str = "full",
    transfer_learned: bool = False,
    base_country: str | None = None,
    s3_client: Any,
) -> ModelBundle:
    """Download and load all artefacts for one model version."""

    import joblib
    import lightgbm as lgb
    import onnxruntime as ort

    point_path, q05_path, q95_path, lgb_path, fe_path = _materialize_artifacts(
        version_tag=version_tag,
        artifact_path=artifact_path,
        bucket=bucket,
        s3_client=s3_client,
    )
    session_point = ort.InferenceSession(str(point_path))
    session_q05 = ort.InferenceSession(str(q05_path))
    session_q95 = ort.InferenceSession(str(q95_path))
    lgb_booster = lgb.Booster(model_file=str(lgb_path))
    feature_engineer = joblib.load(fe_path)
    resolved_feature_names = list(feature_names or [])
    if not resolved_feature_names and hasattr(feature_engineer, "get_feature_names_out"):
        resolved_feature_names = list(feature_engineer.get_feature_names_out())
    return ModelBundle(
        country_code=country_code.lower(),
        version_tag=version_tag,
        session_point=session_point,
        session_q05=session_q05,
        session_q95=session_q95,
        lgb_booster=lgb_booster,
        feature_engineer=feature_engineer,
        input_name=session_point.get_inputs()[0].name,
        feature_names=resolved_feature_names,
        confidence=confidence,
        transfer_learned=transfer_learned,
        base_country=base_country,
        loaded_at=datetime.now(tz=UTC),
    )


class ModelRegistry:
    """Track active model bundles by country and hot-reload them in place."""

    def __init__(
        self,
        *,
        bucket: str,
        s3_client: Any,
        poll_interval_seconds: int = 60,
        shap_explainer: ShapExplainer | None = None,
    ) -> None:
        self._bucket = bucket
        self._s3_client = s3_client
        self._poll_interval_seconds = poll_interval_seconds
        self._shap_explainer = shap_explainer
        self.bundles: dict[str, ModelBundle] = {}

    def get(self, country_code: str) -> ModelBundle | None:
        return self.bundles.get(country_code.lower())

    async def _fetch_active_versions(self, db_pool: Any) -> list[dict[str, Any]]:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (country_code)
                    LOWER(country_code) AS country_code,
                    version_tag,
                    artifact_path,
                    feature_names,
                    COALESCE(confidence, 'full') AS confidence,
                    COALESCE(transfer_learned, FALSE) AS transfer_learned,
                    base_country
                FROM model_versions
                WHERE status = 'active'
                ORDER BY country_code, trained_at DESC, created_at DESC
                """
            )
        return [dict(row) for row in rows]

    async def load_active_models(self, db_pool: Any, s3_client: Any | None = None) -> None:
        """Load the current active model for each country at startup."""

        for row in await self._fetch_active_versions(db_pool):
            await self.reload_country(
                country_code=row["country_code"],
                version_tag=row["version_tag"],
                artifact_path=row["artifact_path"],
                feature_names=list(row.get("feature_names") or []),
                confidence=str(row.get("confidence") or "full"),
                transfer_learned=bool(row.get("transfer_learned") or False),
                base_country=row.get("base_country"),
                s3_client=s3_client,
                count_reload=False,
            )

    async def reload_country(
        self,
        *,
        country_code: str,
        version_tag: str,
        artifact_path: str,
        feature_names: list[str] | None = None,
        confidence: str = "full",
        transfer_learned: bool = False,
        base_country: str | None = None,
        s3_client: Any | None = None,
        count_reload: bool = True,
    ) -> ModelBundle:
        """Hot-swap one country's active bundle."""

        key = country_code.lower()
        old_bundle = self.bundles.get(key)
        new_bundle = await asyncio.to_thread(
            download_bundle,
            version_tag,
            artifact_path,
            self._bucket,
            country_code=key,
            feature_names=feature_names,
            confidence=confidence,
            transfer_learned=transfer_learned,
            base_country=base_country,
            s3_client=s3_client or self._s3_client,
        )
        self.bundles[key] = new_bundle
        if old_bundle is not None:
            SCORER_ACTIVE_MODEL_VERSION.labels(country=key, version=old_bundle.version_tag).set(0)
            if self._shap_explainer is not None:
                self._shap_explainer.invalidate(old_bundle.version_tag)
        SCORER_ACTIVE_MODEL_VERSION.labels(country=key, version=version_tag).set(1)
        if count_reload and old_bundle is not None and old_bundle.version_tag != version_tag:
            SCORER_MODEL_RELOAD_TOTAL.labels(country=key).inc()
        logger.info(
            "model_bundle_loaded",
            country=key,
            version_tag=version_tag,
            previous_version=old_bundle.version_tag if old_bundle else None,
        )
        return new_bundle

    async def poll_loop(self, db_pool: Any) -> None:
        """Poll the model registry and reload active versions without a restart."""

        while True:
            for row in await self._fetch_active_versions(db_pool):
                country_code = row["country_code"]
                current = self.bundles.get(country_code)
                if current is None or current.version_tag != row["version_tag"]:
                    await self.reload_country(
                        country_code=country_code,
                        version_tag=row["version_tag"],
                        artifact_path=row["artifact_path"],
                        feature_names=list(row.get("feature_names") or []),
                        confidence=str(row.get("confidence") or "full"),
                        transfer_learned=bool(row.get("transfer_learned") or False),
                        base_country=row.get("base_country"),
                    )
            await asyncio.sleep(self._poll_interval_seconds)

    async def subscribe_training_completed(self, nc: Any) -> None:
        """Subscribe to promotion events for immediate reloads."""

        async def _on_model_promoted(msg: Any) -> None:
            payload = json.loads(msg.data.decode("utf-8"))
            country_code = str(payload["country_code"]).lower()
            version_tag = str(payload["model_version_tag"])
            artifact_path = str(payload.get("artifact_path") or f"s3://{self._bucket}/models/{version_tag}.onnx")
            asyncio.create_task(
                self.reload_country(
                    country_code=country_code,
                    version_tag=version_tag,
                    artifact_path=artifact_path,
                )
            )

        await nc.subscribe("ml.training.completed", cb=_on_model_promoted)


__all__ = ["ModelBundle", "ModelRegistry", "download_bundle"]
