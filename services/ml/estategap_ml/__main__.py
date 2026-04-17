"""Unified entry point for ML trainer and scorer modes."""

from __future__ import annotations

import argparse
import asyncio
import os


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EstateGap ML service entry point")
    parser.add_argument(
        "--mode",
        choices=["trainer", "scorer"],
        default=os.getenv("SERVICE_MODE", "trainer"),
        help="Select which ML runtime to start",
    )
    return parser


async def main() -> int:
    args, _ = _build_parser().parse_known_args()
    if args.mode == "scorer":
        from estategap_ml.scorer.__main__ import main as scorer_main

        return await scorer_main()
    from estategap_ml.trainer.__main__ import main as trainer_main

    return await trainer_main()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
