"""Tests for the dashboard config JSON Schema.

Covers:
- meta-validation (the schema itself is valid JSON Schema 2020-12)
- positive: minimal and full fixtures validate clean
- negative: each required-key / type / additionalProperties failure path
- multi-error: iter_errors surfaces all errors in one pass
- drift: the canonical example embedded in docs/dashboard_config.md validates
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from joplin_mcp.dashboard.config import (
    _SCHEMA,
    _VALIDATOR,
    ConfigValidationError,
    load_config,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
DOCS_FILE = REPO_ROOT / "docs" / "dashboard_config.md"


def _load_yaml(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


# ----------------------------------------------------------------------------
# Meta-validation
# ----------------------------------------------------------------------------


class TestSchemaMeta:
    def test_schema_is_valid_meta(self):
        """The schema itself conforms to JSON Schema Draft 2020-12."""
        Draft202012Validator.check_schema(_SCHEMA)

    def test_schema_declares_draft(self):
        assert _SCHEMA.get("$schema") == "https://json-schema.org/draft/2020-12/schema"

    def test_schema_rejects_unknown_top_level_keys(self):
        assert _SCHEMA.get("additionalProperties") is False

    def test_schema_rejects_unknown_section_keys(self):
        assert _SCHEMA["properties"]["sections"]["items"]["additionalProperties"] is False


# ----------------------------------------------------------------------------
# Positive — fixtures validate
# ----------------------------------------------------------------------------


class TestFixturesValidate:
    def test_minimal_fixture_validates(self):
        raw = _load_yaml(FIXTURES / "dashboard_config_minimal.yaml")
        errors = list(_VALIDATOR.iter_errors(raw))
        assert errors == []

    def test_full_fixture_validates(self):
        raw = _load_yaml(FIXTURES / "dashboard_config_full.yaml")
        errors = list(_VALIDATOR.iter_errors(raw))
        assert errors == []

    def test_minimal_fixture_loads_via_load_config(self):
        """Round-trip: load_config produces a usable DashboardConfig from minimal fixture."""
        config = load_config(FIXTURES / "dashboard_config_minimal.yaml")
        assert len(config.sections) == 1
        assert config.sections[0].title == "All notes"

    def test_full_fixture_loads_via_load_config(self):
        config = load_config(FIXTURES / "dashboard_config_full.yaml")
        assert len(config.sections) == 2
        assert config.sections[0].title == "People — active"
        assert config.sections[1].group_by_tag_prefix == "Phase "
        assert "priority" in config.sections[1].columns  # frontmatter passthrough


# ----------------------------------------------------------------------------
# Negative — specific failure paths
# ----------------------------------------------------------------------------


class TestSchemaNegative:
    def test_missing_output(self):
        errors = list(_VALIDATOR.iter_errors({"sections": [{"title": "x"}]}))
        assert any("output" in e.message for e in errors)

    def test_missing_sections(self):
        errors = list(_VALIDATOR.iter_errors({"output": "/tmp/x.md"}))
        assert any("sections" in e.message for e in errors)

    def test_missing_section_title(self):
        errors = list(
            _VALIDATOR.iter_errors(
                {"output": "/tmp/x.md", "sections": [{"notebook": "X"}]}
            )
        )
        assert any("title" in e.message for e in errors)

    def test_unknown_top_level_key(self):
        errors = list(
            _VALIDATOR.iter_errors(
                {
                    "output": "/tmp/x.md",
                    "sections": [{"title": "x"}],
                    "bogus_key": "value",
                }
            )
        )
        assert any("bogus_key" in e.message for e in errors)

    def test_unknown_section_key(self):
        errors = list(
            _VALIDATOR.iter_errors(
                {
                    "output": "/tmp/x.md",
                    "sections": [{"title": "x", "group_by_tag_prefx": "X"}],
                }
            )
        )
        assert any("group_by_tag_prefx" in e.message for e in errors)

    def test_sections_not_array(self):
        errors = list(
            _VALIDATOR.iter_errors({"output": "/tmp/x.md", "sections": "not-a-list"})
        )
        assert any("array" in e.message.lower() for e in errors)

    def test_root_not_object(self):
        errors = list(_VALIDATOR.iter_errors(["not", "a", "mapping"]))
        assert any("object" in e.message.lower() for e in errors)

    def test_sort_dir_enum_violation(self):
        errors = list(
            _VALIDATOR.iter_errors(
                {
                    "output": "/tmp/x.md",
                    "sections": [{"title": "x", "sort_dir": "sideways"}],
                }
            )
        )
        assert any("sideways" in e.message for e in errors)

    def test_tags_required_wrong_type(self):
        errors = list(
            _VALIDATOR.iter_errors(
                {
                    "output": "/tmp/x.md",
                    "sections": [{"title": "x", "tags_required": "single-string"}],
                }
            )
        )
        assert any("array" in e.message.lower() for e in errors)

    def test_columns_member_wrong_type(self):
        errors = list(
            _VALIDATOR.iter_errors(
                {
                    "output": "/tmp/x.md",
                    "sections": [{"title": "x", "columns": [123, "title"]}],
                }
            )
        )
        assert errors  # int in columns array should fail; string required


# ----------------------------------------------------------------------------
# Multi-error reporting
# ----------------------------------------------------------------------------


class TestIterErrorsMultiple:
    def test_iter_errors_returns_multiple(self):
        """Config with two distinct errors surfaces both in one pass."""
        bad = {
            "output": "/tmp/x.md",
            "sections": [
                {"title": "x", "sort_dir": "sideways"},
                {"notebook": "Y"},  # missing title
            ],
        }
        errors = list(_VALIDATOR.iter_errors(bad))
        assert len(errors) >= 2
        messages = " ".join(e.message for e in errors)
        assert "sideways" in messages
        assert "title" in messages

    def test_config_validation_error_carries_all_errors(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text(
            "output: /tmp/x.md\n"
            "sections:\n"
            "  - title: x\n"
            "    sort_dir: sideways\n"
            "  - notebook: Y\n"
        )
        with pytest.raises(ConfigValidationError) as ctx:
            load_config(path)
        assert len(ctx.value.errors) >= 2


# ----------------------------------------------------------------------------
# Drift — canonical example in docs validates against schema
# ----------------------------------------------------------------------------


def _extract_canonical_example(docs_text: str) -> str:
    """Extract the YAML between <!-- canonical-example --> markers and the closing fence."""
    match = re.search(
        r"<!-- canonical-example -->\s*```yaml\n(.*?)\n```",
        docs_text,
        flags=re.DOTALL,
    )
    if not match:
        raise AssertionError(
            "Could not find <!-- canonical-example --> YAML block in docs/dashboard_config.md"
        )
    return match.group(1)


class TestCanonicalExampleDrift:
    def test_canonical_example_block_exists(self):
        text = DOCS_FILE.read_text()
        assert "<!-- canonical-example -->" in text
        assert "<!-- /canonical-example -->" in text

    def test_canonical_example_validates(self):
        text = DOCS_FILE.read_text()
        example_yaml = _extract_canonical_example(text)
        parsed = yaml.safe_load(example_yaml)
        errors = list(_VALIDATOR.iter_errors(parsed))
        assert errors == [], (
            "Canonical example in docs/dashboard_config.md does not validate "
            "against schemas/dashboard_config.schema.yaml. The schema and docs "
            "have drifted; reconcile before merging. Errors:\n"
            + "\n".join(f"  - {e.absolute_path}: {e.message}" for e in errors)
        )
