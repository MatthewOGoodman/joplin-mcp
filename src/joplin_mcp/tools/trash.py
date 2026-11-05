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
from joplin_mcp.config import get_config
from joplin_mcp.notebook_utils import is_notebook_accessible, notebook_resolver
from joplin_mcp.tools.notes import find_notes

logger = logging.getLogger(__name__)


def _format_trashed_notebooks(client, limit: int, offset: int) -> str:
    """List trashed notebooks, most recently deleted first.

    Upstream's find_notes(trash=True) lists notes only, so the notebook half of
    list_trash stays fork code. Under a notebook allowlist only notebooks the
    resolver confirms accessible are shown.
    """
    epoch_zero = dt_module.datetime(1970, 1, 1, 0, 0)
    notebooks = client.get_all_notebooks(
        fields="id,title,deleted_time,parent_id", include_deleted=1
    )
    trashed = [
        nb for nb in notebooks
        if getattr(nb, "deleted_time", None) and nb.deleted_time != epoch_zero
    ]
    cfg = get_config()
    if cfg.has_notebook_allowlist:
        trashed = [
            nb for nb in trashed
            if is_notebook_accessible(nb.id, allowlist_entries=cfg.notebook_allowlist)
        ]
    trashed.sort(key=lambda nb: nb.deleted_time, reverse=True)

    total = len(trashed)
    page = trashed[offset : offset + limit]
    if not page:
        return f"TRASHED_NOTEBOOKS: {total}\nSTATUS: No trashed notebooks in this range"

    titles = {getattr(nb, "id", ""): getattr(nb, "title", "Unknown") for nb in notebooks}
    lines = [
        f"TRASHED_NOTEBOOKS: {total}",
        f"SHOWING: {offset + 1}-{offset + len(page)} of {total}",
        "",
    ]
    for i, nb in enumerate(page, offset + 1):
        parent = getattr(nb, "parent_id", "") or ""
        lines.append(f"NOTEBOOK_{i}:")
        lines.append(f"  id: {nb.id}")
        lines.append(f"  title: {getattr(nb, 'title', 'Untitled')}")
        lines.append(f"  deleted: {format_timestamp(nb.deleted_time)}")
        lines.append(f"  original_parent: {titles.get(parent, '(top level)') if parent else '(top level)'}")
    return "\n".join(lines)


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
        LimitType, Field(description="Max results per item type (1-100, default: 20)")
    ] = 20,
    offset: Annotated[
        OffsetType,
        Field(description="Skip count for pagination, per item type (default: 0)"),
    ] = 0,
) -> str:
    """List items in Joplin's trash.

    Notes are listed by find_notes("*", trash=True) - item_type='note' is an
    alias of that call. Notebooks, which find_notes cannot list, follow in their
    own section. With item_type=None both sections are returned, and limit and
    offset apply to each section separately. Restore with restore_from_trash.

    Returns:
        str: Trashed notes (find_notes format) and/or trashed notebooks with ID,
             deletion date, and original parent notebook.
    """
    if item_type not in (None, "note", "notebook"):
        raise ValueError(
            f"item_type must be 'note', 'notebook' or None, got '{item_type}'"
        )

    sections = []
    if item_type in (None, "note"):
        sections.append(
            await find_notes.fn(query="*", limit=limit, offset=offset, trash=True)
        )
    if item_type in (None, "notebook"):
        sections.append(_format_trashed_notebooks(get_joplin_client(), limit, offset))
    return "\n\n".join(sections)


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
