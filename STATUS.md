# STATUS

*Last checkpoint: — | Last prioritized: 2026-07-28 15:58 [auto] | Last shutdown: 2026-06-09 14:45 | Last cleanup: 2026-07-28 15:58*

## 0. Project Overview

### Brief Description

FastMCP-based MCP server giving AI assistants access to Joplin notes; fork of alondmnt/joplin-mcp v0.7.1 with 12 added tools (bulk ops, trash, revisions, backup), a dashboard subpackage (config-driven Joplin → Markdown table renderer), and an mdsync subpackage (round-trip local `.md` file ↔ Joplin note).

## 1. Prioritization

### Focus

Notebook-path support in the dashboard YAML loader is the sole active priority. It is the only open item with a blocked downstream consumer — job_search dashboards are running on a leaf-name workaround — and it is tracked as a cross-project blocker in user-global `STATUS.md`. Next step is `/framing` on the full-path matching approach, then a plan, then implementation in `dashboard/loader.py`.

Recently cleared: dashboard schema validation shipped (`408b754`); the mdsync round-trip tool shipped, committed (`bbacf38` + `43c2c81`), and was dogfooded end-to-end on 2026-07-28 (five plan notes pulled and pushed, drift detection reporting none) — its completed record is archived in `markdowns/session_archive/`.

### Thread Order

Top-to-bottom is recommended execution order. Threads are parallel by default; the one forced ordering is annotated.

#### Notebook-path support in dashboard YAML

Full-path notebook matching in `JoplinRestLoader` — the only thread with a blocked downstream consumer.

#### joplin-dashboard global discoverability

`bin/` wrappers + manifest entry so both `joplin-dashboard` and `joplin-mdsync` resolve outside the conda env.

#### mdsync follow-ups

One visual check on GFM table rendering; near-zero effort, closes out a shipped feature.

#### Upstream contributions to alondmnt/joplin-mcp

Issues #21 and #22 — extensions the maintainer has already agreed to accept.

#### Test suite hygiene

Five long-standing failures that mask real regressions in every other thread's work.

#### Upstream sync strategy  (blocks: CLAUDE.md cross-branch persistence)

Settle rebase-vs-merge before the fork's divergence grows; it also decides the branch roles the cross-branch work waits on.

## 2. Active Threads

### Notebook-path support in dashboard YAML  [plan] (#)

Joplin REST search currently filters notebook by leaf name only; needs full-path matching in `JoplinRestLoader._build_query()` (`dashboard/loader.py:64-74`). Open cross-project blocker that job_search holds against joplin-mcp, tracked in `~/.claude/STATUS.md` under "Notebook-path support in dashboard YAML".

#### Frame and plan full-path matching  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Decide the matching approach before touching the loader.
- [ ] `/framing` on the approach — path-as-query syntax vs walking intermediate notebook nodes
- [ ] Resolve whether fuzzy path matching is supported or exact paths are required (open question carried from 2026-05-15)
- [ ] Write the plan in `markdowns/plans_draft/`

#### Implement and test full-path matching  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Land the change and verify it against the real consumer configs.
- [ ] Implement in `dashboard/loader.py`
- [ ] Test against the job_search YAML configs that use nested notebooks
- [ ] Confirm job_search can drop its leaf-name workaround, then resolve the user-global blocker

### Reprioritize now!  [implement]

#### Run `/project-prioritize`  [ ]

start: 2026-06-06 11:00; update: 2026-07-28 15:58
Items the 2026-07-28 autonomous pass deliberately did not decide. Interactive `/project-prioritize` clears this thread.
- **Replan, do not re-rank — "Notebook-path support in dashboard YAML".** It has been the top priority since 2026-05-15 with zero commits against it in that time, and both the 2026-06-06 and 2026-06-09 session records note it as "remains open — untouched this session". Its first step is a `/framing`, so the thread is stalled at a decision, not at implementation. Consider either scheduling that framing explicitly, or descoping to exact-path-only matching that unblocks job_search without settling the fuzzy-matching question.
- **Stale-thread review (proposals only, never auto-applied).** Untouched since 2026-05-15: "Fork enhancements" `[idea]`, "MCP packaging / distribution infrastructure" `[deferred]`, "CLAUDE.md cross-branch persistence" `[idea]`. Decide whether any should become `[superseded]`.
- **Backlog item possibly mis-filed.** A blind regrouping pass noted that `update_notebook(parent_id)` under "Fork enhancements" is the sibling of Issue #21's `notebook_name` on `update_note` — the same hierarchy-move surface — so it may belong with the upstream-contributions thread rather than the fork-local backlog. Left in place; needs a call on whether it is an upstream PR or a fork-local addition.
- **No prioritization rubric exists.** RICE scoring this pass was uncalibrated. An interactive run can bootstrap `PRIORITIZATION_RUBRIC.md`; autonomous runs never author it.

## 3. Inactive Threads

### joplin-dashboard global discoverability  [queued]

Wrapper at `bin/joplin-dashboard` + a `claude-wrangler-manifest.txt` entry so the CLI is on PATH from any non-conda shell. Design rationale — including the drafted wrapper script and the five rejected alternatives — in `markdowns/DESIGN_NOTES.md` → "Design: joplin-dashboard global discoverability". An interim hardcoded symlink is already in place from a job_search session; the installer will warn-and-skip on it unless run with `--force`.

#### Author the dynamic-resolution wrapper  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Portable wrapper that resolves the conda env at invocation time.
- [ ] Write `bin/joplin-dashboard` resolving the env via `conda info --base` (no hardcoded miniforge path)
- [ ] `chmod +x bin/joplin-dashboard`

#### Register and verify on PATH  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Install through claude-wrangler's universal symlink installer.
- [ ] Add `claude-wrangler-manifest.txt` with `~/.claude/joplin-dashboard:bin/joplin-dashboard`
- [ ] Run `~/projects/dev/claude-wrangler/install.sh --force ~/projects/dev/joplin-mcp` (force overrides the interim symlink)
- [ ] Verify `joplin-dashboard --help` from a fresh non-conda shell
- [ ] Add a one-line pointer in the CLAUDE.md dashboard section

#### Extend the same treatment to joplin-mdsync  [ ]

start: 2026-06-05 20:10; update: 2026-07-28 15:58
The shipped mdsync CLI has the identical PATH problem; it was deferred to ride this thread.
- [ ] Add a `bin/joplin-mdsync` wrapper alongside the dashboard one
- [ ] Add its manifest entry so `joplin-mdsync` resolves outside the conda env

### mdsync follow-ups  [queued]

Residual verification left over from the shipped mdsync subpackage (`bbacf38`). The feature itself is done, committed, and dogfooded; the completed record is archived in `markdowns/session_archive/SWEPT_20260728_1558.md`.

#### Verify Joplin renders API-pushed GFM tables  [ ]

start: 2026-06-05 20:10; update: 2026-07-28 15:58
Confirm a GFM table survives the API round-trip visually; add a reformatter only if it does not.
- [ ] Visually check test note "mdsync test" (Testing notebook, id `ac0f9049…`), which already contains a GFM table
- [ ] Add a reformatter ONLY if the render is broken — do not pre-emptively build one

### Test suite hygiene  [queued]

Five test failures predate current work and have been verified on a clean tree (via `git stash`) in two separate sessions without being tracked anywhere. Surfaced by the 2026-07-28 cleanup from the 2026-06-06 and 2026-06-09 session records, where both sessions independently confirmed and then set them aside.

#### Resolve five pre-existing test failures  [ ]

start: 2026-07-28 15:58; update: 2026-07-28 15:58
The full suite reports 603 passed with these 5 failing; they are unrelated to recent feature work but mask genuine regressions.
- [ ] 4 failures in `tests/test_import_utils.py` — timestamp handling
- [ ] 1 failure in `tests/test_config.py` — home-token leak
- [ ] Decide per failure: fix, or mark `xfail` with a reason so a real regression is not hidden by an expected-red suite

### Upstream contributions to alondmnt/joplin-mcp  [queued]

PR #23 merged 2026-04-17 (`restore_from_trash` + `find_notes(trash=True)`). Two issues alondmnt opened remain, both reflecting their preference for extending existing interfaces over adding tools. Workflow: branch from `upstream/main` as `pr/<topic>`, minimal and focused — see CLAUDE.md "Upstream Contribution Workflow".

#### Issue #21 — notebook_name on update_note  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Fold note-moving into the existing update interface instead of a separate `move_note`.
- [ ] Add `notebook_name` to `update_note`
- [ ] Submit as a focused PR from `upstream/main`

#### Issue #22 — bulk tagging via existing tools  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Extend the existing tag interface rather than shipping `bulk_tag_notes` upstream.
- [ ] Extend `tag_note` / `untag_note` to accept `str | List[str]`
- [ ] Submit as a focused PR from `upstream/main`

### Repo housekeeping  [queued]

Low-priority disposition of leftover scratch files now tracked at the repo root (committed in `41f8cb5`).

#### Disposition of leftover scratch markdowns  [ ]

start: 2026-06-06 11:00; update: 2026-07-28 15:58
Two tracked scratch files have no permanent home; decide retention.
- [ ] `SESSION-joplin-sync.md` — pasted transcript on iOS OneDrive sync recovery; lift any durable lesson into a CLAUDE.md Gotcha or a Joplin note, then delete
- [ ] `markdowns/PR_DESCRIPTION_PR19_2026-03-30.md` — PR #19 closed 2026-04-06; likely archivable

### Upstream sync strategy  [idea]

How to pull alondmnt's `upstream/main` changes onto our `main` and `feature/dev`. No mechanism chosen yet. Our 12 tools are additive, but `fastmcp_server.py` and `formatting.py` carry modifications that could conflict. Open questions and deliberation in `markdowns/DESIGN_NOTES.md` → "Design: Upstream sync strategy".

#### Decide rebase vs merge for the fork  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Settle the sync mechanism before the divergence grows.
- [ ] `/framing` or `/research` on `git merge upstream/main` vs `git rebase --onto upstream/main`
- [ ] Check upstream for any changes since v0.7.1 beyond PR #23
- [ ] Decide how to handle divergence in files both sides modified

### CLAUDE.md cross-branch persistence  [idea]

CLAUDE.md disappears on checkout to clean PR branches, so Claude Code loses project context mid-session. The current proposal — a `## PROJ_SHARED_CLAUDE` section extracted to an untracked floater — is provisional and explicitly not final. Proposed design in `markdowns/DESIGN_NOTES.md` → "Design: CLAUDE.md cross-branch persistence".

#### Survey alternatives before implementing  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
The floating-file design should not be built until better options are ruled out.
- [ ] `/framing` to survey alternatives — post-checkout hook, separate tracked branch, others
- [ ] Define what is shared vs branch-specific — blocked until branch roles are clearer, which the "Upstream sync strategy" thread settles; do not start implementation before it lands
- [ ] Implement the chosen design, carrying STATUS.md as well as CLAUDE.md

### Direct SQLite read layer  [idea]

The Joplin REST API has no server-side filtering, so all filtering is Python-side post-fetch. A read-only SQLite layer over `~/.config/joplin-desktop/database.sqlite` would enable efficient filtered reads while keeping joppy/REST for writes. Caveat: assumes the server shares a host with Joplin Desktop. Design considerations — including the rejected option of contributing filter params upstream to Joplin itself — in `markdowns/DESIGN_NOTES.md` → "Design: Direct SQLite read layer".

#### Frame the hybrid read/write architecture  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Scope the split before committing to a second data path.
- [ ] `/framing` on hybrid SQLite-read / REST-write architecture
- [ ] Decide the preview/execute safety check — ID-set hash rather than the current weak `first_title` + `expected_count`
- [ ] Write the plan

### Fork enhancements  [idea]

Wish-list of fork-local additions; not formally scoped.

#### Candidate tool and API additions  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Unranked backlog — scope individually before starting any.
- [ ] `update_notebook()`: add `parent_id` / `parent_notebook` for hierarchy moves
- [ ] `get_recent_changes`: expose the Joplin events API
- [ ] Resource / attachment management tools
- [ ] Document Joplin search operators in tool descriptions

### MCP packaging / distribution infrastructure  [deferred]

Extract the Docker/install infrastructure from the `extract/mcp-docker-dev` branch into a separate `MatthewOGoodman/mcp-docker-dev` repo, as reusable infrastructure for any MCP project. Parked, not started. What is on that branch, and the reasoning, in `markdowns/DESIGN_NOTES.md` → "Design: MCP packaging / distribution infrastructure".

#### Extract Docker and install infrastructure  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Move the parked snapshot branch's contents into their own repo.
- [ ] Extract from `extract/mcp-docker-dev` into the separate repo

### Joppy `utcfromtimestamp` deprecation warning  [deferred]

`joppy/data_types.py:116` emits `DeprecationWarning: datetime.datetime.utcfromtimestamp() is deprecated and scheduled for removal in a future version.` on every `joplin-dashboard` invocation. Cosmetic CLI noise; surfaced from a job_search session 2026-05-15. Deferred 2026-05-18 in favor of waiting on an upstream joppy fix — deprecated in CPython 3.12 with no removal version announced yet.

#### Decide how to silence the deprecation  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Revisit if joppy has not fixed it by the time a CPython removal version is announced.
- [ ] Choose one: bump `joppy` (if fixed upstream), suppress the warning at joplin-mcp's entry point, or submit an upstream PR

## 4. Deliverables and Deadlines

#### Full-path notebook matching for job_search  [blocked]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Cross-project commitment to job_search — full-path notebook matching in `JoplinRestLoader`.
- Owner: this project; consumer: job_search
- No hard date; job_search is unblocked-but-degraded on a leaf-name workaround
- Tracked as a cross-project blocker in `~/.claude/STATUS.md`; delivered by the "Notebook-path support in dashboard YAML" thread

#### Upstream PRs for issues #21 and #22  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Two extensions alondmnt opened issues for and has agreed to accept.
- No hard deadline
- Delivered by the "Upstream contributions to alondmnt/joplin-mcp" thread

## 5. Blockers

No project-local blockers.

The cross-project blocker "Notebook-path support in dashboard YAML" is one this project OWNS — job_search is blocked on us, we are not blocked on anyone — so it lives in `~/.claude/STATUS.md` and in § 4 Deliverables, and is deliberately not mirrored here.

## 6. Read/Research Topics

#### Rebase vs merge for fork upstream sync  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Read up before choosing the sync mechanism for our fork.
- Read the git docs on `rebase --onto`
- Feeds the "Upstream sync strategy" thread

#### Cross-branch context-file persistence prior art  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Survey how other repos keep a context file alive across branch switches.
- Do this before committing to the floating-file design
- Feeds the "CLAUDE.md cross-branch persistence" thread

## 7. Inbox

Empty — all items routed by the 2026-07-28 cleanup.
