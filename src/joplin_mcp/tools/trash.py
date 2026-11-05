"""Trash management tools for Joplin MCP — list and restore soft-deleted items."""

import datetime as dt_module
import logging
from typing import Annotated, Optional

from pydantic import Field

from joplin_mcp import note_view
from joplin_mcp.content_utils import format_timestamp
from joplin_mcp.fastmcp_server import (
    ItemType,
    JoplinIdType,
    LimitType,
    OffsetType,
    create_tool,
    format_restore_success,
    get_joplin_client,
    validate_joplin_id,
)
from joplin_mcp.notebook_utils import notebook_resolver

logger = logging.getLogger(__name__)


@create_tool("list_trash", "List trashed items")
async def list_trash(
    item_type: Annotated[
        Optional[str],
        Field(
            description=(
                "Filter by type: 'note', 'notebook', or None for both"
                " (default: None)"
            ),
        ),
    ] = None,
    limit: Annotated[
        LimitType, Field(description="Max results (1-100, default: 20)")
    ] = 20,
    offset: Annotated[
        OffsetType,
        Field(description="Skip count for pagination (default: 0)"),
    ] = 0,
) -> str:
    """List items in Joplin's trash.

    Shows notes and/or notebooks that have been soft-deleted (moved to trash).
    These items can be restored with restore_from_trash.

    Returns:
        str: List of trashed items with title, ID, deletion date, and original
             notebook.
    """
    client = get_joplin_client()
    epoch_zero = dt_module.datetime(1970, 1, 1, 0, 0)
    results = []

    if item_type is None or item_type == "note":
        notes = client.get_all_notes(
            fields="id,title,deleted_time,parent_id,is_todo",
            include_deleted=1,
        )
        trashed_notes = [
            n
            for n in notes
            if getattr(n, "deleted_time", None)
            and n.deleted_time != epoch_zero
        ]
        for n in trashed_notes:
            results.append(
                {
                    "type": "note",
                    "id": n.id,
                    "title": getattr(n, "title", "Untitled"),
                    "deleted_time": n.deleted_time,
                    "parent_id": getattr(n, "parent_id", ""),
                    "is_todo": getattr(n, "is_todo", False),
                }
            )

    if item_type is None or item_type == "notebook":
        notebooks = client.get_all_notebooks(
            fields="id,title,deleted_time,parent_id",
            include_deleted=1,
        )
        trashed_notebooks = [
            n
            for n in notebooks
            if getattr(n, "deleted_time", None)
            and n.deleted_time != epoch_zero
        ]
        for n in trashed_notebooks:
            results.append(
                {
                    "type": "notebook",
                    "id": n.id,
                    "title": getattr(n, "title", "Untitled"),
                    "deleted_time": n.deleted_time,
                    "parent_id": getattr(n, "parent_id", ""),
                }
            )

    # Sort by deletion time, most recent first
    results.sort(key=lambda x: x["deleted_time"], reverse=True)

    total_count = len(results)

    # Apply pagination
    paginated = results[offset : offset + limit]

    if not paginated:
        return "TRASH_ITEMS: 0\nSTATUS: Trash is empty"

    # Build notebook name lookup for parent_id display
    try:
        all_notebooks = client.get_all_notebooks(
            fields="id,title", include_deleted=1
        )
        nb_map = {
            getattr(nb, "id", ""): getattr(nb, "title", "Unknown")
            for nb in all_notebooks
        }
    except Exception:
        nb_map = {}

    lines = [
        f"TRASH_ITEMS: {total_count}",
        f"SHOWING: {offset + 1}-{offset + len(paginated)} of {total_count}",
        "",
    ]

    for i, item in enumerate(paginated, offset + 1):
        deleted_str = format_timestamp(item["deleted_time"])
        parent_name = nb_map.get(
            item["parent_id"], item["parent_id"][:12] + "..."
        )
        lines.append(f"ITEM_{i}:")
        lines.append(f"  type: {item['type']}")
        lines.append(f"  id: {item['id']}")
        lines.append(f"  title: {item['title']}")
        lines.append(f"  deleted: {deleted_str}")
        lines.append(f"  original_notebook: {parent_name}")
        if item["type"] == "note" and item.get("is_todo"):
            lines.append("  is_todo: true")

    return "\n".join(lines)


@create_tool("restore_from_trash", "Restore item from trash")
async def restore_from_trash(
    item_id: Annotated[
        JoplinIdType,
        Field(description="Note or notebook ID to restore"),
    ],
    item_type: Annotated[
        str,
        Field(description="Item type: 'note' or 'notebook'. Restoring a notebook does not restore the items inside it."),
    ] = "note",
) -> str:
    """Restore a note or notebook from Joplin's trash.

    Restores a previously deleted item by setting its deleted_time back to 0.
    The item reappears in its original notebook.

    Scope of restore (important):
    - Only the single item identified by item_id is restored. When restoring
      a notebook, its sub-notebooks and the notes inside stay trashed and
      must each be restored individually. Joplin sets deleted_time on every
      descendant when a notebook is trashed, and this tool clears it on one
      item per call.
    - If the original parent notebook is also trashed, restore the parent
      first or the restored item may not be visible.

    To find descendants to restore after restoring a notebook, use
    find_notes(query="*", trash=True) and filter to the relevant subtree.

    Returns:
        str: Success message confirming the item was restored.
    """
    item_id = validate_joplin_id(item_id)

    if item_type == "note":
        client = get_joplin_client()
        note_view.modify_note(client, item_id, deleted_time=0)
        return format_restore_success(ItemType.note, item_id)
    elif item_type == "notebook":
        notebook_resolver.modify_notebook(item_id, deleted_time=0)
        return format_restore_success(ItemType.notebook, item_id)
    else:
        raise ValueError(
            f"item_type must be 'note' or 'notebook', got '{item_type}'"
        )
