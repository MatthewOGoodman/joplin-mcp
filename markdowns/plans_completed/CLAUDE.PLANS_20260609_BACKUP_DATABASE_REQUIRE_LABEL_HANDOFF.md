# backup_database — require informative label on manual backups + document the mechanism (hand-off from joplin_user session)

## Motivation
A joplin_user investigation (2026-06-09) found `~/JoplinBackup/default/mcp-backups/` at **1.3 GB** — full-DB `.sqlite` snapshots (~98 MB each, a complete copy of the Joplin DB). **Manual** backups (`force=True`) are never pruned and carry **no descriptive label**, so the accumulated files are opaque ("which session / why?"). The user wants manual backups to be self-describing, and the backup mechanism documented better in-tool.

## Files to touch (joplin-mcp)
- `src/joplin_mcp/tools/backup_database.py` — the `backup_database` tool + `backup_joplin_database()`.
- `src/joplin_mcp/tools/notes_bulk.py` — the two `backup=(...)` call sites (lines ~134, ~633; the `force` path).
- Tool docstrings + any README/docs describing backups.
- Tests under `tests/`.

## Change 1 — require an informative label on manual backups
- `backup_database` tool currently takes **no args**; add a **required** `label: str` (short reason/slug). Sanitize → lowercase, alnum + dashes, length-capped.
- Thread it into `backup_joplin_database(force=True, label=...)` → filename `joplin_manual_backup_{timestamp}_{slug}.sqlite`.
- For the bulk tools' `backup="force"` path: **auto-derive** the slug from the operation (`bulk-move`, `bulk-update`) so forced bulk backups are labeled without a user arg. (Design point: require an explicit label only on the standalone `backup_database` tool; auto-label the bulk-op forced path.)
- Leave the `force=False` (`"daily"`/auto) path unchanged — no label needed; it's pruned to the last 10.

## Change 2 — document the mechanism (the `/joplin-ops` skill was updated joplin_user-side; mirror in-tool)
- `backup_database` docstring + README: explain **AUTO** (`backup="daily"`, the default on `bulk_move_notes` / `search_and_bulk_update_execute`; once-per-calendar-day guard; retention = last 10 via `_BACKUP_RETENTION`) vs **MANUAL** (`backup="force"` or the standalone tool; **never pruned**). State each backup is a FULL DB copy (~98 MB) at `~/JoplinBackup/default/mcp-backups/`. Clarify `manually_backup_note` writes **no file** (in-Joplin revision).
- Optional: a documented manual-prune helper, since manual backups grow unbounded. The user wants to **KEEP** existing manual snapshots (possible state) — do NOT auto-prune them.

## Success criteria
- `backup_database(label="pre-archive-sweep")` → `joplin_manual_backup_<ts>_pre-archive-sweep.sqlite`.
- `backup_database()` with no label errors clearly (label required).
- Bulk-op forced backups get an auto slug.
- Docstrings/README explain auto-vs-manual + retention accurately.
- Tests updated/added.

## Originating session
joplin_user, 2026-06-09 (backup-folder investigation). Mirror: joplin_user `STATUS.md` §3 "Joplin backup retention + manual-label hygiene" thread.
