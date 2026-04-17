"""ONNX export helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from estategap_ml.features.engineer import FeatureEngineer


class OnnxSelfTestError(RuntimeError):
    """Raised when the exported ONNX artefact does not match native predictions."""


def export_pipeline_to_onnx(
    feature_engineer: FeatureEngineer,
    lgb_model: object,
    version_tag: str,
    output_dir: Path,
) -> Path:
    """Export the trained LightGBM model to ONNX and validate prediction parity."""

    import onnxruntime as ort
    from onnxmltools import convert_lightgbm
    from onnxmltools.convert.common.data_types import FloatTensorType

    if not hasattr(feature_engineer, "_fit_source_frame_"):
        msg = "FeatureEngineer must be fitted before ONNX export."
        raise ValueError(msg)

    sample_source = feature_engineer._fit_source_frame_.head(50)
    sample_matrix = feature_engineer.transform(sample_source)
    initial_types = [("features", FloatTensorType([None, sample_matrix.shape[1]]))]
    onnx_model = convert_lightgbm(lgb_model, initial_types=initial_types, target_opset=17)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{version_tag}.onnx"
    output_path.write_bytes(onnx_model.SerializeToString())

    session = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    predictions = np.asarray(lgb_model.predict(sample_matrix), dtype=np.float32).reshape(-1)
    exported = session.run(None, {input_name: sample_matrix.astype(np.float32)})[0].reshape(-1)
    if not np.allclose(predictions, exported, atol=1.0):
        msg = "Exported ONNX predictions diverged from native LightGBM predictions."
        raise OnnxSelfTestError(msg)
    return output_path
