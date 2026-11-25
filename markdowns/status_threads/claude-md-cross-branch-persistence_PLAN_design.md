# Design: CLAUDE.md cross-branch persistence (proposed; needs /framing)

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
