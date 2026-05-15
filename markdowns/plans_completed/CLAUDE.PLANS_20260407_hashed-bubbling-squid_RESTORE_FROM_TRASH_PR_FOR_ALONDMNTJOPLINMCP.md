# Plan: restore_from_trash PR for alondmnt/joplin-mcp

## Context

alondmnt reviewed our PR #19 and declined the full set of tools, but offered to accept a focused `restore_from_trash` tool as a standalone PR. He specified three changes:

1. Add `_clear_note_cache()` after the mutation
2. Rename test file to `test_*.py` for pytest discovery
3. Use uppercase keys (`OPERATION:`, `STATUS:`) to match existing output format

**Branch:** `pr/restore-from-trash` based on `upstream/main` (v0.7.1, `1a7f40e`). This is clean upstream code — no custom tools exist yet.

## Files to Create/Modify

| File | Action |
|------|--------|
| `src/joplin_mcp/tools/trash.py` | **Create** — restore_from_trash tool only (NOT list_trash — that's issue #20) |
| `src/joplin_mcp/tools/__init__.py` | **Modify** — add `trash` import to register the tool |
| `src/joplin_mcp/config.py` | **Modify** — add `restore_from_trash` to `DEFAULT_TOOLS` and `TOOL_CATEGORIES` |
| `tests/test_tools_trash.py` | **Create** — unit tests (named `test_*` for pytest discovery) |

## Implementation

### Step 1: Create `src/joplin_mcp/tools/trash.py`

Minimal file — only `restore_from_trash`, no `list_trash` (that's a separate issue #20).

**Based on our `main` branch implementation** but with alondmnt's three requested changes:

```python
"""Trash management tools for Joplin MCP — restore soft-deleted items."""
import logging
from typing import Annotated

from pydantic import Field

from joplin_mcp.fastmcp_server import (
    JoplinIdType,
    create_tool,
    get_joplin_client,
    validate_joplin_id,
)
from joplin_mcp.tools.notes import _clear_note_cache
from joplin_mcp.notebook_utils import invalidate_notebook_map_cache

logger = logging.getLogger(__name__)


@create_tool("restore_from_trash", "Restore item from trash")
async def restore_from_trash(
    item_id: Annotated[JoplinIdType, Field(description="Note or notebook ID to restore")],
    item_type: Annotated[str, Field(description="Item type: 'note' or 'notebook'")] = "note",
) -> str:
    """Restore a note or notebook from Joplin's trash.

    Restores a previously deleted item by setting its deleted_time back to 0.
    The item reappears in its original notebook. If the original notebook was
    also trashed, restore it first or the note may not be visible.

    Returns:
        str: Success message confirming the item was restored.
    """
    item_id = validate_joplin_id(item_id)
    client = get_joplin_client()

    if item_type == "note":
        client.modify_note(item_id, deleted_time=0)
        _clear_note_cache()                        # Change 1: cache clearing
        return (
            "OPERATION: RESTORE_NOTE\n"            # Change 3: uppercase format
            "STATUS: SUCCESS\n"
            "ITEM_TYPE: note\n"
            f"ITEM_ID: {item_id}\n"
            "MESSAGE: note restored from trash to its original notebook"
        )
    elif item_type == "notebook":
        client.modify_notebook(item_id, deleted_time=0)
        invalidate_notebook_map_cache()            # Change 1: cache clearing
        return (
            "OPERATION: RESTORE_NOTEBOOK\n"        # Change 3: uppercase format
            "STATUS: SUCCESS\n"
            "ITEM_TYPE: notebook\n"
            f"ITEM_ID: {item_id}\n"
            "MESSAGE: notebook restored from trash"
        )
    else:
        raise ValueError(f"item_type must be 'note' or 'notebook', got '{item_type}'")
```

**Key decisions:**
- Output format follows `formatting.py` convention: `OPERATION: RESTORE_NOTE` / `RESTORE_NOTEBOOK` (matching `DELETE_NOTE`, `CREATE_NOTE` pattern)
- `MESSAGE:` line uses lowercase description (matching `format_delete_success` pattern: "note deleted successfully")
- `_clear_note_cache()` after note restore (matching `delete_note` at notes.py:927)
- `invalidate_notebook_map_cache()` after notebook restore (matching `delete_notebook` at notebooks.py:104)
- No `format_update_success` import — custom output is more descriptive for restore operations

### Step 2: Modify `src/joplin_mcp/tools/__init__.py`

Current (line 2): `from joplin_mcp.tools import notes, notebooks, tags`

Change to: `from joplin_mcp.tools import notes, notebooks, tags, trash`

Also update `__all__` to include `"trash"`.

### Step 3: Modify `src/joplin_mcp/config.py`

**In `DEFAULT_TOOLS` dict (~line 229, after `ping_joplin`):**

Add:
```python
    # Trash operations (1 tool)
    "restore_from_trash": True,  # Restore deleted note/notebook from trash
```

**In `TOOL_CATEGORIES` dict (~line 258, after utility):**

Add:
```python
    "trash": ["restore_from_trash"],
```

### Step 4: Create `tests/test_tools_trash.py`

Named `test_*` for pytest discovery (alondmnt's change 2). Follow the pattern from `test_tools_notes.py` — mock the client, test the tool logic.

Tests:
1. **Restore note** — mock `client.modify_note`, verify called with `deleted_time=0`, verify `_clear_note_cache()` called, verify output format
2. **Restore notebook** — mock `client.modify_notebook`, verify called with `deleted_time=0`, verify `invalidate_notebook_map_cache()` called, verify output format
3. **Invalid item_type** — verify `ValueError` raised for non-note/notebook
4. **Invalid item_id** — verify validation rejects bad IDs
5. **Output format** — verify uppercase keys match pattern (OPERATION, STATUS, ITEM_TYPE, ITEM_ID, MESSAGE)

## Verification

1. `pytest tests/test_tools_trash.py` — new tests pass
2. `pytest` — full test suite passes (no regressions)
3. `ruff check src/joplin_mcp/tools/trash.py tests/test_tools_trash.py` — lint clean
4. `git diff --stat upstream/main` — minimal diff (4 files changed)
5. Manual review: confirm output format matches `format_delete_success` / `format_creation_success` convention

## PR Submission

```bash
git push -u origin pr/restore-from-trash
gh pr create --repo alondmnt/joplin-mcp --base main \
  --title "feat: add restore_from_trash tool" \
  --body "..."
```

Keep PR description short — reference his review on #19, note the three changes he requested.
