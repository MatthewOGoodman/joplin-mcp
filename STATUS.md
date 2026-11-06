# STATUS

*Last checkpoint: 2026-11-06 16:35 | Last prioritized: 2026-07-28 15:58 [auto] | Last shutdown: 2026-08-01 23:00 | Last cleanup: 2026-07-28 15:58*

@markdowns/SESSION_COMPACT_7736159a_20260801_230000.md

## 0. Project Overview

### Brief Description

FastMCP-based MCP server giving AI assistants access to Joplin notes; fork of alondmnt/joplin-mcp v0.10.0 with 11 added tools (bulk ops, trash listing, revisions, backup), a dashboard subpackage (config-driven Joplin → Markdown table renderer), and an mdsync subpackage (round-trip local `.md` file ↔ Joplin note).

## 1. Prioritization

### Focus

Notebook-path support in the dashboard YAML loader is the sole active priority. It is the only open item with a blocked downstream consumer — job_search dashboards are running on a leaf-name workaround — and it is tracked as a cross-project blocker in user-global `STATUS.md`. Next step is `/framing` on the full-path matching approach, then a plan, then implementation in `dashboard/loader.py`.

Recently cleared: dashboard schema validation shipped (`408b754`); the mdsync round-trip tool shipped, committed (`bbacf38` + `43c2c81`), and was dogfooded end-to-end on 2026-07-28 (five plan notes pulled and pushed, drift detection reporting none) — its completed record is archived in `markdowns/session_archive/`.

## Flags

Signals between skills, not threads: a `###` here is raised by one skill and cleared by another. The thread rebuild never touches this section.

### Reprioritize now!  [implement]

#### Run `/project-prioritize`  [ ]

start: 2026-06-06 11:00; update: 2026-07-28 15:58
Items the 2026-07-28 autonomous pass deliberately did not decide. Interactive `/project-prioritize` clears this thread.
- **Replan, do not re-rank — "Notebook-path support in dashboard YAML".** It has been the top priority since 2026-05-15 with zero commits against it in that time, and both the 2026-06-06 and 2026-06-09 session records note it as "remains open — untouched this session". Its first step is a `/framing`, so the thread is stalled at a decision, not at implementation. Consider either scheduling that framing explicitly, or descoping to exact-path-only matching that unblocks job_search without settling the fuzzy-matching question.
- **Stale-thread review (proposals only, never auto-applied).** Untouched since 2026-05-15: "Fork enhancements" `[idea]`, "MCP packaging / distribution infrastructure" `[deferred]`, "CLAUDE.md cross-branch persistence" `[idea]`. Decide whether any should become `[superseded]`.
- **No prioritization rubric exists.** RICE scoring this pass was uncalibrated. An interactive run can bootstrap `PRIORITIZATION_RUBRIC.md`; autonomous runs never author it.

## 2. Active Threads

### Notebook-path support in dashboard YAML  [plan] (#)

Joplin REST search currently filters notebook by leaf name only; needs full-path matching in `JoplinRestLoader._build_query()` (`dashboard/loader.py:64-74`). Open cross-project blocker that job_search holds against joplin-mcp, tracked in `~/.claude/STATUS.md` under "Notebook-path support in dashboard YAML".
→ markdowns/status_threads/notebook-path-support-in-dashboard-yaml_THREAD.md

## 3. Inactive Threads

### joplin-dashboard global discoverability  [queued]

Wrapper at `bin/joplin-dashboard` + a `claude-wrangler-manifest.txt` entry so the CLI is on PATH from any non-conda shell. Design rationale — including the drafted wrapper script and the five rejected alternatives — in `markdowns/DESIGN_NOTES.md` → "Design: joplin-dashboard global discoverability". An interim hardcoded symlink is already in place from a job_search session; the installer will warn-and-skip on it unless run with `--force`.
→ markdowns/status_threads/joplin-dashboard-global-discoverability_THREAD.md

### mdsync follow-ups  [queued]

Residual verification left over from the shipped mdsync subpackage (`bbacf38`). The feature itself is done, committed, and dogfooded; the completed record is archived in `markdowns/session_archive/SWEPT_20260728_1558.md`.
→ markdowns/status_threads/mdsync-follow-ups_THREAD.md

### Test suite hygiene  [queued]

Four test failures predate current work and have been verified on a clean tree (via `git stash`) in two separate sessions without being tracked anywhere. Surfaced by the 2026-07-28 cleanup from the 2026-06-06 and 2026-06-09 session records, where both sessions independently confirmed and then set them aside.
→ markdowns/status_threads/test-suite-hygiene_THREAD.md

### Repo housekeeping  [queued]

Low-priority disposition of leftover scratch files now tracked at the repo root (committed in `41f8cb5`).
→ markdowns/status_threads/repo-housekeeping_THREAD.md

### CLAUDE.md cross-branch persistence  [superseded]

Superseded 2026-11-06: handed to claude-wrangler as the single owner — its Inbox item "Revive or retire the cross-branch context-file carry" carries this thread's unique TODOs (survey alternatives, shared-vs-branch split, carry the thread-file directory too). Drop this thread once that item is picked up.
→ markdowns/status_threads/claude-md-cross-branch-persistence_THREAD.md

### Direct SQLite read layer  [idea]

The Joplin REST API has no server-side filtering, so all filtering is Python-side post-fetch. A read-only SQLite layer over `~/.config/joplin-desktop/database.sqlite` would enable efficient filtered reads while keeping joppy/REST for writes. Caveat: assumes the server shares a host with Joplin Desktop. Design considerations — including the rejected option of contributing filter params upstream to Joplin itself — in `markdowns/DESIGN_NOTES.md` → "Design: Direct SQLite read layer". First consumer in waiting: the dashboard's `Loader` interface (`dashboard/loader.py`) was built so a `JoplinSqliteLoader` can drop in — see CLAUDE.md Learnings → Design Decisions, "Dashboard reads over REST, not SQLite", for the triggers that would justify it.
→ markdowns/status_threads/direct-sqlite-read-layer_THREAD.md

### Fork enhancements  [idea]

Wish-list of fork-local additions; not formally scoped.
→ markdowns/status_threads/fork-enhancements_THREAD.md

### MCP packaging / distribution infrastructure  [deferred]

Extract the Docker/install infrastructure from the `archive/bulk-operations-monolith` tag (`3de13d4`) into a new `MatthewOGoodman/mcp-docker-dev` repo, not yet created, as reusable infrastructure for any MCP project. Parked, not started. What the tag holds, and the reasoning, in `markdowns/DESIGN_NOTES.md` → "Design: MCP packaging / distribution infrastructure".
→ markdowns/status_threads/mcp-packaging-distribution-infrastructure_THREAD.md

### Joppy `utcfromtimestamp` deprecation warning  [deferred]

`joppy/data_types.py:116` emits `DeprecationWarning: datetime.datetime.utcfromtimestamp() is deprecated and scheduled for removal in a future version.` on every `joplin-dashboard` invocation. Cosmetic CLI noise; surfaced from a job_search session 2026-05-15. Deferred 2026-05-18 in favor of waiting on an upstream joppy fix — deprecated in CPython 3.12 with no removal version announced yet.
→ markdowns/status_threads/joppy-utcfromtimestamp-deprecation-warning_THREAD.md

## 4. Deliverables and Deadlines

#### Full-path notebook matching for job_search  [blocked]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Cross-project commitment to job_search — full-path notebook matching in `JoplinRestLoader`.
- Owner: this project; consumer: job_search
- No hard date; job_search is unblocked-but-degraded on a leaf-name workaround
- Tracked as a cross-project blocker in `~/.claude/STATUS.md`; delivered by the "Notebook-path support in dashboard YAML" thread

## 5. Blockers

No project-local blockers.

The cross-project blocker "Notebook-path support in dashboard YAML" is one this project OWNS — job_search is blocked on us, we are not blocked on anyone — so it lives in `~/.claude/STATUS.md` and in § 4 Deliverables, and is deliberately not mirrored here.

## 6. Read/Research Topics

No open research topics.

## 7. Inbox
