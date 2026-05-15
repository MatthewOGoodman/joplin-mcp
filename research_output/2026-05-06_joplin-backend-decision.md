---
title: "Research: Joplin query backend choice for dashboard library"
date: 2026-05-06
project: joplin-mcp
tags: [joplin, dashboard, sqlite, rest-api, backend-decision]
mode: scan
status: complete
---

# Research: Joplin query backend choice for dashboard library

## Executive Summary

Two backends were evaluated for a dashboard library that will query Joplin and serve both job_search and future joplin_user GTD use cases: the Joplin Data REST API (via the existing joplin-mcp client) versus direct SQLite reads against `~/Library/Application Support/joplin-desktop/database.sqlite`. The headline finding is a correction: the previous capability audit was wrong on the most consequential point — combined-criteria queries like `tag:X notebook:Y` **do** work server-side via Joplin's `/search` endpoint, ANDed in the search engine's queryBuilder, with no client-side intersection required. Separately, end-to-end encryption only encrypts items during sync serialization; the local SQLite database stays plaintext at rest, including bodies. Combined with confirmation that Joplin's schema has changed only additively over the last 18 months (migrations 42–49, no renames or type changes to `notes`/`tags`/`note_tags`/`folders` columns relevant to the example dashboard query), the previously-asymmetric tradeoff between the two backends collapses substantially. Recommended path: REST API for v1 behind a thin `Loader` interface; SQLite implementation deferred but cheap to add when sync-index staleness or OCR-text edge-case bugs bite in practice.

## Takeaways and Next Actions

1. **Adopt REST API as the v1 loader** — Lowest implementation effort, reuses the existing joplin-mcp client (`client.search_all(query=...)` already exists at `src/joplin_mcp/tools/field_helpers.py:194`), and supports our combined-criteria queries server-side. Risk: search index can be stale immediately after sync ([joplin#11631](https://github.com/laurent22/joplin/issues/11631)), and free-text-with-filter combos break when OCR text is involved ([joplin#12128](https://github.com/laurent22/joplin/issues/12128)).
2. **Define a `Loader` interface from day 1** — Per user's preference for pluggable design. The interface is small (one or two methods returning typed `NoteRecord` lists). Adds ~10 minutes upfront, removes refactoring cost later. Risk: minor over-engineering; mitigated because the abstraction is genuinely cheap.
3. **Defer SQLite implementation to v1.5** — Schema is stable enough that this is a tractable addition, and E2EE is no longer a blocker (local SQLite is plaintext at rest). Build it when there is a concrete trigger: the search-index staleness or the OCR bug biting a real workflow, OR a use case that needs to run without Joplin Desktop open. Risk: SQLite ecosystem signals (third-party tools tested against Joplin v3) are thin — no surveyed tool advertised v3 compatibility, though no breakage was reported either.
4. **Document the corrected REST capability set** — Update both mini-plans (`job_search/markdowns/plans_draft/job_search_architecture_mini_plan.md` and `joplin-mcp/markdowns/plans_draft/dashboard_script_mini_plan.md`) to reflect that combined `tag:X notebook:Y` queries work in one REST call. The earlier audit's "client-side intersection required" claim was incorrect.

## Research Question

Choose the appropriate backend for querying Joplin from a dashboard library that will serve (a) the job_search project dashboard and (b) future joplin_user GTD/task-management use cases. Two named candidates: Joplin REST API (via existing joplin-mcp client to `localhost:41184`) vs direct SQLite read against the desktop app's database file. Scope of this scan: two specific factual sub-questions — (1) does Joplin's REST `/search` actually support combined-criteria queries server-side, and (2) is the SQLite schema stable enough across recent Joplin versions for direct reads to be a durable strategy.

## Analysis

The retrieval surfaced one significant correction and two confirmations. The correction — that REST `/search` does support `tag:X notebook:Y` server-side — was the deciding finding because it eliminates the previously-cited "client-side intersection required" overhead and matches REST against SQLite on query expressivity for our scale (a few thousand notes). The two confirmations (additive-only schema changes, plaintext-at-rest local SQLite even with E2EE) make the SQLite path more viable than originally feared and remove the assumption that future E2EE adoption forces a REST-only world. Net effect: REST wins on lowest implementation effort and dependency reuse; SQLite remains a respectable fallback for sync-staleness or OCR edge cases. Pluggable Loader is cheap insurance.

## Cross-cutting Findings

### Combined-criteria query support is server-side, not client-side

The previous capability audit (run earlier in this conversation) claimed Joplin's REST API has "no single-call multi-criteria filtering." This is wrong. Joplin's search engine implements `tag:X notebook:Y` as an `AND`-combined `WHERE` clause in [queryBuilder.ts](https://github.com/laurent22/joplin/blob/dev/packages/lib/services/search/queryBuilder.ts), with explicit special-casing to keep the notebook filter ANDed even when `any:1` (OR mode) is set: *"The notebook filter should be independent of the any filter."* The joplin-mcp wrapper passes queries through verbatim to `/search` (see `src/joplin_mcp/tools/field_helpers.py:172-174`: *"The query string is passed to Joplin untouched — never parsed for field names."*) and a test in `tests/pr_tests.py:332-334` confirms that combined queries are sent as-is. This finding affects both backends' viability — REST is now strictly comparable to SQLite on query expressivity for our use cases.

### E2EE encrypts in transit, not at rest

Per the [Joplin E2EE spec](https://joplinapp.org/help/dev/spec/e2ee/), items are encrypted only during sync serialization (`BaseItem.serializeForSync`). The local `database.sqlite` keeps titles, bodies, tags, folders, and resources in plaintext, even with E2EE enabled — confirmed by Joplin maintainer comments and the open meta-issue [joplin#13573](https://github.com/laurent22/joplin/issues/13573). This invalidates the assumption (stated earlier in the framing cycle) that enabling E2EE would degrade SQLite to metadata-only access. SQLite remains fully viable for body queries even after the user enables E2EE.

## Detailed Findings by Framing

### Framing 1 — Joplin REST `/search` capability

This framing asked which combined-criteria query forms actually return correct results from `GET /search`.

- **`tag:X notebook:Y` (AND tag + notebook)** — Works, server-side. Joplin's [filterParser.ts](https://github.com/laurent22/joplin/blob/dev/packages/lib/services/search/filterParser.ts) accepts both `tag:` and `notebook:` as valid operators; queryBuilder ANDs them in the SQL `WHERE`. Test coverage exists in [filterParser.test.ts](https://github.com/laurent22/joplin/blob/dev/packages/lib/services/search/filterParser.test.ts).
- **`folder:` alias for `notebook:`** — Does not exist. The `validFilters` set is exactly `any, title, body, tag, notebook, created, updated, type, iscompleted, due, latitude, longitude, altitude, resource, sourceurl, id`. Use `notebook:` only.
- **`-tag:X` (exclude tag)** — Works. Test cases for "negated tag queries" cover `-tag:mozart`. Negation is rejected only on `type:` and `iscompleted:` (with explicit error messages from the parser).
- **`tag:A tag:B` (require both tags)** — Works as AND by default (`any:0`); the engine uses `INTERSECT` for tag conjunction, switching to `UNION` under `any:1`.
- **Multiple `notebook:` filters** — OR'd together by design; per [Joplin search docs](https://joplinapp.org/help/apps/search/), *"There's an exception for the notebook filters which are connected by 'OR'. The reason being that no note can be in multiple notebooks at once."*
- **Free-text + filter combos** — Generally work, but a current bug ([joplin#12128](https://github.com/laurent22/joplin/issues/12128), opened 2025-06-23, Joplin 3.2.13) breaks them when OCR-extracted text is involved: `notebook:Testing Hello World` returns no results in some cases where `Hello World` alone does.
- **Search index staleness** — [joplin#11631](https://github.com/laurent22/joplin/issues/11631) (open as of 2026-03-14) reports the `/search` index lags after recent edits or sync. SQLite reads bypass this entirely.
- **Pagination** — `/search` supports standard `page`, `limit`, `order_by`, `order_dir`, `has_more`. The joppy library's `search_all()` (used by joplin-mcp) auto-paginates, so combined queries return full result sets at our scale.

### Framing 2 — Joplin SQLite schema stability

This framing asked whether direct SQL reads against the desktop SQLite are durable across Joplin versions.

- **Last 18 months of migrations are additive only.** Migrations 42 through 49 in [`packages/lib/services/database/migrations/`](https://github.com/laurent22/joplin/tree/dev/packages/lib/services/database/migrations) only add columns, indexes, and FTS tables. No renames, no type changes, no drops. Critical columns for our example query (`notes.id`, `notes.title`, `notes.body`, `notes.parent_id`, `notes.updated_time`, plus `tags.id`, `tags.title`, `note_tags.note_id`, `note_tags.tag_id`) remain unchanged.
- **The v3.0 transition (2024) was a sync-protocol bump, not a schema break.** Per the [v3.0 release thread](https://discourse.joplinapp.org/t/desktop-pre-release-v3-0-is-now-available-updated-21-08-2024/36992), v3 introduced trash (`deleted_time` columns added in migration 46) and changed the sync protocol minimum, but the local table schema is backward-compatible.
- **`notes.encryption_cipher_text` exists but is transient.** It is only populated for items received encrypted from sync that haven't been decrypted yet. After decryption it's cleared; the plaintext lives in `body`.
- **WAL concurrency is safe for short reads.** SQLite WAL mode (which Joplin uses based on its standard configuration) lets readers and writers operate concurrently; readers see a consistent snapshot at transaction start ([SQLite WAL docs](https://sqlite.org/wal.html)). Long-running readers can theoretically block checkpoints, but our dashboard queries are short.
- **Third-party tool ecosystem signal is thin.** A [forum thread on direct SQLite queries](https://discourse.joplinapp.org/t/directly-query-the-sqlite-database/4176) acknowledges the practice and recommends copying the file before reading. No surveyed third-party tool (joplin-importer, joplin-batch-web) had explicit "tested against v3" or "broken on v3" claims, in either direction.

## Further Research

- **SQLite reader implementation effort** — A scoped prototype reading `notes`, `note_tags`, `tags`, and `folders` would calibrate the actual code volume relative to the REST loader. Worth a half-day spike before committing to "v1.5 or later" timing.
- **Joplin sync-index lag in practice** — The frequency and severity of [joplin#11631](https://github.com/laurent22/joplin/issues/11631) under our usage pattern is unknown. If dashboard refreshes routinely show stale results after Web Clipper captures or edits, that's a concrete trigger to add the SQLite loader.
- **Confirm Joplin's `journal_mode`** — Read `PRAGMA journal_mode` against a live database to confirm WAL is in use, vs. delete or truncate journaling, which would change the safety profile of concurrent reads. Quick one-liner; not blocking.

## Sources

- [Joplin: filterParser.ts (validFilters set)](https://github.com/laurent22/joplin/blob/dev/packages/lib/services/search/filterParser.ts) — confirms `notebook:` is valid and `folder:` is not, lists the full operator set.
- [Joplin: queryBuilder.ts (notebook AND tag composition)](https://github.com/laurent22/joplin/blob/dev/packages/lib/services/search/queryBuilder.ts) — confirms server-side AND of tag and notebook filters with the explicit comment carving notebook out from `any:1` OR mode.
- [Joplin: filterParser.test.ts (negated tag tests)](https://github.com/laurent22/joplin/blob/dev/packages/lib/services/search/filterParser.test.ts) — covers `-tag:mozart`, title+body field tests.
- [Joplin: search docs (notebook OR semantics)](https://joplinapp.org/help/apps/search/) — confirms multiple `notebook:` filters are OR'd by design.
- [Joplin: REST API reference](https://joplinapp.org/help/api/references/rest_api/) — pagination behavior, endpoint contracts.
- [joplin#12128 (open): notebook filter + free-text broken with OCR](https://github.com/laurent22/joplin/issues/12128) — current edge-case bug.
- [joplin#11631 (open): /search index stale after sync](https://github.com/laurent22/joplin/issues/11631) — known staleness exposure.
- [Joplin: schema migrations 42–49](https://github.com/laurent22/joplin/tree/dev/packages/lib/services/database/migrations) — confirmed additive-only.
- [Joplin v3.0 release thread](https://discourse.joplinapp.org/t/desktop-pre-release-v3-0-is-now-available-updated-21-08-2024/36992) — v3 transition is sync-protocol, not schema.
- [Joplin E2EE spec](https://joplinapp.org/help/dev/spec/e2ee/) — encryption is at sync serialization, not at rest.
- [joplin#13573 (open): local DB unencrypted](https://github.com/laurent22/joplin/issues/13573) — meta-issue tracking the design decision.
- [Forum: directly query the sqlite database](https://discourse.joplinapp.org/t/directly-query-the-sqlite-database/4176) — community precedent and safety guidance.
- [SQLite WAL docs](https://sqlite.org/wal.html) — concurrency semantics for the SQLite reader path.
- joplin-mcp wrapper code: `src/joplin_mcp/tools/field_helpers.py:172-194`, `src/joplin_mcp/tools/notes.py:1012,1036,1358,1443`, `tests/pr_tests.py:332-334`, `CHANGELOG.md:28`, `CLAUDE.md:145,196`.
- [joplin-mcp#9 (closed): emoji notebook names](https://github.com/alondmnt/joplin-mcp/issues/9) — minor `notebook:` filter encoding edge case.

## Empirical verification (2026-05-06, addendum)

To address user concern about `tag:X OR W notebook:Y OR Z` queries specifically (recalled as a real limitation hit during joplin-mcp development), an empirical boolean matrix was run against the live Joplin Desktop REST API on the user's machine. Three known tags and two known notebooks were used; counts were compared against expected set-theoretic outcomes.

All combos behaved as documented:

- `tag:A tag:B` returns A∩B (default AND)
- `any:1 tag:A tag:B` returns A∪B (size = |A| + |B| − |A∩B|, exact match)
- `tag:A -tag:B` returns A∖B (exact match)
- `tag:A notebook:X` returns A∩X
- `any:1 tag:A tag:B notebook:X` returns (A∪B)∩X (exact match by inclusion-exclusion against single-tag-with-notebook counts)
- `notebook:X notebook:Y` returns X∪Y (multiple notebook filters OR'd by design, per Joplin docs)
- **`any:1 tag:A tag:B notebook:X notebook:Y` returns (A∪B)∩(X∪Y) — the specific combo recalled as a limitation works correctly in current Joplin.**

The single structural limitation observed: `any:` is a global flag, so per-clause grouping like `(A AND B) OR (C AND D)` is not expressible in one query. For v1 dashboard sections (single notebook, simple tag filters per section) this is irrelevant.

Conclusion: REST is fully sufficient for v1 dashboard query needs. The limitation the user recalled was either fixed in a more recent Joplin version, was a different bug (e.g., OCR-text or emoji-notebook edge cases), or has been forgotten precisely. None of these affect v1.

## Methodology

Scan mode, standard scoping protocol. Two framings (REST search-syntax behavior, SQLite schema stability) explored in parallel via two general-purpose retrieval agents — each combining local repo inspection with Joplin GitHub source/issue/release-note review and community forum reading. Approximately 20 sources surveyed across both framings. Findings synthesized into a single prioritized recommendation with explicit follow-up triggers. Empirical verification of REST boolean syntax added 2026-05-06 against live Joplin instance. No Joplin push (no Claude_Research notebook target for this work).
