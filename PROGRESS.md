# PROGRESS

Run reports from `/project-prioritize`. Not `@`-imported; read on demand.

## Run 2026-07-28 — --auto (via /project-cleanup)

### Phase 0 — Ground state

| Read | Result |
|---|---|
| Project root | `~/projects/dev/joplin-mcp`, branch `feature/dev` |
| Metadata line | `Last prioritized: 2026-05-18 09:00` (71 days stale) |
| Grooming anchor | `43c2c81` (`session-shutdown:` 2026-06-09) |
| Commits since anchor | 1 — `41f8cb5` (chore: track leftover scratch markdowns) |
| User-global STATUS | 2 Feature Updates for this project (mdsync 2026-06-06, backup_database 2026-06-09); 1 Active blocker owned by this project (Notebook-path support) |
| CLAUDE.md | Read for goal anchoring; restructured to schema this same run |
| SESSION_COMPACT distillation | Blind `Plan` subagent over the two compacts (`32abac0d`, `594bbe9f`) |

No `PRIORITIZATION_RUBRIC.md` exists, so RICE scoring below is **uncalibrated**. Autonomous runs never author the rubric; an interactive run can bootstrap it.

### Phase 1 — Structure inference

**1.0 State-change quadrant.** Only one commit since the anchor, touching the two scratch markdowns — which seeded the "Repo housekeeping" thread. No thread showed commit activity warranting a §2 ↔ §3 promote or demote; all borderline calls stayed put.

**1.4 Thread-restructure (blind subagent, `Plan`, TODOs-only view).** The blind regrouping reproduced the current threading almost exactly: its G1–G7, G9, G10 map one-to-one onto the existing threads. Findings acted on and not acted on:

| Finding | Disposition |
|---|---|
| G1/G3/G4/G5 "four items are facets, not threads" | NOT a defect — those are §4 Deliverables and §6 Read/Research entries, which the schema places outside the thread tree. The agent saw them stripped of section context. |
| G4 blocks G5 ("do not start before it lands") | APPLIED — dependency sharpened in the cross-branch thread's TODO and annotated in Thread Order. |
| G8 merge "Repo housekeeping" + "MCP packaging" | NOT applied — COALESCE gate failed. Deleting scratch files and extracting a Docker toolkit into a new repo are different work products; the agent itself called them "low-coupling". |
| G10 "Fork enhancements should split"; `update_notebook(parent_id)` may belong with Issue #21 | DEFERRED — needs a call on whether it is an upstream PR or a fork-local addition. Recorded in `### Reprioritize now!`. |

**No-loss check:** passed. This pass made one addition and zero deletions; the `####` short-name set is conserved.

### Phase 2 — Value scoring

MoSCoW: 1 Must of 12 threads (8%) — well under the 60% Must-inflation cap. The single Must is user-pinned `(#)`, linked to a §4 deliverable, and is a cross-project blocker.

| Thread | Bucket | R | I | C | E | RICE |
|---|---|---|---|---|---|---|
| Notebook-path support in dashboard YAML | Must | 8 | 8 | 7 | 4 | **112** |
| mdsync follow-ups | Should | 2 | 3 | 9 | 1 | 54 |
| Test suite hygiene | Should | 4 | 5 | 8 | 3 | 53 |
| joplin-dashboard global discoverability | Should | 3 | 4 | 8 | 2 | 48 |
| Upstream contributions | Should | 3 | 5 | 7 | 4 | 26 |
| Upstream sync strategy | Could | 4 | 5 | 4 | 4 | 20 |
| Repo housekeeping | Should | 1 | 2 | 9 | 1 | 18 |
| Joppy deprecation warning | Could | 1 | 1 | 8 | 1 | 8 |
| Direct SQLite read layer | Could | 3 | 6 | 3 | 8 | 6.8 |
| CLAUDE.md cross-branch persistence | Could | 2 | 4 | 3 | 5 | 4.8 |
| MCP packaging / distribution | Could | 2 | 3 | 3 | 8 | 2.3 |
| Fork enhancements | Could | 2 | 3 | 2 | 6 | 2.0 |

**Applied re-rank (conservative — one bucket-order violation only).** Two `[queued]` threads ("Repo housekeeping", "Test suite hygiene") sat below four `[idea]` threads. Section 3 was reordered so every `[queued]` precedes every `[idea]`, which precedes every `[deferred]`; relative order within each bucket was preserved rather than applying the fine-grained RICE order, since the scoring is uncalibrated.

**Sequencing overlays.** "Upstream sync strategy" sorts above "CLAUDE.md cross-branch persistence" (blocker-above-dependent) despite the higher-RICE `[queued]` threads above it in bucket order. "Notebook-path" inherits the §4 deliverable pull-forward and stays top.

**2.5 Stale-thread review — PROPOSALS ONLY, not applied.** Untouched since 2026-05-15 (>70 days) and in a proposable state: "Fork enhancements" `[idea]`, "MCP packaging / distribution infrastructure" `[deferred]`, "CLAUDE.md cross-branch persistence" `[idea]`. Surfaced in `### Reprioritize now!` for human review.

### Phase 3 — Meta-reasoning

One trigger fired; the hard cap of one proposal per pass was respected.

- **Trigger 3 — observation/prediction mismatch.** "Notebook-path support in dashboard YAML" has been top priority since 2026-05-15 with zero commits, and both session records independently note it "remains open — untouched this session". Its first step is a `/framing`, so the thread is stalled at a **decision**, not at implementation. **Proposal: replan, do not re-rank** — either schedule that framing explicitly, or descope to exact-path-only matching that unblocks job_search without settling the fuzzy-matching question. Recorded in `### Reprioritize now!`.
- Triggers 1 (Rule of Three), 2 (parameter accumulation), 4 (TRIZ) did not fire.
- Trigger 5 (inversion check on the top three): the plausible way to make things worse this week is shipping a half-designed matcher that job_search then depends on — which supports the Phase 3 proposal rather than contradicting the ranking. No top item is mis-ranked.

### Phase 4 — Applied vs deferred

**Applied (high-confidence):**
- ↕️ Section 3 re-ranked to MoSCoW bucket order (11 threads).
- ➕ "Test suite hygiene" promoted from the session records — five pre-existing failures confirmed in two sessions and tracked nowhere.
- ↕️ Thread Order rewritten to the ranked sequence with the one forced dependency annotated.
- 🏷️ `Last prioritized` stamped `2026-07-28 15:58 [auto]`.
- §1 Focus refreshed (the mdsync thread it described is complete and archived).

**Deferred to interactive review** (all recorded in `### Reprioritize now!`, which `--auto` does not clear):
- The Notebook-path replan proposal.
- Three stale-thread `[superseded]` proposals.
- The possibly mis-filed `update_notebook(parent_id)` backlog item.
- Bootstrapping `PRIORITIZATION_RUBRIC.md`.

## Run 2026-11-25 — --auto (via /project-cleanup)

### Phase 0 — Ground state

| Read | Result |
|---|---|
| Project root | `~/projects/dev/joplin-mcp`, branch `feature/dev` |
| Layout | thread files; `status_tools validate` OK, 0 warnings |
| Metadata before | Last checkpoint 2026-11-25 12:00 · Last prioritized 2026-07-28 15:58 [auto] · Last shutdown 2026-08-01 23:00 · Last cleanup 2026-07-28 15:58 |
| Grooming anchor | `20c02a0` (project-cleanup, 2026-07-28) |
| Git since anchor | upstream v0.10.0 merge (`e033310`) + fork-tool rewire (`d4f6e19`, `2b04329`); dashboard and mdsync onto `main` (`fe905d1`); timezone-safe tests (`b9b3108`); CI workflow (`1e80f30`); fork README section (`b5bb9e2`); feature/dev scratch cleanup (`597d4a7`). Nothing touches `dashboard/loader.py`. |
| User-global | Blocker "Notebook-path support in dashboard YAML" still Active (owner: this project); no Resolved blocker names this project |
| SESSION_COMPACT | `SESSION_COMPACT_7736159a_20260801_230000.md`, distilled by a blind `Plan` subagent; no item changes a ranking (its two Inbox items were removed by the 2026-11-06 session; its open questions belong to claude-wrangler) |
| Rubric | none — scoring uncalibrated |

### Phase 1 — Structure inference

- Inventory before this pass: 1 active, 9 inactive threads. The cleanup sweep archived "Test suite hygiene" and "Repo housekeeping" (both TODOs `[x]`), leaving 1 active, 7 inactive, 11 TODOs.
- State-change quadrant: no thread has commits since the anchor; all are dormant. No promote/demote signal.
- Blind regrouping (L4, `Plan` subagent, TODOs only): eight groups mapping one-to-one onto the current eight threads. Findings: (a) the upstream-resolver check in "Frame and plan full-path matching" is a precondition listed last — applied (REORDER inside the TODO); (b) the preview/execute safety check inside "Direct SQLite read layer" is independently shippable — deferred; (c) "Survey alternatives before implementing" hides a survey/build split — deferred; (d) "Candidate tool and API additions" is three unrelated units — deferred; (e) "Extend the same treatment to joplin-mdsync" could fold into the two earlier discoverability TODOs — deferred.
- Dependencies: none new. No cycles.
- No-loss check: 11 TODO short-names before and after; none missing.

### Phase 2 — Value scoring

MoSCoW: 1 Must of 8 threads (12%), under the 60% cap; the Must is user-pinned `(#)` and linked to the §4 deliverable.

| Thread | Bucket | R | I | C | E | RICE |
|---|---|---|---|---|---|---|
| Notebook-path support in dashboard YAML | Must | 8 | 8 | 8 | 3 | **171** |
| mdsync follow-ups | Should | 2 | 3 | 9 | 1 | 54 |
| joplin-dashboard global discoverability | Should | 3 | 4 | 8 | 2 | 48 |
| Joppy deprecation warning | Could | 1 | 1 | 8 | 1 | 8 |
| Direct SQLite read layer | Could | 3 | 6 | 3 | 8 | 6.8 |
| MCP packaging / distribution | Could | 2 | 3 | 3 | 8 | 2.3 |
| Fork enhancements | Could | 2 | 3 | 2 | 6 | 2.0 |
| CLAUDE.md cross-branch persistence | Won't | — | — | — | — | — |

Notebook-path Confidence rose 7 → 8 and Effort fell 4 → 3: since v0.10.0 upstream's `get_notebook_id_by_name` resolves `Parent/Child` paths (evidence: the thread's own TODO, written after the `d4f6e19` rewire).

**Applied re-rank (bucket-order only).** "CLAUDE.md cross-branch persistence" (`[superseded]`, Won't) sat above the `[idea]` and `[deferred]` threads; moved to the bottom of Inactive Threads. Relative order within buckets kept, since scoring is uncalibrated.

**Stale-thread review — proposals only, not applied.** Unchanged since 2026-07-28: discoverability, mdsync follow-ups, Direct SQLite read layer, Joppy deprecation. Since 2026-11-05: Fork enhancements, MCP packaging. Recorded in `### Reprioritize now!`.

### Phase 3 — Meta-reasoning

Trigger 3 (observation-prediction mismatch) still fires on "Notebook-path support in dashboard YAML": top priority since 2026-05-15, no commit against it. The one proposal this pass: start with the upstream-resolver check, which may collapse the framing step entirely; applied as a TODO reorder and reflected in Focus. No other trigger fired.

### Phase 4 — Applied vs deferred

Applied:
- (Frame and plan full-path matching, bullet order → upstream check first, blind-regroup finding (a), L5 REORDER)
- (CLAUDE.md cross-branch persistence, rank → last in Inactive, MoSCoW Won't below Could, bucket order)
- (§1 Focus, next step → upstream check before `/framing`, Phase 3 trigger 3)

Deferred for interactive review (in `### Reprioritize now!`): split candidates (b)–(e) from Phase 1; the stale-thread proposals; archiving the superseded cross-branch thread; bootstrapping `PRIORITIZATION_RUBRIC.md`.
