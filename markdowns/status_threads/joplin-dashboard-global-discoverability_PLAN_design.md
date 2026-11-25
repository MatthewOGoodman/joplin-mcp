# Design: joplin-dashboard global discoverability (wrapper + claude-wrangler-manifest.txt)

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
