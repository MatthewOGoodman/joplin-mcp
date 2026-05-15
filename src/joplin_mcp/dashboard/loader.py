"""Note loaders for the dashboard package.

A Loader resolves a SectionConfig into a list of NoteRecord by querying some
backing store (Joplin REST API, SQLite read layer, etc.). Two implementations
are planned; v1 ships only JoplinRestLoader.

The interface is intentionally narrow — one method, one config-shape input —
so a SQLite implementation can be slotted in later without touching callers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import frontmatter

from joplin_mcp.dashboard.config import SectionConfig
from joplin_mcp.dashboard.types import NoteRecord


class Loader(ABC):
    """Abstract Joplin loader. Implementations: REST (v1), SQLite (v1.5)."""

    @abstractmethod
    def load_section(self, section: SectionConfig) -> list[NoteRecord]:
        """Resolve a section config into the matching list of notes."""


class JoplinRestLoader(Loader):
    """Load notes via the Joplin REST API using joppy's ClientApi.

    Reuses joplin_mcp.fastmcp_server.get_joplin_client() so token handling
    matches the rest of joplin-mcp.
    """

    def __init__(self, client=None) -> None:
        if client is None:
            from joplin_mcp.fastmcp_server import get_joplin_client

            client = get_joplin_client()
        self._client = client
        self._notebook_path_cache: dict[str, str] = {}

    def load_section(self, section: SectionConfig) -> list[NoteRecord]:
        query = self._build_query(section)
        notes = _items(self._client.search_all(query=query, fields=_NOTE_FIELDS))

        records: list[NoteRecord] = []
        for note in notes:
            tag_titles = self._tag_titles_for(note.id)
            notebook_path = self._notebook_path_for(note.parent_id)
            metadata, _body = _split_frontmatter(note.body)
            records.append(
                NoteRecord.from_joppy_note(
                    note,
                    notebook_path=notebook_path,
                    tag_titles=tag_titles,
                    body=note.body,
                    frontmatter=metadata,
                )
            )
        return records

    def _build_query(self, section: SectionConfig) -> str:
        parts: list[str] = []
        if section.notebook:
            parts.append(f'notebook:"{section.notebook}"')
        for tag in section.tags_required:
            parts.append(f'tag:"{tag}"')
        for tag in section.tags_excluded:
            parts.append(f'-tag:"{tag}"')
        if section.extra_query:
            parts.append(section.extra_query)
        return " ".join(parts) if parts else "*"

    def _tag_titles_for(self, note_id: str) -> list[str]:
        tags = _items(self._client.get_tags(note_id=note_id))
        return [t.title for t in tags]

    def _notebook_path_for(self, parent_id: str) -> str:
        if parent_id in self._notebook_path_cache:
            return self._notebook_path_cache[parent_id]
        path = self._resolve_notebook_path(parent_id)
        self._notebook_path_cache[parent_id] = path
        return path

    def _resolve_notebook_path(self, parent_id: str) -> str:
        segments: list[str] = []
        current_id = parent_id
        seen = set()
        while current_id and current_id not in seen:
            seen.add(current_id)
            folder = self._client.get_notebook(id_=current_id)
            segments.append(folder.title)
            current_id = folder.parent_id
        return "/".join(reversed(segments))


_NOTE_FIELDS = "id,title,body,parent_id,created_time,updated_time"


def _items(result):
    """Unwrap joppy results that may be a DataList or already a flat list."""
    return result.items if hasattr(result, "items") and not isinstance(result, dict) else result


def _split_frontmatter(body: str | None) -> tuple[dict, str]:
    """Parse YAML frontmatter from the start of a note body.

    Uses python-frontmatter so edge cases (missing frontmatter, malformed YAML,
    encoding) are handled in one place.
    """
    if not body:
        return {}, ""
    post = frontmatter.loads(body)
    return dict(post.metadata), post.content
