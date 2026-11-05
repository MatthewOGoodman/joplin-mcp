"""Field registry and search helpers for bulk operation tools.

Provides:
- JOPLIN_NOTE_FIELDS: Registry mapping field names to type converters
- ALL_NOTE_FIELDS: Comma-separated string of all fields for API requests
- convert_todo_completed: Timestamp converter for todo_completed values
- _search_notes: Single entry point for searching + filtering notes
- _parse_update_params: Separates update values from filter conditions
- validate_notebook_access_for_note: Allowlist check on the notebook holding a note
"""

import datetime
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from joplin_mcp.fastmcp_server import (
    COMMON_NOTE_FIELDS,
    flexible_bool_converter,
    process_search_results,
    timestamp_converter,
)
from joplin_mcp.config import get_config
from joplin_mcp.notebook_utils import is_notebook_accessible, validate_notebook_access


# ---------------------------------------------------------------------------
# todo_completed converter
# ---------------------------------------------------------------------------


def convert_todo_completed(
    value: Union[bool, str, int, None],
) -> tuple[Optional[int], Optional[str]]:
    """Convert todo_completed input to Joplin API epoch-ms timestamp.

    Accepts:
        - True/False  (True -> current time in ms, False -> 0)
        - Epoch milliseconds (int)
        - ISO datetime string ('YYYY-MM-DD HH:MM' or 'YYYY-MM-DD')

    Returns:
        (api_value, warning_message) tuple.
    """
    if value is None:
        return (None, None)

    if isinstance(value, bool):
        return (int(time.time() * 1000) if value else 0, None)

    if isinstance(value, str):
        value_stripped = value.strip()
        value_lower = value_stripped.lower()
        if value_lower in ("true", "yes", "on"):
            return (int(time.time() * 1000), None)
        if value_lower in ("false", "no", "off"):
            return (0, None)
        try:
            dt = datetime.datetime.fromisoformat(value_stripped)
            return (int(dt.timestamp() * 1000), None)
        except ValueError:
            raise ValueError(
                f"Unrecognized todo_completed format: '{value}'. "
                "Accepts: True/False, epoch milliseconds, or ISO datetime "
                "'YYYY-MM-DD HH:MM' / 'YYYY-MM-DD'"
            )

    if isinstance(value, (int, float)):
        int_value = int(value)
        if int_value == 0:
            return (0, None)
        if int_value >= 1_000_000_000_000:
            return (int_value, None)
        return (
            int_value,
            f"WARNING: todo_completed={int_value} interpreted as "
            f"{int_value}ms since epoch (1970-01-01). Did you mean True?",
        )

    raise ValueError(
        f"Invalid todo_completed type: {type(value).__name__}. "
        "Accepts: True/False, epoch milliseconds, or ISO datetime "
        "'YYYY-MM-DD HH:MM' / 'YYYY-MM-DD'"
    )


# ---------------------------------------------------------------------------
# Field registry
# ---------------------------------------------------------------------------

JOPLIN_NOTE_FIELDS: Dict[str, Dict[str, Any]] = {
    "title": {
        "type_converter": lambda x: x,
        "description": "Note title",
    },
    "body": {
        "type_converter": lambda x: x,
        "description": "Note content",
    },
    "is_todo": {
        "type_converter": flexible_bool_converter,
        "description": "Todo status",
    },
    "todo_completed": {
        "type_converter": lambda x: convert_todo_completed(x)[0],
        "description": "Todo completion status",
    },
    "todo_due": {
        "type_converter": lambda x: timestamp_converter(x, "todo_due"),
        "description": "Todo due date (epoch ms or ISO 8601)",
    },
    "parent_id": {
        "type_converter": lambda x: x,
        "description": "Notebook ID",
    },
    "author": {
        "type_converter": lambda x: x,
        "description": "Note author",
    },
    "source_url": {
        "type_converter": lambda x: x,
        "description": "Source URL",
    },
    "latitude": {
        "type_converter": lambda x: x,
        "description": "GPS latitude coordinate",
    },
    "longitude": {
        "type_converter": lambda x: x,
        "description": "GPS longitude coordinate",
    },
    "altitude": {
        "type_converter": lambda x: x,
        "description": "GPS altitude coordinate",
    },
    "markup_language": {
        "type_converter": lambda x: x,
        "description": "Note markup format: 1=Markdown, 2=HTML",
    },
    "user_created_time": {
        "type_converter": lambda x: x,
        "description": "Custom creation timestamp in milliseconds",
    },
    "user_updated_time": {
        "type_converter": lambda x: x,
        "description": "Custom update timestamp in milliseconds",
    },
}

# All fields to request from the API — COMMON_NOTE_FIELDS + registry fields.
# SQLite fetches the full row regardless, so requesting extra columns is free.
ALL_NOTE_FIELDS = ",".join(sorted(set(
    COMMON_NOTE_FIELDS.split(",") + list(JOPLIN_NOTE_FIELDS.keys())
)))


# ---------------------------------------------------------------------------
# Search and filter
# ---------------------------------------------------------------------------


def _search_notes(
    client,
    query: str,
    **filters: Any,
) -> Tuple[List[Any], int]:
    """Search Joplin notes and apply field-value filters.

    Two-phase approach:
    1. Joplin API text search (handles full-text, notebook:, tag:, title:, etc.)
    2. Python post-filtering for field-value conditions the API can't express
       (e.g., author="Albert", is_todo=True). All filters are AND logic.

    The query string is passed to Joplin untouched — never parsed for field
    names. All fields from the registry are always fetched so filters can
    inspect any field without a second API call.

    Args:
        client: Joplin ClientApi instance.
        query: Search query for Joplin. Supports Joplin search operators
            (notebook:, tag:, title:, body:, type:, etc.) and "*" for all notes.
        **filters: Field conditions (AND logic). Keys must be valid field names
            from JOPLIN_NOTE_FIELDS. Example: is_todo=True, author="Albert".

    Returns:
        (matching_notes, skipped_count) tuple.
    """
    # Phase 1: Joplin API search
    if query.strip() == "*":
        results = client.get_all_notes(fields=ALL_NOTE_FIELDS)
        notes = process_search_results(results)
        notes.sort(
            key=lambda x: getattr(x, "updated_time", 0), reverse=True
        )
    else:
        results = client.search_all(query=query, fields=ALL_NOTE_FIELDS)
        notes = process_search_results(results)

    # Allowlist: notes in denied notebooks are invisible to both the preview and
    # the execute pass, so the two count the same set. Applied before the
    # field filters so a denied note is never counted as "skipped" either.
    cfg = get_config()
    if cfg.has_notebook_allowlist:
        notes = [
            n for n in notes
            if is_notebook_accessible(
                getattr(n, "parent_id", ""),
                allowlist_entries=cfg.notebook_allowlist,
            )
        ]

    # Phase 2: Python field-value filtering (AND logic)
    if not filters:
        return notes, 0

    matching = []
    skipped = 0
    for note in notes:
        match = True
        for field, expected in filters.items():
            if expected is not None and getattr(note, field, None) != expected:
                match = False
                break
        if match:
            matching.append(note)
        else:
            skipped += 1

    return matching, skipped


# ---------------------------------------------------------------------------
# Update parameter parsing
# ---------------------------------------------------------------------------


def _parse_update_params(**kwargs: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Separate update values from filter conditions.

    Convention: parameters ending in ``_filter`` are conditions (used by
    _search_notes for post-fetch filtering). All other parameters matching
    JOPLIN_NOTE_FIELDS keys are update values. Unknown keys are ignored.

    Args:
        **kwargs: All tool parameters (field values, filters, and anything else).

    Returns:
        (updates, filters) tuple.
        - updates: {field_name: new_value} for fields to modify.
        - filters: {field_name: required_value} for _search_notes filtering.
    """
    updates: Dict[str, Any] = {}
    filters: Dict[str, Any] = {}

    for key, value in kwargs.items():
        if value is None:
            continue
        if key.endswith("_filter"):
            field = key[:-7]  # strip "_filter"
            if field in JOPLIN_NOTE_FIELDS:
                filters[field] = value
        elif key in JOPLIN_NOTE_FIELDS:
            updates[key] = value

    return updates, filters


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def validate_notebook_access_for_note(client: Any, note_id: str) -> None:
    """Raise AllowlistDeniedError unless the notebook holding ``note_id`` is accessible.

    Differs from ``notebook_utils.validate_notebook_access`` in taking a NOTE id:
    it fetches the note's ``parent_id`` first. A no-op when no allowlist is
    configured, so it costs no request in the common case.
    """
    cfg = get_config()
    if not cfg.has_notebook_allowlist:
        return
    note = client.get_note(note_id, fields="id,parent_id")
    validate_notebook_access(
        getattr(note, "parent_id", ""), allowlist_entries=cfg.notebook_allowlist
    )
