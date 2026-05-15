"""Markdown rendering for the dashboard package.

Two layers:
- render_section(notes, config) -> str: one section's Markdown (header + table[s])
- assemble_dashboard(sections, header, footer) -> str: concatenated dashboard

Pure functions; no I/O. Testable in isolation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from joplin_mcp.dashboard.config import SectionConfig
from joplin_mcp.dashboard.types import NoteRecord


def render_section(notes: list[NoteRecord], section: SectionConfig) -> str:
    """Render one section. Groups by tag prefix if configured."""
    sorted_notes = _sort(notes, section.sort_by, section.sort_dir)

    parts: list[str] = [f"## {section.title}\n"]

    if not sorted_notes:
        parts.append("_No matching notes._\n")
        return "\n".join(parts)

    if section.group_by_tag_prefix:
        groups = _group_by_tag_prefix(sorted_notes, section.group_by_tag_prefix)
        for group_key in sorted(groups):
            parts.append(f"### {section.group_by_tag_prefix}{group_key}\n")
            parts.append(_render_table(groups[group_key], section.columns))
            parts.append("")
    else:
        parts.append(_render_table(sorted_notes, section.columns))

    return "\n".join(parts)


def assemble_dashboard(
    section_blocks: Iterable[str],
    header: str = "",
    footer: str = "",
    timestamp: datetime | None = None,
) -> str:
    """Concatenate section blocks with optional header/footer.

    `{timestamp}` in header/footer is replaced with the formatted refresh time.
    """
    ts = (timestamp or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M UTC")
    parts: list[str] = []
    if header:
        parts.append(header.replace("{timestamp}", ts).rstrip())
        parts.append("")
    parts.extend(block.rstrip() for block in section_blocks)
    if footer:
        parts.append("")
        parts.append(footer.replace("{timestamp}", ts).rstrip())
    return "\n\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------


_SORT_KEYS = {
    "title": lambda n: n.title.lower(),
    "updated": lambda n: n.updated_time,
    "created": lambda n: n.created_time,
    "notebook": lambda n: n.notebook_path.lower(),
}


def _sort(notes: list[NoteRecord], sort_by: str, sort_dir: str) -> list[NoteRecord]:
    key = _SORT_KEYS.get(sort_by)
    if key is None:
        # Frontmatter field fallback
        key = lambda n: str(n.frontmatter.get(sort_by, ""))
    return sorted(notes, key=key, reverse=(sort_dir == "desc"))


def _group_by_tag_prefix(notes: list[NoteRecord], prefix: str) -> dict[str, list[NoteRecord]]:
    """Group notes by the suffix of the first tag matching `prefix`.

    Notes with no matching tag go into a `(none)` bucket.
    """
    groups: dict[str, list[NoteRecord]] = {}
    for note in notes:
        suffix = "(none)"
        for tag in note.tags:
            if tag.startswith(prefix):
                suffix = tag[len(prefix):].strip()
                break
        groups.setdefault(suffix, []).append(note)
    return groups


def _render_table(notes: list[NoteRecord], columns: list[str]) -> str:
    if not columns:
        columns = ["title", "updated"]

    header = "| " + " | ".join(_column_header(c) for c in columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    rows = ["| " + " | ".join(_column_cell(n, c) for c in columns) + " |" for n in notes]
    return "\n".join([header, sep, *rows])


def _column_header(column: str) -> str:
    return column.replace("_", " ").title()


def _column_cell(note: NoteRecord, column: str) -> str:
    if column == "title":
        return _md_escape(note.title) or "_(untitled)_"
    if column == "tags":
        return ", ".join(_md_escape(t) for t in note.tags)
    if column == "notebook":
        return _md_escape(note.notebook_path)
    if column == "updated":
        return note.updated_time.strftime("%Y-%m-%d")
    if column == "created":
        return note.created_time.strftime("%Y-%m-%d")
    if column == "id":
        return note.id
    # Frontmatter fallback
    value = note.frontmatter.get(column, "")
    if isinstance(value, list):
        return ", ".join(_md_escape(str(v)) for v in value)
    return _md_escape(str(value))


def _md_escape(text: str) -> str:
    """Minimal Markdown table escaping: pipes and newlines."""
    return text.replace("|", "\\|").replace("\n", " ")
