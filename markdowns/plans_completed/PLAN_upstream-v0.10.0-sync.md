# Mini-plan: bring main and feature/dev forward to upstream v0.10.0

**Source:** `markdowns/plans_draft/HANDOFF_20261105_114933_branch-cleanup-upstream-sync.md`, step 5.

## Goal

`main` = upstream `b84c313` (v0.10.0) + the fork tools we keep, each one using upstream's current helpers and enforcing the notebook allowlist. `feature/dev` = that `main` + the dashboard and mdsync subpackages. No history rewrite on either public branch.

## Mechanism choices

- **Merge, not rebase.** `git merge upstream/main` on a `sync/upstream-v0.10.0` branch cut from `main`, then fast-forward `main` to it, then `git merge main` into `feature/dev`. Picked over rebase because both branches are public and replaying 19 commits across upstream's refactor rewrites history for no gain.
- **Alias three tools to the upstream functions that now cover them.** Each keeps its tool name and parameters, but its body is a thin call into upstream's implementation with no logic of its own, so a fix upstream reaches the alias automatically:
  - `move_note` -> `update_note(note_id, notebook_name=...)` (`e976751`, #21). Its `target_notebook_id` argument resolves to a name or path first, because upstream's `update_note` takes only `notebook_name`.
  - `bulk_tag_notes` -> `tag_note(note_id=[...], tag_name=[...])` (`96ace20`, #22), an exact equivalent: both apply every tag to every note.
  - `list_trash` -> `find_notes("*", trash=True)` (`c68dbf4`, #23), for NOTES ONLY. Upstream cannot list trashed notebooks (its `find_notes` filters notes alone), so `item_type="notebook"` and the both-types default keep the fork's own notebook listing. See O1.
- **Make two kept tools parallel to upstream's list-input convention**, which `tag_note`/`untag_note` set: a singular-named parameter typed `Union[JoplinIdType, List[JoplinIdType]]` that accepts one ID or a list.
  - `strip_note_tags(note_id: str | list)` instead of one note only.
  - `bulk_move_notes(note_id: str | list, notebook_name: ...)` in place of `note_ids: List[str]` / `target_notebook`, mirroring `update_note`'s `notebook_name`, so paths resolve the same way. `target_notebook_id` and the `backup` flag stay, because upstream has no equivalent.
- **Keep and rewire the rest** onto upstream's helpers in place of the four removed imports:
  - `notes_bulk.py`: `apply_pagination` and `format_search_results_with_pagination` -> the pagination code now beside `find_notes`
  - `tags_bulk.py`: `_tag_note_impl` / `_untag_note_impl` -> upstream's tag/untag path (the `bulk_tag_notes` alias calls `tag_note`; `strip_note_tags` calls the untag path)
  - `notes_revisions.py`: `get_notebook_id_by_name` -> `NotebookResolver`
  - `mdsync/transport.py`: `_clear_note_cache` -> `note_view`'s cache invalidation
- **Add the allowlist check to every kept note-touching tool**, using upstream's own pattern: `if get_config().has_notebook_allowlist: validate_notebook_access(parent_id, ...)` per note, and `is_notebook_accessible` to filter search results. Covers `bulk_move_notes` (source and destination), `search_and_bulk_update_*`, the three revision tools, `strip_note_tags`, and the three mdsync tools. `backup_database` needs no check because it touches no notes.
- **fastmcp v3:** take upstream's pin (`>=3,<4,!=3.3.1`). It needs no fork-side change beyond the merge, because our tools register through upstream's `create_tool`. `pyproject.toml` = upstream's dependencies plus ours (`jsonschema`, `diff-match-patch`, `python-frontmatter`).
- **Conflicts** (8 files): take upstream's side in `notes.py`, `notebooks.py`, `trash.py`, `formatting.py` and `tools/__init__.py`, then re-add only our registrations. Tests: take upstream's, then delete the tracked `tests/test_config.py.bak*` files.

## Verification

- Record the test baseline on `feature/dev` before the merge (CLAUDE.md lists 5 known failures).
- After the merge: the full suite passes apart from the baseline, and upstream's own suite passes untouched.
- A new allowlist test for each rewired fork tool. Before the check is wired in, it must FAIL for the reason intended (the access is denied), with one control test that should pass.
- Run the in-process `fastmcp.Client` smoke test (CLAUDE.md, Learnings) against live Joplin for every kept tool; then `/mcp` reload.

## Open decisions

None.

## Settled (user, 2026-11-05)

- `list_trash` keeps its interface and its combined notes-plus-notebooks output; only its note half is replaced by a call to `find_notes("*", trash=True)`. The notebook half stays fork code.
- `bulk_move_notes` switches outright to `note_id` / `notebook_name`, with no deprecated aliases for the old names.
- Alias `move_note`, `list_trash`, `bulk_tag_notes` rather than deleting them.
- Make kept tools parallel to upstream's list-input convention where a list input applies.
- No upstream PR in this plan. CLAUDE.md Tool Inventory and Upstream Relationship are updated in the same change (handoff step 6).
