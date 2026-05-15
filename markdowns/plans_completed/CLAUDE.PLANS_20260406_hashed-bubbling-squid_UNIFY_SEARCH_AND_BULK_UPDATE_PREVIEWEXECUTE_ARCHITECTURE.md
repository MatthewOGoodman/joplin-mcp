# Plan: Unify search_and_bulk_update Preview/Execute Architecture

## Context

**Problem:** `search_and_bulk_update_preview` and `search_and_bulk_update_execute` have divergent search, filter, and sorting logic. This causes:

1. **User-reported bug:** `parent_id_filter` not applied in preview — shows TOTAL_RESULTS: 3688 instead of 5 notes
2. **Search divergence:** Preview has `condition_search_on_TODOs` gate (default False) that skips ALL filters; execute always applies filters → different result sets from identical params
3. **Sort divergence:** Preview sorts by `updated_time` DESC; execute never sorts → `first_title` safety check fails
4. **Filter logic divergence:** Preview uses all-or-nothing `generate_field_checks()`; execute uses per-field `should_update_field()` → conditional update simulation counts don't match actual execution
5. **Bug:** Execute references undefined `task` and `completed` variables (NameError)
6. **Invalid search syntax:** `build_general_search_filters` generates `parent_id:"..."`, `author:"..."` — Joplin's search API doesn't support these field queries

**User requirement:** Preview and execute must run the EXACT SAME code for search and filter phases, diverging only at the action step (preview → format/display, execute → update notes).

## Critical File

`src/joplin_mcp/fastmcp_server.py` — all changes are in this file

## Implementation

### Step 1: Add `SEARCH_LEVEL_FILTERS` Constant

**Where:** After `JOPLIN_NOTE_FIELDS` dict (~line 399)

```python
# Filters that Joplin's search API supports natively.
# is_todo → type:todo/type:note, todo_completed → iscompleted:0/1
# All other *_filter params require post-search note-by-note checking.
SEARCH_LEVEL_FILTERS = frozenset({'is_todo', 'todo_completed'})
```

**Why:** Joplin's search endpoint only supports `type:todo`/`type:note` and `iscompleted:0`/`iscompleted:1`. The current code generates `parent_id:"abc"` which is silently ignored. This constant makes the boundary explicit.

---

### Step 2: Promote `should_update_field` to Module Level

**Where:** Near `generate_field_pars` (~line 2250)

Move the function currently defined locally inside execute (line 2753) to module scope. Identical logic:

```python
def should_update_field(note, field_name, new_value, current_required_value):
    """Check if a field should be updated based on its filter condition."""
    if new_value is None:
        return False
    if current_required_value is None:
        return True
    current_value = getattr(note, field_name, None)
    return current_value == current_required_value
```

---

### Step 3: Create `_search_and_filter_notes` Shared Function

**Where:** Insert before preview function (~line 2470)

**Signature:**
```python
def _search_and_filter_notes(
    client,
    query: str,
    **field_params  # All update + filter params (NOT preview_limit, expected_count, etc.)
) -> dict:
```

**Returns:**
```python
{
    'notes': List,           # Filtered, sorted notes
    'total_count': int,      # len(notes) after filtering
    'field_pars': dict,      # From generate_field_pars (update_fields, filter_fields)
}
```

**Logic (in order):**

1. **Partition filters** into search-level vs post-search:
   - `field_pars = generate_field_pars(**field_params)`
   - `search_filters = [f for f in field_pars['filter_fields'] if f in SEARCH_LEVEL_FILTERS]`
   - `post_filters = [f for f in field_pars['filter_fields'] if f not in SEARCH_LEVEL_FILTERS]`

2. **Build search fields** — ensure search results include data needed for post-filtering:
   - Start with `COMMON_NOTE_FIELDS`
   - Add fields from `extract_query_fields(query)` 
   - Add `post_filters` field names (e.g. if `parent_id_filter` set, ensure `parent_id` is fetched — it already is via COMMON_NOTE_FIELDS, but `author` etc. are not)
   - Use `build_enhanced_field_list()` to merge/deduplicate

3. **Build search-level query parts** using `build_search_filters()` (alondmnt's original, line 245) for is_todo/todo_completed only:
   ```python
   search_parts = []
   is_todo_val = field_params.get('is_todo_filter')
   completed_val = field_params.get('todo_completed_filter')
   if is_todo_val is not None or completed_val is not None:
       search_parts.extend(build_search_filters(is_todo_val, completed_val))
   ```

4. **Execute search:**
   ```python
   if query.strip() == "*":
       if search_parts:
           results = client.search_all(query=" ".join(search_parts), fields=search_fields)
       else:
           results = client.get_all_notes(fields=search_fields)
   else:
       full_query = " ".join([query] + search_parts) if search_parts else query
       results = client.search_all(query=full_query, fields=search_fields)
   notes = process_search_results(results)
   ```

5. **Post-filter** — apply non-search-level filters note-by-note:
   ```python
   if post_filters:
       filtered = []
       for note in notes:
           match = True
           for field_name in post_filters:
               expected = field_params.get(f"{field_name}_filter")
               actual = getattr(note, field_name, None)
               if actual != expected:
                   match = False
                   break
           if match:
               filtered.append(note)
       notes = filtered
   ```

   **Note on field availability:** Fields with `in_common_fields: True` in `JOPLIN_NOTE_FIELDS` (title, body, is_todo, todo_completed, parent_id) are always in search results. Fields with `in_common_fields: False` (author, source_url, latitude, etc.) are added to `search_fields` in step 2, so they're also available without per-note API calls.

6. **Sort consistently:**
   ```python
   notes = sorted(notes, key=lambda x: getattr(x, 'updated_time', 0), reverse=True)
   ```

7. **Return** the result dict.

---

### Step 4: Rewrite `search_and_bulk_update_preview`

**Remove:** `condition_search_on_TODOs` parameter entirely.

**Keep:** `query`, `preview_limit`, `inspect_count`, `get_conditional_update_counts`, all update params, all filter params, `parent_notebook`.

**Search section** (replace lines 2530-2589): 
- `parent_notebook` → `parent_id` conversion (keep as-is)
- Call `_search_and_filter_notes(client, query, **field_params)`
- Use returned `notes`, `total_count`, `field_pars`

**Conditional update simulation** (replace lines 2611-2648):
- Use per-field `should_update_field()` instead of all-or-nothing `generate_field_checks()`
- This makes the simulation match execute's actual behavior exactly

**Everything else** (pagination, formatting, content inspection): Keep unchanged, operating on the filtered notes list.

---

### Step 5: Rewrite `search_and_bulk_update_execute`

**Remove:**
- Lines 2739-2740: `task = flexible_bool_converter(task)` and `completed = flexible_bool_converter(completed)` — undefined variables, NameError bug
- Local `should_update_field` definition (lines 2753-2762) — use module-level version

**Search section** (replace lines 2774-2795):
- `parent_notebook` → `parent_id` conversion (keep)
- Bool conversions for `is_todo`, `is_todo_filter`, `todo_completed_filter` (keep)
- Call `_search_and_filter_notes(client, query, **field_params)` — same as preview

**Safety verification** (lines 2797-2803): Keep as-is. Now works correctly because preview and execute produce identical note lists.

**Update loop** (lines 2813-2837): Keep per-field logic using module-level `should_update_field()`. Use `field_pars` from shared function return.

---

### Step 6: Remove Dead Code

| Function | Line | Action | Reason |
|----------|------|--------|--------|
| `build_general_search_filters` | 265 | Delete | Only called from preview/execute search blocks being replaced. Generated invalid Joplin syntax for non-todo fields. |
| `generate_field_checks` | 2222 | Delete | Only called at line 2641 (preview simulation), replaced by `should_update_field` |
| `build_conditional_fields_list` | 2177 (if exists) | Verify and delete if unused | |

**Keep:** `build_search_filters` (line 245) — still used by `find_notes` and called from shared function.

---

### Step 7: Construct Clean Param Dicts

Both preview and execute currently use `**locals()` to pass params to helpers. This is fragile (includes `client`, `preview_limit`, loop variables, etc.). 

In both functions, after `parent_notebook` → `parent_id` conversion, build an explicit dict:

```python
field_params = {}
for field_name in JOPLIN_NOTE_FIELDS:
    val = locals().get(field_name)
    if val is not None:
        field_params[field_name] = val
    fval = locals().get(f"{field_name}_filter")
    if fval is not None:
        field_params[f"{field_name}_filter"] = fval
```

Pass `**field_params` to `_search_and_filter_notes` and use it for simulation/update loops.

---

## Verification

### Unit Tests

Add to `tests/` (new file `tests/test_bulk_update.py` or extend existing):

1. **`_search_and_filter_notes` with `parent_id_filter`**: Mock client returning 10 notes from 3 notebooks. Verify only notes matching `parent_id_filter` are returned.

2. **`_search_and_filter_notes` with `is_todo_filter`**: Verify search query includes `type:todo` (search-level), not post-filtered.

3. **`should_update_field`**: Test all 4 branches (new_value=None, filter=None, filter matches, filter doesn't match).

4. **Preview/execute consistency**: Mock client, call preview, extract `total_count` and `first_title`, pass to execute. Verify safety check passes.

5. **Conditional simulation matches execute**: Set up mixed-filter scenario. Preview's `get_conditional_update_counts` affected/skipped counts must match execute's actual success/skipped counts.

6. **No NameError**: Call execute — verify no reference to undefined `task`/`completed`.

### Manual MCP Test

```
search_and_bulk_update_preview(
    query="*",
    parent_id_filter="<notebook_id>",  # notebook with 5 notes
    parent_notebook="0-Inbox",
    preview_limit=5,
    inspect_count=2
)
# Expected: TOTAL_RESULTS: 5 (not 3688)
# Previewed notes all from the source notebook
```

### Regression Check

Run existing test suite: `pytest tests/`
