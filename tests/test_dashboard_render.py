"""Tests for joplin_mcp.dashboard.render — pure rendering functions."""

from datetime import datetime, timezone

import pytest

from joplin_mcp.dashboard.config import SectionConfig
from joplin_mcp.dashboard.render import (
    _column_cell,
    _column_header,
    _group_by_tag_prefix,
    _md_escape,
    _sort,
    assemble_dashboard,
    render_section,
)
from joplin_mcp.dashboard.types import NoteRecord


def _note(
    *,
    id="abc",
    title="Title",
    notebook_path="N",
    tags=None,
    created=datetime(2026, 1, 1, tzinfo=timezone.utc),
    updated=datetime(2026, 5, 7, tzinfo=timezone.utc),
    frontmatter=None,
) -> NoteRecord:
    return NoteRecord(
        id=id,
        title=title,
        notebook_path=notebook_path,
        tags=tags or [],
        created_time=created,
        updated_time=updated,
        frontmatter=frontmatter or {},
    )


class TestSort:
    def test_by_updated_desc(self):
        a = _note(id="a", updated=datetime(2026, 1, 1, tzinfo=timezone.utc))
        b = _note(id="b", updated=datetime(2026, 5, 1, tzinfo=timezone.utc))
        assert [n.id for n in _sort([a, b], "updated", "desc")] == ["b", "a"]

    def test_by_title_asc_case_insensitive(self):
        a = _note(id="a", title="banana")
        b = _note(id="b", title="Apple")
        assert [n.id for n in _sort([a, b], "title", "asc")] == ["b", "a"]

    def test_frontmatter_field_fallback(self):
        a = _note(id="a", frontmatter={"priority": "low"})
        b = _note(id="b", frontmatter={"priority": "high"})
        assert [n.id for n in _sort([a, b], "priority", "asc")] == ["b", "a"]

    def test_missing_frontmatter_field_sorts_as_empty(self):
        a = _note(id="a", frontmatter={})
        b = _note(id="b", frontmatter={"priority": "high"})
        # asc: empty string sorts before "high"
        assert [n.id for n in _sort([a, b], "priority", "asc")] == ["a", "b"]


class TestGroupByTagPrefix:
    def test_groups_by_tag_suffix(self):
        a = _note(id="a", tags=["Job: Phase 4", "x"])
        b = _note(id="b", tags=["Job: Phase 5"])
        c = _note(id="c", tags=["Job: Phase 4"])
        groups = _group_by_tag_prefix([a, b, c], "Job: Phase ")
        assert sorted(groups.keys()) == ["4", "5"]
        assert {n.id for n in groups["4"]} == {"a", "c"}

    def test_notes_without_matching_tag_go_to_none_bucket(self):
        a = _note(id="a", tags=["something"])
        groups = _group_by_tag_prefix([a], "Job: Phase ")
        assert "(none)" in groups and groups["(none)"] == [a]

    def test_first_match_wins(self):
        a = _note(id="a", tags=["Job: Phase 3", "Job: Phase 5"])
        groups = _group_by_tag_prefix([a], "Job: Phase ")
        assert "3" in groups
        assert "5" not in groups


class TestColumnCell:
    def test_title_column(self):
        assert _column_cell(_note(title="Foo"), "title") == "Foo"

    def test_untitled_fallback(self):
        assert _column_cell(_note(title=""), "title") == "_(untitled)_"

    def test_tags_column_joins(self):
        assert (
            _column_cell(_note(tags=["a", "b"]), "tags") == "a, b"
        )

    def test_updated_column_iso_date(self):
        n = _note(updated=datetime(2026, 5, 7, 12, tzinfo=timezone.utc))
        assert _column_cell(n, "updated") == "2026-05-07"

    def test_frontmatter_string_value(self):
        n = _note(frontmatter={"org": "mgb"})
        assert _column_cell(n, "org") == "mgb"

    def test_frontmatter_list_value_joins(self):
        n = _note(frontmatter={"contacts": ["chen", "wang"]})
        assert _column_cell(n, "contacts") == "chen, wang"

    def test_frontmatter_missing_renders_empty(self):
        assert _column_cell(_note(), "missing") == ""


class TestMdEscape:
    def test_escapes_pipe(self):
        assert _md_escape("a|b") == "a\\|b"

    def test_collapses_newline(self):
        assert _md_escape("a\nb") == "a b"


class TestColumnHeader:
    def test_underscore_to_space_titlecase(self):
        assert _column_header("updated_time") == "Updated Time"


class TestRenderSection:
    def test_empty_notes_returns_placeholder(self):
        section = SectionConfig(title="People")
        out = render_section([], section)
        assert "## People" in out
        assert "_No matching notes._" in out

    def test_renders_table_with_default_columns(self):
        section = SectionConfig(title="People")
        out = render_section([_note(title="Bob")], section)
        assert "## People" in out
        assert "| Title | Updated |" in out
        assert "| Bob |" in out

    def test_grouped_section_emits_subheaders(self):
        section = SectionConfig(
            title="Apps",
            group_by_tag_prefix="Job: Phase ",
            columns=["title"],
        )
        notes = [
            _note(id="a", title="N4", tags=["Job: Phase 4"]),
            _note(id="b", title="N5", tags=["Job: Phase 5"]),
        ]
        out = render_section(notes, section)
        assert "### Job: Phase 4" in out
        assert "### Job: Phase 5" in out


class TestAssembleDashboard:
    def test_assembles_with_header_and_footer(self):
        ts = datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc)
        out = assemble_dashboard(
            ["## Section A\n\ntable",  "## Section B\n\ntable"],
            header="# Dash {timestamp}",
            footer="end {timestamp}",
            timestamp=ts,
        )
        assert "# Dash 2026-05-07 12:00 UTC" in out
        assert "## Section A" in out
        assert "## Section B" in out
        assert "end 2026-05-07 12:00 UTC" in out
        assert out.endswith("\n")

    def test_header_and_footer_optional(self):
        out = assemble_dashboard(["## A\n\nx"])
        assert "## A" in out
