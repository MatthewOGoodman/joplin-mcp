# Direct SQLite read layer

The Joplin REST API has no server-side filtering, so all filtering is Python-side post-fetch. A read-only SQLite layer over `~/.config/joplin-desktop/database.sqlite` would enable efficient filtered reads while keeping joppy/REST for writes. Caveat: assumes the server shares a host with Joplin Desktop. Design considerations — including the rejected option of contributing filter params upstream to Joplin itself — in `markdowns/DESIGN_NOTES.md` → "Design: Direct SQLite read layer". First consumer in waiting: the dashboard's `Loader` interface (`dashboard/loader.py`) was built so a `JoplinSqliteLoader` can drop in — see CLAUDE.md Learnings → Design Decisions, "Dashboard reads over REST, not SQLite", for the triggers that would justify it.

## TODO

### Frame the hybrid read/write architecture  [ ]

start: 2026-05-15 22:00; update: 2026-07-28 15:58
Scope the split before committing to a second data path.
- [ ] `/framing` on hybrid SQLite-read / REST-write architecture
- [ ] Decide the preview/execute safety check — ID-set hash rather than the current weak `first_title` + `expected_count`
- [ ] Write the plan
