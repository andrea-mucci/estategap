"""Static ML feature configuration assets and settings re-exports."""

from __future__ import annotations

from pathlib import Path

from ..settings import Config

CONFIG_DIR = Path(__file__).resolve().parent

__all__ = ["CONFIG_DIR", "Config"]
