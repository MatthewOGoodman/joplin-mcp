# SESSION COMPACT

**datetime:** 2026-06-06 11:00
**head_commit:** 0101d9a
**project_root:** /Users/mattheworlando/projects/dev/joplin-mcp
**session_id:** 32abac0d (first 8 of session UUID)

## Executive summary

Built, tested, and live-verified the **mdsync subpackage** end-to-end in one session (uncommitted — feature commit queued in STATUS.md `### Resolve git state now!`). The session is also the **prototype run of the `/preplan` pipeline** now handed off to claude-wrangler: mini-plan → adversarial subagent review → /framing integration → revised plan → implementation — with the adversarial review *empirically disproving* the initially-approved design (in-file frontmatter metadata via python-frontmatter) and four user-ruling rounds reshaping verbs, hashes, and tags before code. What a fresh agent can't get from STATUS/CLAUDE.md: the design was inverted mid-planning (push-first/file-canonical → pull-edit-update/note-canonical) by user correction of the use case, and the drift mechanism went through three designs (updated_time + re-fetch → single body hash → two-field prior/current hash, the last dissolving an entire spurious-drift complication the user kept flagging as confusing — confusion that turned out to be a design smell, not a comprehension gap).

## Brief narrative of thread progress

1. User asked whether a round-trip .md ↔ note CLI idea was in the Inbox — it wasn't (never captured anywhere). /framing run; thread created directly in §2 on user ruling.
2. Mini-plan drafted → user rulings (mdsync/md_push_pull naming, overwrite-with-backup default) → **adversarial general-purpose agent** dispatched with /framing methodology; it live-probed `python-frontmatter` re-serialization in /tmp (comments deleted, keys alphabetized, quoting rewritten) and proposed the sidecar pivot; orchestrator spot-verified its codebase claims (`imports/` subpackage — absent from CLAUDE.md docs; `get_notebook_id_by_name` path support) before relaying.
3. User pushed back on sidecar ("why is format preservation hard?") → ruamel/line-splice alternatives surfaced → **fenced in-file block via exact line-splice** won (user: "I thought you were going to suggest fencing to begin with"). `mdsync:` key chosen over `joplin:` (collision insurance vs Joplin's own export-frontmatter keys).
4. Three further user-ruling rounds during plan mode: API-verbatim block keys (`id`/`title`/`parent_id`/`tags`); three verbs update(default)/push/pull with push --force = clobber ("update and push are both PUTs; the difference is ceremony"); two-hash drift model (`prior_Joplin_hash` refreshed at EVERY GET/PUT, `current_Joplin_hash` just-in-time) replacing all timestamp machinery; tags applied on update when line present; pull = overwrite-with-`.bak` + `markdown_bak:` line instead of refuse/--force.
5. Implementation in one pass (block.py → transport.py → cli.py → MCP wrappers → registration → 71 tests, first-run green). One live-found bug: PyYAML `default_flow_style=None` collapsed the tags-less block to one flow line — fixed to `False`.
6. Live verification: full CLI matrix on Testing notebook; then **in-process MCP layer** via `fastmcp.Client(mcp)` (all 37 tools listed, 3 new ones exercised); then post-`/mcp` real-session calls incl. the error path. md_tools section-edit on a synced file demonstrated the known frontmatter mangle live (worse than documented — see Gotchas) and the `pull --note-id` recovery.
7. Two outbound handoffs authored to claude-wrangler (see § Emergent plans below) + docs (CLAUDE.md Mdsync section, tool inventory 21 write ops, `imports/` row).

## Decisions made this session

Session-tactical (narrative only): single-commit plan rather than staged; `test_scripts/` used for the rerunnable MCP live test (gitignored); pre-existing test failures (4× import_utils timestamps, 1× config home-token leak) verified on clean tree and left alone.

#### In-process MCP-layer testing via fastmcp.Client  [CLAUDE.md: Design Decision]

- **Date:** 2026-06-06
- **Files:** test_scripts/mdsync_mcp_live_test.py
- **Problem:** New MCP tools can't be exercised through the live Claude session until the user runs `/mcp` (server reload is user-side), leaving the registration/schema/invocation path untested at implementation time.
- **Chosen approach:** `fastmcp.Client(mcp_instance)` in-memory transport against the imported server instance — exercises tool registration, pydantic schema validation, invocation, and the error path (`with_client_error_handling` wrapping) against live Joplin, missing only the desktop JSON-RPC hop. Pattern is reusable for every future tool addition.
- **Alternatives rejected:** calling the decorated functions directly (bypasses schema layer; @create_tool returns FunctionTool, not a callable); waiting for user `/mcp` (blocks the dev loop).

## Open questions

- GFM-table render in Joplin: pending user visual check — tracked as the open item in the "Md-file ↔ Joplin round-trip tool" thread; both test notes are in the Testing notebook.
- Disposition of pre-existing untracked scratch at repo root: `SESSION-joplin-sync.md` (pasted transcript re iOS OneDrive sync recovery — content may belong in a Joplin note / CLAUDE.md gotcha, then delete) and `markdowns/PR_DESCRIPTION_PR19_2026-03-30.md` (likely archivable; PR #19 closed).
- Old-style `@SESSION_COMPACT.md` root import + `<!-- session-checkpoint-anchor -->` comment still in STATUS.md header — legacy from the 2026-05-15 schema; cleanup should migrate to `markdowns/session_archive/`.

## Retrospective gotchas + dead ends

### Gotchas

- **md_tools frontmatter mangle is WORSE than documented** (2026-06-06): on a frontmatter file, `md_tools insert` deletes only the `---` fences, leaves frontmatter contents as body text, and **misparses YAML comments (`# …`) as markdown H1 section anchors** (observed: resolved a section path THROUGH a YAML comment). Mitigation: mdsync recovery via `joplin-mdsync pull --note-id <id>` (mangled file auto-`.bak`ed); fix handed off (claude-wrangler "md_tools enhancements" thread, opaque-prefix-splice approach). Already documented in project CLAUDE.md "Known gap (transient)" — this entry adds the H1-misparse severity datum.
- **PyYAML `safe_dump(default_flow_style=None)` collapses leaf-only mappings to one flow line** (2026-06-06): a dict whose values are all scalars (no nested list/dict) renders as `key: {a: 1, b: 2}` single-line; presence of any nested collection switches to block style — so output FORMAT changes based on CONTENT (mdsync block went one-line whenever `tags` was absent). Mitigation: `default_flow_style=False` for canonical line-oriented machine output.

### Dead Ends

- **python-frontmatter parse→re-serialize for user-owned YAML** (2026-06-06): tried (mini-plan v1) storing sync metadata in frontmatter via python-frontmatter merge/strip; failed because PyYAML re-serialization destroys hand-maintained formatting — comments deleted, keys alphabetized, quoting/list style rewritten (adversarial-agent /tmp probe). Use exact line-splice of machine-owned spans instead; never parse user content. Revisit only if a true format-preserving YAML round-trip becomes load-bearing (ruamel.yaml is "mostly" preserving).
- **Timestamp-based drift detection (updated_time + post-PUT re-fetch)** (2026-06-06): tried comparing note `updated_time` against a stored snapshot; failed because (a) our own PUT bumps the stamp → requires a re-fetch dance to avoid self-triggered drift, (b) metadata-only changes (retitle, notebook move) false-positive. Body-hash comparison (prior vs just-in-time) detects exactly body drift with zero timestamp bookkeeping. Recurring user confusion about the re-fetch was the tell — confusion about a mechanism can be a design smell, not a comprehension gap.

## Files touched

New: `src/joplin_mcp/mdsync/{__init__,block,transport,cli}.py`, `src/joplin_mcp/tools/notes_files.py`, `tests/test_mdsync_{block,transport,cli}.py`, `tests/fixtures/mdsync_{user_frontmatter,no_frontmatter,with_block}.md`, `test_scripts/mdsync_mcp_live_test.py` (gitignored), `markdowns/plans_completed/CLAUDE.PLANS_20260606_1100_…MDSYNC….md` (archived plan).
Modified: `src/joplin_mcp/tools/__init__.py`, `src/joplin_mcp/config.py`, `pyproject.toml`, `tests/test_config.py` (count 29→32), `CLAUDE.md`, `STATUS.md`.
Cross-project (sanctioned handoff writes, uncommitted in their repos): `claude-wrangler/markdowns/plans_draft/CLAUDE.PLANS_20260606_preplan_skill_HANDOFF.md` (new), `claude-wrangler/STATUS.md` (§7 Inbox entry + md_tools thread handoff bullets), `~/.claude/STATUS.md` (Activity Log append).
Live Joplin artifacts: notes "mdsync test" (`ac0f9049…`, has the GFM table) + "mdsync mcp test" (`dab8a499…`) in Testing; tag `mdsync-livetest`.

## Emergent plans / docs / incoming handoffs

- **OUTBOUND → claude-wrangler:** `/preplan` skill handoff — plan at `claude-wrangler/markdowns/plans_draft/CLAUDE.PLANS_20260606_preplan_skill_HANDOFF.md` + §7 Inbox entry (tier schemas owned by the skill as durable reference files per user directive). No joplin-mcp routing needed.
- **OUTBOUND → claude-wrangler:** md_tools YAML-passthrough handoff — appended to the existing "YAML frontmatter preservation on insert/replace" item under "md_tools enhancements" (recommended opaque-prefix splice, rejected alternatives, `_frontmatter_bounds()` port pointer, acceptance tests). No joplin-mcp routing needed.
- Archived implementation plan: `markdowns/plans_completed/CLAUDE.PLANS_20260606_1100_…MDSYNC….md` (included in the queued feature commit).

## Cross-project signal — audit copy

Appended to `~/.claude/STATUS.md` `## Activity Log` this session (user-global is source of truth):

- 2026-06-06 11:00  joplin-mcp  mdsync round-trip  mdsync subpackage shipped: round-trip local .md ↔ Joplin note. CLI `joplin-mdsync update|push|pull` (bare path = update) + 3 MCP tools `update_note_from_file`/`push_md_file`/`pull_note_to_file`. File bytes travel verbatim (user YAML never parsed); fenced `mdsync:` frontmatter block via line-splice; body-hash drift detection with revision backup + persisted deletable diff region; `tags:` line reconciled; pull backs up dirty files to `.bak`. Enables agent pull-edit-push of Joplin notes (GTD `!PLAN:` ≡ STATUS.md editing workflows). `src/joplin_mcp/mdsync/`, `tools/notes_files.py`. Tested: 71 unit + live CLI + in-process MCP + live-session MCP. (uncommitted — feature commit queued)

Blockers: none resolved (the "Notebook-path support in dashboard YAML" blocker joplin-mcp owns remains open — untouched this session).
