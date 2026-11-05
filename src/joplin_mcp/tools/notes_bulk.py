"""Bulk note operation tools for Joplin MCP."""

from typing import Annotated, List, Optional, Tuple, Union

from pydantic import Field

from joplin_mcp.fastmcp_server import (
    ItemType,
    JoplinIdType,
    OptionalBoolType,
    _sanitise_error,
    create_tool,
    flexible_bool_converter,
    format_update_success,
    get_joplin_client,
    validate_joplin_id,
)
from joplin_mcp import note_view
from joplin_mcp.config import get_config
from joplin_mcp.note_view import format_search_results_with_pagination
from joplin_mcp.notebook_utils import get_notebook_id_by_name, validate_notebook_access
from joplin_mcp.revision_utils import save_note_revision
from joplin_mcp.tools.backup_database import backup_joplin_database
from joplin_mcp.tools.field_helpers import (
    JOPLIN_NOTE_FIELDS,
    _search_notes,
    _parse_update_params,
    validate_notebook_access_for_note,
)
from joplin_mcp.tools.notes import update_note


# === BULK NOTE TOOLS ===


def _resolve_target_notebook(
    notebook_name: Optional[str], target_notebook_id: Optional[str]
) -> str:
    """Resolve exactly one of a notebook name/path or a notebook ID to an ID."""
    if notebook_name is None and target_notebook_id is None:
        raise ValueError(
            "Must specify either notebook_name (name or path) or target_notebook_id (ID)"
        )
    if notebook_name is not None and target_notebook_id is not None:
        raise ValueError(
            "Cannot specify both notebook_name and target_notebook_id. Use one or the other."
        )
    if notebook_name is not None:
        return get_notebook_id_by_name(notebook_name)
    return validate_joplin_id(target_notebook_id)


def _move_notes(
    client, note_ids: List[str], target_notebook_id: str
) -> List[Tuple[str, bool, str]]:
    """Move each note into ``target_notebook_id``; one (note_id, ok, error) row per note.

    Enforces the notebook allowlist as update_note does: the destination is
    checked once up front (a denial raises before anything moves), and each
    note's source notebook per note (a denial is a failed row; the rest still
    run). Writes go through note_view so the note cache stays coherent.
    """
    cfg = get_config()
    if cfg.has_notebook_allowlist:
        validate_notebook_access(
            target_notebook_id, allowlist_entries=cfg.notebook_allowlist
        )

    results: List[Tuple[str, bool, str]] = []
    for nid in note_ids:
        try:
            validate_notebook_access_for_note(client, nid)
            note_view.modify_note(client, nid, parent_id=target_notebook_id)
            results.append((nid, True, ""))
        except Exception as e:
            results.append((nid, False, _sanitise_error(str(e))))
    return results


def _format_move_report(
    results: List[Tuple[str, bool, str]], target_notebook_id: str
) -> str:
    """Aggregated BULK_MOVE_NOTES report, field-for-field parallel to tag_note's."""
    total = len(results)
    succeeded = sum(1 for _, ok, _ in results if ok)
    failed = total - succeeded
    lines = [
        "OPERATION: BULK_MOVE_NOTES",
        f"STATUS: {'SUCCESS' if failed == 0 else 'PARTIAL'}",
        f"TOTAL_OPS: {total}",
        f"SUCCEEDED: {succeeded}",
        f"FAILED: {failed}",
        f"TARGET_NOTEBOOK_ID: {target_notebook_id}",
        f"MESSAGE: {succeeded} of {total} operations succeeded",
    ]
    if failed:
        lines.append("FAILURES:")
        for nid, ok, err in results:
            if not ok:
                clean_err = " ".join(err.split()).replace('"', "'")
                lines.append(f'  - note_id={nid} error="{clean_err}"')
    return "\n".join(lines)


@create_tool("move_note", "Move note")
async def move_note(
    note_id: Annotated[JoplinIdType, Field(description="Note ID to move")],
    target_notebook: Annotated[
        Optional[str],
        Field(description="Target notebook name or path (e.g. 'Archive' or 'Projects/Work')"),
    ] = None,
    target_notebook_id: Annotated[
        Optional[str],
        Field(description="Target notebook ID (alternative to notebook name)"),
    ] = None,
) -> str:
    """Move a single note to a different notebook.

    Alias of update_note(note_id, notebook_name=...) when given a notebook name
    or path. Specify either target_notebook (name/path) OR target_notebook_id
    (ID) - one is required. update_note takes no notebook ID, so the ID form
    moves through the same path as bulk_move_notes.

    Returns:
        str: Success message confirming the note was moved.

    Examples:
        - move_note("note123", target_notebook="Archive") - Move note to Archive notebook
        - move_note("note123", target_notebook="Projects/Work") - Move by notebook path
        - move_note("note123", target_notebook_id="abc123def456") - Move using notebook ID
    """
    note_id = validate_joplin_id(note_id)
    if target_notebook is not None and target_notebook_id is None:
        return await update_note.fn(note_id=note_id, notebook_name=target_notebook)

    notebook_id = _resolve_target_notebook(target_notebook, target_notebook_id)
    (_, ok, err), = _move_notes(get_joplin_client(), [note_id], notebook_id)
    if not ok:
        raise ValueError(err)
    return format_update_success(ItemType.note, note_id)


@create_tool("bulk_move_notes", "Bulk move notes")
async def bulk_move_notes(
    note_id: Annotated[
        Union[JoplinIdType, List[JoplinIdType]],
        Field(description="Note ID, or list of note IDs"),
    ],
    notebook_name: Annotated[
        Optional[str],
        Field(description="Target notebook by name or path (e.g. 'Work' or 'Projects/Work/Tasks')"),
    ] = None,
    target_notebook_id: Annotated[
        Optional[str],
        Field(description="Target notebook ID (alternative to notebook_name)"),
    ] = None,
    backup: Annotated[
        Optional[str],
        Field(description="Database backup before operation: 'daily' (default, once per day), 'force' (always), 'suppress' (skip). WARNING: Never set to 'suppress' unless the user explicitly requests it."),
    ] = "daily",
) -> str:
    """Move one or more notes to a target notebook in one call.

    note_id accepts a single ID or a list, as tag_note does. Specify either
    notebook_name (name or path, resolved like update_note's) OR
    target_notebook_id - one is required. Backs up the database first unless
    told not to.

    Output: aggregated BULK_MOVE_NOTES report with TOTAL_OPS / SUCCEEDED /
    FAILED. Per-note failures (e.g. a missing note, or an allowlist denial of
    the note's current notebook) are captured in the report; other moves still
    run. A denied destination stops the call before anything moves.

    Examples:
        - bulk_move_notes(["note1", "note2", "note3"], notebook_name="Archive")
        - bulk_move_notes("note1", notebook_name="Projects/Work/Tasks")
        - bulk_move_notes(["note1", "note2"], target_notebook_id="abc123def456")
    """
    note_ids = [note_id] if isinstance(note_id, str) else list(note_id)
    if not note_ids:
        raise ValueError("note_id list must not be empty")
    note_ids = [validate_joplin_id(nid) for nid in note_ids]

    notebook_id = _resolve_target_notebook(notebook_name, target_notebook_id)

    client = get_joplin_client()

    if backup != "suppress":
        backup_joplin_database(force=(backup == "force"))

    results = _move_notes(client, note_ids, notebook_id)
    return _format_move_report(results, notebook_id)


@create_tool(
    "search_and_bulk_update_preview", "Search and bulk update preview"
)
async def search_and_bulk_update_preview(
    query: Annotated[
        str, Field(description="Search text or '*' for all notes")
    ],
    preview_limit: Annotated[
        int,
        Field(description="Number of notes to show in preview (default: 5)"),
    ] = 5,
    inspect_count: Annotated[
        int,
        Field(
            description="Number of notes to show full content for (default: 2)"
        ),
    ] = 2,
    # Update parameters
    title: Annotated[
        Optional[str], Field(description="New title to simulate (optional)")
    ] = None,
    body: Annotated[
        Optional[str],
        Field(description="New content to simulate (optional)"),
    ] = None,
    is_todo: Annotated[
        OptionalBoolType,
        Field(description="Convert to/from todo to simulate (optional)"),
    ] = None,
    todo_completed: Annotated[
        Optional[Union[bool, str, int]],
        Field(
            description="Mark todo completed to simulate. Accepts: True/False (uses current time), epoch milliseconds, or ISO datetime 'YYYY-MM-DD HH:MM' / 'YYYY-MM-DD' (optional)"
        ),
    ] = None,
    parent_id: Annotated[
        Optional[str],
        Field(
            description="Move notes to different notebook to simulate (notebook ID, optional)"
        ),
    ] = None,
    parent_notebook: Annotated[
        Optional[str],
        Field(
            description="Move notes to different notebook to simulate (notebook name, optional)"
        ),
    ] = None,
    author: Annotated[
        Optional[str],
        Field(description="Note author to simulate (optional)"),
    ] = None,
    source_url: Annotated[
        Optional[str],
        Field(description="Source URL to simulate (optional)"),
    ] = None,
    latitude: Annotated[
        Optional[float],
        Field(description="GPS latitude coordinate to simulate (optional)"),
    ] = None,
    longitude: Annotated[
        Optional[float],
        Field(description="GPS longitude coordinate to simulate (optional)"),
    ] = None,
    altitude: Annotated[
        Optional[float],
        Field(description="GPS altitude coordinate to simulate (optional)"),
    ] = None,
    markup_language: Annotated[
        Optional[int],
        Field(
            description="Note markup format: 1=Markdown, 2=HTML to simulate (optional)"
        ),
    ] = None,
    user_created_time: Annotated[
        Optional[int],
        Field(
            description="Custom creation timestamp in milliseconds to simulate (optional)"
        ),
    ] = None,
    user_updated_time: Annotated[
        Optional[int],
        Field(
            description="Custom update timestamp in milliseconds to simulate (optional)"
        ),
    ] = None,
    # Filter parameters for conditional updates
    is_todo_filter: Annotated[
        OptionalBoolType,
        Field(
            description="Only update if current is_todo matches this (optional)"
        ),
    ] = None,
    todo_completed_filter: Annotated[
        OptionalBoolType,
        Field(
            description="Only update if current todo_completed matches this (optional)"
        ),
    ] = None,
    title_filter: Annotated[
        Optional[str],
        Field(
            description="Only update if current title matches this (optional)"
        ),
    ] = None,
    body_filter: Annotated[
        Optional[str],
        Field(
            description="Only update if current body matches this (optional)"
        ),
    ] = None,
    parent_id_filter: Annotated[
        Optional[str],
        Field(
            description="Only update if current parent_id matches this (optional)"
        ),
    ] = None,
    author_filter: Annotated[
        Optional[str],
        Field(
            description="Only update if current author matches this (optional)"
        ),
    ] = None,
    source_url_filter: Annotated[
        Optional[str],
        Field(
            description="Only update if current source_url matches this (optional)"
        ),
    ] = None,
    latitude_filter: Annotated[
        Optional[float],
        Field(
            description="Only update if current latitude matches this (optional)"
        ),
    ] = None,
    longitude_filter: Annotated[
        Optional[float],
        Field(
            description="Only update if current longitude matches this (optional)"
        ),
    ] = None,
    altitude_filter: Annotated[
        Optional[float],
        Field(
            description="Only update if current altitude matches this (optional)"
        ),
    ] = None,
    markup_language_filter: Annotated[
        Optional[int],
        Field(
            description="Only update if current markup_language matches this (optional)"
        ),
    ] = None,
    user_created_time_filter: Annotated[
        Optional[int],
        Field(
            description="Only update if current user_created_time matches this (optional)"
        ),
    ] = None,
    user_updated_time_filter: Annotated[
        Optional[int],
        Field(
            description="Only update if current user_updated_time matches this (optional)"
        ),
    ] = None,
) -> str:
    """Preview search results for bulk update operations.

    Shows three levels of information:
    1. Total count of matching notes with filter statistics.
    2. Preview of first N notes with metadata (titles, IDs, dates).
    3. Full content inspection of first few notes for verification.

    This function helps verify what notes would be affected before executing
    bulk updates.  Always call this before search_and_bulk_update_execute.

    Returns:
        str: Complete preview with count, metadata, and content samples.

    Examples:
        - search_and_bulk_update_preview("project") - Preview notes containing "project"
        - search_and_bulk_update_preview("*", is_todo=True, preview_limit=10)
    """
    # Handle parent_notebook -> parent_id conversion
    if parent_notebook is not None and parent_id is not None:
        raise ValueError(
            "Cannot specify both parent_id and parent_notebook. Use one or the other."
        )
    if parent_notebook is not None:
        parent_id = get_notebook_id_by_name(parent_notebook)

    # Runtime validation (must match search_and_bulk_update_execute)
    is_todo = flexible_bool_converter(is_todo)
    is_todo_filter = flexible_bool_converter(is_todo_filter)
    todo_completed_filter = flexible_bool_converter(todo_completed_filter)

    updates, filters = _parse_update_params(
        title=title, body=body, is_todo=is_todo,
        todo_completed=todo_completed, parent_id=parent_id,
        author=author, source_url=source_url,
        latitude=latitude, longitude=longitude, altitude=altitude,
        markup_language=markup_language,
        user_created_time=user_created_time, user_updated_time=user_updated_time,
        is_todo_filter=is_todo_filter, todo_completed_filter=todo_completed_filter,
        title_filter=title_filter, body_filter=body_filter,
        parent_id_filter=parent_id_filter, author_filter=author_filter,
        source_url_filter=source_url_filter,
        latitude_filter=latitude_filter, longitude_filter=longitude_filter,
        altitude_filter=altitude_filter,
        markup_language_filter=markup_language_filter,
        user_created_time_filter=user_created_time_filter,
        user_updated_time_filter=user_updated_time_filter,
    )

    # Allowlist: a move destination must itself be accessible. Notes in denied
    # notebooks are already excluded from the match set by _search_notes.
    if "parent_id" in updates and get_config().has_notebook_allowlist:
        validate_notebook_access(
            updates["parent_id"], allowlist_entries=get_config().notebook_allowlist
        )

    client = get_joplin_client()
    try:
        all_notes, skipped_by_filter = _search_notes(client, query, **filters)
        total_found = len(all_notes) + skipped_by_filter
        paginated_notes = all_notes[:preview_limit]
        if not paginated_notes:
            return f"No notes found matching query: {query}"

        search_description = "all notes" if query.strip() == "*" else f"text search: {query}"
        preview_result = format_search_results_with_pagination(
            search_description, paginated_notes, len(all_notes),
            preview_limit, 0, "search_results", original_query=query,
            config=get_config(),
        )

        filter_info = ""
        if filters:
            filter_info = (
                f"\n\n=== FILTER RESULTS ===\n"
                f"Notes matching search: {total_found}\n"
                f"Notes passing filters: {len(all_notes)}\n"
                f"Notes skipped by filters: {skipped_by_filter}\n"
                f"Active filters: {', '.join(f'{k}={v}' for k, v in filters.items())}\n"
            )

        note_ids = [getattr(n, "id") for n in paginated_notes[:inspect_count]]
        content_parts = []
        for nid in note_ids:
            try:
                note = client.get_note(nid, fields="id,title,body")
                body_text = getattr(note, "body", "")
                preview = body_text[:500] + "..." if len(body_text) > 500 else body_text
                content_parts.append(f"--- NOTE {nid} ({note.title}) ---\n{preview}\n")
            except Exception as e:
                content_parts.append(f"--- NOTE {nid} ERROR ---\n{e}\n")
    except Exception as e:
        return f"Error during preview: {e}"

    result_parts = [preview_result]
    if filter_info:
        result_parts.append(filter_info)
    if content_parts:
        result_parts.append(f"\n=== FULL CONTENT INSPECTION ===\nShowing full content for first {len(note_ids)} notes for verification:\n")
        result_parts.extend(content_parts)
    return "\n".join(result_parts)


@create_tool(
    "search_and_bulk_update_execute", "Search and bulk update execute"
)
async def search_and_bulk_update_execute(
    query: Annotated[
        str,
        Field(
            description="Search text or '*' for all notes (must match preview)"
        ),
    ],
    expected_count: Annotated[
        int, Field(description="Expected number of notes from preview")
    ],
    first_title: Annotated[
        str, Field(description="Title of first note from preview")
    ],
    # Update parameters
    title: Annotated[
        Optional[str], Field(description="New title (optional)")
    ] = None,
    body: Annotated[
        Optional[str], Field(description="New content (optional)")
    ] = None,
    is_todo: Annotated[
        OptionalBoolType,
        Field(description="Convert to/from todo (optional)"),
    ] = None,
    todo_completed: Annotated[
        Optional[Union[bool, str, int]],
        Field(
            description="Mark todo completed. Accepts: True/False (uses current time), epoch milliseconds, or ISO datetime 'YYYY-MM-DD HH:MM' / 'YYYY-MM-DD' (optional)"
        ),
    ] = None,
    parent_id: Annotated[
        Optional[str],
        Field(
            description="Move notes to different notebook (notebook ID, optional)"
        ),
    ] = None,
    parent_notebook: Annotated[
        Optional[str],
        Field(
            description="Move notes to different notebook (notebook name, optional)"
        ),
    ] = None,
    author: Annotated[
        Optional[str], Field(description="Note author (optional)")
    ] = None,
    source_url: Annotated[
        Optional[str],
        Field(description="Source URL for web clips (optional)"),
    ] = None,
    latitude: Annotated[
        Optional[float],
        Field(description="GPS latitude coordinate (optional)"),
    ] = None,
    longitude: Annotated[
        Optional[float],
        Field(description="GPS longitude coordinate (optional)"),
    ] = None,
    altitude: Annotated[
        Optional[float],
        Field(description="GPS altitude coordinate (optional)"),
    ] = None,
    markup_language: Annotated[
        Optional[int],
        Field(
            description="Note markup format: 1=Markdown, 2=HTML (optional)"
        ),
    ] = None,
    user_created_time: Annotated[
        Optional[int],
        Field(
            description="Custom creation timestamp in milliseconds (optional)"
        ),
    ] = None,
    user_updated_time: Annotated[
        Optional[int],
        Field(
            description="Custom update timestamp in milliseconds (optional)"
        ),
    ] = None,
    # Filter parameters
    is_todo_filter: Annotated[
        OptionalBoolType,
        Field(
            description="Only update if current is_todo matches this (optional)"
        ),
    ] = None,
    todo_completed_filter: Annotated[
        OptionalBoolType,
        Field(
            description="Only update if current todo_completed matches this (optional)"
        ),
    ] = None,
    title_filter: Annotated[
        Optional[str],
        Field(
            description="Only update if current title matches this (optional)"
        ),
    ] = None,
    body_filter: Annotated[
        Optional[str],
        Field(
            description="Only update if current body matches this (optional)"
        ),
    ] = None,
    parent_id_filter: Annotated[
        Optional[str],
        Field(
            description="Only update if current parent_id matches this (optional)"
        ),
    ] = None,
    author_filter: Annotated[
        Optional[str],
        Field(
            description="Only update if current author matches this (optional)"
        ),
    ] = None,
    source_url_filter: Annotated[
        Optional[str],
        Field(
            description="Only update if current source_url matches this (optional)"
        ),
    ] = None,
    latitude_filter: Annotated[
        Optional[float],
        Field(
            description="Only update if current latitude matches this (optional)"
        ),
    ] = None,
    longitude_filter: Annotated[
        Optional[float],
        Field(
            description="Only update if current longitude matches this (optional)"
        ),
    ] = None,
    altitude_filter: Annotated[
        Optional[float],
        Field(
            description="Only update if current altitude matches this (optional)"
        ),
    ] = None,
    markup_language_filter: Annotated[
        Optional[int],
        Field(
            description="Only update if current markup_language matches this (optional)"
        ),
    ] = None,
    user_created_time_filter: Annotated[
        Optional[int],
        Field(
            description="Only update if current user_created_time matches this (optional)"
        ),
    ] = None,
    user_updated_time_filter: Annotated[
        Optional[int],
        Field(
            description="Only update if current user_updated_time matches this (optional)"
        ),
    ] = None,
    backup: Annotated[
        Optional[str],
        Field(description="Database backup before operation: 'daily' (default, once per day), 'force' (always), 'suppress' (skip). WARNING: Never set to 'suppress' unless the user explicitly requests it."),
    ] = "daily",
) -> str:
    """Execute bulk update operation on notes matching search criteria.

    Performs bulk updates on all notes matching the search query after safety
    verification.  The query and expected results must match what was shown in
    the preview (search_and_bulk_update_preview).

    Returns:
        str: Detailed results including success/failure/skipped counts.

    Examples:
        - search_and_bulk_update_execute("project", 15, "Project Meeting", parent_id="archive_id")
        - search_and_bulk_update_execute("*", 200, "Daily Notes", is_todo=True)
    """
    # Runtime validation
    is_todo = flexible_bool_converter(is_todo)
    is_todo_filter = flexible_bool_converter(is_todo_filter)
    todo_completed_filter = flexible_bool_converter(todo_completed_filter)

    if parent_notebook is not None and parent_id is not None:
        raise ValueError(
            "Cannot specify both parent_id and parent_notebook. Use one or the other."
        )
    if parent_notebook is not None:
        parent_id = get_notebook_id_by_name(parent_notebook)

    updates, filters = _parse_update_params(
        title=title, body=body, is_todo=is_todo,
        todo_completed=todo_completed, parent_id=parent_id,
        author=author, source_url=source_url,
        latitude=latitude, longitude=longitude, altitude=altitude,
        markup_language=markup_language,
        user_created_time=user_created_time, user_updated_time=user_updated_time,
        is_todo_filter=is_todo_filter, todo_completed_filter=todo_completed_filter,
        title_filter=title_filter, body_filter=body_filter,
        parent_id_filter=parent_id_filter, author_filter=author_filter,
        source_url_filter=source_url_filter,
        latitude_filter=latitude_filter, longitude_filter=longitude_filter,
        altitude_filter=altitude_filter,
        markup_language_filter=markup_language_filter,
        user_created_time_filter=user_created_time_filter,
        user_updated_time_filter=user_updated_time_filter,
    )

    if not updates:
        raise ValueError("At least one update field must be provided")

    # Allowlist: a move destination must itself be accessible. Notes in denied
    # notebooks are already excluded from the match set by _search_notes.
    if "parent_id" in updates and get_config().has_notebook_allowlist:
        validate_notebook_access(
            updates["parent_id"], allowlist_entries=get_config().notebook_allowlist
        )

    if backup != "suppress":
        backup_joplin_database(force=(backup == "force"))

    client = get_joplin_client()
    matching_notes, skipped_by_filter = _search_notes(client, query, **filters)

    if len(matching_notes) != expected_count:
        raise ValueError(
            f"Results changed: expected {expected_count}, found {len(matching_notes)}"
        )
    if matching_notes and getattr(matching_notes[0], "title", "") != first_title:
        actual = getattr(matching_notes[0], "title", "Unknown")
        raise ValueError(f"First note changed: expected '{first_title}', found '{actual}'")

    # Build ONE update payload, apply to ALL matching notes
    update_payload = {}
    for field, value in updates.items():
        converter = JOPLIN_NOTE_FIELDS[field]["type_converter"]
        update_payload[field] = converter(value)

    success_count = 0
    failed_updates = []

    for note in matching_notes:
        note_id = getattr(note, "id")
        try:
            if "body" in update_payload or "title" in update_payload:
                save_note_revision(client, note_id)
            note_view.modify_note(client, note_id, **update_payload)
            success_count += 1
        except Exception as e:
            note_title = getattr(note, "title", "Unknown")
            failed_updates.append(f"Note {note_id} ({note_title}): {e}")

    update_summary = ", ".join(f"{k}: {v}" for k, v in updates.items())
    filter_summary = ", ".join(f"{k}={v}" for k, v in filters.items()) if filters else "none"

    result_lines = [
        "operation: search_and_bulk_update_execute",
        f"status: {'partial_success' if failed_updates else 'success'}",
        f"search_query: {query}",
        f"total_matching: {len(matching_notes)}",
        f"skipped_by_filter: {skipped_by_filter}",
        f"updated_successfully: {success_count}",
        f"updates_applied: {update_summary}",
        f"filters_used: {filter_summary}",
    ]
    if failed_updates:
        result_lines.append(f"failed_updates: {len(failed_updates)}")
        result_lines.extend([f"  - {error}" for error in failed_updates])
    return "\n".join(result_lines)
