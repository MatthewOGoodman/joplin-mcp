"""Tests for joplin_mcp.mdsync.block — fenced-block + drift-region line surgery."""

from pathlib import Path

import pytest

from joplin_mcp.mdsync.block import (
    BLOCK_BEGIN,
    BLOCK_END,
    DRIFT_BEGIN,
    SyncMeta,
    body_hash,
    canonical_body,
    read_block,
    strip_block,
    strip_drift_region,
    write_block,
    write_drift_region,
)

FIXTURES = Path(__file__).parent / "fixtures"
USER_FM = (FIXTURES / "mdsync_user_frontmatter.md").read_text()
NO_FM = (FIXTURES / "mdsync_no_frontmatter.md").read_text()
WITH_BLOCK = (FIXTURES / "mdsync_with_block.md").read_text()


def _meta(**overrides) -> SyncMeta:
    base = {
        "id": "a" * 32,
        "title": "My Note",
        "parent_id": "b" * 32,
        "tags": ["GTD", "Tag: Foo"],
        "notebook": "Projects/GTD",
        "synced": "2026-06-06 10:00",
        "prior_Joplin_hash": body_hash("base"),
        "current_Joplin_hash": body_hash("base"),
    }
    base.update(overrides)
    return SyncMeta(**base)


class TestStripBlock:
    def test_user_yaml_byte_identical_after_strip(self):
        """The load-bearing guarantee: user frontmatter is never re-serialized."""
        with_block = write_block(USER_FM, _meta())
        assert strip_block(with_block) == USER_FM

    def test_absent_block_is_idempotent(self):
        assert strip_block(USER_FM) == USER_FM
        assert strip_block(NO_FM) == NO_FM

    def test_block_only_frontmatter_removes_fences(self):
        plain = "just a body line\n"
        with_block = write_block(plain, _meta())
        assert strip_block(with_block) == plain

    def test_duplicate_begin_marker_errors(self):
        text = "\n".join(
            [
                "---",
                BLOCK_BEGIN,
                "mdsync:",
                "  id: x",
                BLOCK_BEGIN,
                BLOCK_END,
                "---",
                "",
            ]
        )
        with pytest.raises(ValueError, match="duplicate"):
            strip_block(text)

    def test_begin_without_end_errors(self):
        text = "\n".join(["---", BLOCK_BEGIN, "mdsync:", "  id: x", "---", ""])
        with pytest.raises(ValueError, match="without"):
            strip_block(text)

    def test_end_without_begin_errors(self):
        text = "\n".join(["---", BLOCK_END, "---", ""])
        with pytest.raises(ValueError, match="without"):
            strip_block(text)

    def test_marker_in_body_code_sample_ignored(self):
        """Markers outside the leading frontmatter are never matched."""
        assert read_block(NO_FM) is None
        assert strip_block(NO_FM) == NO_FM


class TestWriteBlock:
    def test_insert_into_existing_frontmatter(self):
        result = write_block(USER_FM, _meta())
        lines = result.split("\n")
        assert lines[0] == "---"
        assert lines[1] == BLOCK_BEGIN
        # User keys still inside the SAME frontmatter (one fence pair).
        close = lines.index("---", 1)
        assert "status: 'active'" in lines[:close]
        assert result.endswith(USER_FM.split("---", 2)[2])

    def test_create_frontmatter_when_none(self):
        result = write_block("body only\n", _meta())
        lines = result.split("\n")
        assert lines[0] == "---"
        assert lines[1] == BLOCK_BEGIN
        assert BLOCK_END in lines
        assert lines[lines.index(BLOCK_END) + 1] == "---"
        assert result.endswith("body only\n")

    def test_replace_existing_block_in_place(self):
        v1 = write_block(USER_FM, _meta(title="Old Title"))
        v2 = write_block(v1, _meta(title="New Title"))
        assert v2.count(BLOCK_BEGIN) == 1
        assert read_block(v2).title == "New Title"
        assert strip_block(v2) == USER_FM

    def test_tags_none_omits_line_tags_empty_keeps_it(self):
        no_tags = write_block("x\n", _meta(tags=None))
        assert "tags:" not in no_tags
        empty_tags = write_block("x\n", _meta(tags=[]))
        assert "tags: []" in empty_tags

    def test_markdown_bak_omitted_when_none(self):
        result = write_block("x\n", _meta())
        assert "markdown_bak" not in result
        result2 = write_block("x\n", _meta(markdown_bak="plan_x.md.bak"))
        assert "markdown_bak: plan_x.md.bak" in result2


class TestReadBlock:
    def test_parse_all_fields(self):
        meta = read_block(WITH_BLOCK)
        assert meta.id == "abcdef0123456789abcdef0123456789"
        assert meta.title == "Hand-Quoted Title"
        assert meta.parent_id == "0123456789abcdef0123456789abcdef"
        assert meta.tags == ["GTD", "Tag: Foo"]
        assert meta.notebook == "Projects/GTD"
        assert meta.synced == "2026-06-06 09:30"
        assert meta.prior_Joplin_hash.startswith("sha256:")

    def test_absent_returns_none(self):
        assert read_block(USER_FM) is None
        assert read_block("no frontmatter\n") is None

    def test_round_trip_through_write(self):
        meta = _meta()
        parsed = read_block(write_block(USER_FM, meta))
        assert parsed.to_dict() == meta.to_dict()

    def test_tags_absent_is_none_distinct_from_empty(self):
        assert read_block(write_block("x\n", _meta(tags=None))).tags is None
        assert read_block(write_block("x\n", _meta(tags=[]))).tags == []

    def test_corrupt_yaml_errors(self):
        text = "\n".join(
            ["---", BLOCK_BEGIN, "mdsync: [unclosed", BLOCK_END, "---", "body"]
        )
        with pytest.raises(ValueError, match="corrupt mdsync block"):
            read_block(text)

    def test_missing_mdsync_key_errors(self):
        text = "\n".join(["---", BLOCK_BEGIN, "other: 1", BLOCK_END, "---", "body"])
        with pytest.raises(ValueError, match="missing 'mdsync:'"):
            read_block(text)

    def test_numeric_looking_values_coerced_to_str(self):
        text = "\n".join(
            [
                "---",
                BLOCK_BEGIN,
                "mdsync:",
                "  id: 12345678901234567890123456789012",
                BLOCK_END,
                "---",
                "body",
            ]
        )
        assert read_block(text).id == "12345678901234567890123456789012"


class TestDriftRegion:
    def test_write_then_strip_round_trips(self):
        with_block = write_block(USER_FM, _meta())
        with_drift = write_drift_region(with_block, "WARNING: drift\n+a diff line")
        assert DRIFT_BEGIN in with_drift
        assert strip_drift_region(with_drift) == with_block

    def test_region_sits_after_frontmatter(self):
        with_drift = write_drift_region(write_block(USER_FM, _meta()), "W")
        lines = with_drift.split("\n")
        close = lines.index("---", 1)
        assert lines[close + 1] == DRIFT_BEGIN

    def test_excluded_from_canonical_body_and_hash(self):
        with_block = write_block(USER_FM, _meta())
        with_drift = write_drift_region(with_block, "WARNING: drift")
        assert canonical_body(with_drift) == USER_FM
        assert body_hash(canonical_body(with_drift)) == body_hash(USER_FM)

    def test_multiple_stale_regions_all_stripped(self):
        text = write_drift_region(write_drift_region("body\n", "one"), "two")
        assert strip_drift_region(text) == "body\n"

    def test_begin_without_end_errors(self):
        with pytest.raises(ValueError, match="drift"):
            strip_drift_region(f"{DRIFT_BEGIN}\nno end\n")

    def test_no_frontmatter_inserts_at_top(self):
        result = write_drift_region("body\n", "W")
        assert result.split("\n")[0] == DRIFT_BEGIN


class TestBodyHash:
    def test_deterministic_and_prefixed(self):
        assert body_hash("abc") == body_hash("abc")
        assert body_hash("abc").startswith("sha256:")
        assert body_hash("abc") != body_hash("abd")
