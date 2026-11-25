# joplin-dashboard global discoverability

Put the joplin-dashboard and joplin-mdsync CLIs on PATH outside the conda env.
- Wrapper at `bin/joplin-dashboard` + a `claude-wrangler-manifest.txt` entry so the CLI resolves from any non-conda shell.
- Design rationale — including the drafted wrapper script and the five rejected alternatives — in `joplin-dashboard-global-discoverability_PLAN_design.md`.
- An interim hardcoded symlink is already in place from a job_search session; the installer will warn-and-skip on it unless run with `--force`.

## TODO

### Author the dynamic-resolution wrapper  [x]

start: 2026-05-15 22:00; update: 2026-11-25 14:53
Portable wrapper that resolves the conda env at invocation time.
- [ ] Write `bin/joplin-dashboard` resolving the env via `conda info --base` (no hardcoded miniforge path)
- [ ] `chmod +x bin/joplin-dashboard`

### Register and verify on PATH  [x]

start: 2026-05-15 22:00; update: 2026-11-25 14:47
Install through claude-wrangler's universal symlink installer.
- [ ] Add `claude-wrangler-manifest.txt` with `~/.claude/joplin-dashboard:bin/joplin-dashboard`
- [ ] Run `~/projects/dev/claude-wrangler/install.sh --force ~/projects/dev/joplin-mcp` (force overrides the interim symlink)
- [ ] Verify `joplin-dashboard --help` from a fresh non-conda shell
- [ ] Add a one-line pointer in the CLAUDE.md dashboard section
- 2026-11-25: manifest and wrappers committed and verified by path from a conda-free shell; the `install.sh --force` run is handed to claude-wrangler (its Inbox: "Install joplin-mcp's CLI links into ~/.claude"). Check off when it reports back.
- Done 2026-11-25 by claude-wrangler: both ~/.claude links now point at bin/; `env -i HOME="$HOME" PATH="$HOME/.claude:/usr/bin:/bin" joplin-dashboard --help` and the same for `joplin-mdsync` print usage. install.sh also added `backups/` to joplin-mcp's `.gitignore` (uncommitted, for a joplin-mcp session to commit).

### Extend the same treatment to joplin-mdsync  [x]

start: 2026-06-05 20:10; update: 2026-11-25 14:38
The shipped mdsync CLI has the identical PATH problem; it was deferred to ride this thread.
- [ ] Add a `bin/joplin-mdsync` wrapper alongside the dashboard one
- [ ] Add its manifest entry so `joplin-mdsync` resolves outside the conda env
