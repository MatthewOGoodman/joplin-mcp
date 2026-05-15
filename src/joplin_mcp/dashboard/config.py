"""YAML config loading + JSON Schema validation for the dashboard CLI.

A dashboard config defines an output path, optional header/footer templates,
and an ordered list of sections. Each section is one query with its own
filters, columns, sort, and optional grouping.

The full key-by-key spec lives in `docs/dashboard_config.md`; the machine
schema this module consumes is `schemas/dashboard_config.schema.yaml`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

_SCHEMA_PATH = Path(__file__).parent / "schemas" / "dashboard_config.schema.yaml"


def _load_schema() -> dict:
    with _SCHEMA_PATH.open() as f:
        return yaml.safe_load(f)


_SCHEMA = _load_schema()
Draft202012Validator.check_schema(_SCHEMA)
_VALIDATOR = Draft202012Validator(_SCHEMA)


class ConfigValidationError(ValueError):
    """Raised when a dashboard config fails JSON Schema validation.

    Subclasses ValueError so existing `except ValueError` catches still work.
    `errors` is the list of jsonschema ValidationError objects collected via
    iter_errors() — preserved so CLIs can format them with JSON Pointer paths.
    """

    def __init__(self, errors: list[ValidationError]):
        self.errors = errors
        summary = "; ".join(self._summarize(e) for e in errors)
        super().__init__(f"config validation failed: {summary}")

    @staticmethod
    def _summarize(err: ValidationError) -> str:
        pointer = "/" + "/".join(str(p) for p in err.absolute_path)
        return f"{pointer}: {err.message}"


@dataclass
class SectionConfig:
    """One queryable section of a dashboard."""

    title: str
    notebook: str | None = None
    tags_required: list[str] = field(default_factory=list)
    tags_excluded: list[str] = field(default_factory=list)
    extra_query: str | None = None
    columns: list[str] = field(default_factory=lambda: ["title", "updated"])
    group_by_tag_prefix: str | None = None
    sort_by: str = "updated"
    sort_dir: str = "desc"


@dataclass
class DashboardConfig:
    """Top-level dashboard config."""

    output: Path
    sections: list[SectionConfig]
    header: str = ""
    footer: str = ""


def load_config(path: str | Path) -> DashboardConfig:
    """Load and validate a dashboard config from a YAML file.

    Validation runs before dataclass construction; any schema violation raises
    ConfigValidationError (a ValueError subclass) carrying all errors found
    in a single pass.
    """
    path = Path(path).expanduser()
    with path.open() as f:
        raw = yaml.safe_load(f)

    errors = list(_VALIDATOR.iter_errors(raw))
    if errors:
        raise ConfigValidationError(errors)

    sections = [_section_from_dict(s) for s in raw["sections"]]

    return DashboardConfig(
        output=Path(raw["output"]).expanduser(),
        sections=sections,
        header=raw.get("header", ""),
        footer=raw.get("footer", ""),
    )


def _section_from_dict(d: dict[str, Any]) -> SectionConfig:
    return SectionConfig(
        title=d["title"],
        notebook=d.get("notebook"),
        tags_required=list(d.get("tags_required", [])),
        tags_excluded=list(d.get("tags_excluded", [])),
        extra_query=d.get("extra_query"),
        columns=list(d.get("columns", ["title", "updated"])),
        group_by_tag_prefix=d.get("group_by_tag_prefix"),
        sort_by=d.get("sort_by", "updated"),
        sort_dir=d.get("sort_dir", "desc"),
    )
