# Manual MCP Tool Test Plan

Reproducible test plan for verifying joplin-mcp tools via live MCP calls against a running Joplin Desktop instance.

## Prerequisites

- Joplin Desktop running with Web Clipper API enabled (port 41184)
- A "Testing" notebook exists in Joplin
- A "Restored Notes" notebook exists in Joplin
- The joplin-mcp conda environment is active
- Claude Code session connected to the Joplin MCP server (`/mcp` shows connection)

## Test Execution Log: 2026-03-30

All tests run on `rebase/upstream-pr` branch at commit `e042032`.

---

## 1. Connection: ping_joplin

**Call:**
```
mcp__joplin__ping_joplin()
```

**Expected:** `STATUS: SUCCESS`, `CONNECTION: ESTABLISHED`

**Verified:** Connection to Joplin server is live.

---

## 2. Database Backup: backup_database

**Call:**
```
mcp__joplin__backup_database()
```

**Expected:**
- `STATUS: SUCCESS`
- `BACKUP_PATH` contains `joplin_manual_backup_` prefix (not `joplin_backup_` or `joplin_auto_backup_`)
- `SIZE` is reported in MB (database is ~98MB)
- File actually exists on disk at the reported path

**Verified:**
- Created `joplin_manual_backup_20260330_104711.sqlite` (97.9 MB)
- Confirmed file exists in `~/JoplinBackup/default/mcp-backups/`
- The `force=True` path (manual backup) was exercised, producing the `manual_backup` prefix
- Manual backups are never subject to auto-retention cleanup

**Follow-up check (filesystem):**
```bash
ls -lt ~/JoplinBackup/default/mcp-backups/
```

---

## 3. Trash Management: list_trash

**Call:**
```
mcp__joplin__list_trash()
```

**Expected:**
- `TRASH_ITEMS: N` where N >= 0
- Each item shows: `type`, `id`, `title`, `deleted` (formatted timestamp), `original_notebook`
- Notes with `is_todo: true` show that field
- Pagination info if results > limit

**Verified:**
- Returned 28 trashed items (showing 1-20, paginated)
- Each item had correct fields: type (note), id (32 hex chars), title, deleted timestamp, original_notebook name
- Todo notes showed `is_todo: true`
- Pagination summary showed page 1 of 2

---

## 4. Trash Management: restore_from_trash

**Setup:** Identify a trashed note from `list_trash` output.

**Call:**
```
mcp__joplin__restore_from_trash(
    item_id="9bedd1bd739b486cae11844bb0f54c1c",
    item_type="note"
)
```

**Expected:**
- `OPERATION: RESTORE_FROM_TRASH`
- `STATUS: SUCCESS`
- `ITEM_TYPE: note`
- The note reappears in its original notebook in Joplin Desktop

**Verified:**
- Note "Chain Test" restored successfully
- Note appeared back in the "Testing" notebook

---

## 5. Revision System: manually_backup_note

**Setup:** Create a test note first.

```
mcp__joplin__create_note(
    title="PR Test Note",
    notebook_name="Testing",
    body="This is a test note for verifying the ported MCP tools."
)
```
Record the returned `ITEM_ID` (e.g., `ce5dac0902bd4ea6a2919f5b8924e986`).

**Call:**
```
mcp__joplin__manually_backup_note(
    note_id="<note_id from above>"
)
```

**Expected:**
- `OPERATION: MANUALLY_BACKUP_NOTE`
- `STATUS: SUCCESS`
- `REVISION_ID` is a 32-char hex string
- A revision is created in Joplin's revision system

**Verified:**
- Revision `b2acd34886204718aa35e3d5b2f1d4f6` created
- This is the first revision for this note (no parent)

---

## 6. Enhanced update_note: Auto-Backup and convert_todo_completed

**Setup:** Use the same test note from Step 5.

### 6a. Update title and body (triggers auto-backup)

**Call:**
```
mcp__joplin__update_note(
    note_id="<note_id>",
    title="PR Test Note - Updated",
    body="This content has been updated to test auto-backup revision."
)
```

**Expected:**
- `STATUS: SUCCESS`
- A new revision is automatically created BEFORE the overwrite (auto-backup)
- The revision chains to the manual backup from Step 5 via `parent_id`

**Verified:** See Step 7 — `get_note_history` confirmed 2 revisions with parent chaining.

### 6b. Set todo_completed with boolean (convert_todo_completed)

**Call:**
```
mcp__joplin__update_note(
    note_id="<note_id>",
    is_todo=true,
    todo_completed=true
)
```

**Expected:**
- `STATUS: SUCCESS`
- `is_todo` set to 1
- `todo_completed` set to current epoch milliseconds (NOT just `1`)
- Auto-sets `is_todo=1` when `todo_completed` is truthy

**Verified:**
- `get_note` metadata showed `IS_TODO: true`, `TODO_COMPLETED: true`
- `convert_todo_completed(True)` produced a proper epoch-ms timestamp (Joplin stores this as ms, displays as boolean in metadata view)

---

## 7. Revision System: get_note_history

**Setup:** Use the test note that had Steps 5 and 6a applied (manual backup + update with auto-backup).

**Call:**
```
mcp__joplin__get_note_history(
    note_id="<note_id>"
)
```

**Expected:**
- `REVISIONS: 2` (or more if additional updates were done)
- Revision 1 (newest): created by auto-backup in Step 6a, `has_parent: yes`, `parent_id` points to Revision 2
- Revision 2 (oldest): created by manual backup in Step 5, `has_parent: no (first revision)`
- Both show title, timestamp, revision_id

**Verified:**
- 2 revisions found
- REVISION_1: `bc12810584d042a49a5f199e54058e69`, created 14:47:33, title "PR Test Note", parent_id = `b2acd34886204718aa35e3d5b2f1d4f6`
- REVISION_2: `b2acd34886204718aa35e3d5b2f1d4f6`, created 14:47:29, title "PR Test Note", no parent (first revision)
- Sequential diff chain confirmed: revision 1 chains to revision 2

---

## 8. Revision System: restore_note_revision

**Setup:** Use a revision_id from Step 7 (the first/oldest revision).

**Call:**
```
mcp__joplin__restore_note_revision(
    revision_id="b2acd34886204718aa35e3d5b2f1d4f6",
    target_notebook="Testing"
)
```

**Expected:**
- `OPERATION: RESTORE_NOTE_REVISION`
- `STATUS: SUCCESS`
- `RESTORED_NOTE_ID` is a new note ID (different from the original)
- `TITLE` matches the original title at that revision
- The restored note is created in the target notebook

**Verified:**
- New note `0a0054fe822545aba947ff84a23c3ee3` created
- Title: "PR Test Note" (original title before update)
- Created in "Testing" notebook

**Content verification:**
```
mcp__joplin__get_note(note_id="<restored_note_id>")
```

**Verified:**
- Body: "This is a test note for verifying the ported MCP tools." — matches the original content from Step 5 exactly
- Diff chain reconstruction worked correctly (walked parent chain, applied diffs sequentially)

---

## 9. Note Operations: move_note

**Setup:** Use the test note from Step 5.

**Call:**
```
mcp__joplin__move_note(
    note_id="<note_id>",
    target_notebook="Restored Notes"
)
```

**Expected:**
- `STATUS: SUCCESS`
- `MOVED_TO_NOTEBOOK_ID` shows the target notebook's ID
- Note appears in "Restored Notes" in Joplin Desktop

**Verified:**
- Note moved to notebook `1fc0b20bd71b415996d46e3257384b75` (Restored Notes)

---

## 10. Tag Operations: strip_note_tags

**Setup:** First apply tags to the test note using existing tags.

```
mcp__joplin__tag_note(note_id="<note_id>", tag_name="claude: artifact")
mcp__joplin__tag_note(note_id="<note_id>", tag_name="comp: mcp/api")
```

Both should return `STATUS: SUCCESS`.

**Call:**
```
mcp__joplin__strip_note_tags(
    note_id="<note_id>"
)
```

**Expected:**
- `OPERATION: STRIP_TAGS`
- `STATUS: SUCCESS`
- `TAGS_REMOVED: 2`
- `REMOVED:` lists both tag names

**Verified:**
- 2 tags removed: "claude: artifact", "comp: mcp/api"
- Note confirmed to have no tags after strip

---

## 11. Bulk Operations: search_and_bulk_update_preview

**Call:**
```
mcp__joplin__search_and_bulk_update_preview(
    query="PR Test",
    is_todo=true
)
```

**Expected:**
- `SEARCH_QUERY` shows the query
- `TOTAL_RESULTS` count
- Each result shows: `note_id`, `title`, `created`, `updated`, `notebook_path`, `is_todo`, `content_preview`
- Pagination info if results > limit
- `FULL CONTENT INSPECTION` section showing first N notes' full content

**Verified:**
- Found 733 results for "PR Test" (broad match across all notes)
- First 5 results displayed with all expected fields
- Content preview showed matching lines with search term highlighting
- Full content inspection showed complete note bodies for first 2 results
- Pagination summary: page 1 of 147

**Note:** This is a preview only — no notes were modified. The `is_todo=true` parameter would be applied as an update if `search_and_bulk_update_execute` were called.

---

## Tools NOT Tested (Disabled by Default)

The following tools are disabled in `DEFAULT_TOOLS` config and were not tested:

| Tool | Reason Disabled | To Enable |
|------|----------------|-----------|
| `bulk_move_notes` | Modifies many notes | Set `"bulk_move_notes": true` in config |
| `search_and_bulk_update_execute` | Modifies many notes | Set `"search_and_bulk_update_execute": true` in config |
| `bulk_tag_notes` | Modifies many notes | Set `"bulk_tag_notes": true` in config |
| `delete_note` | Destructive (alondmnt default) | Set `"delete_note": true` in config |

To enable for testing, modify `~/.claude.json` or the project's `.claude/settings.json` to override tool permissions, or update `DEFAULT_TOOLS` in `src/joplin_mcp/config.py`.

---

## Test Cleanup

After testing, the following items were created in Joplin and can be manually deleted:

1. **"PR Test Note - Updated"** in "Restored Notes" notebook (moved from Testing, is_todo=true)
2. **"PR Test Note"** in "Testing" notebook (restored from revision)
3. **"Chain Test"** restored from trash back to "Testing" notebook
4. **Database backup:** `joplin_manual_backup_20260330_104711.sqlite` in `~/JoplinBackup/default/mcp-backups/`

---

## Test Results Summary

| # | Tool | Test | Result |
|---|------|------|--------|
| 1 | `ping_joplin` | Connection check | PASS |
| 2 | `backup_database` | SQLite backup with manual prefix | PASS |
| 3 | `list_trash` | List 28 soft-deleted items with metadata | PASS |
| 4 | `restore_from_trash` | Restore trashed note to original notebook | PASS |
| 5 | `manually_backup_note` | Create first revision snapshot | PASS |
| 6a | `update_note` | Auto-backup revision before title/body overwrite | PASS |
| 6b | `update_note` | `convert_todo_completed(True)` epoch-ms timestamp | PASS |
| 7 | `get_note_history` | 2 revisions with parent chain | PASS |
| 8 | `restore_note_revision` | Reconstruct from diff chain, verify content | PASS |
| 9 | `move_note` | Move note between notebooks by name | PASS |
| 10 | `strip_note_tags` | Apply 2 tags then strip all | PASS |
| 11 | `search_and_bulk_update_preview` | Search + preview without modification | PASS |
