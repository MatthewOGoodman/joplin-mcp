# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Branch Strategy

| Branch | Purpose | Status |
|--------|---------|--------|
| `main` | Clean codebase. alondmnt v0.7.1 modular structure + our 12 tools + fixes. Always deployable. | Active |
| `feature/dev` | Ongoing development. CLAUDE.md, new features, fixes. Merges to main. | Active, primary work branch |
| `extract/mcp-docker-dev` | Snapshot of old monolithic branch. Starting point for extracting Docker/install infrastructure into separate `mcp-docker-dev` repo. Will be destructively edited. | Parked |
| `feature/bulk-operations-and-api-enhancements` | Original monolithic dev branch. Historical reference only. Do not modify. | Frozen |
| _(deleted)_ `rebase/upstream-pr` | Former PR #19 branch. Tip was `5777d44`. Full history preserved in `main`. PR record at alondmnt/joplin-mcp#19. | Deleted |
| `pr/*` | Per-contribution branches for upstream PRs. Created from `upstream/main`, minimal and focused. | Created as needed |

**Workflow:** Develop on `feature/dev`, merge to `main` when ready. For upstream contributions, create `pr/<topic>` branches from `upstream/main` — these are minimal, focused changes matching alondmnt's conventions. Do not mix our fork's extras into PR branches.

## Upstream Relationship

- **Original Repository**: https://github.com/alondmnt/joplin-mcp
- **Our Fork**: https://github.com/MatthewOGoodman/joplin-mcp
- **Upstream version**: v0.7.1 (`1a7f40e`)
- **Our main**: v0.7.1 + 12 new tools (3 commits on top of upstream)

### PR #19 Status (closed 2026-04-06)

PR was declined — alondmnt prefers extending existing interfaces over new tools. He opened three issues for contributions he would accept:
- **#20 — Trash listing**: Fold into `find_notes(trash=True)` instead of separate `list_trash`
- **#21 — Moving notes**: Add `notebook_name` to `update_note` instead of separate `move_note`
- **#22 — Bulk tagging**: Extend `tag_note`/`untag_note` to accept `str | List[str]` instead of separate `bulk_tag_notes`

**Accepted for separate PR:** `restore_from_trash` with three changes:
- Add `_clear_note_cache()` after the mutation
- Rename test file to `test_*.py` for pytest discovery
- Use uppercase keys (`OPERATION:`, `STATUS:`) to match existing output format

### Upstream Contribution Workflow

For PRs to alondmnt, create a branch from `upstream/main`:
```bash
git fetch upstream
git checkout -b fix/restore-from-trash upstream/main
# Make changes, test, submit PR to alondmnt/joplin-mcp
```

## Development Setup

```bash
cd /Users/mattheworlando/Documents/Projects/Code_Projects/joplin-mcp
source /Users/mattheworlando/miniforge3/etc/profile.d/conda.sh && conda activate joplin-mcp
pip install -e .       # editable install — code edits take effect on MCP server reload
pip install -e ".[dev]" # includes pytest, black, ruff, mypy
```

**macOS permissions**: `python3.13` needs Full Disk Access (System Settings > Privacy & Security) because Claude Desktop spawns it as a subprocess without TCC propagation.

**Dev workflow** (edit code, reload, test — no pip install or app restart):
1. Edit source files in `src/joplin_mcp/`
2. Run `/mcp` in Claude Code to reload the server
3. Changes are live

## Development Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_config.py

# Format and lint
black src/ tests/ && ruff check src/ tests/ && mypy src/

# Test server locally
PYTHONPATH=src python -m joplin_mcp.server
```

**Manual MCP testing**: Use the "Testing" notebook in Joplin for test notes, tags, etc.

## Architecture

FastMCP-based MCP server providing AI assistants access to Joplin notes. Based on alondmnt's v0.7.1 modular structure with our additions.

### Source Layout

| File | Contents |
|------|----------|
| `src/joplin_mcp/fastmcp_server.py` | Shared infrastructure: validators, converters, client, pagination, search helpers, formatting |
| `src/joplin_mcp/formatting.py` | `ItemType` enum, `format_*_success`, pagination header/summary |
| `src/joplin_mcp/content_utils.py` | Markdown parsing, TOC, previews, timestamps |
| `src/joplin_mcp/notebook_utils.py` | Notebook lookup by name/path, caching |
| `src/joplin_mcp/revision_utils.py` | Revision diff/reconstruct logic, `save_note_revision()` |
| `src/joplin_mcp/config.py` | Configuration: JSON/YAML/env, tool permissions, content exposure |
| `src/joplin_mcp/server.py` | Entry point (`joplin-mcp-server` CLI) |
| `src/joplin_mcp/tools/notes.py` | Note tools: get, create, update, edit, delete, find, links (alondmnt's) |
| `src/joplin_mcp/tools/notes_bulk.py` | **Our additions**: move_note, bulk_move_notes, search_and_bulk_update_preview/execute |
| `src/joplin_mcp/tools/notebooks.py` | Notebook CRUD (alondmnt's) |
| `src/joplin_mcp/tools/tags.py` | Tag CRUD + tag_note/untag_note (alondmnt's) |
| `src/joplin_mcp/tools/tags_bulk.py` | **Our additions**: bulk_tag_notes, strip_note_tags |
| `src/joplin_mcp/tools/trash.py` | **Our additions**: list_trash, restore_from_trash |
| `src/joplin_mcp/tools/notes_revisions.py` | **Our additions**: get_note_history, restore_note_revision, manually_backup_note |
| `src/joplin_mcp/tools/backup_database.py` | **Our addition**: backup_database |
| `src/joplin_mcp/tools/field_helpers.py` | **Our addition**: JOPLIN_NOTE_FIELDS registry, _search_notes, _parse_update_params |

### Tool Inventory

**Read-only (15 tools):**
- **System**: `ping_joplin`
- **Note Retrieval**: `get_note` (smart TOC/section/line reading), `get_links` (outgoing + backlinks)
- **Search**: `find_notes`, `find_notes_with_tag`, `find_notes_in_notebook`, `find_in_note`, `get_all_notes`
- **Notebooks and Tags**: `list_notebooks`, `list_tags`, `get_tags_by_note`
- **Bulk Preview**: `search_and_bulk_update_preview`
- **Trash**: `list_trash`
- **History**: `get_note_history`

**Write operations (18 tools):**
- **Notes**: `create_note`, `update_note`, `edit_note`, `delete_note` (soft-delete), `move_note`
- **Bulk**: `bulk_move_notes`, `search_and_bulk_update_execute`, `strip_note_tags`, `bulk_tag_notes`
- **Notebooks**: `create_notebook`, `update_notebook`, `delete_notebook` (soft-delete)
- **Tags**: `create_tag`, `update_tag`, `delete_tag` (**permanent**), `tag_note`, `untag_note`
- **Recovery**: `restore_from_trash`, `restore_note_revision`, `manually_backup_note`
- **Backup**: `backup_database`

### Key Patterns

- **Modular tools**: Each `tools/*.py` file registers tools via `@create_tool` decorator
- **Shared search**: `_search_notes()` in `field_helpers.py` — two-phase (API search + Python post-filter). Both preview and execute call this identically.
- **Field registry**: `JOPLIN_NOTE_FIELDS` in `field_helpers.py` — maps field names to type converters. Used by bulk update tools.
- **Tool permissions**: Controlled via config file (`joplin-mcp.json`). Tools default to enabled/disabled per `DEFAULT_TOOLS` in `config.py`.
- **Safety**: `delete_note`/`delete_notebook` soft-delete to trash. `permanent=1` intentionally not exposed. `search_and_bulk_update_execute` requires preview first. Auto-backup revisions before title/body overwrites.

### Configuration

Active config: `~/.joplin-mcp.json` (checked first by `auto_discover()`). Must be valid JSON — no comments.

Config search order: `~/.joplin-mcp.json` > `~/.config/joplin-mcp/config.json` > `./joplin-mcp.json`

MCP server config for Claude Code: global `mcpServers` in `~/.claude.json` — launches `joplin-mcp-server` with env vars for token/host/port.

## Joplin API Notes

**Unexposed capabilities** worth knowing about:
- **Resources/Attachments**: Full CRUD + OCR text extraction. `joppy` has all methods — unused.
- **Events API**: Activity feed with cursor-based pagination, 90-day retention.
- **Search operators**: `title:`, `body:`, `tag:`, `notebook:`, `created:`, `updated:`, `due:`, `type:`, `iscompleted:`, `resource:`, `sourceurl:`, `any:1` (OR), `-` (negation), `*` (wildcard).

## TODO: Future Development

### Upstream Contributions (accepted by alondmnt)
- [ ] `restore_from_trash` standalone PR (with cache clearing, test naming, output format changes)
- [ ] #20 — Trash listing via `find_notes(trash=True)`
- [ ] #21 — Moving notes via `notebook_name` on `update_note`
- [ ] #22 — Bulk tagging via `str | List[str]` on `tag_note`/`untag_note`

### Our Fork Enhancements
- [ ] Enhanced notebook hierarchy: Add `parent_id`/`parent_notebook` to `update_notebook()`
- [ ] `get_recent_changes`: Expose Joplin events API
- [ ] Resource/attachment management tools
- [ ] Document Joplin search operators in tool descriptions

### Infrastructure
- [ ] Extract Docker/install infrastructure from `extract/mcp-docker-dev` into separate `mcp-docker-dev` repo
- [ ] **Direct SQLite read layer in joplin-mcp** — the Joplin REST API has no server-side filtering (no WHERE-clause params, no field-value filters on collection endpoints). All filtering is done client-side in Python after fetching full result sets via joppy. This affects trash listing, notebook-scoped queries, todo filtering, and any field-based search. Two options:
  - **Option A (preferred): Add SQLite reader directly to joplin-mcp.** Read-only queries against `~/.config/joplin-desktop/database.sqlite` for efficient filtered reads; keep joppy/REST API for writes (which need Joplin's sync/indexing). This belongs in joplin-mcp, not in joppy — joppy is a REST client and has no SQLite basis.
  - **Option B: Contribute filtering params to Joplin's REST API.** Would require forking/PR to `laurent22/joplin` itself — much heavier overhead for uncertain acceptance. The API appears intentionally minimal.
  - **Design considerations for hybrid SQLite-read / REST-write**:
    - SQLite reads return note IDs; writes pass those IDs directly to joppy REST calls. The MCP agent never handles raw ID lists — the tool internally pipes SQLite query results to REST update calls.
    - Preview/execute pattern needs a proper safety check. Current `first_title` + `expected_count` verification is weak. Should compare the exact set of note IDs between preview and execute (e.g., hash of sorted ID list) to catch any drift.
    - May need a dry-run mode for updates: SQLite query shows what would change, user confirms, then REST applies. Similar to current `search_and_bulk_update_preview` but with accurate counts from SQLite rather than overfetched/post-filtered results.
  - **Caveat**: Direct SQLite access assumes local filesystem (same host as Joplin Desktop). Remote HTTP MCP transport would break this, but would also break `backup_database` and other filesystem-dependent features — a broader re-engineering at that point.
