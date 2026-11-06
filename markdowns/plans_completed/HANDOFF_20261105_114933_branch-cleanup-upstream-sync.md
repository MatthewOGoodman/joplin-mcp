# Branch cleanup and upstream v0.10.0 sync (hand-off from job_search session)

**Originating project:** job_search · **Written:** 2026-11-05 11:49 · **State checked:** 2026-11-05, read-only (no fetch, no git writes in this repo)

## Motivation

The fork's branches have drifted since the April PR work: one branch is already merged upstream, two point at the same frozen commit, and the local `upstream/main` ref is stale. The public GitHub profile links to this fork, so the branch list a visitor sees should reflect the live work only. Separately, upstream has moved from v0.7.1 to v0.10.0, and `main` / `feature/dev` have not been brought forward.

## Findings

**Local `upstream/main` is stale.** It points at `1a7f40e` (v0.7.1). GitHub reports upstream `main` at `b84c313` (2026-09-12, "docs: trim the v0.10.0 changelog entry"). Every ahead/behind count below is against the stale ref; run `git fetch upstream` first and recompute.

**Upstream PRs from this fork:** #23 `pr/restore-from-trash` MERGED 2026-04-17. #19 (bulk ops, revisions, trash, backup) CLOSED — maintainer prefers extending existing tools; he opened issues #20 (trash listing via `find_notes(trash=True)`), #21 (moving notes via `notebook_name` on `update_note`), and a third (see CLAUDE.md "PR #19 Status").

**Uncommitted state on `feature/dev`:** `STATUS.md` modified; `markdowns/SESSION_COMPACT_7736159a_20260801_230000.md` untracked. Commit both before any branch operation.

| Branch | Tip | State (vs stale upstream/main) | Recommendation |
|---|---|---|---|
| `main` | `0c5aa02` 2026-04-06 | v0.7.1 + 4 commits (12 new tools, optional enhancements, bool-conversion fix); ancestor of `feature/dev` | Keep. Bring forward to upstream v0.10.0 (see below). |
| `feature/dev` | `ee30989` 2026-07-28 | `main` + 14 commits: dashboard subpackage, mdsync subpackage, labelled `backup_database`, state-file commits | Keep; primary branch. Commit the dirty files first. |
| `pr/restore-from-trash` | `6877ea0` 2026-04-15 | Shipped as upstream #23; squash-merged, so `git merge-base --is-ancestor` reports not merged | Delete local and `origin`. Confirm the squash commit exists in upstream first. |
| `feature/bulk-operations-and-api-enhancements` | `3de13d4` 2026-03-31 | Original monolithic branch, 21 ahead / 128 behind; its tools were re-ported onto v0.7.1 as `main` | Replace with a tag (e.g. `archive/bulk-operations-monolith`) and delete the branch, or delete outright. CLAUDE.md marks it "Frozen, historical reference only", so a tag preserves that. |
| `extract/mcp-docker-dev` | `3de13d4` 2026-03-31 | SAME commit as the bulk-ops branch; kept as the start point for the parked "extract Docker/install infra into `mcp-docker-dev` repo" thread (STATUS.md) | Keep while that thread is live. If the thread is dropped, delete; the tag above holds the same commit either way. |

## Approach

1. Commit the dirty `STATUS.md` and the untracked SESSION_COMPACT on `feature/dev`.
2. `git fetch upstream` and `git fetch origin`; recompute ahead/behind for every branch.
3. Verify #23's content is in upstream `main` (`git log upstream/main --grep "restore_from_trash"` or by file content), then delete `pr/restore-from-trash` locally and on `origin`.
4. Decide tag-vs-delete for `feature/bulk-operations-and-api-enhancements`; apply. Decide whether the `mcp-docker-dev` extraction thread is still wanted; keep or delete `extract/mcp-docker-dev` accordingly.
5. **Upstream v0.10.0 sync (the substantive part).** Before merging, compare upstream's tool surface against the fork's 12 tools: upstream may have implemented issues #20 / #21 / the third issue in its own way, which would make some fork tools redundant or conflicting. Decide per tool: drop (upstream equivalent exists), keep, or reshape to match upstream's interface. Then merge or rebase `main` onto upstream and bring `feature/dev` forward. Run the test suite; CLAUDE.md records five pre-existing failures, so compare against that baseline.
6. Update CLAUDE.md → Branch Strategy table and Upstream Relationship ("Upstream version", "Our main") to the new state.
7. Optional: set the GitHub default branch and check what the fork's repo page shows a visitor (README, default branch).

## Dependencies

None outside this repo. Deleting remote branches and force-moving refs are destructive — confirm with the user before each.

## Success criteria

- Remote branch list is `main`, `feature/dev`, plus `extract/mcp-docker-dev` only if its thread is live.
- `main` is based on upstream v0.10.0 (or a deliberate later version) with every fork tool either kept, reshaped, or dropped by an explicit decision.
- CLAUDE.md Branch Strategy and Upstream Relationship match reality.
- Tests pass apart from the recorded pre-existing failures.
