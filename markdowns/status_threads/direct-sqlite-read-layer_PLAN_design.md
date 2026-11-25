# Design: Direct SQLite read layer

The Joplin REST API has no server-side filtering — no WHERE-clause params, no field-value filters on collection endpoints. All filtering is done client-side in Python after fetching full result sets via joppy. This affects trash listing, notebook-scoped queries, todo filtering, and any field-based search.

**Two options:**

- **Option A (preferred): Add SQLite reader directly to joplin-mcp.** Read-only queries against `~/.config/joplin-desktop/database.sqlite` for efficient filtered reads; keep joppy/REST API for writes (which need Joplin's sync/indexing). Belongs in joplin-mcp, not in joppy — joppy is a REST client and has no SQLite basis.
- **Option B: Contribute filtering params to Joplin's REST API.** Would require forking/PR to `laurent22/joplin` itself — much heavier overhead for uncertain acceptance. The API appears intentionally minimal.

**Design considerations for hybrid SQLite-read / REST-write:**

- SQLite reads return note IDs; writes pass those IDs directly to joppy REST calls. The MCP agent never handles raw ID lists — the tool internally pipes SQLite query results to REST update calls.
- Preview/execute pattern needs a proper safety check. Current `first_title` + `expected_count` verification is weak. Should compare the exact set of note IDs between preview and execute (e.g., hash of sorted ID list) to catch any drift.
- May need a dry-run mode for updates: SQLite query shows what would change, user confirms, then REST applies. Similar to current `search_and_bulk_update_preview` but with accurate counts from SQLite rather than overfetched/post-filtered results.

**Caveat:** Direct SQLite access assumes local filesystem (same host as Joplin Desktop). Remote HTTP MCP transport would break this, but would also break `backup_database` and other filesystem-dependent features — a broader re-engineering at that point.
