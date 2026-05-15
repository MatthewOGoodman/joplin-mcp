"""Data types shared across the dashboard package."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class NoteRecord:
    """A note plus the metadata the dashboard needs to render it.

    Times are stored as timezone-aware datetimes for consistent formatting.
    """

    id: str
    title: str
    notebook_path: str
    tags: list[str]
    created_time: datetime
    updated_time: datetime
    body: str | None = None
    frontmatter: dict = field(default_factory=dict)

    @classmethod
    def from_joppy_note(
        cls,
        note,
        notebook_path: str,
        tag_titles: list[str],
        body: str | None = None,
        frontmatter: dict | None = None,
    ) -> "NoteRecord":
        """Build a NoteRecord from a joppy note object plus resolved metadata.

        The notebook path and tag titles must be resolved by the caller because
        joppy returns parent_id/tag IDs, not human-readable names.
        """
        return cls(
            id=note.id,
            title=note.title or "",
            notebook_path=notebook_path,
            tags=tag_titles,
            created_time=_to_utc(note.created_time),
            updated_time=_to_utc(note.updated_time),
            body=body,
            frontmatter=frontmatter or {},
        )


def _to_utc(value) -> datetime:
    """Normalize a joppy time value into a timezone-aware UTC datetime.

    joppy returns either a datetime or an int (milliseconds since epoch),
    depending on version. Handle both.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, int):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    raise TypeError(f"Unsupported time type: {type(value).__name__}")
