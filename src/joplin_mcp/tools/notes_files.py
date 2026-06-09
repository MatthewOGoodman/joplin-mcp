"""File round-trip tools for Joplin MCP — mdsync thin wrappers.

Thin MCP wrappers over joplin_mcp.mdsync.transport (the shared plain-Python
helpers also used by the `joplin-mdsync` CLI). Local-filesystem paths assume
the MCP server runs on the same host as the files (same constraint as
backup_database).
"""

from typing import Annotated, Optional

from pydantic import Field

from joplin_mcp.fastmcp_server import create_tool
from joplin_mcp.mdsync.transport import pull_note, push_file, update_file


@create_tool("update_note_from_file", "Update note from file")
async def update_note_from_file(
    file_path: Annotated[
        str,
        Field(
            description="Path to a markdown file bound to a note via its mdsync block"
        ),
    ],
    no_diff: Annotated[
        bool,
        Field(
            description="On drift, omit the unified diff from the persisted drift region"
        ),
    ] = False,
    dry_run: Annotated[
        bool, Field(description="Report what would happen without writing")
    ] = False,
) -> str:
    """Update an existing Joplin note from a bound local markdown file.

    The default mdsync verb (pull-edit-push workflow). PUTs the file's body
    (minus the mdsync block) and the block's title onto the note identified by
    the block's id. Detects drift — the note body changed in Joplin since the
    last sync — by comparing prior_Joplin_hash against the just-fetched remote
    body; on drift it still pushes, saves the pre-overwrite version as a
    revision, and persists a warning + diff region at the top of the file.
    A `tags:` line in the block is reconciled onto the note; no line → tags
    untouched.

    Returns:
        str: Operation report; on drift the warning is the first line.
    """
    return update_file(file_path, no_diff=no_diff, dry_run=dry_run)


@create_tool("push_md_file", "Push markdown file to new note")
async def push_md_file(
    file_path: Annotated[str, Field(description="Path to the markdown file to push")],
    notebook: Annotated[
        Optional[str],
        Field(
            description="Target notebook name or 'Parent/Child' path (required to create)"
        ),
    ] = None,
    title: Annotated[
        Optional[str],
        Field(
            description="Note title (default: mdsync block title, else filename stem)"
        ),
    ] = None,
    force: Annotated[
        bool,
        Field(
            description=(
                "Replace an existing note in place (prior version saved as revision). "
                "Without force, push refuses when the note already exists."
            )
        ),
    ] = False,
    dry_run: Annotated[
        bool, Field(description="Report what would happen without writing")
    ] = False,
) -> str:
    """Create a new Joplin note from a local markdown file.

    Create-only verb: GETs first and refuses if the note already exists
    (bound mdsync id, or an exact-title match in the target notebook) —
    use update_note_from_file for the drift-checked PUT, or force=True to
    clobber in place. Never compares content hashes: with no prior pull there
    is no interim window to check. Writes the mdsync block (note id, title,
    parent_id, hashes) back into the file, binding it for future updates.

    Returns:
        str: Operation report (ACTION: CREATED or REPLACED).
    """
    return push_file(
        file_path, notebook=notebook, title=title, force=force, dry_run=dry_run
    )


@create_tool("pull_note_to_file", "Pull note to markdown file")
async def pull_note_to_file(
    file_path: Annotated[str, Field(description="Destination markdown file path")],
    note_id: Annotated[
        Optional[str],
        Field(
            description="Note id (32 hex) for first-time adoption of an unbound file"
        ),
    ] = None,
    dry_run: Annotated[
        bool, Field(description="Report what would happen without writing")
    ] = False,
) -> str:
    """Write a Joplin note to a local markdown file for local editing.

    The note body is written verbatim with a regenerated mdsync block (id,
    title, parent_id, tags, notebook path, sync hashes) spliced into the
    frontmatter. If the existing local file has unsynced edits, it is backed
    up verbatim to <stem>_<timestamp>.md.bak alongside and the backup name is
    recorded as markdown_bak in the block — pull never adds warnings to the
    body itself.

    Returns:
        str: Operation report including any backup filename.
    """
    return pull_note(file_path, note_id=note_id, dry_run=dry_run)
