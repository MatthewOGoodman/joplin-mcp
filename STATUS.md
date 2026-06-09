# STATUS

*Last checkpoint: — | Last prioritized: 2026-05-18 09:00 | Last shutdown: 2026-06-09 14:45 | Last cleanup: —*

@markdowns/SESSION_COMPACT_32abac0d_20260606_110015.md
@markdowns/SESSION_COMPACT_594bbe9f_20260609_144500.md

<!-- session-checkpoint-anchor: 2026-05-15T22:00:00Z -->

@SESSION_COMPACT.md

## 0. Brief Description

FastMCP-based MCP server giving AI assistants access to Joplin notes; fork of alondmnt/joplin-mcp v0.7.1 with 12 added tools (bulk ops, trash, revisions, backup) and a dashboard subpackage (config-driven Joplin → Markdown table renderer).

## 1. Focus

Dashboard schema validation shipped (commit `408b754`) and CLAUDE.md ↔ STATUS.md migration complete (commit `b417649`). Primary §2 thread: `/framing` then plan + implement full notebook-path matching in `JoplinRestLoader` to clear the remaining cross-project blocker for job_search. Second §2 thread added 2026-06-05: md-file ↔ Joplin round-trip tool (framing converged; plan next).

## 2. Active Threads

### Reprioritize now!  [implement]

#### Run `/project-prioritize`  [ ]

start: 2026-06-06 11:00; update: 2026-06-06 11:00
Re-rank §2 / §3 against this session's additions.
- New §2 thread "Md-file ↔ Joplin round-trip tool" added and substantially COMPLETED this session (implementation shipped; remaining: GFM-table visual check, bin/ wrapper, commit) — needs demote/re-rank decision.
- Interactive `/project-prioritize` clears this thread on completion.

### Notebook-path support in dashboard YAML  [plan]

Joplin REST search currently filters notebook by leaf name only; need full-path matching in `JoplinRestLoader._build_query()` (`loader.py:64-74`). Open job_search blocker against joplin-mcp.

- 2026-05-15 22:00  [ ]  /framing on full-path matching approach (path-as-query syntax, intermediate node walk)
- 2026-05-15 22:00  [ ]  Write plan in `markdowns/plans_draft/`
- 2026-05-15 22:00  [ ]  Implement in `dashboard/loader.py`
- 2026-05-15 22:00  [ ]  Test against job_search YAML configs that use nested notebooks

Cross-project blocker tracked in `~/.claude/STATUS.md` under "Notebook-path support in dashboard YAML".

### Md-file ↔ Joplin round-trip tool  [plan]

SHIPPED 2026-06-06 (uncommitted — see `### Resolve git state now!`). Pull-edit-update round-trip (note-canonical primary workflow): `joplin-mdsync update|push|pull` CLI + 3 MCP tools over shared `mdsync/` transport helpers. File bytes verbatim; fenced `mdsync:` frontmatter block via exact line-splice (user YAML never parsed); body-hash drift detection owned by `update`; revision backup before every PUT. Full design in CLAUDE.md → "Mdsync Subpackage". (Original framing 2026-06-05 was push-first/file-canonical — inverted by user ruling during planning.)

- 2026-06-05 20:10  [x]  Write plan — iterated through /framing + adversarial agent review + user rulings 2026-06-05/06; final design: API-verbatim fenced `mdsync:` block via line-splice (user YAML never parsed); three verbs update/push/pull, drift check (prior_Joplin_hash vs just-in-time current_Joplin_hash) owned by update alone; push --force = clobber; pull backs up dirty files to `.bak` + `markdown_bak:` line; tags reconciled when line present. Plan at `~/.claude/plans/approved-entering-plan-mode-hazy-gadget.md` (archive to plans_completed on commit)
- 2026-06-06 07:30  [x]  Implement subpackage: `mdsync/block.py` (line surgery; identity.py renamed), `mdsync/transport.py` (3 verbs), `mdsync/cli.py` (`joplin-mdsync`, bare path = update); registered in pyproject [project.scripts]
- 2026-06-06 07:30  [x]  Thin MCP tools in `tools/notes_files.py` (update_note_from_file, push_md_file, pull_note_to_file); registered in tools/__init__.py + config DEFAULT_TOOLS/TOOL_CATEGORIES
- 2026-06-06 07:30  [x]  Unit tests: 71 tests in test_mdsync_{block,transport,cli}.py + fixtures; full suite 603 passed (5 pre-existing failures verified on clean tree: 4× test_import_utils timestamps, 1× test_config home-token leak); ruff+black clean on new files
- 2026-06-06 07:30  [x]  Live verification against Testing notebook: create/refuse/force-clobber/drift-warning+region/repeat-update-no-drift/dirty-pull-bak/tags-reconcile/tags-absent-untouched/md_tools-mangle→pull-rebind-recovery all confirmed (via `joplin-mdsync` CLI; note "mdsync test")
- 2026-06-06 07:45  [x]  MCP-layer live test (in-process `fastmcp.Client` against the server instance — full registration/schema/invocation path, minus only the desktop JSON-RPC hop): all 3 tools registered (37 total); push created note "mdsync mcp test" (`dab8a499…`); update no-drift; pull round trip byte-faithful incl. user frontmatter; push refusal surfaces through the MCP error path naming both verbs. Script: `test_scripts/mdsync_mcp_live_test.py` (gitignored)
- 2026-06-06 10:40  [x]  Real-session MCP check after `/mcp` reload: `update_note_from_file` (SUCCESS, no drift, revision saved), `pull_note_to_file` (SUCCESS, clean), and the push-refusal error path all confirmed through Claude Code's live connection — every layer now tested (CLI / in-process MCP / live session)
- 2026-06-05 20:10  [ ]  Verify Joplin render of GFM tables pushed via API — test note "mdsync test" (Testing notebook, id ac0f9049…) contains a GFM table NOW; user visual check pending; add reformatter ONLY if broken
- 2026-06-05 20:10  [ ]  `bin/` wrapper + manifest entry for global PATH (ride the queued joplin-dashboard discoverability thread)
- 2026-06-06 07:30  [x]  Commit (feature/dev) + archive plan — committed `bbacf38` 2026-06-09 (plan now in `markdowns/plans_completed/`); MCP tools live after next `/mcp` reload

v1 exclusions: no attachments/resources, no directory ↔ notebook batch mode, no watch/daemon mode.

## 3. Inactive Threads

### joplin-dashboard global discoverability  [queued]

Wrapper at `bin/joplin-dashboard` + `claude-wrangler-manifest.txt` so the CLI is on PATH from any non-conda shell. Plan exists; well-scoped. Interim hardcoded symlink already in place from job_search session.

- 2026-05-15 22:00  [ ]  Author `bin/joplin-dashboard` wrapper (dynamic conda resolution via `conda info --base`)
- 2026-05-15 22:00  [ ]  Add `claude-wrangler-manifest.txt` with `~/.claude/joplin-dashboard:bin/joplin-dashboard`
- 2026-05-15 22:00  [ ]  Run `~/projects/dev/claude-wrangler/install.sh --force ~/projects/dev/joplin-mcp` (force overrides the interim symlink)
- 2026-05-15 22:00  [ ]  Verify `joplin-dashboard --help` from fresh non-conda shell
- 2026-05-15 22:00  [ ]  Add one-line pointer in CLAUDE.md "Dashboard Subpackage" section

Design + rationale in `CLAUDE.md` → "Design Notes / Design: joplin-dashboard global discoverability (wrapper + claude-wrangler-manifest.txt)".

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

- 2026-06-08  [ ]  Retire the "Known gap (transient)" paragraph in `CLAUDE.md` → "Mdsync Subpackage" (line ~223 — "md_tools currently strips frontmatter fences on section ops, breaking the binding"). RESOLVED in claude-wrangler 2026-06-08: md_tools now holds YAML frontmatter opaque and reattaches it byte-verbatim across all verbs (89/89 tests), so an `md_tools` body edit no longer breaks the mdsync binding (the `id` lives in frontmatter, preserved). Update the paragraph to current behavior (no-ghosts). [hand-off from claude-wrangler]

### TODO: backup_database — require label on manual backups + doc mechanism  [x]

start: 2026-06-09 09:39; update: 2026-06-09 14:25
DONE 2026-06-09 — implemented + tested (24 backup tests pass; full suite 603 passed, 5 pre-existing failures unchanged). Code committed on feature/dev; this STATUS entry rides the next /project-cleanup.
Hand-off from a joplin_user session (backup-folder investigation: `~/JoplinBackup/default/mcp-backups/` at 1.3 GB; manual backups unlabeled + never pruned).
- [x] Required informative `label` on the standalone `backup_database` tool → `joplin_manual_backup_{ts}_{slug}.sqlite`; auto-derived slug (`bulk-move` / `bulk-update`) on the bulk-op `backup="force"` path.
- [x] Docstrings: AUTO (`"daily"`, once/calendar-day guard, last-10 retention) vs MANUAL (`"force"`/standalone, never pruned); `manually_backup_note` writes no file (in-Joplin revision).
- Plan: markdowns/plans_completed/CLAUDE.PLANS_20260609_BACKUP_DATABASE_REQUIRE_LABEL_HANDOFF.md