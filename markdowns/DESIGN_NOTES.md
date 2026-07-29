# Design notes

Durable design rationale for features that are not yet built — problem statements, the approach selected, and the alternatives rejected along the way.

Each note's corresponding work is tracked as a thread in `STATUS.md`, and each thread points back here. The threads carry the decisions and the steps; these notes carry the reasoning behind them, so that picking a thread up later does not mean re-deriving why it is shaped the way it is.

A note graduates out of this file once its feature ships: the settled rationale moves to `CLAUDE.md` under Learnings → Design Decisions, which is scoped to implemented work.

## Design: joplin-dashboard global discoverability (wrapper + claude-wrangler-manifest.txt)

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

## Design: CLAUDE.md cross-branch persistence (proposed; needs /framing)

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

## Design: Direct SQLite read layer

The Joplin REST API has no server-side filtering — no WHERE-clause params, no field-value filters on collection endpoints. All filtering is done client-side in Python after fetching full result sets via joppy. This affects trash listing, notebook-scoped queries, todo filtering, and any field-based search.

**Two options:**

- **Option A (preferred): Add SQLite reader directly to joplin-mcp.** Read-only queries against `~/.config/joplin-desktop/database.sqlite` for efficient filtered reads; keep joppy/REST API for writes (which need Joplin's sync/indexing). Belongs in joplin-mcp, not in joppy — joppy is a REST client and has no SQLite basis.
- **Option B: Contribute filtering params to Joplin's REST API.** Would require forking/PR to `laurent22/joplin` itself — much heavier overhead for uncertain acceptance. The API appears intentionally minimal.

**Design considerations for hybrid SQLite-read / REST-write:**

- SQLite reads return note IDs; writes pass those IDs directly to joppy REST calls. The MCP agent never handles raw ID lists — the tool internally pipes SQLite query results to REST update calls.
- Preview/execute pattern needs a proper safety check. Current `first_title` + `expected_count` verification is weak. Should compare the exact set of note IDs between preview and execute (e.g., hash of sorted ID list) to catch any drift.
- May need a dry-run mode for updates: SQLite query shows what would change, user confirms, then REST applies. Similar to current `search_and_bulk_update_preview` but with accurate counts from SQLite rather than overfetched/post-filtered results.

**Caveat:** Direct SQLite access assumes local filesystem (same host as Joplin Desktop). Remote HTTP MCP transport would break this, but would also break `backup_database` and other filesystem-dependent features — a broader re-engineering at that point.

## Design: Upstream sync strategy (open questions)

PR #23 merged into alondmnt/joplin-mcp on 2026-04-17 (`restore_from_trash` + `find_notes(trash=True)` + docstring fixes). Our `main` and `feature/dev` don't have these changes from upstream's side. Open questions before settling on a sync workflow:

- Is our code structure clean enough to rebase on upstream? Our 12 tools in `tools/*.py` are additive, but `fastmcp_server.py` and `formatting.py` have modifications.
- `git merge upstream/main` vs `git rebase --onto upstream/main` for our branches?
- How to handle divergence if alondmnt modifies files we also modified?
- Any other upstream changes since v0.7.1 besides PR #23?

Affects both `main` and `feature/dev`. The goal is to pull upstream changes readily.

## Design: MCP packaging / distribution infrastructure (parked)

The `extract/mcp-docker-dev` branch (snapshot of old monolithic branch) contains Docker development toolkit, deployment modes, install enhancements, and config management (`mcp-config-manager.sh`). Original plan was to extract into separate `MatthewOGoodman/mcp-docker-dev` repo as reusable infrastructure for any MCP project. Status: parked, not started.
