## Summary

12 new MCP tools across 7 new modules, plus supporting infrastructure. Adds bulk note/tag operations, trash management, revision history browsing and restore, and SQLite database backup — all with built-in safety mechanisms.

The overall design goal is to make it safe to ask an AI agent to completely reorganize notes across topics, notebooks, or an entire database, walk away, and know that catastrophic failures can be recovered at multiple levels — per-note revision snapshots, plus full database backup as a backstop.

Structured as 3 commits for easy review:
1. **New files only** (3,100 lines) — all our tools, helpers, and 87 unit tests. Zero changes to existing code.
2. **Required wiring** (58 lines) — dependency, imports, config entries.
3. **Optional enhancements** (56 lines) — auto-backup on update_note/edit_note, soft-delete formatting, docstring updates. Accept or reject independently.

## New Tools

**Bulk operations** (`tools/notes_bulk.py`, `tools/tags_bulk.py`):
- `move_note` — move a note to a different notebook by name or ID
- `bulk_move_notes` — move multiple notes with auto database backup
- `search_and_bulk_update_preview` — preview what a bulk update would change
- `search_and_bulk_update_execute` — execute bulk update with safety verification (count + title match from preview)
- `bulk_tag_notes` — add one or more tags to a list of notes (additive only — does not remove existing tags)
- `strip_note_tags` — remove all tags from a note

**Trash management** (`tools/trash.py`):
- `list_trash` — list soft-deleted notes/notebooks with deletion date and original notebook
- `restore_from_trash` — restore items by setting deleted_time to 0

**Revision history** (`tools/notes_revisions.py`):
- `get_note_history` — list all revisions for a note with timestamps and parent chain
- `restore_note_revision` — reconstruct content from diff chain, create as new note in the original notebook (falls back to "Restored Notes" if original is trashed)
- `manually_backup_note` — create on-demand revision snapshot

**Database backup** (`tools/backup_database.py`):
- `backup_database` — SQLite snapshot via `sqlite3 .backup`, last 10 auto-backups retained, manual backups never auto-deleted. Currently backup-only — no automated restore/swap feature; intended as a backstop for catastrophic failures.

## Safety Features

- **Preview/confirm flow**: `search_and_bulk_update_preview` → `search_and_bulk_update_execute` with count + first-title verification
- **Auto database backup**: bulk operations trigger SQLite backup before proceeding (configurable per-call: `daily`/`force`/`suppress`). Backup-only — no automated restore; intended as a backstop for catastrophic failures.
- **Per-note revision snapshots**: `save_note_revision` before title/body overwrites, following Joplin's `createNoteRevision_` algorithm with sequential diffs and parent chaining
- **All tools gated by config**: entries in `DEFAULT_TOOLS` / `TOOL_CATEGORIES` for user control

## Supporting Infrastructure

- `revision_utils.py` — diff-match-patch based revision creation and reconstruction for `restore_note_revision`
- `tools/field_helpers.py` — field registry (`JOPLIN_NOTE_FIELDS`), type converters, `_search_notes` (unified search + post-fetch AND filtering since Joplin's API can't do arbitrary WHERE clauses), `_parse_update_params`
- Note: `_search_notes` could serve as a shared internal for `find_notes` if you're interested — we deliberately didn't modify `find_notes` but designed the API to be compatible. Also, `list_trash` queries with `include_deleted=1` which `find_notes` doesn't currently expose.

## New Dependency

- `diff-match-patch>=20230430` — for revision creation/reconstruction in `restore_note_revision`

## Optional Enhancements (commit 3)

- `update_note`: auto-backup to new note revision before title/body overwrites; `convert_todo_completed` accepts bool, epoch milliseconds, or ISO datetime strings and converts to proper Joplin epoch-ms format
- `edit_note`: auto-backup to new note revision before body modifications
- `format_delete_success`: `soft_delete` param (default=True since Joplin default is soft-delete)
- `delete_note`/`delete_notebook` docstrings updated for soft-delete semantics
- `delete_tag`: explicit `soft_delete=False` (tags are permanently deleted)

## Test Plan

- [x] 87 unit tests with mocked Joplin client (`tests/pr_tests.py`)
- [x] 370 existing tests still pass (0 regressions)
- [x] Live MCP testing against Joplin Desktop 3.5.13: all 12 tools verified
- [x] Database integrity verified: no unintended modifications to user data

Happy to restructure if you prefer a different organization.
