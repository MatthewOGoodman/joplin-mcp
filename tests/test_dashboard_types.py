"""Tests for joplin_mcp.dashboard.types — NoteRecord and time normalization."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from joplin_mcp.dashboard.types import NoteRecord, _to_utc


class TestToUtc:
    """_to_utc must normalize joppy time values into tz-aware UTC datetimes."""

    def test_utc_aware_datetime_passes_through(self):
        dt = datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc)
        assert _to_utc(dt) is dt

    def test_naive_datetime_gets_utc_tz(self):
        dt = datetime(2026, 5, 7, 12, 0)
        result = _to_utc(dt)
        assert result.tzinfo is timezone.utc
        assert result.replace(tzinfo=None) == dt

    def test_int_milliseconds_converts_to_utc_datetime(self):
        # 1714867200000 ms = 2024-05-05 00:00:00 UTC
        result = _to_utc(1714867200000)
        assert result.tzinfo is timezone.utc
        assert result.year == 2024 and result.month == 5 and result.day == 5

    def test_unsupported_type_raises(self):
        with pytest.raises(TypeError):
            _to_utc("2026-05-07")


class TestNoteRecordFromJoppyNote:
    """from_joppy_note should build a NoteRecord from a joppy-shaped object."""

    def _fake_note(self, **overrides):
        defaults = dict(
            id="abc",
            title="My Note",
            created_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            updated_time=datetime(2026, 5, 7, tzinfo=timezone.utc),
        )
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def test_builds_record_with_resolved_metadata(self):
        note = self._fake_note()
        record = NoteRecord.from_joppy_note(
            note,
            notebook_path="1-Job Search/People",
            tag_titles=["Job: Status: Active"],
            body="hello",
            frontmatter={"org": "mgb"},
        )
        assert record.id == "abc"
        assert record.title == "My Note"
        assert record.notebook_path == "1-Job Search/People"
        assert record.tags == ["Job: Status: Active"]
        assert record.body == "hello"
        assert record.frontmatter == {"org": "mgb"}

    def test_default_frontmatter_is_empty_dict(self):
        record = NoteRecord.from_joppy_note(
            self._fake_note(), notebook_path="N", tag_titles=[]
        )
        assert record.frontmatter == {}

    def test_none_title_becomes_empty_string(self):
        record = NoteRecord.from_joppy_note(
            self._fake_note(title=None), notebook_path="N", tag_titles=[]
        )
        assert record.title == ""

    def test_int_times_normalize_to_utc(self):
        note = self._fake_note(created_time=1609459200000, updated_time=1609545600000)
        record = NoteRecord.from_joppy_note(note, notebook_path="N", tag_titles=[])
        assert record.created_time.tzinfo is timezone.utc
        assert record.updated_time.tzinfo is timezone.utc
