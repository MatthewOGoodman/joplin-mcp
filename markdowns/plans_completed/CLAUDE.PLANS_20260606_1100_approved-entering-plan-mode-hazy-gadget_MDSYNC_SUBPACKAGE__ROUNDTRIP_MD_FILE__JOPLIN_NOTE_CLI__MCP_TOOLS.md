# Plan: `mdsync` subpackage — round-trip .md file ↔ Joplin note (CLI + MCP tools)

## Context

The primary workflow is **pull-edit-push**: pull a Joplin note to a local .md file, edit it with `md_tools` / line edits / Claude Code, push it back. Targets include files with load-bearing YAML frontmatter (SKILL.md-class, dashboard-read fields), so mdsync must NEVER parse or re-serialize user content — the adversarial review empirically confirmed `python-frontmatter` re-serialization mangles hand-maintained YAML (comments deleted, keys reordered).

**Settled design (user-ruled):**
- Bookkeeping lives **in-file** in a fenced `mdsync:` block maintained by **exact line-splice** — user text travels byte-verbatim; only our own canonical machine-written lines are ever parsed (plain PyYAML, no new deps).
- Parent key is `mdsync:` (not `joplin:`) — single-key collision surface, clear of Joplin's own export-frontmatter keys and Anthropic's SKILL.md keys. Fences are YAML comments (`# mdsync-begin/end`) — inert to all parsers.
- Joplin **Title round-trips via the block** (H1 never touched — avoids the literal-`#` external-editor gotcha).
- **Three verbs, all GET-first** (user-ruled): `update` (default; bound file → PUT existing note with the drift ceremony; error if note gone), `push` (create-new; existence check ONLY, never a hash comparison: refuses if the note already exists — bound id found OR exact-title match in target notebook — with the message "note already exists (id: <found-id>). To PUT with drift warning + diff: use 'update'. To replace in place (prior version saved as revision automatically): use 'push --force'."; creates fresh with NEW id if block-id note was deleted; multiple title matches → error listing candidate ids), `push --force` (clobber: PUT over the existing note with revision backup but NO drift ceremony; binds an unbound file to the title-matched note's id), `pull` (note → file; dirty local file → `.bak` backup + `markdown_bak:` line in the block, body untouched by warnings).
- **Block keys mirror the API verbatim** (`id`, `title`, `parent_id`, `tags`) plus our keys (`notebook` — the API routes only by `parent_id`, name kept for humans and create-time resolution; `synced`; the two hash fields; `markdown_bak` after a pull collision).
- **Tags are APPLIED on update/push** (user-ruled): `tags:` line present → reconcile the note's tags to the list (add/remove diff, create missing tags — reuse `tools/tags.py` tag_note/untag_note logic); line ABSENT → tags untouched (a plain `modify_note` PUT carries only title/body and cannot affect tags — tags change only via the separate tag endpoints); `tags: []` → remove all.
- **Drift detection is two-field hash comparison, body-only, owned by `update` ALONE** (user-ruled): `prior_Joplin_hash` = the note body's hash at the most recent sync point — **refreshed by EVERY successful GET or PUT** (pull, update, push, push --force), so it always dates the start of the next interim window; `current_Joplin_hash` = recomputed just-in-time from the remote body fetched by update's GET pre-check, recorded in the block. **Drift = the two differ** → revision backup, PUT anyway, warning + diff. `push`/`push --force` never compare hashes (no prior pull → no interim window to check). Metadata-only changes (notebook move, retitle) never raise drift; a remote title difference gets one informational payload line (our update overrides it with the block's title). No timestamps — because every PUT refreshes `prior_Joplin_hash` to the just-pushed body, a session's own updates can never self-trigger drift (repeat update without interim pull stays clean).
- Push default = **overwrite-with-revision-backup**; on drift the result payload **leads with a warning** + revision id, AND the warning + unified diff are **persisted into the local file** as a fenced, easily-deletable region (diff on by default; `--no-diff` suppresses).
- Pull default = **overwrite-with-local-backup** (symmetric with push): local unsynced edits (hash(local body) ≠ `synced_body_hash`) → back up existing file to `<name>_<YYYYMMDD_HHMMSS>.md.bak` alongside, then overwrite; payload reports the backup path. Clean file → no backup. (`*.bak` already gitignored.)

Tracked in STATUS.md → "Md-file ↔ Joplin round-trip tool". Mini-plan iterated through /framing + adversarial agent review + three user-ruling rounds.

## The fenced block (canonical form)

Lives inside the file's frontmatter, immediately after the opening `---`. Exact lines (machine-written, never hand-formatted). **Keys mirror the API field names verbatim** (`id`, `title`, `parent_id`, `tags`) so file ↔ API correspondence is 1:1; YAML punctuation (no JSON commas) because the block must remain valid YAML for other frontmatter parsers:

```yaml
---
# mdsync-begin
mdsync:
  id: "4a7b9c…(32-hex)"                       # API field, verbatim
  title: "Note Title"                          # API field, verbatim
  parent_id: "9f8e7d…"                         # API field, verbatim
  tags: ["GTD", "Tag: Foo"]                    # from GET /notes/:id/tags; APPLIED on update (reconcile); line ABSENT → tags untouched; [] → remove all
  notebook: "Projects/Foo"                     # informational — API routes ONLY by parent_id; used at create to resolve name→parent_id
  synced: "2026-06-06 09:30"                   # ours, informational
  prior_Joplin_hash: "sha256:…"                # note body hash at most recent sync point — refreshed at EVERY successful GET or PUT
  current_Joplin_hash: "sha256:…"              # remote body hash found at update's GET pre-check (just-in-time; API provides no hash)
  markdown_bak: "plan_20260606_093000.md.bak"  # present only after a pull collision; points at the local-edits backup
# mdsync-end
…user frontmatter keys, untouched…
---
```

**Drift = `prior_Joplin_hash` ≠ `current_Joplin_hash`** (sync-point base vs remote-now), checked by `update` only. The local file's body hash is NOT part of drift — it's used only by pull's local-collision check (hash(local canonical body) ≠ `prior_Joplin_hash` → local edits exist → `.bak`).

Splice rules (all deterministic, no stored state):
- **strip**: remove the inclusive `# mdsync-begin` … `# mdsync-end` line span (exact-match, tolerate trailing whitespace). If the remaining frontmatter is empty → remove the `---` fences too (we created them). Idempotent when absent. Two `# mdsync-begin` markers → error (corrupt block).
- **write**: replace existing span in place; else insert after opening `---`; else (no frontmatter) create `---\nblock\n---\n` at top.
- **hash**: `hashlib.sha256` over the UTF-8 **canonical body** (file minus mdsync block minus drift region, below) — identical bytes to what push sends / pull writes.

## The drift region (persisted warning + diff)

On drift, push writes a second fenced region into the **local file only**, at the top of the body (immediately after frontmatter), spliced by the same exact-marker-line mechanics as the block:

```
<!-- mdsync-drift-begin -->
WARNING: note had changed in Joplin since last sync (pushed anyway); pre-overwrite version saved as revision <id>
<unified diff: changes this push applied to the note>
<!-- mdsync-drift-end -->
```

- **Never pushed**: stripped (with contents) before sending; **excluded from the hash** so its presence doesn't mark the file dirty.
- User/agent reviews and deletes it; any stale region is dropped automatically whenever push next rewrites the file (fresh one written only on new drift).
- Markers matched as whole lines (interior diff content is irrelevant to the splice; a `-->` inside the diff could glitch HTML-comment *rendering* only — acceptable for a transient working-copy annotation).

## Files

### New: `src/joplin_mcp/mdsync/` (mirrors `dashboard/` precedent)

**`__init__.py`** — public exports: `SyncMeta`, `push_file`, `pull_note`.

**`block.py`** — fenced-block line surgery. `SyncMeta` dataclass with API-verbatim fields (`id`, `title`, `parent_id`, `tags` — `tags=None` when the line is absent, distinct from `[]`) + our fields (`notebook`, `synced`, `prior_Joplin_hash`, `current_Joplin_hash`, `markdown_bak` optional); `read_block(text) -> SyncMeta | None`; `strip_block(text) -> str`; `write_block(text, meta) -> str`; `body_hash(stripped_text) -> str`. Parses only the block span with `yaml.safe_load` (PyYAML already a dep).

**`transport.py`** — plain-Python helpers (sync functions; shared by CLI + MCP). Client via `get_joplin_client()` (`fastmcp_server.py:329`), injectable for tests. Three verbs; ALL GET first.

- `update_file(path, no_diff=False, dry_run=False, client=None) -> str` — **the default / most-used verb (pull-edit-push workflow)**
  1. Read file → strip drift region + `strip_block` → canonical body; `read_block` → meta. No block / no `id` → error ("file not bound to a note — use push to create or pull --note-id to adopt").
  2. ONE fetch `client.get_note(id, fields="id,title,body,parent_id")`. Note missing (deleted in Joplin) → **error** with warning (suggest `push` to create fresh).
  3. `current_Joplin_hash = body_hash(note.body)` (just-in-time). **Drift = `current_Joplin_hash != meta.prior_Joplin_hash`** (sync-point base vs remote-now; remote title difference → one informational payload line). Then: `save_note_revision(client, id)` (`revision_utils.py:125`, returns revision id) → `client.modify_note(id, title=…, body=…)` → `_clear_note_cache()` (`tools/notes.py:31`).
  4. **Tags reconcile** (only if `tags:` key present in block): fetch `client.get_tags(note_id=…)`; add/remove the set difference, creating missing tags — reuse the `tools/tags.py` tag_note/untag_note logic. Key absent → skip (tags untouched; the PUT cannot affect them).
  5. Rewrite file: updated block (`prior_Joplin_hash = body_hash(pushed body)` — the PUT is the new sync point; `current_Joplin_hash` as found at the pre-check; refreshed `synced` stamp) + body, dropping any stale drift region; **on drift, write a fresh drift region** (warning + revision id + `difflib.unified_diff(current_note_body, pushed_body)`; omit diff text if `no_diff`).
  6. No-op fast path: no drift, local `body_hash == meta.prior_Joplin_hash`, title unchanged, tags set-equal → report "no changes", skip all writes.
  7. Result string in the repo's uppercase-key format (`OPERATION:`, `STATUS:`). **Drift warning is the FIRST line**, mirroring the persisted region.
- `push_file(path, notebook=None, title=None, force=False, dry_run=False, client=None) -> str` — **create-new with exists-guards; `--force` = clobber. Existence check ONLY — never a hash comparison (no prior pull → no interim window).**
  1. Locate existing note: block `id` → GET it; no `id` → title-search (`client.search`, `title:"…"` scoped to target notebook; multiple exact matches → error listing candidate ids).
  2. Note found, no `force` → **refuse**: "note already exists (id: <found-id>). To PUT with drift warning + diff: use 'update'. To replace in place (prior version saved as revision automatically): use 'push --force'."
  3. Note found, `force` → clobber: `save_note_revision()` → `modify_note(found_id, title=…, body=…)` → `_clear_note_cache()` → tags reconcile if line present → `write_block` (binds unbound file to found id; `prior_Joplin_hash = body_hash(pushed body)`, `current_Joplin_hash` = pre-clobber remote hash as evidence). NO drift warning, NO drift region.
  4. Note not found (incl. block `id` whose note was deleted) → create fresh: notebook required (`--notebook` or block `notebook`) else clear error; resolve via `get_notebook_id_by_name()` (`notebook_utils.py:193` — handles `Parent/Child` paths, helpful errors); title = `--title` > block title > filename stem; `client.add_note(title=…, body=…, parent_id=…)` → apply `tags:` if present (reconcile against empty) → `write_block` with API-returned `id`/`parent_id`, resolved notebook, both hash fields = `body_hash(pushed body)`.
- `pull_note(path, note_id=None, dry_run=False, client=None) -> str`
  1. id = `note_id` arg (first-time adoption) or block's `id`; neither → error.
  2. If file exists with local unsynced edits (`body_hash(canonical body) != meta.prior_Joplin_hash`): back up existing file verbatim to `<stem>_<YYYYMMDD_HHMMSS>.md.bak` alongside and record `markdown_bak: "<backup name>"` in the new block (payload also reports it). Clean file → no backup, no `markdown_bak` line.
  3. Fetch note + tags (`client.get_tags(note_id=…)` — separate endpoint) → write file = block (refreshed: title, parent_id, tags, notebook path, both hash fields = `body_hash(pulled body)`, `synced` stamp, `markdown_bak` if applicable) + body verbatim.

**`cli.py`** — modeled on `dashboard/cli.py:67` exactly: `main(argv=None) -> int`, subparsers `update` / `push` / `pull`; **bare `joplin-mdsync <file>` defaults to `update`**; args: `path`; update: `--no-diff`; push: `--notebook`, `--title`, `--force`; pull: `--note-id`; all: `--dry-run`. Errors as `error: …` to stderr, no tracebacks; exit 0 success / 2 error.

### New: `src/joplin_mcp/tools/notes_files.py`

Thin async MCP wrappers per house pattern (helpers do the work; `@create_tool` functions can't call each other):
- `@create_tool("update_note_from_file", "Update note from markdown file")` → `transport.update_file(...)`
- `@create_tool("push_md_file", "Push markdown file to new note")` → `transport.push_file(...)`
- `@create_tool("pull_note_to_file", "Pull note to markdown file")` → `transport.pull_note(...)`

### Modified

| File | Change |
|---|---|
| `src/joplin_mcp/tools/__init__.py` | add `notes_files` import (registers tools) |
| `src/joplin_mcp/config.py` | `DEFAULT_TOOLS`: `"push_md_file": True`, `"pull_note_to_file": True`; add to `TOOL_CATEGORIES` |
| `pyproject.toml` | `[project.scripts]` add `joplin-mdsync = "joplin_mcp.mdsync.cli:main"`. **No new dependencies** (PyYAML, hashlib, difflib all present/stdlib) |
| `CLAUDE.md` | Source-layout table: `mdsync/` + `tools/notes_files.py` rows (and the missing `imports/` row, discovered during exploration); tool-inventory counts; short "Mdsync Subpackage" section |
| `STATUS.md` | tick thread items as completed |

## Tests (gate: implementation not complete until these pass in the FULL suite — subset runs trip `--cov-fail-under=20`)

Fixtures `tests/fixtures/mdsync_user_frontmatter.md` (frontmatter with comments + quoting quirks), `mdsync_no_frontmatter.md`, `mdsync_with_block.md`. Mock joppy per `tests/conftest.py` `mock_joppy_client` / `SimpleNamespace` note objects (dashboard-test pattern).

- **`tests/test_mdsync_block.py`** — `TestStripBlock`: removes span; absent → unchanged (idempotent); block-only frontmatter → fences removed too; double-begin → error; **user YAML byte-identical after strip** (the load-bearing guarantee). `TestWriteBlock`: insert into existing frontmatter; create frontmatter when none; replace existing in place. `TestReadBlock`: field parse; absent → None. `TestDriftRegion`: write/strip drift region; excluded from hash; stale region dropped on rewrite.
- **`tests/test_mdsync_transport.py`** — `TestUpdate`: **call order** `save_note_revision` → `modify_note` → `_clear_note_cache`; `prior_Joplin_hash` refreshed to pushed body → **repeat update without interim pull reports no drift**; `current_Joplin_hash` recorded from the GET pre-check; remote-title-difference → informational line, NOT drift; unbound file (no block id) → error; note deleted in Joplin → error suggesting push. `TestUpdateDrift`: drift fires iff `current_Joplin_hash != prior_Joplin_hash`; warning is first line of payload + revision id; drift region persisted into file with unified diff (omitted with `no_diff`); drift region never reaches pushed body. `TestUpdateTags`: `tags:` present → reconcile (adds tagged, removals untagged, missing tag created); key absent → no tag API calls; `tags: []` → all removed. `TestUpdateNoop`: unchanged content + set-equal tags → no write calls. `TestPushCreate`: `add_note` called with resolved notebook id; block written back with API-returned id/parent_id; tags applied when present; missing notebook → clear error. `TestPushGuards`: note exists (bound id or exact-title match) → refuse with found-id + both-verbs message; NO hash comparison performed; multiple title matches → error listing candidates; block id + note deleted → creates fresh with NEW id. `TestPushForce`: clobbers found note (revision saved, `modify_note` called, NO drift region/warning); binds unbound file to title-matched note's id; behaves as plain create when nothing exists. `TestPull`: body verbatim (frontmatter content intact); block regenerated with API-verbatim keys incl. `tags` from `get_tags`; title refreshed. `TestPullDirty`: local hash ≠ `prior_Joplin_hash` → `.bak` backup created (verbatim copy, timestamped name) + `markdown_bak:` line in new block, then overwrite; clean file → no backup, no `markdown_bak` line. `TestRoundTrip`: pull→update no-edit → no-op; pull→edit→update→pull → byte-stable.
- **`tests/test_mdsync_cli.py`** — `TestCliUpdate` / `TestCliPush` / `TestCliPull`: `patch.object` on transport; **bare `<file>` (no subcommand) dispatches to update**; exit codes 0/2; `error: ` stderr format; `--dry-run` writes nothing.

## Verification

1. `pytest` (full suite) + `black src/ tests/ && ruff check src/ tests/`
2. `pip install -e .` → `joplin-mcp` env; against live Joplin ("Testing" notebook): `joplin-mdsync push --notebook Testing --title "mdsync test" /tmp/mdsync_test.md` → confirm note created + block written with API-verbatim keys; `push` the same file again → confirm refusal naming both next steps (update / push --force); `push --force` → confirm clobber with revision saved and NO drift region; edit in Joplin → `joplin-mdsync /tmp/mdsync_test.md` (bare = update) → confirm drift warning leads the payload AND the fenced drift region + diff appears at top of the local file (and is absent from the note); update again immediately → confirm NO false drift (prior_Joplin_hash refreshed); delete the region → next update clean; edit the local file → pull → confirm `.bak` created + `markdown_bak:` line in block, then file overwritten; add a tag to the `tags:` line → update → confirm tag applied in Joplin; remove the `tags:` line entirely → update → confirm tags untouched; pull → edit locally with `md_tools insert` → update → verify in Joplin.
3. `/mcp` reload → exercise `push_md_file` / `pull_note_to_file` MCP tools.
4. **GFM-table render check (deferred-gate item)**: include a Markdown table in the test push; visually verify Joplin's render. Broken → open the table-reformatter thread in STATUS.md; fine → close the question.

## Out of scope (v1)

Attachments/resources; directory ↔ notebook batch (block design doesn't foreclose it); watch mode; table reformatter (pending check above); pure their-edits-only drift diff via revision reconstruction (`revision_utils._reconstruct_revision_content` exists — note as v1.1 option).
