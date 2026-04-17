"""EstateGap ML service package."""

from __future__ import annotations

import os

from estategap_common.logging import configure_logging
import structlog

from .config import Config

configure_logging(level=os.getenv("LOG_LEVEL", "INFO"), service="ml-trainer")
logger = structlog.get_logger("estategap_ml")

__all__ = ["Config", "logger"]
