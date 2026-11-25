# STATUS

*Last checkpoint: 2026-11-25 12:00 | Last prioritized: 2026-11-25 14:39 | Last shutdown: 2026-08-01 23:00 | Last cleanup: 2026-11-25 12:01*

## 0. Project Overview

### Brief Description

FastMCP-based MCP server giving AI assistants access to Joplin notes; fork of alondmnt/joplin-mcp v0.10.0 with 11 added tools (bulk ops, trash listing, revisions, backup), a dashboard subpackage (config-driven Joplin → Markdown table renderer), and an mdsync subpackage (round-trip local `.md` file ↔ Joplin note).

## 1. Prioritization

### Focus

Full-path notebook matching shipped 2026-11-25 (`20d0bd6`): a dashboard section can now name `"1-Job Search/People"`, and the job_search blocker is resolved — switching job_search's config over is job_search's call. Its thread is complete and awaits the next cleanup sweep.

Two small threads are active alongside it: "mdsync follow-ups" is complete (the table renders correctly), and "joplin-dashboard global discoverability" has its wrappers and manifest committed and waits on claude-wrangler to run the `~/.claude` install. Nothing else is in flight; the inactive threads are ideas or deferred.

## Flags

Signals between skills, not threads: a `###` here is raised by one skill and cleared by another. The thread rebuild never touches this section.

### Reprioritize now!  [implement]

#### Run `/project-prioritize`  [ ]

start: 2026-06-06 11:00; update: 2026-11-25 14:39
Two restructuring proposals the 2026-11-25 interactive pass did not take up; everything else in this flag was decided that day.
- Pull the preview/execute ID-set-hash safety check out of "Direct SQLite read layer" into its own TODO — it could ship on the current REST path.
- Split "Fork enhancements" → "Candidate tool and API additions" into events API, resource write tools, and search-operator docs.

## 2. Active Threads

### mdsync follow-ups  [implement]

Residual verification left over from the shipped mdsync subpackage (`bbacf38`). The feature itself is done, committed, and dogfooded; the completed record is archived in `markdowns/session_archive/SWEPT_20260728_1558.md`.
→ markdowns/status_threads/mdsync-follow-ups_THREAD.md

### joplin-dashboard global discoverability  [implement]

Put the joplin-dashboard and joplin-mdsync CLIs on PATH outside the conda env.
→ markdowns/status_threads/joplin-dashboard-global-discoverability_THREAD.md

### Notebook-path support in dashboard YAML  [plan] (#)

Full-path notebook matching in the dashboard loader, to unblock job_search.
→ markdowns/status_threads/notebook-path-support-in-dashboard-yaml_THREAD.md

## 3. Inactive Threads

### Direct SQLite read layer  [idea]

Read-only SQLite layer for filtered reads, keeping REST for writes.
→ markdowns/status_threads/direct-sqlite-read-layer_THREAD.md

### Fork enhancements  [idea]

Wish-list of fork-local additions; not formally scoped.
→ markdowns/status_threads/fork-enhancements_THREAD.md

### MCP packaging / distribution infrastructure  [dropped]

Extract the archived Docker/install tooling into a reusable mcp-docker-dev repo.
→ markdowns/status_threads/mcp-packaging-distribution-infrastructure_THREAD.md

### Joppy `utcfromtimestamp` deprecation warning  [deferred]

Silence joppy's utcfromtimestamp DeprecationWarning on every dashboard run.
→ markdowns/status_threads/joppy-utcfromtimestamp-deprecation-warning_THREAD.md

### CLAUDE.md cross-branch persistence  [superseded]

Superseded 2026-11-06 — handed to claude-wrangler as the single owner.
→ markdowns/status_threads/claude-md-cross-branch-persistence_THREAD.md

## 4. Deliverables and Deadlines

#### Full-path notebook matching for job_search  [x]

start: 2026-05-15 22:00; update: 2026-11-25 14:39
Cross-project commitment to job_search — full-path notebook matching in `JoplinRestLoader`.
- Owner: this project; consumer: job_search
- No hard date; job_search is unblocked-but-degraded on a leaf-name workaround
- Tracked as a cross-project blocker in `~/.claude/STATUS.md`; delivered by the "Notebook-path support in dashboard YAML" thread
- Delivered 2026-11-25 in `20d0bd6`; user-global blocker moved to Resolved. Switching job_search's config to full paths is job_search's call.

## 5. Blockers

No project-local blockers.

The cross-project blocker "Notebook-path support in dashboard YAML" is one this project OWNS — job_search is blocked on us, we are not blocked on anyone — so it lives in `~/.claude/STATUS.md` and in § 4 Deliverables, and is deliberately not mirrored here.

## 6. Read/Research Topics

No open research topics.

## 7. Inbox

No items.
