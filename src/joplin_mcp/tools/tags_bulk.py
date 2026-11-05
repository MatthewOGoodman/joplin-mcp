"""Bulk tag operation tools for Joplin MCP."""

import logging
from typing import Annotated, List, Tuple, Union

from pydantic import Field

from joplin_mcp.fastmcp_server import (
    JoplinIdType,
    _sanitise_error,
    create_tool,
    get_joplin_client,
    process_search_results,
    validate_joplin_id,
)
from joplin_mcp.notebook_utils import AllowlistDeniedError
from joplin_mcp.tools.field_helpers import validate_notebook_access_for_note
from joplin_mcp.tools.tags import _format_tag_op_report, tag_note

logger = logging.getLogger(__name__)


# === BULK TAG TOOLS ===


@create_tool("strip_note_tags", "Remove all tags from note")
async def strip_note_tags(
    note_id: Annotated[
        Union[JoplinIdType, List[JoplinIdType]],
        Field(description="Note ID, or list of note IDs, to remove all tags from"),
    ],
) -> str:
    """Remove every tag from one or more notes.

    note_id accepts a single ID or a list, as untag_note does. Unlike
    untag_note, no tag names are given: each note loses whatever tags it has.

    Output: aggregated STRIP_NOTE_TAGS report in untag_note's format, one row
    per (note, tag) pair removed, with TOTAL_OPS / SUCCEEDED / FAILED. A note
    with no tags contributes no rows. Per-note failures (a missing note, or an
    allowlist denial) are captured in the report; other notes still run.

    Examples:
        - strip_note_tags("a1b2c3d4e5f6...") - Remove all tags from one note
        - strip_note_tags(["a1b2...", "c3d4..."]) - Clear tags from two notes
    """
    note_ids = [note_id] if isinstance(note_id, str) else list(note_id)
    if not note_ids:
        raise ValueError("note_id list must not be empty")
    note_ids = [validate_joplin_id(nid) for nid in note_ids]

    client = get_joplin_client()
    results: List[Tuple[str, str, bool, str]] = []
    notes_cleared = 0

    for nid in note_ids:
        try:
            validate_notebook_access_for_note(client, nid)
            tags = process_search_results(
                client.get_tags(note_id=nid, fields="id,title")
            )
        except AllowlistDeniedError as e:
            results.append((nid, "(all tags)", False, str(e)))
            continue
        except Exception as e:
            results.append((nid, "(all tags)", False, _sanitise_error(str(e))))
            continue

        notes_cleared += 1
        for tag in tags:
            tag_name = getattr(tag, "title", "Unknown Tag")
            try:
                client.delete(f"/tags/{getattr(tag, 'id', '')}/notes/{nid}")
                results.append((nid, tag_name, True, ""))
            except Exception as e:
                results.append((nid, tag_name, False, _sanitise_error(str(e))))

    report = _format_tag_op_report("STRIP_NOTE_TAGS", results)
    return f"{report}\nNOTES_PROCESSED: {notes_cleared} of {len(note_ids)}"


@create_tool("bulk_tag_notes", "Bulk tag notes")
async def bulk_tag_notes(
    note_ids: Annotated[
        List[JoplinIdType],
        Field(description="List of note IDs to add tags to"),
    ],
    tag_names: Annotated[
        List[str],
        Field(description="List of tag names to add to each note"),
    ],
) -> str:
    """Apply multiple tags to multiple notes in a single bulk operation.

    Alias of tag_note(note_id=note_ids, tag_name=tag_names): every tag is
    applied to every note, with tag_note's report, allowlist checks and
    missing-tag handling (tags must already exist; use create_tag first).

    Examples:
        - bulk_tag_notes(["note1", "note2"], ["Important", "Work"])
        - bulk_tag_notes(["abc123", "def456", "ghi789"], ["Project-Alpha"])
    """
    return await tag_note.fn(note_id=list(note_ids), tag_name=list(tag_names))
