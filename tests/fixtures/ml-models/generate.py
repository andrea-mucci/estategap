from __future__ import annotations

from pathlib import Path

import numpy as np
import onnxruntime as ort
from sklearn.linear_model import LinearRegression
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType


COUNTRY_OFFSETS = {
    "es": 0.0,
    "it": 15000.0,
    "fr": 30000.0,
    "pt": -10000.0,
    "gb": 60000.0,
}

FEATURE_ROWS = np.array(
    [
        [45.0, 1.0, 1.0],
        [55.0, 2.0, 1.0],
        [62.0, 2.0, 1.0],
        [70.0, 2.0, 2.0],
        [78.0, 3.0, 2.0],
        [85.0, 3.0, 2.0],
        [92.0, 3.0, 2.0],
        [105.0, 4.0, 2.0],
        [118.0, 4.0, 3.0],
        [130.0, 5.0, 3.0],
    ],
    dtype=np.float32,
)


def train_model(offset: float) -> LinearRegression:
    targets = (
        FEATURE_ROWS[:, 0] * 3300.0
        + FEATURE_ROWS[:, 1] * 14000.0
        + FEATURE_ROWS[:, 2] * 9000.0
        + offset
    )
    model = LinearRegression()
    model.fit(FEATURE_ROWS, targets)
    return model


def export_model(country: str, output_dir: Path) -> None:
    model = train_model(COUNTRY_OFFSETS[country])
    onnx_model = convert_sklearn(
        model,
        initial_types=[("features", FloatTensorType([None, 3]))],
        target_opset=17,
    )
    serialized = onnx_model.SerializeToString()

    session = ort.InferenceSession(serialized, providers=["CPUExecutionProvider"])
    sample = np.array([[72.0, 2.0, 2.0]], dtype=np.float32)
    outputs = session.run(None, {"features": sample})
    if not outputs or not outputs[0].size:
        raise RuntimeError(f"ONNX validation failed for {country}")

    (output_dir / f"{country}.onnx").write_bytes(serialized)


def main() -> None:
    output_dir = Path(__file__).resolve().parent
    for country in COUNTRY_OFFSETS:
        export_model(country, output_dir)


if __name__ == "__main__":
    main()
