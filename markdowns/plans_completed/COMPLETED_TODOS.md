# Completed TODOs

## TODO: Fix todo_completed Timestamp Handling

**Bug**: `todo_completed` writes `1` instead of actual epoch-ms timestamp. Joplin expects milliseconds since epoch (e.g., `1740700800000`). Writing `1` means "completed at 1ms after 1970-01-01" — breaks completion date display, sorting, and sync.

**Root cause**: `flexible_bool_converter()` collapses all truthy input to `True`, then write paths do `1 if todo_completed else 0`.

**Revised solution**: Replace parameter splitting proposal with smart single-parameter converter. Keep one `todo_completed` parameter, handle input type intelligently:

| Input | Interpretation | API value |
|---|---|---|
| `True` | Completed now | `int(time.time() * 1000)` |
| `False` | Not completed | `0` |
| Large int (>1_000_000_000_000) | Explicit epoch ms | Pass through |
| `"2026-02-27 14:30"` or `"2026-02-27"` | ISO datetime string | Parse to epoch ms |
| `1` (or small int) | **Warning**: "Interpreted as 1ms since epoch. Did you mean True?" | Write as-is |

**Implementation plan**:

1. **Add `convert_todo_completed()` function** (near `flexible_bool_converter`):
   - `bool` → `int(time.time() * 1000)` if True, `0` if False
   - `int > 1_000_000_000_000` → pass through
   - `int` 1-999_999_999_999 → write as-is + return warning string
   - `str` matching ISO datetime → `datetime.fromisoformat()` → epoch ms (accepts `YYYY-MM-DD HH:MM` or `YYYY-MM-DD`)
   - `str` "true"/"false" etc → same as bool path
   - Returns `(int, Optional[str])` tuple: (api_value, warning_message)

2. **Update `JOPLIN_NOTE_FIELDS` registry** (line ~296):
   - Change `todo_completed` entry `type_converter` from `flexible_bool_converter` to `convert_todo_completed`
   - Registry is used by bulk update execute path

3. **Update `create_note`** (line ~1906):
   - Replace `todo_completed=1 if todo_completed else 0`
   - With `todo_completed=convert_todo_completed(todo_completed)[0]`

4. **Update `update_note`** (line ~1963):
   - Replace `update_data["todo_completed"] = 1 if todo_completed else 0`
   - With converted value from `convert_todo_completed()`

5. **Update Field descriptions** in `create_note`, `update_note`, `search_and_bulk_update_preview`, `search_and_bulk_update_execute`:
   - Change `Field(description="Mark todo completed (optional)")` to document accepted formats:
   - `Field(description="Mark todo completed. Accepts: True/False (uses current time), epoch milliseconds (e.g. 1740700800000), or ISO datetime string 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD' (optional)")`

6. **Leave filter path unchanged**:
   - `todo_completed_filter` stays on `flexible_bool_converter` — boolean filtering is correct for "show completed vs incomplete"

7. **Handle warnings**: Surface warning messages in tool return strings where applicable