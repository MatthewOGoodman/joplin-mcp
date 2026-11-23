"""mdsync — round-trip a local .md file ↔ a Joplin note.

Pull a note to a file, edit locally (md_tools, editors, Claude Code), update
it back. File bytes travel verbatim; bookkeeping lives in a fenced `mdsync:`
block inside the file's frontmatter (see block.py for the splice guarantees).
"""

from joplin_mcp.mdsync.block import SyncMeta, body_hash, canonical_body, read_block
from joplin_mcp.mdsync.transport import pull_note, push_file, update_file

__all__ = [
    "SyncMeta",
    "body_hash",
    "canonical_body",
    "read_block",
    "pull_note",
    "push_file",
    "update_file",
]
