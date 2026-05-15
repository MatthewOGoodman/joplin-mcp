"""Tests for joplin_mcp.dashboard.config — YAML loading and validation.

Schema validation tests live in tests/test_dashboard_schema.py. This file
covers the dataclass mapping and ConfigValidationError surface.
"""

from pathlib import Path

import pytest

from joplin_mcp.dashboard.config import (
    ConfigValidationError,
    DashboardConfig,
    SectionConfig,
    load_config,
)


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(content)
    return path


class TestLoadConfigHappyPath:
    """Minimal valid YAML loads and produces correctly populated dataclasses."""

    def test_minimal_valid_config(self, tmp_path):
        path = _write(
            tmp_path,
            """
output: /tmp/dashboard.md
sections:
  - title: People
    notebook: "People"
            """,
        )
        config = load_config(path)
        assert isinstance(config, DashboardConfig)
        assert config.output == Path("/tmp/dashboard.md")
        assert config.header == "" and config.footer == ""
        assert len(config.sections) == 1

        section = config.sections[0]
        assert isinstance(section, SectionConfig)
        assert section.title == "People"
        assert section.notebook == "People"
        assert section.tags_required == []
        assert section.tags_excluded == []
        assert section.columns == ["title", "updated"]
        assert section.sort_by == "updated"
        assert section.sort_dir == "desc"

    def test_full_section_options_parse(self, tmp_path):
        path = _write(
            tmp_path,
            """
output: /tmp/d.md
header: "# Header {timestamp}"
footer: "Footer line"
sections:
  - title: Apps
    notebook: "Applications"
    tags_required: ["Status: Active"]
    tags_excluded: ["Status: Archived"]
    extra_query: "title:foo"
    columns: [title, tags, updated]
    group_by_tag_prefix: "Phase "
    sort_by: title
    sort_dir: asc
            """,
        )
        config = load_config(path)
        assert config.header == "# Header {timestamp}"
        assert config.footer == "Footer line"
        section = config.sections[0]
        assert section.tags_required == ["Status: Active"]
        assert section.tags_excluded == ["Status: Archived"]
        assert section.extra_query == "title:foo"
        assert section.columns == ["title", "tags", "updated"]
        assert section.group_by_tag_prefix == "Phase "
        assert section.sort_by == "title"
        assert section.sort_dir == "asc"

    def test_user_path_expanded(self, tmp_path):
        path = _write(
            tmp_path,
            """
output: ~/somewhere/dashboard.md
sections:
  - title: A
            """,
        )
        config = load_config(path)
        assert "~" not in str(config.output)


class TestLoadConfigErrors:
    """Invalid configs raise ConfigValidationError (a ValueError subclass)."""

    def test_missing_output_raises(self, tmp_path):
        path = _write(tmp_path, "sections:\n  - title: A\n")
        with pytest.raises(ConfigValidationError, match="output"):
            load_config(path)

    def test_missing_sections_raises(self, tmp_path):
        path = _write(tmp_path, "output: /tmp/x.md\n")
        with pytest.raises(ConfigValidationError, match="sections"):
            load_config(path)

    def test_sections_not_list_raises(self, tmp_path):
        path = _write(tmp_path, "output: /tmp/x.md\nsections: not-a-list\n")
        with pytest.raises(ConfigValidationError):
            load_config(path)

    def test_section_missing_title_raises(self, tmp_path):
        path = _write(
            tmp_path, "output: /tmp/x.md\nsections:\n  - notebook: People\n"
        )
        with pytest.raises(ConfigValidationError, match="title"):
            load_config(path)

    def test_root_not_mapping_raises(self, tmp_path):
        path = _write(tmp_path, "- just a list\n")
        with pytest.raises(ConfigValidationError):
            load_config(path)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "does-not-exist.yaml")

    def test_unknown_top_level_key_raises(self, tmp_path):
        """Schema rejects typos / unknown keys (additionalProperties: false)."""
        path = _write(
            tmp_path,
            "output: /tmp/x.md\nsections:\n  - title: A\nfooterz: oops\n",
        )
        with pytest.raises(ConfigValidationError, match="footerz"):
            load_config(path)

    def test_unknown_section_key_raises(self, tmp_path):
        path = _write(
            tmp_path,
            "output: /tmp/x.md\nsections:\n  - title: A\n    group_by_tag_prefx: 'X '\n",
        )
        with pytest.raises(ConfigValidationError, match="group_by_tag_prefx"):
            load_config(path)

    def test_sort_dir_enum_violation_raises(self, tmp_path):
        path = _write(
            tmp_path,
            "output: /tmp/x.md\nsections:\n  - title: A\n    sort_dir: sideways\n",
        )
        with pytest.raises(ConfigValidationError, match="sideways"):
            load_config(path)

    def test_config_validation_error_is_value_error(self, tmp_path):
        """Existing `except ValueError` catches still work after migration."""
        path = _write(tmp_path, "output: /tmp/x.md\n")
        with pytest.raises(ValueError):
            load_config(path)
