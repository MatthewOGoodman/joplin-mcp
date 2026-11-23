"""Fenced mdsync block + drift region line surgery.

The mdsync block lives inside the file's YAML frontmatter, delimited by exact
marker comment lines (`# mdsync-begin` / `# mdsync-end`). The drift region is
a marker-delimited HTML-comment span at the top of the body.

Core guarantee: user content is NEVER parsed or re-serialized. All operations
on user text are exact line splices; only our own machine-written block span
is YAML-parsed (its formatting is canonical, so re-serialization is lossless
by construction).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import yaml

BLOCK_BEGIN = "# mdsync-begin"
BLOCK_END = "# mdsync-end"
DRIFT_BEGIN = "<!-- mdsync-drift-begin -->"
DRIFT_END = "<!-- mdsync-drift-end -->"
FENCE = "---"


@dataclass
class SyncMeta:
    """Bookkeeping stored in the fenced mdsync block.

    Keys `id`, `title`, `parent_id`, `tags` mirror the Joplin Data API field
    names verbatim. `tags=None` means the line is absent (tags untouched on
    update); `tags=[]` explicitly means "remove all tags".
    """

    id: str | None = None
    title: str | None = None
    parent_id: str | None = None
    tags: list[str] | None = None
    notebook: str | None = None  # informational; API routes only by parent_id
    synced: str | None = None  # informational human-readable stamp
    prior_Joplin_hash: str | None = None  # note body hash at most recent sync point
    current_Joplin_hash: str | None = None  # remote hash at last GET pre-check
    markdown_bak: str | None = None  # local-edits backup filename (pull collision)

    def to_dict(self) -> dict:
        """Ordered dict of non-None fields (tags=[] is kept; tags=None dropped)."""
        out = {}
        for key in (
            "id",
            "title",
            "parent_id",
            "tags",
            "notebook",
            "synced",
            "prior_Joplin_hash",
            "current_Joplin_hash",
            "markdown_bak",
        ):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        return out


def body_hash(text: str) -> str:
    """sha256 over UTF-8 text, prefixed for self-description in the block."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _frontmatter_bounds(lines: list[str]) -> tuple[int, int] | None:
    """(open_idx, close_idx) of the leading `---` fences, or None."""
    if not lines or lines[0].strip() != FENCE:
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == FENCE:
            return (0, i)
    return None


def _block_span(lines: list[str]) -> tuple[int, int] | None:
    """(begin_idx, end_idx) inclusive of the mdsync block markers.

    Searched ONLY within the leading frontmatter region — a marker line inside
    the body (e.g. in a code sample) is never matched. Raises ValueError on a
    corrupt block (begin without end, or duplicate begin markers).
    """
    bounds = _frontmatter_bounds(lines)
    if bounds is None:
        return None
    open_idx, close_idx = bounds
    begin = end = None
    for i in range(open_idx + 1, close_idx):
        stripped = lines[i].strip()
        if stripped == BLOCK_BEGIN:
            if begin is not None:
                raise ValueError(
                    "corrupt mdsync block: duplicate '# mdsync-begin' markers"
                )
            begin = i
        elif stripped == BLOCK_END:
            if begin is None:
                raise ValueError(
                    "corrupt mdsync block: '# mdsync-end' without '# mdsync-begin'"
                )
            if end is not None:
                raise ValueError(
                    "corrupt mdsync block: duplicate '# mdsync-end' markers"
                )
            end = i
    if begin is not None and end is None:
        raise ValueError(
            "corrupt mdsync block: '# mdsync-begin' without '# mdsync-end'"
        )
    if begin is None:
        return None
    return (begin, end)


def read_block(text: str) -> SyncMeta | None:
    """Parse the mdsync block into a SyncMeta, or None if no block present."""
    lines = text.split("\n")
    span = _block_span(lines)
    if span is None:
        return None
    begin, end = span
    block_yaml = "\n".join(lines[begin + 1 : end])
    try:
        data = yaml.safe_load(block_yaml)
    except yaml.YAMLError as exc:
        raise ValueError(f"corrupt mdsync block: YAML parse failed: {exc}") from exc
    if not isinstance(data, dict) or "mdsync" not in data:
        raise ValueError("corrupt mdsync block: missing 'mdsync:' key")
    fields = data["mdsync"] or {}
    if not isinstance(fields, dict):
        raise ValueError("corrupt mdsync block: 'mdsync:' is not a mapping")
    meta = SyncMeta()
    for key in (
        "id",
        "title",
        "parent_id",
        "tags",
        "notebook",
        "synced",
        "prior_Joplin_hash",
        "current_Joplin_hash",
        "markdown_bak",
    ):
        if key in fields and fields[key] is not None:
            value = fields[key]
            # Defend against YAML implicit typing on hand-edited values
            # (e.g. an all-digit id parsing as int, a stamp as datetime).
            if key != "tags" and not isinstance(value, str):
                value = str(value)
            setattr(meta, key, value)
    if meta.tags is not None:
        meta.tags = [str(t) for t in meta.tags]
    return meta


def strip_block(text: str) -> str:
    """Remove the mdsync block span. Idempotent when absent.

    If the frontmatter contains nothing but the block, the `---` fences are
    removed too (we created them).
    """
    lines = text.split("\n")
    span = _block_span(lines)
    if span is None:
        return text
    begin, end = span
    del lines[begin : end + 1]
    # Drop the fences if the remaining frontmatter is empty/whitespace-only.
    bounds = _frontmatter_bounds(lines)
    if bounds is not None:
        open_idx, close_idx = bounds
        if all(not line.strip() for line in lines[open_idx + 1 : close_idx]):
            del lines[open_idx : close_idx + 1]
    return "\n".join(lines)


def _render_block_lines(meta: SyncMeta) -> list[str]:
    """Canonical machine-written block lines, including the marker fences."""
    dumped = yaml.safe_dump(
        {"mdsync": meta.to_dict()},
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,  # one key per line, always (line-oriented diffs)
        width=10_000,  # never wrap long titles/hashes across lines
    )
    return [BLOCK_BEGIN, *dumped.rstrip("\n").split("\n"), BLOCK_END]


def write_block(text: str, meta: SyncMeta) -> str:
    """Insert or replace the mdsync block.

    Replace in place if a block exists; else insert immediately after the
    opening `---`; else (no frontmatter) create a frontmatter region holding
    only the block.
    """
    lines = text.split("\n")
    block_lines = _render_block_lines(meta)
    span = _block_span(lines)
    if span is not None:
        begin, end = span
        lines[begin : end + 1] = block_lines
        return "\n".join(lines)
    bounds = _frontmatter_bounds(lines)
    if bounds is not None:
        open_idx, _ = bounds
        lines[open_idx + 1 : open_idx + 1] = block_lines
        return "\n".join(lines)
    return "\n".join([FENCE, *block_lines, FENCE, *lines])


def strip_drift_region(text: str) -> str:
    """Remove ALL drift regions (marker pairs + contents). Idempotent."""
    lines = text.split("\n")
    while True:
        begin = end = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == DRIFT_BEGIN and begin is None:
                begin = i
            elif stripped == DRIFT_END and begin is not None:
                end = i
                break
        if begin is None:
            return "\n".join(lines)
        if end is None:
            raise ValueError(
                "corrupt drift region: 'mdsync-drift-begin' without matching end"
            )
        # Also swallow ONE trailing blank separator line we wrote after the region.
        stop = end + 1
        if stop < len(lines) and not lines[stop].strip():
            stop += 1
        del lines[begin:stop]


def write_drift_region(text: str, content: str) -> str:
    """Insert a drift region at the top of the body (after frontmatter)."""
    lines = text.split("\n")
    region = [DRIFT_BEGIN, *content.split("\n"), DRIFT_END, ""]
    bounds = _frontmatter_bounds(lines)
    insert_at = bounds[1] + 1 if bounds is not None else 0
    lines[insert_at:insert_at] = region
    return "\n".join(lines)


def canonical_body(text: str) -> str:
    """File content minus the mdsync block and any drift regions.

    These are the exact bytes pushed as the note body, and the input to
    body_hash for both the drift check and pull's local-collision check.
    """
    return strip_drift_region(strip_block(text))
