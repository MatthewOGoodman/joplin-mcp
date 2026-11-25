# CLAUDE.md cross-branch persistence

Superseded 2026-11-06 — handed to claude-wrangler as the single owner.
- claude-wrangler's Inbox item "Revive or retire the cross-branch context-file carry" carries this thread's unique TODOs: survey alternatives, the shared-vs-branch split, and carrying the thread-file directory too.
- Drop this thread once that item is picked up.
- The draft design that preceded the hand-off is in `claude-md-cross-branch-persistence_PLAN_design.md`; it archives with this thread.

## TODO

### Survey alternatives before implementing  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
The floating-file design should not be built until better options are ruled out.
- [ ] `/framing` to survey alternatives — post-checkout hook, separate tracked branch, others
- [ ] Define what is shared vs branch-specific — branch roles are now settled (merge-based sync; see CLAUDE.md Upstream Relationship)
- [ ] Implement the chosen design, carrying STATUS.md as well as CLAUDE.md
