"""Tests for joplin_mcp.mdsync.transport — update / push / pull verbs.

All Joplin access goes through a MagicMock joppy client (injected via the
client= parameter); revision backup, cache clearing, and notebook resolution
are patched at their transport-module indirection points.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import joplin_mcp.mdsync.transport as transport
from joplin_mcp.mdsync.block import (
    SyncMeta,
    body_hash,
    canonical_body,
    read_block,
    write_block,
)

NOTE_ID = "a" * 32
PARENT_ID = "b" * 32
BODY_0 = "## Section\n\noriginal line\n"
BODY_1 = "## Section\n\nedited line\n"


def _note(id=NOTE_ID, title="My Note", body=BODY_0, parent_id=PARENT_ID):
    return SimpleNamespace(id=id, title=title, body=body, parent_id=parent_id)


def _client(note=None, tags=(), all_tags=(), search=()):
    client = MagicMock()
    if note is not None:
        client.get_note.return_value = note
    client.get_tags.return_value = list(tags)
    client.get_all_tags.return_value = list(all_tags)
    client.search_all.return_value = list(search)
    return client


def _bound_file(tmp_path, body=BODY_0, **meta_overrides):
    meta_kwargs = {
        "id": NOTE_ID,
        "title": "My Note",
        "parent_id": PARENT_ID,
        "notebook": "Projects/GTD",
        "synced": "2026-06-06 09:00",
        "prior_Joplin_hash": body_hash(BODY_0),
        "current_Joplin_hash": body_hash(BODY_0),
    }
    meta_kwargs.update(meta_overrides)
    path = tmp_path / "note.md"
    path.write_text(write_block(body, SyncMeta(**meta_kwargs)))
    return path


@pytest.fixture(autouse=True)
def _patch_indirections():
    with patch.object(
        transport, "_save_revision", return_value="rev123"
    ) as save_rev, patch.object(transport, "_clear_cache") as clear_cache, patch.object(
        transport, "_resolve_notebook_id", return_value=PARENT_ID
    ) as resolve_nb, patch.object(
        transport, "_notebook_path", return_value="Projects/GTD"
    ):
        yield SimpleNamespace(
            save_revision=save_rev, clear_cache=clear_cache, resolve_nb=resolve_nb
        )


class TestUpdate:
    def test_put_sequence_and_payload(self, tmp_path, _patch_indirections):
        path = _bound_file(tmp_path, body=BODY_1)
        order = []
        _patch_indirections.save_revision.side_effect = (
            lambda *a: order.append("rev") or "rev123"
        )
        _patch_indirections.clear_cache.side_effect = lambda: order.append("clear")
        client = _client(note=_note())
        client.modify_note.side_effect = lambda *a, **k: order.append("modify")

        result = transport.update_file(str(path), client=client)

        assert order == ["rev", "modify", "clear"]
        client.modify_note.assert_called_once_with(
            NOTE_ID, title="My Note", body=BODY_1
        )
        assert "STATUS: SUCCESS" in result
        assert "DRIFT: none" in result

    def test_prior_hash_refreshed_no_drift_on_repeat_update(self, tmp_path):
        path = _bound_file(tmp_path, body=BODY_1)
        client = _client(note=_note(body=BODY_0))
        transport.update_file(str(path), client=client)

        meta = read_block(path.read_text())
        assert meta.prior_Joplin_hash == body_hash(BODY_1)
        assert meta.current_Joplin_hash == body_hash(BODY_0)

        # Second update: remote now holds OUR pushed body; edit locally again.
        client.get_note.return_value = _note(body=BODY_1)
        path.write_text(write_block(BODY_1 + "more\n", read_block(path.read_text())))
        result = transport.update_file(str(path), client=client)
        assert "DRIFT: none" in result
        assert "WARNING" not in result

    def test_remote_title_difference_is_info_not_drift(self, tmp_path):
        path = _bound_file(tmp_path, body=BODY_1)
        client = _client(note=_note(title="Renamed In Joplin"))
        result = transport.update_file(str(path), client=client)
        assert "INFO: title in Joplin" in result
        assert "WARNING" not in result
        client.modify_note.assert_called_once_with(
            NOTE_ID, title="My Note", body=BODY_1
        )

    def test_unbound_file_errors(self, tmp_path):
        path = tmp_path / "loose.md"
        path.write_text("no block here\n")
        with pytest.raises(ValueError, match="not bound"):
            transport.update_file(str(path), client=_client())

    def test_note_deleted_in_joplin_errors_suggesting_push(self, tmp_path):
        path = _bound_file(tmp_path)
        client = MagicMock()
        client.get_note.side_effect = RuntimeError("404")
        with pytest.raises(ValueError, match="push"):
            transport.update_file(str(path), client=client)

    def test_dry_run_writes_nothing(self, tmp_path, _patch_indirections):
        path = _bound_file(tmp_path, body=BODY_1)
        before = path.read_text()
        client = _client(note=_note())
        result = transport.update_file(str(path), dry_run=True, client=client)
        assert "STATUS: DRY_RUN" in result
        assert path.read_text() == before
        client.modify_note.assert_not_called()
        _patch_indirections.save_revision.assert_not_called()


class TestUpdateDrift:
    def test_drift_warns_first_and_persists_region_with_diff(self, tmp_path):
        path = _bound_file(tmp_path, body=BODY_1)
        remote = _note(body="## Section\n\nphone edit\n")
        result = transport.update_file(str(path), client=_client(note=remote))

        assert result.split("\n")[0].startswith("WARNING:")
        assert "revision rev123" in result
        text = path.read_text()
        assert "<!-- mdsync-drift-begin -->" in text
        assert "phone edit" in text  # the overwritten content appears in the diff
        assert "+edited line" in text

    def test_no_diff_flag_omits_diff_keeps_warning(self, tmp_path):
        path = _bound_file(tmp_path, body=BODY_1)
        remote = _note(body="## Section\n\nphone edit\n")
        transport.update_file(str(path), no_diff=True, client=_client(note=remote))
        text = path.read_text()
        assert "<!-- mdsync-drift-begin -->" in text
        assert "WARNING:" in text
        assert "+edited line" not in text

    def test_drift_region_never_reaches_pushed_body(self, tmp_path):
        # File still carries a stale drift region from a previous drift.
        path = _bound_file(tmp_path, body=BODY_1)
        remote = _note(body="## Section\n\nphone edit\n")
        transport.update_file(str(path), client=_client(note=remote))

        client2 = _client(note=_note(body=BODY_1))
        client2.get_note.return_value = _note(body="changed again\n")
        transport.update_file(str(path), client=client2)
        pushed_body = client2.modify_note.call_args.kwargs["body"]
        assert "mdsync-drift" not in pushed_body
        assert "mdsync-begin" not in pushed_body

    def test_drift_with_failed_revision_aborts(self, tmp_path, _patch_indirections):
        _patch_indirections.save_revision.side_effect = None
        _patch_indirections.save_revision.return_value = None
        path = _bound_file(tmp_path, body=BODY_1)
        client = _client(note=_note(body="someone else edited\n"))
        with pytest.raises(ValueError, match="revision backup failed"):
            transport.update_file(str(path), client=client)
        client.modify_note.assert_not_called()


class TestUpdateTags:
    def test_tags_line_reconciles(self, tmp_path):
        path = _bound_file(tmp_path, body=BODY_1, tags=["keep", "new"])
        client = _client(
            note=_note(),
            tags=[
                SimpleNamespace(id="t1", title="keep"),
                SimpleNamespace(id="t2", title="old"),
            ],
            all_tags=[
                SimpleNamespace(id="t1", title="keep"),
                SimpleNamespace(id="t2", title="old"),
            ],
        )
        client.add_tag.return_value = "t3"
        result = transport.update_file(str(path), client=client)

        client.add_tag.assert_called_once_with(title="new")
        client.add_tag_to_note.assert_called_once_with("t3", NOTE_ID)
        client.delete.assert_called_once_with(f"/tags/t2/notes/{NOTE_ID}")
        assert "TAGS_ADDED: new" in result
        assert "TAGS_REMOVED: old" in result

    def test_tags_line_absent_no_tag_calls(self, tmp_path):
        path = _bound_file(tmp_path, body=BODY_1, tags=None)
        client = _client(note=_note())
        transport.update_file(str(path), client=client)
        client.get_tags.assert_not_called()
        client.add_tag_to_note.assert_not_called()
        client.delete.assert_not_called()

    def test_tags_empty_list_removes_all(self, tmp_path):
        path = _bound_file(tmp_path, body=BODY_1, tags=[])
        client = _client(note=_note(), tags=[SimpleNamespace(id="t1", title="gone")])
        transport.update_file(str(path), client=client)
        client.delete.assert_called_once_with(f"/tags/t1/notes/{NOTE_ID}")
        client.add_tag_to_note.assert_not_called()


class TestUpdateNoop:
    def test_unchanged_everything_skips_all_writes(self, tmp_path, _patch_indirections):
        path = _bound_file(tmp_path, body=BODY_0, tags=None)
        before = path.read_text()
        client = _client(note=_note(body=BODY_0))
        result = transport.update_file(str(path), client=client)
        assert "STATUS: NO_CHANGES" in result
        assert path.read_text() == before
        client.modify_note.assert_not_called()
        _patch_indirections.save_revision.assert_not_called()


class TestPushCreate:
    def test_creates_and_binds(self, tmp_path, _patch_indirections):
        path = tmp_path / "new.md"
        path.write_text("# Fresh\n\ncontent\n")
        client = _client(search=[])
        client.add_note.return_value = "c" * 32

        result = transport.push_file(str(path), notebook="Projects/GTD", client=client)

        _patch_indirections.resolve_nb.assert_called_once_with("Projects/GTD")
        client.add_note.assert_called_once_with(
            title="new", body="# Fresh\n\ncontent\n", parent_id=PARENT_ID
        )
        assert "ACTION: CREATED" in result
        meta = read_block(path.read_text())
        assert meta.id == "c" * 32
        assert meta.prior_Joplin_hash == body_hash("# Fresh\n\ncontent\n")

    def test_title_precedence_arg_over_block_over_stem(self, tmp_path):
        path = tmp_path / "stem-name.md"
        path.write_text("x\n")
        client = _client(search=[])
        client.add_note.return_value = "c" * 32
        transport.push_file(str(path), notebook="NB", title="Explicit", client=client)
        assert client.add_note.call_args.kwargs["title"] == "Explicit"

    def test_missing_notebook_errors(self, tmp_path):
        path = tmp_path / "new.md"
        path.write_text("x\n")
        with pytest.raises(ValueError, match="notebook required"):
            transport.push_file(str(path), client=_client())

    def test_tags_applied_on_create(self, tmp_path):
        path = tmp_path / "new.md"
        meta = SyncMeta(tags=["alpha"], notebook="NB")
        path.write_text(write_block("body\n", meta))
        client = _client(search=[], tags=[], all_tags=[])
        client.add_note.return_value = "c" * 32
        client.add_tag.return_value = "t9"
        result = transport.push_file(str(path), client=client)
        client.add_tag_to_note.assert_called_once_with("t9", "c" * 32)
        assert "TAGS_ADDED: alpha" in result


class TestPushGuards:
    def test_bound_existing_refuses_naming_both_verbs(self, tmp_path):
        path = _bound_file(tmp_path)
        client = _client(note=_note())
        with pytest.raises(ValueError) as exc:
            transport.push_file(str(path), client=client)
        message = str(exc.value)
        assert NOTE_ID in message
        assert "'update'" in message
        assert "push --force" in message
        client.modify_note.assert_not_called()
        client.add_note.assert_not_called()

    def test_unbound_exact_title_match_refuses(self, tmp_path):
        path = tmp_path / "dup.md"
        path.write_text("x\n")
        match = SimpleNamespace(id="d" * 32, title="dup", parent_id=PARENT_ID)
        client = _client(note=_note(id="d" * 32, title="dup"), search=[match])
        with pytest.raises(ValueError, match="already exists"):
            transport.push_file(str(path), notebook="NB", client=client)

    def test_title_match_other_notebook_does_not_block(self, tmp_path):
        path = tmp_path / "dup.md"
        path.write_text("x\n")
        elsewhere = SimpleNamespace(id="d" * 32, title="dup", parent_id="z" * 32)
        client = _client(search=[elsewhere])
        client.add_note.return_value = "c" * 32
        result = transport.push_file(str(path), notebook="NB", client=client)
        assert "ACTION: CREATED" in result

    def test_multiple_title_matches_error_listing_ids(self, tmp_path):
        path = tmp_path / "dup.md"
        path.write_text("x\n")
        matches = [
            SimpleNamespace(id="d" * 32, title="dup", parent_id=PARENT_ID),
            SimpleNamespace(id="e" * 32, title="dup", parent_id=PARENT_ID),
        ]
        client = _client(search=matches)
        with pytest.raises(ValueError, match="multiple notes titled"):
            transport.push_file(str(path), notebook="NB", client=client)

    def test_bound_but_deleted_creates_fresh_with_new_id(self, tmp_path):
        path = _bound_file(tmp_path)
        client = _client()
        client.get_note.side_effect = RuntimeError("404")
        client.add_note.return_value = "f" * 32
        result = transport.push_file(str(path), client=client)  # notebook from block
        assert "ACTION: CREATED" in result
        assert read_block(path.read_text()).id == "f" * 32


class TestPushForce:
    def test_clobbers_with_revision_no_drift_ceremony(
        self, tmp_path, _patch_indirections
    ):
        path = _bound_file(tmp_path, body=BODY_1)
        remote = _note(body="completely different remote body\n")
        client = _client(note=remote)
        result = transport.push_file(str(path), force=True, client=client)

        _patch_indirections.save_revision.assert_called_once()
        client.modify_note.assert_called_once_with(
            NOTE_ID, title="My Note", body=BODY_1
        )
        assert "ACTION: REPLACED" in result
        assert "REVISION_ID: rev123" in result
        assert "WARNING" not in result
        text = path.read_text()
        assert "mdsync-drift" not in text
        meta = read_block(text)
        assert meta.prior_Joplin_hash == body_hash(BODY_1)
        assert meta.current_Joplin_hash == body_hash(
            "completely different remote body\n"
        )

    def test_unbound_force_binds_to_title_match(self, tmp_path):
        path = tmp_path / "dup.md"
        path.write_text("local content\n")
        match = SimpleNamespace(id="d" * 32, title="dup", parent_id=PARENT_ID)
        client = _client(note=_note(id="d" * 32, title="dup"), search=[match])
        result = transport.push_file(
            str(path), notebook="NB", force=True, client=client
        )
        assert "ACTION: REPLACED" in result
        assert read_block(path.read_text()).id == "d" * 32

    def test_force_with_nothing_existing_creates(self, tmp_path):
        path = tmp_path / "new.md"
        path.write_text("x\n")
        client = _client(search=[])
        client.add_note.return_value = "c" * 32
        result = transport.push_file(
            str(path), notebook="NB", force=True, client=client
        )
        assert "ACTION: CREATED" in result

    def test_failed_revision_aborts_clobber(self, tmp_path, _patch_indirections):
        _patch_indirections.save_revision.return_value = None
        path = _bound_file(tmp_path)
        client = _client(note=_note())
        with pytest.raises(ValueError, match="revision backup failed"):
            transport.push_file(str(path), force=True, client=client)
        client.modify_note.assert_not_called()


class TestPull:
    def test_writes_body_verbatim_with_block(self, tmp_path):
        path = tmp_path / "pulled.md"
        note_body = "---\nuser_key: stays\n---\n## Content\n"
        client = _client(
            note=_note(body=note_body),
            tags=[SimpleNamespace(id="t1", title="GTD")],
        )
        result = transport.pull_note(str(path), note_id=NOTE_ID, client=client)

        text = path.read_text()
        assert canonical_body(text) == note_body  # body verbatim incl. user frontmatter
        meta = read_block(text)
        assert meta.id == NOTE_ID
        assert meta.title == "My Note"
        assert meta.tags == ["GTD"]
        assert (
            meta.prior_Joplin_hash == meta.current_Joplin_hash == body_hash(note_body)
        )
        assert text.split("\n").count("---") == 2  # block merged into the SAME fences
        assert "STATUS: SUCCESS" in result

    def test_no_note_id_anywhere_errors(self, tmp_path):
        path = tmp_path / "loose.md"
        path.write_text("x\n")
        with pytest.raises(ValueError, match="no note id"):
            transport.pull_note(str(path), client=_client())

    def test_invalid_note_id_errors(self, tmp_path):
        with pytest.raises(ValueError, match="invalid note id"):
            transport.pull_note(
                str(tmp_path / "f.md"), note_id="nope", client=_client()
            )

    def test_dry_run_writes_nothing(self, tmp_path):
        path = tmp_path / "pulled.md"
        client = _client(note=_note())
        result = transport.pull_note(
            str(path), note_id=NOTE_ID, dry_run=True, client=client
        )
        assert "STATUS: DRY_RUN" in result
        assert not path.exists()


class TestPullDirty:
    def test_dirty_file_backed_up_then_overwritten(self, tmp_path):
        path = _bound_file(tmp_path, body=BODY_1)  # local edits: prior is hash(BODY_0)
        original_text = path.read_text()
        client = _client(note=_note(body="fresh remote\n"))
        result = transport.pull_note(str(path), client=client)

        baks = list(tmp_path.glob("note_*.md.bak"))
        assert len(baks) == 1
        assert baks[0].read_text() == original_text  # verbatim backup
        meta = read_block(path.read_text())
        assert meta.markdown_bak == baks[0].name
        assert canonical_body(path.read_text()) == "fresh remote\n"
        assert f"BACKUP: {baks[0].name}" in result

    def test_clean_file_no_backup(self, tmp_path):
        path = _bound_file(tmp_path, body=BODY_0)  # matches prior hash
        client = _client(note=_note(body="fresh remote\n"))
        transport.pull_note(str(path), client=client)
        assert list(tmp_path.glob("*.bak")) == []
        assert read_block(path.read_text()).markdown_bak is None

    def test_unbound_existing_file_differing_content_backed_up(self, tmp_path):
        path = tmp_path / "note.md"
        path.write_text("precious local text\n")
        client = _client(note=_note(body="remote body\n"))
        transport.pull_note(str(path), note_id=NOTE_ID, client=client)
        baks = list(tmp_path.glob("note_*.md.bak"))
        assert len(baks) == 1
        assert baks[0].read_text() == "precious local text\n"


class TestRoundTrip:
    def test_pull_then_update_unedited_is_noop(self, tmp_path):
        path = tmp_path / "rt.md"
        client = _client(note=_note(body=BODY_0), tags=[])
        transport.pull_note(str(path), note_id=NOTE_ID, client=client)
        result = transport.update_file(str(path), client=client)
        assert "STATUS: NO_CHANGES" in result
        client.modify_note.assert_not_called()

    def test_pull_edit_update_pull_is_stable(self, tmp_path):
        path = tmp_path / "rt.md"
        client = _client(note=_note(body=BODY_0), tags=[])
        transport.pull_note(str(path), note_id=NOTE_ID, client=client)

        # Edit the body locally (line edit below the block).
        edited = path.read_text().replace("original line", "edited line")
        path.write_text(edited)
        transport.update_file(str(path), client=client)
        after_update = path.read_text()
        pushed = client.modify_note.call_args.kwargs["body"]
        assert pushed == BODY_1

        # Remote now returns what we pushed; pull again → stable, no backup.
        client.get_note.return_value = _note(body=pushed)
        transport.pull_note(str(path), client=client)
        after_pull = path.read_text()
        assert canonical_body(after_pull) == canonical_body(after_update) == BODY_1
        meta = read_block(after_pull)
        assert meta.id == NOTE_ID
        assert meta.prior_Joplin_hash == body_hash(BODY_1)
        assert list(tmp_path.glob("*.bak")) == []
