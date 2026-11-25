# Notebook-path support in dashboard YAML

Full-path notebook matching in the dashboard loader, to unblock job_search.
- Joplin REST search currently filters notebook by leaf name only; the change lands in `JoplinRestLoader._build_query()` (`dashboard/loader.py:64-74`).
- Open cross-project blocker that job_search holds against joplin-mcp, tracked in `~/.claude/STATUS.md` under "Notebook-path support in dashboard YAML".

## TODO

### Frame and plan full-path matching  [x]

start: 2026-05-15 22:00; update: 2026-11-25 14:38
Decide the matching approach before touching the loader.
- [ ] Check upstream's `notebook_utils.get_notebook_id_by_name` first: since v0.10.0 it resolves `Parent/Child` paths through the cached `NotebookResolver` (and filters by the allowlist), so the loader may only need to resolve the configured path to an ID and query by that ID — if so, the two questions below may not need answering
- [ ] `/framing` on the approach — path-as-query syntax vs walking intermediate notebook nodes
- [ ] Resolve whether fuzzy path matching is supported or exact paths are required (open question carried from 2026-05-15)
- [ ] Write the plan in `markdowns/plans_draft/`

### Implement and test full-path matching  [x]

start: 2026-05-15 22:00; update: 2026-11-25 14:38
Land the change and verify it against the real consumer configs.
- [ ] Implement in `dashboard/loader.py`
- [ ] Test against the job_search YAML configs that use nested notebooks
- [ ] Confirm job_search can drop its leaf-name workaround, then resolve the user-global blocker
