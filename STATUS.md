# STATUS

*Last checkpoint: — | Last prioritized: 2026-05-18 09:00 | Last shutdown: 2026-05-15 22:00*

<!-- session-checkpoint-anchor: 2026-05-15T22:00:00Z -->

@SESSION_COMPACT.md

## 0. Brief Description

FastMCP-based MCP server giving AI assistants access to Joplin notes; fork of alondmnt/joplin-mcp v0.7.1 with 12 added tools (bulk ops, trash, revisions, backup) and a dashboard subpackage (config-driven Joplin → Markdown table renderer).

## 1. Focus

Dashboard schema validation shipped (commit `408b754`) and CLAUDE.md ↔ STATUS.md migration complete (commit `b417649`). Single §2 thread in focus: `/framing` then plan + implement full notebook-path matching in `JoplinRestLoader` to clear the remaining cross-project blocker for job_search.

## 2. Active Threads

### Notebook-path support in dashboard YAML  [plan]

Joplin REST search currently filters notebook by leaf name only; need full-path matching in `JoplinRestLoader._build_query()` (`loader.py:64-74`). Open job_search blocker against joplin-mcp.

- 2026-05-15 22:00  [ ]  /framing on full-path matching approach (path-as-query syntax, intermediate node walk)
- 2026-05-15 22:00  [ ]  Write plan in `markdowns/plans_draft/`
- 2026-05-15 22:00  [ ]  Implement in `dashboard/loader.py`
- 2026-05-15 22:00  [ ]  Test against job_search YAML configs that use nested notebooks

Cross-project blocker tracked in `~/.claude/STATUS.md` under "Notebook-path support in dashboard YAML".

## 3. Inactive Threads

### joplin-dashboard global discoverability  [queued]

Wrapper at `bin/joplin-dashboard` + `manifest.txt` so the CLI is on PATH from any non-conda shell. Plan exists; well-scoped. Interim hardcoded symlink already in place from job_search session.

- 2026-05-15 22:00  [ ]  Author `bin/joplin-dashboard` wrapper (dynamic conda resolution via `conda info --base`)
- 2026-05-15 22:00  [ ]  Add `manifest.txt` with `~/.claude/joplin-dashboard:bin/joplin-dashboard`
- 2026-05-15 22:00  [ ]  Run `~/projects/dev/claude-wrangler/install.sh --force ~/projects/dev/joplin-mcp` (force overrides the interim symlink)
- 2026-05-15 22:00  [ ]  Verify `joplin-dashboard --help` from fresh non-conda shell
- 2026-05-15 22:00  [ ]  Add one-line pointer in CLAUDE.md "Dashboard Subpackage" section

Design + rationale in `CLAUDE.md` → "Design Notes / Design: joplin-dashboard global discoverability (wrapper + manifest.txt)".

### Upstream contributions to alondmnt/joplin-mcp  [queued]

PR #23 merged 2026-04-17 (`restore_from_trash` + `find_notes(trash=True)`). Two open issues remain per alondmnt's preference for extending existing interfaces.

- 2026-05-15 22:00  [ ]  Issue #21 — Moving notes: add `notebook_name` to `update_note`
- 2026-05-15 22:00  [ ]  Issue #22 — Bulk tagging: extend `tag_note`/`untag_note` to accept `str | List[str]`

Workflow: branch from `upstream/main` as `pr/<topic>`, minimal & focused. See CLAUDE.md "Upstream Contribution Workflow".

### Upstream sync strategy  [idea]

How to pull alondmnt's `upstream/main` changes onto our `main` and `feature/dev`. Our 12 tools are additive but `fastmcp_server.py` and `formatting.py` have modifications.

- 2026-05-15 22:00  [ ]  /framing or /research on rebase vs merge approach
- 2026-05-15 22:00  [ ]  Check upstream for changes since v0.7.1

### CLAUDE.md cross-branch persistence  [idea]

CLAUDE.md disappears on checkout to clean PR branches. Current proposal: `## PROJ_SHARED_CLAUDE` section extracted to untracked floater. Needs /framing — proposal isn't final.

- 2026-05-15 22:00  [ ]  /framing to survey alternatives (post-checkout hook, separate tracked branch, etc.)
- 2026-05-15 22:00  [ ]  Define shared-vs-branch-specific content (blocked until branch roles clearer)
- 2026-05-15 22:00  [ ]  Implement chosen design

Proposed design in CLAUDE.md → "Design Notes / Design: CLAUDE.md cross-branch persistence (proposed; needs /framing)".

### Direct SQLite read layer  [idea]

Joplin REST API has no server-side filtering; all filtering is Python-side post-fetch. Adding read-only SQLite access to `~/.config/joplin-desktop/database.sqlite` would enable efficient filtered reads. Keep joppy/REST for writes.

- 2026-05-15 22:00  [ ]  /framing on hybrid SQLite-read / REST-write architecture
- 2026-05-15 22:00  [ ]  Write plan

Design considerations in CLAUDE.md → "Design Notes / Design: Direct SQLite read layer".

### Fork enhancements  [idea]

Wish-list, not formally scoped.

- 2026-05-15 22:00  [ ]  `update_notebook()`: add `parent_id`/`parent_notebook` for hierarchy moves
- 2026-05-15 22:00  [ ]  `get_recent_changes`: expose Joplin events API
- 2026-05-15 22:00  [ ]  Resource/attachment management tools
- 2026-05-15 22:00  [ ]  Document Joplin search operators in tool descriptions

### MCP packaging / distribution infrastructure  [deferred]

Extract Docker/install infrastructure from `extract/mcp-docker-dev` branch into a separate `MatthewOGoodman/mcp-docker-dev` repo. Parked, not started.

- 2026-05-15 22:00  [ ]  Extract from `extract/mcp-docker-dev` into separate repo

### Joppy `utcfromtimestamp` deprecation warning  [deferred]

`joppy/data_types.py:116` emits `DeprecationWarning: datetime.datetime.utcfromtimestamp() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.fromtimestamp(timestamp, datetime.UTC).` on every `joplin-dashboard` invocation. Cosmetic CLI noise. Surfaced from `job_search` session 2026-05-15 dashboard regeneration.

Deferred 2026-05-18 — relying on joppy upstream to ship a fix before CPython actually removes `utcfromtimestamp()`. Revisit if joppy hasn't fixed it by the time a CPython removal version is announced (deprecated in 3.12; no removal version yet).

- 2026-05-15 22:00  [ ]  Decide: bump `joppy` version (if fixed upstream), suppress warning at joplin-mcp's entry point, or submit upstream PR

## 4. Deliverables and Deadlines

- **Notebook-path support in dashboard YAML**  [blocked]
  - 2026-05-15 22:00
  - Description: Cross-project commitment to job_search — full-path notebook matching in `JoplinRestLoader`
  - Owner: this project; consumer: job_search

- **Upstream PRs #21 and #22**  [queued]
  - 2026-05-15 22:00
  - Description: Two issues alondmnt opened for accepted extensions. No hard deadline.

## 5. Blockers

(no project-local blockers; the two cross-project blockers job_search holds against joplin-mcp are tracked in `~/.claude/STATUS.md`, not duplicated here — we OWN them, we are not blocked by them)

## 6. Read / Research Topics

- 2026-05-15 22:00  [ ]  Upstream sync — rebase vs merge for our fork; read git docs on `--onto`
- 2026-05-15 22:00  [ ]  CLAUDE.md cross-branch persistence — survey other repos' solutions before committing to floating-file design

## 7. Inbox

(empty — first-run migration)