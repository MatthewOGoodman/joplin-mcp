# STATUS

*Last checkpoint: 2026-11-25 10:28 | Last prioritized: 2026-07-28 15:58 [auto] | Last shutdown: 2026-08-01 23:00 | Last cleanup: 2026-07-28 15:58*

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

Full-path notebook matching in the dashboard loader, to unblock job_search.
→ markdowns/status_threads/notebook-path-support-in-dashboard-yaml_THREAD.md

## 3. Inactive Threads

### joplin-dashboard global discoverability  [queued]

Put the joplin-dashboard and joplin-mdsync CLIs on PATH outside the conda env.
→ markdowns/status_threads/joplin-dashboard-global-discoverability_THREAD.md

### mdsync follow-ups  [queued]

Residual verification left over from the shipped mdsync subpackage (`bbacf38`). The feature itself is done, committed, and dogfooded; the completed record is archived in `markdowns/session_archive/SWEPT_20260728_1558.md`.
→ markdowns/status_threads/mdsync-follow-ups_THREAD.md

### Test suite hygiene  [queued]

Resolve long-standing test failures so the suite can catch real regressions.
→ markdowns/status_threads/test-suite-hygiene_THREAD.md

### Repo housekeeping  [queued]

Low-priority disposition of leftover scratch files now tracked at the repo root (committed in `41f8cb5`).
→ markdowns/status_threads/repo-housekeeping_THREAD.md

### CLAUDE.md cross-branch persistence  [superseded]

Superseded 2026-11-06 — handed to claude-wrangler as the single owner.
→ markdowns/status_threads/claude-md-cross-branch-persistence_THREAD.md

### Direct SQLite read layer  [idea]

Read-only SQLite layer for filtered reads, keeping REST for writes.
→ markdowns/status_threads/direct-sqlite-read-layer_THREAD.md

### Fork enhancements  [idea]

Wish-list of fork-local additions; not formally scoped.
→ markdowns/status_threads/fork-enhancements_THREAD.md

### MCP packaging / distribution infrastructure  [deferred]

Extract the archived Docker/install tooling into a reusable mcp-docker-dev repo.
→ markdowns/status_threads/mcp-packaging-distribution-infrastructure_THREAD.md

### Joppy `utcfromtimestamp` deprecation warning  [deferred]

Silence joppy's utcfromtimestamp DeprecationWarning on every dashboard run.
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
