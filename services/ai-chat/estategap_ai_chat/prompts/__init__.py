"""Prompt rendering helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from importlib import resources
from typing import Any

try:
    from jinja2 import Environment
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained local envs
    Environment = None


@dataclass(slots=True)
class PromptContext:
    """Structured context injected into the system prompt."""

    language: str
    countries: list[str]
    property_types: list[str]
    active_zones: list[dict[str, Any]]
    market_data: dict[str, Any] | None


def render_system_prompt(context: PromptContext) -> str:
    """Render the system prompt template with JSON-encoded context blocks."""

    template_path = resources.files(__package__).joinpath("system_prompt.jinja2")
    payload = asdict(context)
    render_context = {
        **payload,
        "countries_json": json.dumps(context.countries, ensure_ascii=True),
        "property_types_json": json.dumps(context.property_types, ensure_ascii=True),
        "active_zones_json": json.dumps(context.active_zones, ensure_ascii=True),
        "market_data_json": json.dumps(context.market_data or {}, ensure_ascii=True),
    }
    template_text = template_path.read_text(encoding="utf-8")
    if Environment is None:
        rendered = template_text
        for key, value in render_context.items():
            rendered = rendered.replace(f"{{{{ {key} }}}}", str(value))
        return rendered
    template = Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True).from_string(
        template_text
    )
    return str(template.render(**render_context))
