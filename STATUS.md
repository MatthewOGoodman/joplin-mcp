# STATUS

*Last checkpoint: 2026-11-25 12:00 | Last prioritized: 2026-11-25 12:01 [auto] | Last shutdown: 2026-08-01 23:00 | Last cleanup: 2026-11-25 12:01*

## 0. Project Overview

### Brief Description

FastMCP-based MCP server giving AI assistants access to Joplin notes; fork of alondmnt/joplin-mcp v0.10.0 with 11 added tools (bulk ops, trash listing, revisions, backup), a dashboard subpackage (config-driven Joplin → Markdown table renderer), and an mdsync subpackage (round-trip local `.md` file ↔ Joplin note).

## 1. Prioritization

### Focus

Notebook-path support in the dashboard YAML loader is the sole active priority. It is the only open item with a blocked downstream consumer — job_search dashboards are running on a leaf-name workaround — and it is tracked as a cross-project blocker in user-global `STATUS.md`. Next step is checking whether upstream's `get_notebook_id_by_name` (path-aware since v0.10.0) already does the resolution; only if it does not, `/framing` on the matching approach, then a plan, then implementation in `dashboard/loader.py`.

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
- **Deferred by the 2026-11-25 autonomous pass (split candidates from the blind regrouping):** (a) pull the preview/execute ID-set-hash safety check out of "Direct SQLite read layer" — it ships on the current REST path; (b) split "Survey alternatives before implementing" into survey vs build; (c) split "Candidate tool and API additions" into events API, resource write tools, and search-operator docs; (d) fold "Extend the same treatment to joplin-mdsync" into the two earlier discoverability TODOs.
- **Stale-thread review, 2026-11-25 (proposals only):** "joplin-dashboard global discoverability", "mdsync follow-ups", "Direct SQLite read layer" and "Joppy `utcfromtimestamp` deprecation warning" unchanged since 2026-07-28; "Fork enhancements" and "MCP packaging" since 2026-11-05. "CLAUDE.md cross-branch persistence" is already `[superseded]` but still holds one open TODO — archive it once claude-wrangler confirms ownership.

## 2. Active Threads

### Notebook-path support in dashboard YAML  [plan] (#)

Full-path notebook matching in the dashboard loader, to unblock job_search.
→ markdowns/status_threads/notebook-path-support-in-dashboard-yaml_THREAD.md

### joplin-dashboard global discoverability  [implement]

Put the joplin-dashboard and joplin-mdsync CLIs on PATH outside the conda env.
→ markdowns/status_threads/joplin-dashboard-global-discoverability_THREAD.md

## 3. Inactive Threads

### mdsync follow-ups  [queued]

Residual verification left over from the shipped mdsync subpackage (`bbacf38`). The feature itself is done, committed, and dogfooded; the completed record is archived in `markdowns/session_archive/SWEPT_20260728_1558.md`.
→ markdowns/status_threads/mdsync-follow-ups_THREAD.md

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

### CLAUDE.md cross-branch persistence  [superseded]

Superseded 2026-11-06 — handed to claude-wrangler as the single owner.
→ markdowns/status_threads/claude-md-cross-branch-persistence_THREAD.md

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

No items.
