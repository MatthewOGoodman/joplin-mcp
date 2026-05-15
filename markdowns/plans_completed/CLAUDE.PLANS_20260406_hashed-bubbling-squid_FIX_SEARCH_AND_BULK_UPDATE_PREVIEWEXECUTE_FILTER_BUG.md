# Plan: Fix search_and_bulk_update Preview/Execute Filter Bug

## Context

**Branch:** `rebase/upstream-pr` (PR #19 to alondmnt/joplin-mcp, based on v0.7.1 modular structure)

**Problem:** `search_and_bulk_update_preview` reports misleading TOTAL_RESULTS when `*_filter` parameters are provided. The user sees 3688 total results when only 5 notes match the filter. This is because the `TOTAL_RESULTS` header is fed `len(all_notes)` (post-filter count) but `format_search_results_with_pagination` shows it — and the pagination math uses it correctly.

**Wait — re-audit needed.** On this branch, the architecture is already clean:
- Both preview and execute call the **same shared function** `_search_notes()` (in `field_helpers.py:160`)
- `_search_notes()` does Phase 1 (API search) then Phase 2 (Python post-filtering with AND logic)
- Filters ARE applied in preview — `_parse_update_params()` separates them, then `**filters` is passed to `_search_notes()`
- Both functions use identical `_parse_update_params()` → `_search_notes()` pipeline
- Sorting is consistent (only for `query="*"`, in `_search_notes()`)

**So the original bug may already be fixed on this branch.** The bug was observed with the OLD installed code (v0.3.1 from the feature branch). After installing v0.7.1 from this branch, the filters should work.

## Architecture on This Branch (Audit Summary)

### Files

| File | Role |
|------|------|
| `src/joplin_mcp/tools/notes_bulk.py` | `search_and_bulk_update_preview` (L164-412), `search_and_bulk_update_execute` (L418-677) |
| `src/joplin_mcp/tools/field_helpers.py` | `_search_notes` (L160-214), `_parse_update_params` (L222-250), `JOPLIN_NOTE_FIELDS` (L89-146), `ALL_NOTE_FIELDS` (L150-152), `extract_note_ids_from_result` (L258-278) |
| `src/joplin_mcp/fastmcp_server.py` | `process_search_results` (L450), `flexible_bool_converter`, `apply_pagination`, `format_search_results_with_pagination` |
| `src/joplin_mcp/formatting.py` | `build_pagination_header` (L80) — generates `TOTAL_RESULTS: {total_count}` |

### Shared Search Pipeline (both functions use identically)

```
_parse_update_params(**kwargs)           # field_helpers.py:222
  → returns (updates, filters)           # updates: {field: value}, filters: {field: expected}

_search_notes(client, query, **filters)  # field_helpers.py:160
  Phase 1: Joplin API search
    query="*" → client.get_all_notes(fields=ALL_NOTE_FIELDS), sorted by updated_time DESC
    query=text → client.search_all(query=query, fields=ALL_NOTE_FIELDS)
  Phase 2: Python post-filter (AND logic)
    For each note: check getattr(note, field) == expected for all filters
  → returns (matching_notes, skipped_count)
```

### Preview (notes_bulk.py:164-412)

1. `parent_notebook` → `parent_id` conversion
2. `_parse_update_params()` → `(updates, filters)`
3. `_search_notes(client, query, **filters)` → `(all_notes, skipped_by_filter)`
4. `total_found = len(all_notes) + skipped_by_filter`
5. `apply_pagination(all_notes, preview_limit, 0)` → paginated notes
6. `format_search_results_with_pagination(..., len(all_notes), ...)` — **TOTAL_RESULTS = len(all_notes)** = post-filter count
7. Filter info section (if filters): shows search count, passing count, skipped count
8. Content inspection: fetch full body for first `inspect_count` notes

### Execute (notes_bulk.py:418-677)

1. Bool conversions for `is_todo`, `is_todo_filter`, `todo_completed_filter`
2. `parent_notebook` → `parent_id` conversion
3. `_parse_update_params()` → `(updates, filters)` — identical to preview
4. Validation: at least one update field required
5. Database backup (unless suppressed)
6. `_search_notes(client, query, **filters)` → `(matching_notes, skipped_by_filter)` — identical to preview
7. Safety: `len(matching_notes) == expected_count` and `first_title` match
8. Build ONE `update_payload` dict with type converters applied
9. Loop: for each matching note → save revision if body/title changing → `client.modify_note()`

### Key Differences (acceptable divergences)

| Aspect | Preview | Execute |
|--------|---------|---------|
| Extra params | `preview_limit`, `inspect_count` | `expected_count`, `first_title`, `backup` |
| Bool conversion | Not done (relies on Pydantic) | Lines 595-597: explicit `flexible_bool_converter` for `is_todo`, `is_todo_filter`, `todo_completed_filter` |
| Post-search action | Format + display | Update notes |
| Side effects | None | DB backup, revisions, note modifications |

### Remaining Issue: Bool Conversion Asymmetry

Preview does NOT call `flexible_bool_converter()` on `is_todo`, `is_todo_filter`, or `todo_completed_filter` before passing to `_parse_update_params()`. Execute does (lines 595-597).

This means if a non-bool value (e.g., string "true") is passed:
- Preview: passes raw string to `_search_notes()` → filter comparison `getattr(note, 'is_todo') != "true"` will likely fail (Joplin stores `is_todo` as int 0/1)
- Execute: converts to proper bool first → filter comparison works correctly

This could cause preview and execute to produce different filter results for the same parameters when bool-like strings are passed.

**Fix needed:** Add the same `flexible_bool_converter()` calls to preview, before `_parse_update_params()`.

## Implementation Plan

### Step 1: Add Bool Conversion to Preview

**File:** `src/joplin_mcp/tools/notes_bulk.py`
**Where:** After `parent_notebook` → `parent_id` conversion (line 349), before `_parse_update_params()` (line 351)

Add:
```python
is_todo = flexible_bool_converter(is_todo)
is_todo_filter = flexible_bool_converter(is_todo_filter)
todo_completed_filter = flexible_bool_converter(todo_completed_filter)
```

This matches execute's lines 595-597 exactly.

### Step 2: Verify Filter Behavior with Live MCP Test

After `/mcp` reload, test:
```
search_and_bulk_update_preview(
    query="*",
    parent_id_filter="<notebook_id>",   # a notebook with known count
    parent_notebook="0-Inbox",          # target for move
    preview_limit=5,
    inspect_count=2
)
```

Expected: `TOTAL_RESULTS` should show the filtered count (not 3688).

### Step 3: Verify Preview/Execute Consistency

Call execute with the `expected_count` and `first_title` from preview. The safety check should pass because both functions call `_search_notes()` identically.

## Verification

1. **Manual MCP test** — preview with `parent_id_filter` shows correct filtered count
2. **Preview → execute round-trip** — safety check passes (counts + first_title match)
3. **Bool conversion** — preview with `is_todo_filter=True` matches execute behavior
4. **Regression** — `pytest tests/` passes
