"""Tests for joplin_mcp.dashboard.loader — query construction and metadata resolution.

No live network calls — all Joplin API access is mocked. Verifies that the
JoplinRestLoader builds the right queries from a SectionConfig, handles joppy
DataList vs flat-list returns, resolves notebook paths via parent_id walking
and caches them, and parses YAML frontmatter from note bodies.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from joplin_mcp.dashboard.config import SectionConfig
from joplin_mcp.dashboard.loader import JoplinRestLoader, _items, _split_frontmatter


def _data_list(items):
    """Mimic joppy's DataList: an object with .items attribute holding a list."""
    return SimpleNamespace(items=items, has_more=False, cursor=None)


def _fake_note(*, id="n1", title="T", parent_id="folder1", body=""):
    return SimpleNamespace(
        id=id,
        title=title,
        parent_id=parent_id,
        body=body,
        created_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_time=datetime(2026, 5, 7, tzinfo=timezone.utc),
    )


def _fake_folder(id, title, parent_id=""):
    return SimpleNamespace(id=id, title=title, parent_id=parent_id)


def _fake_tag(title):
    return SimpleNamespace(title=title)


class TestItems:
    def test_unwraps_data_list(self):
        dl = _data_list(["a", "b"])
        assert _items(dl) == ["a", "b"]

    def test_passes_through_plain_list(self):
        assert _items(["a", "b"]) == ["a", "b"]

    def test_dict_passes_through_unchanged(self):
        # dict has .items as a method; must NOT be unwrapped via .items
        d = {"a": 1}
        assert _items(d) is d


class TestSplitFrontmatter:
    def test_empty_body_returns_empty(self):
        meta, body = _split_frontmatter("")
        assert meta == {}
        assert body == ""

    def test_none_body_returns_empty(self):
        meta, body = _split_frontmatter(None)
        assert meta == {}

    def test_parses_yaml_frontmatter(self):
        text = "---\norg: mgb\npriority: high\n---\nbody text"
        meta, body = _split_frontmatter(text)
        assert meta == {"org": "mgb", "priority": "high"}
        assert body.strip() == "body text"

    def test_no_frontmatter_returns_body_as_content(self):
        meta, body = _split_frontmatter("just some content")
        assert meta == {}


class TestBuildQuery:
    def setup_method(self):
        self.loader = JoplinRestLoader(client=MagicMock())

    def test_notebook_only(self):
        section = SectionConfig(title="X", notebook="1-Job Search/People")
        assert self.loader._build_query(section) == 'notebook:"1-Job Search/People"'

    def test_notebook_plus_required_tag(self):
        section = SectionConfig(
            title="X", notebook="People", tags_required=["Job: Status: Active"]
        )
        q = self.loader._build_query(section)
        assert 'notebook:"People"' in q
        assert 'tag:"Job: Status: Active"' in q

    def test_excluded_tag_uses_minus_prefix(self):
        section = SectionConfig(
            title="X", notebook="People", tags_excluded=["Job: Status: Archived"]
        )
        assert '-tag:"Job: Status: Archived"' in self.loader._build_query(section)

    def test_extra_query_appended(self):
        section = SectionConfig(title="X", notebook="P", extra_query="title:foo")
        q = self.loader._build_query(section)
        assert q.endswith("title:foo")

    def test_empty_section_falls_back_to_wildcard(self):
        section = SectionConfig(title="X")
        assert self.loader._build_query(section) == "*"

    def test_multiple_required_tags(self):
        section = SectionConfig(
            title="X",
            notebook="P",
            tags_required=["Job: Status: Active", "Job: Priority: High"],
        )
        q = self.loader._build_query(section)
        assert 'tag:"Job: Status: Active"' in q
        assert 'tag:"Job: Priority: High"' in q


class TestNotebookPathResolution:
    def setup_method(self):
        self.client = MagicMock()
        self.loader = JoplinRestLoader(client=self.client)

    def test_walks_parent_chain_and_joins(self):
        # parent_id chain: leaf -> mid -> root (parent_id="")
        self.client.get_notebook.side_effect = [
            _fake_folder("leaf", "People", parent_id="mid"),
            _fake_folder("mid", "1-Job Search", parent_id=""),
        ]
        path = self.loader._notebook_path_for("leaf")
        assert path == "1-Job Search/People"

    def test_caches_resolved_path(self):
        self.client.get_notebook.side_effect = [
            _fake_folder("leaf", "X", parent_id=""),
        ]
        first = self.loader._notebook_path_for("leaf")
        second = self.loader._notebook_path_for("leaf")
        assert first == second == "X"
        # only called once because of cache
        assert self.client.get_notebook.call_count == 1


class TestLoadSectionEndToEnd:
    def setup_method(self):
        self.client = MagicMock()
        self.loader = JoplinRestLoader(client=self.client)

    def test_returns_records_with_resolved_metadata(self):
        notes = [
            _fake_note(id="n1", title="Note one", parent_id="folder1"),
            _fake_note(id="n2", title="Note two", parent_id="folder1"),
        ]
        self.client.search_all.return_value = _data_list(notes)
        # All notes have the same parent; each get_tags returns one tag.
        self.client.get_tags.return_value = _data_list([_fake_tag("Job: Status: Active")])
        self.client.get_notebook.return_value = _fake_folder(
            "folder1", "People", parent_id=""
        )

        section = SectionConfig(
            title="People",
            notebook="People",
            tags_required=["Job: Status: Active"],
        )
        records = self.loader.load_section(section)

        assert len(records) == 2
        assert records[0].title == "Note one"
        assert records[0].tags == ["Job: Status: Active"]
        assert records[0].notebook_path == "People"

        # Verify the search query was built correctly
        call_query = self.client.search_all.call_args.kwargs["query"]
        assert 'notebook:"People"' in call_query
        assert 'tag:"Job: Status: Active"' in call_query

    def test_parses_frontmatter_from_body(self):
        body = "---\norg: mgb\n---\nbody text"
        self.client.search_all.return_value = _data_list(
            [_fake_note(id="n1", body=body)]
        )
        self.client.get_tags.return_value = _data_list([])
        self.client.get_notebook.return_value = _fake_folder("f", "X", parent_id="")

        records = self.loader.load_section(SectionConfig(title="X", notebook="X"))
        assert records[0].frontmatter == {"org": "mgb"}

    def test_empty_search_result_returns_empty_list(self):
        self.client.search_all.return_value = _data_list([])
        records = self.loader.load_section(SectionConfig(title="X", notebook="X"))
        assert records == []
