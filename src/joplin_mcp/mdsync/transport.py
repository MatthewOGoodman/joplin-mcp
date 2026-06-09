"""Transport verbs for mdsync: update (default), push (create), pull.

Plain synchronous helpers shared by the CLI (cli.py) and the thin MCP tool
wrappers (tools/notes_files.py). All verbs GET first.

Drift model (update only): `prior_Joplin_hash` (note body hash at the most
recent sync point — refreshed by every successful GET or PUT) is compared
against `current_Joplin_hash` (recomputed just-in-time from the remote body
fetched by update's pre-check). push/pull never compare hashes: push has no
prior pull, so there is no interim window to check; pull uses the local
file's hash only to detect local-edit collisions.
"""

from __future__ import annotations

import difflib
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from joplin_mcp.mdsync.block import (
    SyncMeta,
    body_hash,
    canonical_body,
    read_block,
    write_block,
    write_drift_region,
)

_NOTE_FIELDS = "id,title,body,parent_id"
_JOPLIN_ID_RE = re.compile(r"^[a-f0-9]{32}$")


# === Lazy indirection wrappers ===
# Keep heavy imports (fastmcp_server pulls in FastMCP + config discovery) out
# of module import time, and give tests stable patch points.


def _get_client() -> Any:
    from joplin_mcp.fastmcp_server import get_joplin_client

    return get_joplin_client()


def _save_revision(client: Any, note_id: str) -> str | None:
    from joplin_mcp.revision_utils import save_note_revision

    return save_note_revision(client, note_id)


def _clear_cache() -> None:
    from joplin_mcp.tools.notes import _clear_note_cache

    _clear_note_cache()


def _resolve_notebook_id(name: str) -> str:
    from joplin_mcp.notebook_utils import get_notebook_id_by_name

    return get_notebook_id_by_name(name)


# === Small shared helpers ===


def _now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _bak_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _items(result: Any) -> list[Any]:
    """Unwrap joppy results that may be a DataList or already a flat list."""
    return (
        result.items
        if hasattr(result, "items") and not isinstance(result, dict)
        else result
    )


def _notebook_path(client: Any, notebook_id: str | None) -> str:
    """Human-readable `Parent/Child` path for a notebook id (informational).

    Best-effort: any failure falls back to the bare id rather than blocking
    a sync operation on display metadata.
    """
    if not notebook_id:
        return ""
    try:
        parts: list[str] = []
        current = notebook_id
        seen = set()
        while current and current not in seen and len(parts) < 20:
            seen.add(current)
            nb = client.get_notebook(current, fields="id,title,parent_id")
            parts.append(getattr(nb, "title", "") or "")
            current = getattr(nb, "parent_id", "") or ""
        return "/".join(reversed(parts))
    except Exception:
        return notebook_id


def _fetch_note(client: Any, note_id: str) -> Any:
    """GET a note or raise ValueError with the underlying reason."""
    try:
        return client.get_note(note_id, fields=_NOTE_FIELDS)
    except Exception as exc:
        raise ValueError(
            f"note '{note_id}' not found in Joplin ({exc}). "
            "If it was deleted, use 'push' to create it fresh."
        ) from exc


def _current_tag_names(client: Any, note_id: str) -> list[str]:
    tags = _items(client.get_tags(note_id=note_id, fields="id,title"))
    return [getattr(t, "title", "") or "" for t in tags]


def _find_or_create_tag_id(client: Any, name: str) -> str:
    """Tag id by case-insensitive exact title; create the tag if missing."""
    all_tags = _items(client.get_all_tags(fields="id,title"))
    matches = [
        t
        for t in all_tags
        if (getattr(t, "title", "") or "").casefold() == name.casefold()
    ]
    if len(matches) > 1:
        ids = ", ".join(getattr(t, "id", "?") for t in matches)
        raise ValueError(
            f"multiple tags named '{name}' exist ({ids}) — resolve manually"
        )
    if matches:
        return matches[0].id
    return str(client.add_tag(title=name))


def _reconcile_tags(
    client: Any, note_id: str, desired: list[str]
) -> tuple[list[str], list[str]]:
    """Make the note's tags match `desired`. Returns (added, removed) names."""
    current = _items(client.get_tags(note_id=note_id, fields="id,title"))
    current_by_fold = {(getattr(t, "title", "") or "").casefold(): t for t in current}
    desired_folds = {name.casefold() for name in desired}

    added: list[str] = []
    removed: list[str] = []
    for name in desired:
        if name.casefold() not in current_by_fold:
            tag_id = _find_or_create_tag_id(client, name)
            client.add_tag_to_note(tag_id, note_id)
            added.append(name)
    for fold, tag in current_by_fold.items():
        if fold not in desired_folds:
            client.delete(f"/tags/{tag.id}/notes/{note_id}")
            removed.append(getattr(tag, "title", "") or "")
    return added, removed


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {path}") from exc


def _unified_diff(remote_body: str, pushed_body: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            remote_body.split("\n"),
            pushed_body.split("\n"),
            fromfile="note (Joplin, pre-update)",
            tofile="file (pushed)",
            lineterm="",
        )
    )


# === Verbs ===


def update_file(
    path: str,
    no_diff: bool = False,
    dry_run: bool = False,
    client: Any = None,
) -> str:
    """PUT a bound file's body (and title) onto its existing Joplin note.

    The only verb that performs the drift comparison; see module docstring.
    """
    file_path = Path(path).expanduser()
    text = _read_text(file_path)
    meta = read_block(text)
    if meta is None or not meta.id:
        raise ValueError(
            f"'{file_path}' is not bound to a note (no mdsync block with an id). "
            "Use 'push' to create a new note, or 'pull --note-id <id>' to adopt one."
        )
    body = canonical_body(text)

    client = client or _get_client()
    note = _fetch_note(client, meta.id)
    remote_body = getattr(note, "body", "") or ""
    remote_title = getattr(note, "title", "") or ""
    current_hash = body_hash(remote_body)

    info_lines: list[str] = []
    if meta.prior_Joplin_hash:
        drift = current_hash != meta.prior_Joplin_hash
    else:
        drift = False
        info_lines.append(
            "INFO: no prior_Joplin_hash recorded — drift check skipped this update"
        )

    title_to_push = meta.title or remote_title
    if remote_title != title_to_push:
        info_lines.append(
            f"INFO: title in Joplin ('{remote_title}') differs — pushing block title "
            f"('{title_to_push}')"
        )

    # Tags: fetch current set only when the block has a tags line.
    tags_changed = False
    if meta.tags is not None:
        current_tags = _current_tag_names(client, meta.id)
        tags_changed = {t.casefold() for t in current_tags} != {
            t.casefold() for t in meta.tags
        }

    # No-op fast path: nothing to write anywhere.
    if (
        not drift
        and meta.prior_Joplin_hash
        and body_hash(body) == meta.prior_Joplin_hash
        and title_to_push == remote_title
        and not tags_changed
    ):
        return (
            "OPERATION: UPDATE_NOTE_FROM_FILE\n"
            "STATUS: NO_CHANGES\n"
            f"NOTE_ID: {meta.id}\n"
            f"FILE: {file_path}"
        )

    if dry_run:
        lines = [
            "OPERATION: UPDATE_NOTE_FROM_FILE",
            "STATUS: DRY_RUN",
            f"NOTE_ID: {meta.id}",
            f"FILE: {file_path}",
            f"DRIFT: {'detected — would warn and write drift region' if drift else 'none'}",
            f"WOULD: PUT title='{title_to_push}' + body ({len(body)} chars)",
        ]
        if tags_changed:
            lines.append(f"WOULD: reconcile tags to {meta.tags}")
        lines.extend(info_lines)
        return "\n".join(lines)

    # Revision backup: the safety net for the overwrite. On drift it is the
    # net for ANOTHER party's edits, so a failed backup aborts; otherwise it
    # only guards our own prior content — best-effort like update_note.
    revision_id = _save_revision(client, meta.id)
    if drift and not revision_id:
        raise ValueError(
            "drift detected but the pre-overwrite revision backup failed — "
            "aborting update to avoid unrecoverable overwrite"
        )

    client.modify_note(meta.id, title=title_to_push, body=body)
    _clear_cache()

    tags_added: list[str] = []
    tags_removed: list[str] = []
    if meta.tags is not None and tags_changed:
        tags_added, tags_removed = _reconcile_tags(client, meta.id, meta.tags)

    # Refresh bookkeeping: this PUT is the new sync point.
    meta.title = title_to_push
    meta.parent_id = getattr(note, "parent_id", None) or meta.parent_id
    meta.notebook = _notebook_path(client, meta.parent_id) or meta.notebook
    meta.prior_Joplin_hash = body_hash(body)
    meta.current_Joplin_hash = current_hash
    meta.synced = _now_stamp()

    new_text = write_block(body, meta)
    warning = (
        "WARNING: note had changed in Joplin since last sync (pushed anyway); "
        f"pre-overwrite version saved as revision {revision_id}"
    )
    if drift:
        region = warning
        if not no_diff:
            region += "\ndiff (changes this update applied to the note):\n"
            region += _unified_diff(remote_body, body)
        new_text = write_drift_region(new_text, region)
    file_path.write_text(new_text, encoding="utf-8")

    lines = []
    if drift:
        lines.append(warning)
    lines.extend(
        [
            "OPERATION: UPDATE_NOTE_FROM_FILE",
            "STATUS: SUCCESS",
            f"NOTE_ID: {meta.id}",
            f"TITLE: {title_to_push}",
            f"FILE: {file_path}",
            f"REVISION_ID: {revision_id or 'unavailable (backup failed; update proceeded)'}",
            f"DRIFT: {'detected (see drift region at top of file)' if drift else 'none'}",
        ]
    )
    if tags_added:
        lines.append(f"TAGS_ADDED: {', '.join(tags_added)}")
    if tags_removed:
        lines.append(f"TAGS_REMOVED: {', '.join(tags_removed)}")
    lines.extend(info_lines)
    return "\n".join(lines)


def push_file(
    path: str,
    notebook: str | None = None,
    title: str | None = None,
    force: bool = False,
    dry_run: bool = False,
    client: Any = None,
) -> str:
    """Create a new note from a file; `force` clobbers an existing one.

    Existence check ONLY — never a hash comparison (no prior pull means there
    is no interim window to reason about). The clobber path still saves a
    revision before the PUT; that is its entire safety story.
    """
    file_path = Path(path).expanduser()
    text = _read_text(file_path)
    meta = read_block(text) or SyncMeta()
    body = canonical_body(text)

    client = client or _get_client()

    # Locate an existing note: bound id wins; else exact-title match in the
    # target notebook (resolved below only when needed for search/create).
    existing = None
    if meta.id:
        try:
            existing = client.get_note(meta.id, fields=_NOTE_FIELDS)
        except Exception:
            existing = None  # bound note was deleted → create fresh below

    notebook_name = notebook or meta.notebook
    push_title = title or meta.title or file_path.stem
    parent_id: str | None = None

    if existing is None:
        if not notebook_name:
            raise ValueError(
                "notebook required to create a note: pass --notebook or set "
                "'notebook:' in the mdsync block"
            )
        parent_id = _resolve_notebook_id(notebook_name)
        if not meta.id:
            # Duplicate-title guard, scoped to the target notebook. Quotes are
            # dropped from the query phrase; the exact match happens in Python.
            query_title = push_title.replace('"', " ").strip()
            results = _items(
                client.search_all(
                    query=f'title:"{query_title}"', fields="id,title,parent_id"
                )
            )
            exact = [
                r
                for r in results
                if (getattr(r, "title", "") or "") == push_title
                and (getattr(r, "parent_id", "") or "") == parent_id
            ]
            if len(exact) > 1:
                ids = ", ".join(getattr(r, "id", "?") for r in exact)
                raise ValueError(
                    f"multiple notes titled '{push_title}' exist in '{notebook_name}' "
                    f"({ids}) — cannot determine a target; rename or use "
                    "'pull --note-id <id>' to bind one explicitly"
                )
            if exact:
                existing = _fetch_note(client, exact[0].id)

    if existing is not None and not force:
        raise ValueError(
            f"note already exists (id: {getattr(existing, 'id', '?')}). "
            "To PUT with drift warning + diff: use 'update'. To replace in "
            "place (prior version saved as revision automatically): use "
            "'push --force'."
        )

    if dry_run:
        action = (
            f"WOULD: replace note {getattr(existing, 'id', '?')} (clobber, revision backup)"
            if existing is not None
            else f"WOULD: create note '{push_title}' in '{notebook_name}'"
        )
        return (
            "OPERATION: PUSH_MD_FILE\n"
            "STATUS: DRY_RUN\n"
            f"FILE: {file_path}\n"
            f"{action}"
        )

    if existing is not None:
        # Clobber path: revision backup is the entire safety net — required.
        target_id = existing.id
        pre_clobber_hash = body_hash(getattr(existing, "body", "") or "")
        revision_id = _save_revision(client, target_id)
        if not revision_id:
            raise ValueError(
                "pre-clobber revision backup failed — aborting push --force"
            )
        client.modify_note(target_id, title=push_title, body=body)
        _clear_cache()
        action_lines = [
            "ACTION: REPLACED",
            f"REVISION_ID: {revision_id}",
        ]
        meta.id = target_id
        meta.parent_id = getattr(existing, "parent_id", None) or parent_id
        meta.current_Joplin_hash = pre_clobber_hash
    else:
        new_id = str(client.add_note(title=push_title, body=body, parent_id=parent_id))
        meta.id = new_id
        meta.parent_id = parent_id
        meta.current_Joplin_hash = body_hash(body)
        action_lines = ["ACTION: CREATED"]

    tags_added: list[str] = []
    if meta.tags:
        tags_added, _ = _reconcile_tags(client, meta.id, meta.tags)

    meta.title = push_title
    meta.notebook = _notebook_path(client, meta.parent_id) or notebook_name
    meta.prior_Joplin_hash = body_hash(body)
    meta.synced = _now_stamp()

    file_path.write_text(write_block(body, meta), encoding="utf-8")

    lines = [
        "OPERATION: PUSH_MD_FILE",
        "STATUS: SUCCESS",
        *action_lines,
        f"NOTE_ID: {meta.id}",
        f"TITLE: {push_title}",
        f"NOTEBOOK: {meta.notebook}",
        f"FILE: {file_path}",
    ]
    if tags_added:
        lines.append(f"TAGS_ADDED: {', '.join(tags_added)}")
    return "\n".join(lines)


def pull_note(
    path: str,
    note_id: str | None = None,
    dry_run: bool = False,
    client: Any = None,
) -> str:
    """Write a Joplin note to a local file (adopting or refreshing it).

    Local unsynced edits are backed up verbatim to `<stem>_<ts>.md.bak`
    alongside, recorded as `markdown_bak:` in the new block — the body never
    carries warnings on pull.
    """
    file_path = Path(path).expanduser()

    old_text: str | None = None
    old_meta: SyncMeta | None = None
    if file_path.exists():
        old_text = file_path.read_text(encoding="utf-8")
        try:
            old_meta = read_block(old_text)
        except ValueError:
            old_meta = (
                None  # corrupt block: treat as unbound; backup logic still applies
            )

    target_id = note_id or (old_meta.id if old_meta else None)
    if not target_id:
        raise ValueError(
            "no note id: pass --note-id for first-time adoption, or pull a file "
            "whose mdsync block already has one"
        )
    if not _JOPLIN_ID_RE.match(target_id):
        raise ValueError(f"invalid note id '{target_id}' (expected 32 hex characters)")

    client = client or _get_client()
    note = _fetch_note(client, target_id)
    note_body = getattr(note, "body", "") or ""

    # Local-collision check: with a recorded sync point, dirty means the local
    # canonical body no longer matches it; without one, anything that differs
    # from the incoming body would be silently lost — back it up too.
    bak_name: str | None = None
    if old_text is not None:
        old_canonical = canonical_body(old_text)
        if old_meta and old_meta.prior_Joplin_hash:
            dirty = body_hash(old_canonical) != old_meta.prior_Joplin_hash
        else:
            dirty = old_canonical != note_body
        if dirty and not dry_run:
            bak_name = f"{file_path.stem}_{_bak_stamp()}.md.bak"
            (file_path.parent / bak_name).write_text(old_text, encoding="utf-8")
        elif dirty:
            bak_name = f"{file_path.stem}_<timestamp>.md.bak (dry run)"

    tag_names = _current_tag_names(client, target_id)
    parent_id = getattr(note, "parent_id", "") or ""
    pulled_hash = body_hash(note_body)
    meta = SyncMeta(
        id=target_id,
        title=getattr(note, "title", "") or "",
        parent_id=parent_id,
        tags=tag_names,
        notebook=_notebook_path(client, parent_id),
        synced=_now_stamp(),
        prior_Joplin_hash=pulled_hash,
        current_Joplin_hash=pulled_hash,
        markdown_bak=bak_name,
    )

    if dry_run:
        return (
            "OPERATION: PULL_NOTE_TO_FILE\n"
            "STATUS: DRY_RUN\n"
            f"NOTE_ID: {target_id}\n"
            f"TITLE: {meta.title}\n"
            f"FILE: {file_path}\n"
            + (f"WOULD_BACKUP: {bak_name}\n" if bak_name else "")
            + f"WOULD: write {len(note_body)} chars + mdsync block"
        )

    file_path.write_text(write_block(note_body, meta), encoding="utf-8")

    lines = [
        "OPERATION: PULL_NOTE_TO_FILE",
        "STATUS: SUCCESS",
        f"NOTE_ID: {target_id}",
        f"TITLE: {meta.title}",
        f"NOTEBOOK: {meta.notebook}",
        f"FILE: {file_path}",
    ]
    if bak_name:
        lines.append(f"BACKUP: {bak_name} (local edits preserved)")
    if tag_names:
        lines.append(f"TAGS: {', '.join(tag_names)}")
    return "\n".join(lines)
