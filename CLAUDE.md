# joplin-mcp

FastMCP-based MCP server giving AI assistants access to Joplin notes. A fork of alondmnt/joplin-mcp v0.7.1, adding 12 tools (bulk operations, trash, revisions, database backup), a dashboard subpackage that renders Joplin queries to Markdown tables, and an mdsync subpackage that round-trips local `.md` files against Joplin notes.

## Project

### State

**Live project state** is auto-imported from STATUS.md below. To update it — capturing emergent items, reclassifying threads, or grooming state — invoke `/session-checkpoint` (mid-session) or `/session-shutdown` (session end).

@STATUS.md

Run reports from autonomous prioritization passes accumulate in `PROGRESS.md` at the repo root. It is deliberately NOT `@`-imported — read it on demand when you need the reasoning behind the current ranking.

### Overview

Joplin is a local-first note-taking application; its desktop client exposes a Web Clipper REST API on `localhost:41184`. This project wraps that API as an MCP server so AI assistants can read, search, and edit a personal Joplin corpus directly.

Because the server talks to a locally-running Joplin Desktop, several capabilities — database backup, mdsync file round-tripping, and any future direct-SQLite read layer — assume the server and the Joplin data live on the same host. A remote HTTP transport would break all of them together.

The fork exists to carry tools upstream declined to take as-is; see "Upstream Relationship" for which additions are being folded back into alondmnt's interfaces and which stay fork-local.

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

## Environment

### Software

```bash
cd ~/projects/dev/joplin-mcp
source /Users/mattheworlando/miniforge3/etc/profile.d/conda.sh && conda activate joplin-mcp
pip install -e .       # editable install — code edits take effect on MCP server reload
pip install -e ".[dev]" # includes pytest, black, ruff, mypy
```

**macOS permissions**: `python3.13` needs Full Disk Access (System Settings > Privacy & Security) because Claude Desktop spawns it as a subprocess without TCC propagation.

**Dev workflow** (edit code, reload, test — no pip install or app restart):
1. Edit source files in `src/joplin_mcp/`
2. Run `/mcp` in Claude Code to reload the server
3. Changes are live

## Architecture

FastMCP-based MCP server providing AI assistants access to Joplin notes. Based on alondmnt's v0.7.1 modular structure with our additions.

### Code

How the server is organized and how a request flows through it: the shared infrastructure layer, the per-domain tool modules that register against it, and the two subpackages that ride the same client and config.

#### Tool Inventory

38 tools are defined in total. Which of them a running server actually exposes depends on the per-tool permissions in the active config — see "Configuration" below.

**Read-only (14 tools):**
- **System**: `ping_joplin`
- **Note Retrieval**: `get_note` (smart TOC/section/line reading), `get_links` (outgoing + backlinks)
- **Search**: `find_notes`, `find_notes_with_tag`, `find_notes_in_notebook`, `find_in_note`, `get_all_notes`
- **Notebooks and Tags**: `list_notebooks`, `list_tags`, `get_tags_by_note`
- **Bulk Preview**: `search_and_bulk_update_preview`
- **Trash**: `list_trash`
- **History**: `get_note_history`

**Write operations (24 tools):**
- **Notes**: `create_note`, `update_note`, `edit_note`, `delete_note` (soft-delete), `move_note`
- **Bulk**: `bulk_move_notes`, `search_and_bulk_update_execute`, `strip_note_tags`, `bulk_tag_notes`
- **Notebooks**: `create_notebook`, `update_notebook`, `delete_notebook` (soft-delete)
- **Tags**: `create_tag`, `update_tag`, `delete_tag` (**permanent**), `tag_note`, `untag_note`
- **Recovery**: `restore_from_trash`, `restore_note_revision`, `manually_backup_note`
- **Backup**: `backup_database`
- **File round-trip (mdsync)**: `update_note_from_file`, `push_md_file`, `pull_note_to_file` (pull is read-only on Joplin but writes local files; all assume server and files share a host)

#### Key Patterns

- **Modular tools**: Each `tools/*.py` file registers tools via `@create_tool` decorator
- **Shared search**: `_search_notes()` in `field_helpers.py` — two-phase (API search + Python post-filter). Both preview and execute call this identically.
- **Field registry**: `JOPLIN_NOTE_FIELDS` in `field_helpers.py` — maps field names to type converters. Used by bulk update tools.
- **Tool permissions**: Controlled via config file (`joplin-mcp.json`). Tools default to enabled/disabled per `DEFAULT_TOOLS` in `config.py`.
- **Safety**: `delete_note`/`delete_notebook` soft-delete to trash. `permanent=1` intentionally not exposed. `search_and_bulk_update_execute` requires preview first. Auto-backup revisions before title/body overwrites.

#### Configuration

Active config: `~/.joplin-mcp.json` (checked first by `auto_discover()`). Must be valid JSON — no comments.

Config search order: `~/.joplin-mcp.json` > `~/.config/joplin-mcp/config.json` > `./joplin-mcp.json`

MCP server config for Claude Code: global `mcpServers` in `~/.claude.json` — launches `joplin-mcp-server` with env vars for token/host/port.

#### Dashboard Subpackage

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

Consumer projects own their config files; joplin-mcp does not track or reference them. Two dirs under `src/joplin_mcp/dashboard/` exist to organize the relationship: `schemas/` (tracked) holds JSON Schema validators for the config format; `configs/` (gitignored) holds symlinks into consumer repos — e.g., `configs/job_search.yaml` → `~/projects/dev/job_search/dashboards/job_search.yaml`. Each dir has a `README.md` with the full convention; full key-by-key spec lives in `docs/dashboard_config.md` and the machine schema in `schemas/dashboard_config.schema.yaml`.

**Validation:** `joplin-dashboard --validate <config>` parses + validates without rendering (exit 0/2). Validation runs at `load_config()` entry; multi-error reporting via `jsonschema.Draft202012Validator.iter_errors()` with JSON Pointer paths.

**Symlink-discovery:** `joplin-dashboard <name>` (bare name, no path separator, no `.yaml` extension) resolves to `configs/<name>.yaml`; broken symlinks surface as clean errors.

**Backend decision (recorded 2026-05-06):** REST API for v1 via existing joplin-mcp client. Pluggable Loader interface in place; `JoplinSqliteLoader` deferred to v1.5 with documented triggers (sync-index staleness from #11631, OCR-text bug from #12128, or use cases needing Joplin Desktop closed). Verified empirically: `any:1 tag:A tag:B notebook:X notebook:Y` returns `(A∪B)∩(X∪Y)` correctly. See `research_output/2026-05-06_joplin-backend-decision.md`.

**Architectural note:** The dashboard subpackage is technically a REST-API consumer rather than an MCP feature, but lives in joplin-mcp because it reuses joplin-mcp's joppy client wrapper, config/auth handling, install path, and test infrastructure. If it grows beyond what fits cleanly, promote to a sibling repo `joplin-dashboard/`.

**Tests:** `tests/test_dashboard_*.py` (matching pytest conventions of the rest of joplin-mcp).

**Implementation plans (completed):**
- `markdowns/plans_completed/CLAUDE.PLANS_20260507_dashboard_script_mini_plan.md` — seed mini-plan for the subpackage
- `markdowns/plans_completed/CLAUDE.PLANS_20260515_dashboard-config-schema-validation.md` — schema validation + `--validate` + symlink-discovery

#### Mdsync Subpackage

The `joplin_mcp.mdsync` subpackage round-trips a local .md file ↔ a Joplin note. Primary workflow is **pull-edit-update**: pull a note to a file, edit locally (md_tools, editors, Claude Code), update it back. File bytes travel **verbatim** — user content (including frontmatter) is never parsed or re-serialized; bookkeeping lives in a fenced `mdsync:` block spliced into the file's frontmatter by exact line surgery.

**Layout:**

| File | Contents |
|------|----------|
| `mdsync/block.py` | `SyncMeta`; fenced-block + drift-region line splice; `body_hash`; `canonical_body` |
| `mdsync/transport.py` | The three verbs (`update_file`, `push_file`, `pull_note`), shared by CLI + MCP tools |
| `mdsync/cli.py` | `joplin-mdsync update|push|pull` entry point (bare `<file>` = update) |
| `tools/notes_files.py` | Thin MCP wrappers: `update_note_from_file`, `push_md_file`, `pull_note_to_file` |

**The block** (inside the file's frontmatter, `# mdsync-begin/end` comment fences): API-verbatim keys `id`, `title`, `parent_id`, `tags` + `notebook` (name, informational — the API routes only by `parent_id`), `synced`, `prior_Joplin_hash`, `current_Joplin_hash`, `markdown_bak`. Title round-trips via the block (H1 never touched — avoids the literal-`#` external-editor gotcha).

**Verbs (all GET first):**
- `update` (default): the only verb that drift-checks. Drift = `prior_Joplin_hash` (body hash at last sync point; refreshed by every successful GET/PUT) ≠ just-in-time hash of the fetched remote body. On drift: revision backup, PUT anyway, warning leads the payload AND a deletable fenced drift region (warning + unified diff; `--no-diff`) is persisted at the top of the body — never pushed, excluded from hashes, auto-dropped on next rewrite. Tags: `tags:` line present → reconciled onto the note (missing tags created); line absent → untouched (the PUT cannot affect tags); `[]` → remove all.
- `push`: create-only; refuses if the note exists (bound id, or exact-title match in target notebook) naming both next steps; `--force` clobbers in place (revision backup, no drift ceremony) and binds unbound files.
- `pull`: note → file; local unsynced edits are backed up to `<stem>_<ts>.md.bak` and recorded as `markdown_bak:` in the block.

**Rebinding a damaged file:** the binding lives in the file's frontmatter, so a tool that rewrites frontmatter can sever it. `md_tools` holds frontmatter opaque and reattaches it byte-verbatim on every verb, so its section ops are safe. If some other editor does mangle a file, recover with `joplin-mdsync pull --note-id <id>` — the damaged file is backed up to `.bak` and the block is rewritten from the note.

**Tests:** `tests/test_mdsync_{block,transport,cli}.py` + `tests/fixtures/mdsync_*.md` (mocked joppy client; byte-identity of user YAML is the load-bearing assertion).

**Plan:** `markdowns/plans_draft/` → archived on commit (mini-plan iterated via /framing + adversarial agent review; drift model and verb semantics user-ruled 2026-06-05/06).

### Project Dir

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
| `src/joplin_mcp/tools/notes_files.py` | **Our addition**: update_note_from_file, push_md_file, pull_note_to_file (thin wrappers over `mdsync/`) |
| `src/joplin_mcp/tools/backup_database.py` | **Our addition**: backup_database |
| `src/joplin_mcp/imports/` | Upstream (alondmnt): `import_from_file` + MarkdownImporter (bulk file ingest; distinct from mdsync round-trip) |
| `src/joplin_mcp/tools/field_helpers.py` | **Our addition**: JOPLIN_NOTE_FIELDS registry, _search_notes, _parse_update_params |
| `src/joplin_mcp/dashboard/` | **Our addition**: dashboard subpackage (config-driven Joplin → Markdown table renderer). See "Dashboard Subpackage" below. |
| `src/joplin_mcp/mdsync/` | **Our addition**: mdsync subpackage (round-trip .md file ↔ Joplin note; `joplin-mdsync` CLI). See "Mdsync Subpackage" below. |

## Protocols

### Code Development

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

## Learnings

Durable knowledge. Append-only.

### Design Decisions

#### In-process MCP-layer testing via fastmcp.Client

- **Date:** 2026-06-06
- **Files:** `test_scripts/mdsync_mcp_live_test.py` (gitignored; rerunnable)
- **Problem:** New MCP tools cannot be exercised through the live Claude session until the user runs `/mcp`, because the server reload is user-side. That leaves the registration / schema / invocation path untested at implementation time.
- **Chosen approach:** `fastmcp.Client(mcp_instance)` over the in-memory transport against the imported server instance. This exercises tool registration, pydantic schema validation, invocation, and the error path (`with_client_error_handling` wrapping) against live Joplin — missing only the desktop JSON-RPC hop. The pattern is reusable for every future tool addition.
- **Alternatives rejected:** calling the decorated functions directly (bypasses the schema layer — `@create_tool` returns a `FunctionTool`, not a callable); waiting for the user's `/mcp` reload (blocks the dev loop).

#### Artifact sizes stay out of published tool docs

- **Date:** 2026-06-09
- **Files:** `src/joplin_mcp/tools/backup_database.py`
- **Problem:** A first draft of the backup docstrings stated each backup is "~98 MB" — a contingent fact about one particular database at one moment, not a property of the tool.
- **Chosen approach:** Describe a backup as "a full copy of the Joplin database", with no size figure. The runtime `SIZE:` field in the tool's success output stays, because it is a real per-invocation measurement of the actual file rather than a hardcoded documentation claim.
- **Alternatives rejected:** keeping "~98 MB" as a rough guide — inappropriate for a tool that ships to other people.

#### Manual database backups are never pruned

- **Date:** 2026-06-09
- **Files:** `src/joplin_mcp/tools/backup_database.py`
- **Problem:** Automatic (`"daily"`) backups are guarded to once per calendar day and retained to the last 10, but manual backups accumulate without bound — the folder had reached 1.3 GB when this was investigated.
- **Chosen approach:** Keep manual backups unbounded and document the asymmetry in the docstrings instead of pruning them. A manual backup is taken deliberately, before something risky, so the user wants it retained. The required `label` argument makes each one self-describing, which is what actually made the folder navigable.
- **Alternatives rejected:** an automated prune helper — the user wants explicit control over retention and wants existing snapshots kept. Revisit only if folder size becomes a problem again.

### Gotchas

- **PyYAML `default_flow_style=None` collapses leaf-only mappings** (2026-06-06): a dict whose values are all scalars renders as a single flow line (`key: {a: 1, b: 2}`), while the presence of any nested collection switches it to block style — so the output FORMAT changes based on the CONTENT. The mdsync block silently went one-line whenever `tags` was absent. Mitigation: use `default_flow_style=False` for any canonical line-oriented machine output.
- **This repo's HEAD is not clean under the installed black** (2026-06-09): `git show HEAD:src/joplin_mcp/tools/backup_database.py | black --check -` reports "would reformat" under black 26.1.0, and `tests/pr_tests.py` already ships 9 `I001` isort violations from its inline-per-test imports. The committed code predates this formatter version, so the project does not in practice enforce it. Mitigation: never run a blanket `black` / `ruff --fix` as "cleanup" — it produces a large diff across unrelated pre-existing lines. Match the surrounding multi-line style for new code and stay within 88 columns.

### Dead Ends

- **python-frontmatter parse-then-reserialize for user-owned YAML** (2026-06-06): tried storing mdsync metadata in the file's frontmatter via python-frontmatter merge/strip; failed because PyYAML re-serialization destroys hand-maintained formatting — comments deleted, keys alphabetized, quoting and list style rewritten. The fix was exact line-splice of machine-owned spans, never parsing user content. Revisit only if a genuinely format-preserving YAML round-trip becomes load-bearing (ruamel.yaml is only "mostly" preserving).
- **Timestamp-based drift detection for mdsync** (2026-06-06): tried comparing a note's `updated_time` against a stored snapshot; failed because our own PUT bumps the stamp (forcing a re-fetch dance to avoid self-triggered drift) and because metadata-only changes such as a retitle or notebook move false-positive as body drift. Body-hash comparison (`prior_Joplin_hash` vs a just-in-time `current_Joplin_hash`) detects exactly body drift with no timestamp bookkeeping. Revisit only if body hashing proves insufficient.
- **Collapsing a return to a single-line f-string for formatter stability** (2026-06-09): rewrote a FAILED-branch `return (...)` as one f-string to stop black reformatting it into awkward implicit concatenation; failed on two counts — it broke consistency with the file's other multi-line `OPERATION` / `STATUS` / `MESSAGE` return blocks, and HEAD is not black-clean anyway, so "black-stability" was never a real constraint. Reverted to the multi-line form. Do not optimize for a formatter the repo does not enforce.

## Reference

### Skills

No project-local skills (`.claude/skills/`) are defined. The skills this project is worked with — `/project-cleanup`, `/session-shutdown`, `/claude-md-review`, and the rest — are global; see user-global CLAUDE.md.

### Project Docs

| Path | Contents |
|------|----------|
| `docs/dashboard_config.md` | Human-readable, key-by-key spec for the dashboard YAML config format |
| `docs/troubleshooting.md` | Operational troubleshooting notes |
| `docs/content-privacy.md` | Content-exposure / privacy configuration notes |
| `docs/enhancement-proposal.md` | Enhancement proposal write-up |
| `src/joplin_mcp/dashboard/schemas/` | Tracked JSON Schema validators for dashboard configs (`dashboard_config.schema.yaml`, Draft 2020-12) |
| `markdowns/plans_completed/` | Shipped implementation plans (tracked); referenced from commit messages |
| `markdowns/session_archive/` | Consumed `SESSION_COMPACT_*.md` files and per-run `SWEPT_*.md` completed-entry archives (tracked) |

`markdowns/plans_draft/` and `markdowns/plans_backup/` are gitignored working space, not durable docs.

### Active

The `@`-import surface — files pulled into context automatically at session start. Listed here without the `@` so they are indexed rather than re-imported:

- `STATUS.md` → imported under Project → State. It in turn `@`-imports any un-archived `markdowns/SESSION_COMPACT_*.md` files.

### Passive

Read-on-demand references and external links.

- Upstream repository: https://github.com/alondmnt/joplin-mcp
- This fork: https://github.com/MatthewOGoodman/joplin-mcp
- Joplin data API: https://joplinapp.org/help/api/references/rest_api

#### Joplin API Notes

**Unexposed capabilities** worth knowing about:
- **Resources/Attachments**: Full CRUD + OCR text extraction. `joppy` has all methods — unused.
- **Events API**: Activity feed with cursor-based pagination, 90-day retention.
- **Search operators**: `title:`, `body:`, `tag:`, `notebook:`, `created:`, `updated:`, `due:`, `type:`, `iscompleted:`, `resource:`, `sourceurl:`, `any:1` (OR), `-` (negation), `*` (wildcard).

## Loose Ends

Transient holding pen — content that is legitimate but not yet placed, awaiting a human call on where it belongs. Drained by `/claude-md-review`; this section is compliant only when empty.

(NEEDS-REVIEW: decide the permanent home for the "Design Notes" subtree below — these are durable problem statements and rejected alternatives for features that are mostly NOT yet implemented, so they do not fit `Learnings → Design Decisions` (scoped to implemented features) and they are too substantive to be a `Reference → Passive` link list. Options: (a) split them — the implemented ones become Design Decisions, the rest move to their STATUS.md threads; (b) keep them together under a new Reference facet for pre-implementation rationale. Needs a human because the schema does not name a facet for durable rationale about unbuilt work, and each STATUS.md thread currently cross-references these sections by name.)

### Design Notes

Active work is tracked in [STATUS.md](STATUS.md) above. The following are durable design notes — problem statements, proposed solutions, rejected alternatives — that outlive the threads they came from. They serve as reference material when the corresponding STATUS.md thread is picked up.

#### Design: joplin-dashboard global discoverability (wrapper + claude-wrangler-manifest.txt)

**Problem.** The `joplin-dashboard` CLI is only on PATH while the `joplin-mcp` conda env is active. Consumer projects (e.g. `~/projects/dev/job_search/`) want to invoke it from any non-interactive shell without per-call conda activation. Hardcoding the env's bin path (`~/miniforge3/envs/joplin-mcp/bin/joplin-dashboard`) would make the wrapper machine-specific (assumes miniforge install path AND env name).

**Selected solution.** Add a tracked wrapper at `bin/joplin-dashboard` that resolves the env path dynamically at invocation time via `conda info --base`. Add a `claude-wrangler-manifest.txt` so claude-wrangler's universal symlink installer (`~/projects/dev/claude-wrangler/install.sh`) creates a symlink at `~/.claude/joplin-dashboard` (already on user's PATH).

**Approaches considered and rejected:**

- *Hardcoded wrapper* (`exec ~/miniforge3/envs/joplin-mcp/bin/joplin-dashboard "$@"`) — machine-specific.
- *Install-time generated wrapper, gitignored* — faster per call (no `conda info` subprocess) but requires `install.py` changes and breaks on env rename / conda-flavor switch unless reinstalled. Brittle.
- *Add env-bin sources to claude-wrangler's manifest format* (e.g., `target:env:joplin-mcp:bin/script`) — extends a generic tool for one symlink. YAGNI.
- *PATH-prepend the env's bin directory in `.zshenv`* — leaks every env binary to global PATH (joplin-mcp-server, joppy, fastmcp, etc.). Pollution.
- *pipx install* — would be a SECOND install of joplin-mcp, breaking the editable-install dev sync.

Dynamic-resolution wrapper wins: portable, tracked, works through claude-wrangler's existing installer with no installer changes. Adds ~150ms `conda info --base` subprocess per call — imperceptible for manual regen. Drift-resistant.

**Why no extension to claude-wrangler.** claude-wrangler's `install.sh` requires `source` paths inside the project repo (`SOURCE_PATH="$REPO_DIR/$SOURCE_REL"`). The wrapper-in-repo pattern fits without requiring claude-wrangler changes.

**Files to add when implementing:**

`bin/joplin-dashboard`:
```bash
#!/usr/bin/env bash
# Wrapper that delegates to the env-installed joplin-dashboard CLI.
# Resolves conda env dynamically; portable across miniforge/anaconda/miniconda.
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

`claude-wrangler-manifest.txt`:
```
~/.claude/joplin-dashboard:bin/joplin-dashboard
```

Then run: `~/projects/dev/claude-wrangler/install.sh --force ~/projects/dev/joplin-mcp` (force overrides the interim symlink documented below).

**Interim workaround currently in place.** A direct symlink was created from the job_search session to unblock dashboard invocation in non-conda shells immediately:

```
~/.claude/joplin-dashboard → ~/miniforge3/envs/joplin-mcp/bin/joplin-dashboard
```

Hardcoded and machine-specific. Exists ONLY so job_search could finish testing the dashboard pipeline end-to-end without waiting for the proper wrapper. claude-wrangler's installer will detect this as a "wrong-target symlink" when the wrapper lands and warn-and-skip unless invoked with `--force`. Use `--force` once to overwrite.

#### Design: CLAUDE.md cross-branch persistence (proposed; needs /framing)

**Problem.** CLAUDE.md is tracked on the main dev branch but disappears when checking out other branches (e.g., clean PR branches off `upstream/main`). Claude Code loses project context mid-session.

**Proposed architecture (not final).** CLAUDE.md on `feature/dev` contains a `## PROJ_SHARED_CLAUDE` section with cross-branch content (TODOs, branch strategy, upstream relationship, architecture). This section is the canonical tracked version. Before branch switch, it's extracted to an untracked `PROJ_SHARED_CLAUDE.md` that floats across branches. On return, changes are merged back.

**Proposed design — single untracked floating file with branch-keyed sections:**

```
# PROJ_SHARED_CLAUDE
## PROJ_SHARED_CLAUDE_main
## PROJ_SHARED_CLAUDE_feature/dev
## PROJ_SHARED_CLAUDE_pr/restore-from-trash
```

Post-checkout hook uses `md_tools insert` to add/update the section for the current branch. Accumulation works well (new TODOs, notes, context). Edits/deletions to shared content are harder — corrections noted in the branch section, resolved during merge-back on `feature/dev`. Critical for the hook: must NOT overwrite existing content in other branch sections — `md_tools insert` preferred over `cp`.

**Scope-extension note (2026-05-06).** Once Plan 1 (Project State Hygiene — see `claude-wrangler/CLAUDE.md` Active Work) lands, this floating-file design must also carry `STATUS.md`. Either extend to a sibling `PROJ_SHARED_STATUS.md`, or merge both into a single floating file with branch-keyed sections per artifact.

Working proposal only — `/framing` should survey better solutions (post-checkout hook, separate tracked branch) before implementing.

#### Design: Upstream sync strategy (open questions)

PR #23 merged into alondmnt/joplin-mcp on 2026-04-17 (`restore_from_trash` + `find_notes(trash=True)` + docstring fixes). Our `main` and `feature/dev` don't have these changes from upstream's side. Open questions before settling on a sync workflow:

- Is our code structure clean enough to rebase on upstream? Our 12 tools in `tools/*.py` are additive, but `fastmcp_server.py` and `formatting.py` have modifications.
- `git merge upstream/main` vs `git rebase --onto upstream/main` for our branches?
- How to handle divergence if alondmnt modifies files we also modified?
- Any other upstream changes since v0.7.1 besides PR #23?

Affects both `main` and `feature/dev`. The goal is to pull upstream changes readily.

#### Design: MCP packaging / distribution infrastructure (parked)

The `extract/mcp-docker-dev` branch (snapshot of old monolithic branch) contains Docker development toolkit, deployment modes, install enhancements, and config management (`mcp-config-manager.sh`). Original plan was to extract into separate `MatthewOGoodman/mcp-docker-dev` repo as reusable infrastructure for any MCP project. Status: parked, not started.

#### Design: Direct SQLite read layer

The Joplin REST API has no server-side filtering — no WHERE-clause params, no field-value filters on collection endpoints. All filtering is done client-side in Python after fetching full result sets via joppy. This affects trash listing, notebook-scoped queries, todo filtering, and any field-based search.

**Two options:**

- **Option A (preferred): Add SQLite reader directly to joplin-mcp.** Read-only queries against `~/.config/joplin-desktop/database.sqlite` for efficient filtered reads; keep joppy/REST API for writes (which need Joplin's sync/indexing). Belongs in joplin-mcp, not in joppy — joppy is a REST client and has no SQLite basis.
- **Option B: Contribute filtering params to Joplin's REST API.** Would require forking/PR to `laurent22/joplin` itself — much heavier overhead for uncertain acceptance. The API appears intentionally minimal.

**Design considerations for hybrid SQLite-read / REST-write:**

- SQLite reads return note IDs; writes pass those IDs directly to joppy REST calls. The MCP agent never handles raw ID lists — the tool internally pipes SQLite query results to REST update calls.
- Preview/execute pattern needs a proper safety check. Current `first_title` + `expected_count` verification is weak. Should compare the exact set of note IDs between preview and execute (e.g., hash of sorted ID list) to catch any drift.
- May need a dry-run mode for updates: SQLite query shows what would change, user confirms, then REST applies. Similar to current `search_and_bulk_update_preview` but with accurate counts from SQLite rather than overfetched/post-filtered results.

**Caveat:** Direct SQLite access assumes local filesystem (same host as Joplin Desktop). Remote HTTP MCP transport would break this, but would also break `backup_database` and other filesystem-dependent features — a broader re-engineering at that point.
