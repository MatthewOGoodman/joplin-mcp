# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

**Live project state** is auto-imported from STATUS.md below. To update — capturing emergent items, reclassifying threads, or grooming state — invoke `/session-checkpoint` (mid-session) or `/session-shutdown` (session end).

@STATUS.md

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
| `src/joplin_mcp/dashboard/` | **Our addition**: dashboard subpackage (config-driven Joplin → Markdown table renderer). See "Dashboard Subpackage" below. |

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

### Dashboard Subpackage

The `joplin_mcp.dashboard` subpackage is a config-driven utility that queries Joplin (via REST API) and renders a Markdown table-style dashboard to a file. First consumer is the `job_search` project (`~/projects/dev/job_search/`); designed for reuse across other GTD aggregations where the table IS the answer (no priority triage required).

**Layout:**

| File | Contents |
|------|----------|
| `dashboard/types.py` | `NoteRecord` dataclass; joppy time normalization to UTC datetime |
| `dashboard/config.py` | `DashboardConfig` / `SectionConfig` dataclasses; YAML config loading and validation |
| `dashboard/loader.py` | `Loader` ABC and `JoplinRestLoader` (joppy-backed). v1.5 will add `JoplinSqliteLoader` per CLAUDE.md TODO. |
| `dashboard/render.py` | Pure rendering: `render_section`, `assemble_dashboard`, sort, group-by-tag-prefix, Markdown escape |
| `dashboard/cli.py` | `joplin-dashboard <config.yaml>` entry point with `--dry-run` |

**CLI:** Registered as `joplin-dashboard` via `[project.scripts]` in `pyproject.toml`. After `pip install -e .`, runs from any cwd.

**Dependency:** `python-frontmatter>=1.0.0` (pulled in via `pyproject.toml` deps). Used to parse YAML frontmatter from note bodies for cross-reference fields and arbitrary frontmatter columns.

**YAML config schema** (consumer-owned; the CLI accepts a path to any such YAML file):

```yaml
output: /path/to/DASHBOARD.md
header: |
  # My Dashboard
  _Auto-generated. Last refresh: {timestamp}_

sections:
  - title: "Section A"
    notebook: "Notebook Path"
    tags_required: ["Tag: Foo"]
    tags_excluded: []
    extra_query: null              # optional raw appended to /search query
    columns: [title, tags, updated]
    group_by_tag_prefix: null      # or e.g. "Prefix " for prefix-grouped sections
    sort_by: updated               # built-in: title|updated|created|notebook; else looks up frontmatter field
    sort_dir: desc                 # asc|desc
```

Consumer projects own their config files; joplin-mcp does not track or reference them. Two dirs under `src/joplin_mcp/dashboard/` exist to organize the relationship: `schemas/` (tracked) holds JSON Schema validators for the config format; `configs/` (gitignored) holds symlinks into consumer repos — e.g., `configs/job_search.yaml` → `~/projects/dev/job_search/dashboards/job_search.yaml`. Each dir has a `README.md` with the full convention; full key-by-key spec lives in `docs/dashboard_config.md` (pending the schema TODO).

**Backend decision (recorded 2026-05-06):** REST API for v1 via existing joplin-mcp client. Pluggable Loader interface in place; `JoplinSqliteLoader` deferred to v1.5 with documented triggers (sync-index staleness from #11631, OCR-text bug from #12128, or use cases needing Joplin Desktop closed). Verified empirically: `any:1 tag:A tag:B notebook:X notebook:Y` returns `(A∪B)∩(X∪Y)` correctly. See `research_output/2026-05-06_joplin-backend-decision.md`.

**Architectural note:** The dashboard subpackage is technically a REST-API consumer rather than an MCP feature, but lives in joplin-mcp because it reuses joplin-mcp's joppy client wrapper, config/auth handling, install path, and test infrastructure. If it grows beyond what fits cleanly, promote to a sibling repo `joplin-dashboard/`.

**Tests:** `tests/test_dashboard_*.py` (matching pytest conventions of the rest of joplin-mcp).

**Mini-plan:** `markdowns/plans_draft/dashboard_script_mini_plan.md`.

## Joplin API Notes

**Unexposed capabilities** worth knowing about:
- **Resources/Attachments**: Full CRUD + OCR text extraction. `joppy` has all methods — unused.
- **Events API**: Activity feed with cursor-based pagination, 90-day retention.
- **Search operators**: `title:`, `body:`, `tag:`, `notebook:`, `created:`, `updated:`, `due:`, `type:`, `iscompleted:`, `resource:`, `sourceurl:`, `any:1` (OR), `-` (negation), `*` (wildcard).

## TODO: Future Development

### TODO: joplin-dashboard global discoverability — wrapper + manifest.txt

**Problem.** The `joplin-dashboard` CLI script is only on PATH while the `joplin-mcp` conda env is active. Consumer projects (e.g. `~/projects/dev/job_search/`) want to invoke it from any non-interactive shell without per-call conda activation. Hardcoding the env's bin path (`~/miniforge3/envs/joplin-mcp/bin/joplin-dashboard`) would make the wrapper machine-specific (assumes miniforge install path AND env name).

**Solution.** Add a tracked wrapper at `bin/joplin-dashboard` in this repo that resolves the env path dynamically at invocation time via `conda info --base`. Then add a `manifest.txt` so claude-wrangler's universal symlink installer (`~/projects/dev/claude-wrangler/install.sh`) creates a symlink at `~/.claude/joplin-dashboard` (already on user's PATH).

**Approaches considered before settling here:**

- *Hardcoded wrapper* (`exec ~/miniforge3/envs/joplin-mcp/bin/joplin-dashboard "$@"`) — rejected as machine-specific (assumes miniforge install + env name + path).
- *Install-time generated wrapper, gitignored* — faster per call (no `conda info` subprocess) but requires `install.py` changes and breaks on env rename / conda-flavor switch unless reinstalled. Brittle.
- *Add env-bin sources to claude-wrangler's manifest format* (e.g., `target:env:joplin-mcp:bin/script`) — extends a generic tool for one symlink. YAGNI; rejected.
- *PATH-prepend the env's bin directory in `.zshenv`* — leaks every env binary to global PATH (joplin-mcp-server, joppy, fastmcp, etc.). Pollution.
- *pipx install* — would be a SECOND install of joplin-mcp, breaking the editable-install dev sync.
- The dynamic-resolution wrapper below was selected: portable, tracked, works through claude-wrangler's existing installer with no installer changes.

**Files to add (both tracked):**

`bin/joplin-dashboard`:
```bash
#!/usr/bin/env bash
# Wrapper that delegates to the env-installed joplin-dashboard CLI.
# Resolves conda env dynamically; portable across miniforge/anaconda/miniconda
# installs as long as a conda env named 'joplin-mcp' exists.
set -euo pipefail
CONDA_BASE="$(conda info --base 2>/dev/null)" || {
  echo "ERROR: conda not on PATH" >&2; exit 1
}
ENV_BIN="$CONDA_BASE/envs/joplin-mcp/bin/joplin-dashboard"
[[ -x "$ENV_BIN" ]] || {
  echo "ERROR: $ENV_BIN missing — run 'pip install -e .' in the joplin-mcp env" >&2
  exit 1
}
exec "$ENV_BIN" "$@"
```
`chmod +x bin/joplin-dashboard` after creation.

`manifest.txt`:
```
# joplin-mcp symlink manifest (consumed by ~/projects/dev/claude-wrangler/install.sh)
# Format: target:source-relative-to-repo

~/.claude/joplin-dashboard:bin/joplin-dashboard
```

**Setup command (post-implementation, run by user once):**
```bash
~/projects/dev/claude-wrangler/install.sh ~/projects/dev/joplin-mcp
```

**Why dynamic resolution and not install-time generation:**

- Adds ~150ms (`conda info --base` subprocess) per call. Imperceptible for a manual dashboard regen.
- One tracked file, identical across machines.
- No `install.py` change needed.
- Drift-resistant — surviving a dotfiles port or conda-flavor switch doesn't require reinstall.

The faster alternative (install-time-generated wrapper, gitignored, with hardcoded resolved path) is brittle and adds install-script work for marginal benefit.

**Why no extension to claude-wrangler.** claude-wrangler's `install.sh` requires `source` paths to be inside the project repo (`SOURCE_PATH="$REPO_DIR/$SOURCE_REL"`). The wrapper-in-repo pattern fits this constraint exactly without requiring claude-wrangler changes. Discussed and rejected: extending claude-wrangler's manifest format to support out-of-repo sources (e.g., env-bin) — generic but YAGNI for one symlink.

**Background.** Claude-wrangler's universal installer was verified to handle this pattern cleanly (see `~/projects/dev/claude-wrangler/install.sh` and `manifest.txt`). It supports running against any project: `install.sh /path/to/project` reads that project's `manifest.txt`. joplin-mcp would be the second project (after claude-wrangler itself) to use the universal installer, validating the design.

**Interim workaround already in place — will be overwritten by the proper solution.**

A direct symlink was created from the job_search session to unblock dashboard invocation in non-conda shells immediately:

```
~/.claude/joplin-dashboard → ~/miniforge3/envs/joplin-mcp/bin/joplin-dashboard
```

This is hardcoded and machine-specific (the exact thing the proper solution avoids). It exists ONLY so the job_search session could finish testing the dashboard pipeline end-to-end without waiting for this TODO to land.

When this TODO ships:

1. The new `bin/joplin-dashboard` wrapper exists in the repo.
2. Running `~/projects/dev/claude-wrangler/install.sh ~/projects/dev/joplin-mcp` will detect the existing symlink at `~/.claude/joplin-dashboard` as a "wrong-target symlink" (it points at the env binary; the manifest expects it to point at `~/projects/dev/joplin-mcp/bin/joplin-dashboard`).
3. claude-wrangler's installer behavior (per its docs) is to **warn and skip** in that case unless invoked with `--force`. The user (or the joplin-mcp implementer) should run `install.sh --force ~/projects/dev/joplin-mcp` once to overwrite the interim symlink with one pointing at the new wrapper.
4. Once overwritten, the interim symlink is gone — the path `~/.claude/joplin-dashboard` now resolves through the wrapper, which dynamically resolves the env binary. Same effect, machine-portable.

Until that overwrite happens, both the interim direct symlink AND the new wrapper would work at the call site (they ultimately invoke the same env binary), but only the wrapper survives a machine reorg / conda-flavor switch.

**Acceptance criteria:**

- [ ] `bin/joplin-dashboard` (tracked, executable) exists in joplin-mcp repo
- [ ] `manifest.txt` (tracked) exists with the one symlink entry
- [ ] Running `~/projects/dev/claude-wrangler/install.sh ~/projects/dev/joplin-mcp` creates / reconciles `~/.claude/joplin-dashboard` to point at `bin/joplin-dashboard`
- [ ] `joplin-dashboard --help` works from a fresh non-conda shell (already verified for the temporary symlink; should continue working through the wrapper)
- [ ] CLAUDE.md "Dashboard Subpackage" section (under Architecture) gains a one-line pointer to this wrapper + manifest pattern

### Dashboard config schema + validation
Shipped 2026-05-15. Plan: `markdowns/plans_completed/CLAUDE.PLANS_20260515_dashboard-config-schema-validation.md`.

### TODO: CLAUDE.md Cross-Branch Persistence (needs /framing + plan)

**Architecture (decided):** CLAUDE.md on `feature/dev` contains a `## PROJ_SHARED_CLAUDE` section with cross-branch content (TODOs, branch strategy, upstream relationship, architecture). This section is the canonical tracked version. Before branch switch, it's extracted to an untracked `PROJ_SHARED_CLAUDE.md` that floats across branches. On return, changes are merged back.

**Remaining work:**
- [ ] Define which CLAUDE.md content is shared vs branch-specific (blocked until branch roles are clearer — `feature/dev` currently mirrors `main`)
- [ ] Create the `## PROJ_SHARED_CLAUDE` section and restructure CLAUDE.md accordingly
- [ ] **Before implementing:** Apply /framing and /research to survey whether better solutions exist for cross-branch CLAUDE.md persistence. The design below is a working proposal, not a final decision.
- [ ] **Proposed design:** Single untracked `PROJ_SHARED_CLAUDE.md` with branch-keyed sections:
  ```
  # PROJ_SHARED_CLAUDE
  ## PROJ_SHARED_CLAUDE_main
  ## PROJ_SHARED_CLAUDE_feature/dev
  ## PROJ_SHARED_CLAUDE_pr/restore-from-trash
  ```
  Post-checkout hook uses `md_tools insert` to add/update the section for the current branch. Accumulation works well (new TODOs, notes, context). Edits/deletions to shared content are harder — corrections noted in the branch section, resolved during merge-back on `feature/dev`.
- [ ] Implement post-checkout hook for the above. **Critical:** must not overwrite existing content in other branch sections. `md_tools insert` preferred over `cp`.
- [ ] Implement merge-back step: on return to `feature/dev`, review branch sections and reconcile into the canonical `## PROJ_SHARED_CLAUDE` section of tracked CLAUDE.md.
- [ ] Consider whether this pattern should be generalized via claude-wrangler for other multi-branch repos
- [ ] **Scope-extension note (2026-05-06):** Once Plan 1 (Project State Hygiene — see `claude-wrangler/CLAUDE.md` Active Work, master plan `claude-wrangler/markdowns/plans_draft/CLAUDE.PLANS_20260506_vigilant-grooming-codex_PROJECT_STATE_HYGIENE_MINIPLAN.md`) lands, this floating-file design must also carry `STATUS.md`. Either extend the design to a sibling `PROJ_SHARED_STATUS.md`, or merge both into a single floating file with branch-keyed sections for each artifact. Revisit when Plan 1 is approved.

### TODO: Upstream Sync Strategy (needs plan)

PR #23 merged into alondmnt/joplin-mcp on 2026-04-17 (`restore_from_trash` + `find_notes(trash=True)` + docstring fixes). Our `main` and `feature/dev` don't have these changes from upstream's side. Need to determine:
- Whether our code structure is clean enough to rebase on upstream (our 12 tools in `tools/*.py` are additive, but `fastmcp_server.py` and `formatting.py` have modifications)
- Whether to `git merge upstream/main` or `git rebase --onto upstream/main` for our branches
- How to handle divergence if alondmnt modifies files we also modified
- Check upstream for any other changes since v0.7.1
This affects both `main` and `feature/dev`. The goal is to be able to pull upstream changes readily.

### TODO: Upstream Contributions
- [x] PR #23 merged (2026-04-17) — `restore_from_trash` + `find_notes(trash=True)` + soft-delete docstrings
- [ ] #21 — Moving notes via `notebook_name` on `update_note`
- [ ] #22 — Bulk tagging via `str | List[str]` on `tag_note`/`untag_note`

### Our Fork Enhancements
- [ ] Enhanced notebook hierarchy: Add `parent_id`/`parent_notebook` to `update_notebook()`
- [ ] `get_recent_changes`: Expose Joplin events API
- [ ] Resource/attachment management tools
- [ ] Document Joplin search operators in tool descriptions

### TODO: MCP Packaging/Distribution Infrastructure (needs plan)

The `extract/mcp-docker-dev` branch (snapshot of old monolithic branch) contains Docker development toolkit, deployment modes, install enhancements, and config management (`mcp-config-manager.sh`). Plan was to extract into separate `MatthewOGoodman/mcp-docker-dev` repo as reusable infrastructure for any MCP project. Status: parked, not started.

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
