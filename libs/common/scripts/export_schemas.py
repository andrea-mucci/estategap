"""Export shared model JSON Schemas for docs consumers."""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from estategap_common.models import (
    AlertRule,
    Country,
    Listing,
    NormalizedListing,
    RawListing,
    ScoringResult,
    User,
    Zone,
)

MODELS = (
    AlertRule,
    Country,
    Listing,
    NormalizedListing,
    RawListing,
    ScoringResult,
    User,
    Zone,
)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    output_dir = repo_root / "docs" / "schemas"
    output_dir.mkdir(parents=True, exist_ok=True)

    for model in MODELS:
        output_path = output_dir / f"{model.__name__}.json"
        output_path.write_text(
            json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        )


if __name__ == "__main__":
    main()
