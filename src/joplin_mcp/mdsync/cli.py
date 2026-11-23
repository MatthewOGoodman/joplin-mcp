"""CLI entry point for mdsync.

Usage:
  joplin-mdsync <file.md>                              # default verb: update
  joplin-mdsync update <file.md> [--no-diff] [--dry-run]
  joplin-mdsync push <file.md> [--notebook NB] [--title T] [--force] [--dry-run]
  joplin-mdsync pull <file.md> [--note-id ID] [--dry-run]

update: PUT a bound file onto its existing note (the drift-checked verb).
push:   create a new note; refuses if it already exists (--force clobbers,
        with an automatic prior-version revision).
pull:   note → file; local unsynced edits are backed up to <stem>_<ts>.md.bak.
"""

from __future__ import annotations

import argparse
import sys

from joplin_mcp.mdsync.transport import pull_note, push_file, update_file

_VERBS = {"update", "push", "pull"}


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    # Bare `joplin-mdsync <file>` defaults to the update verb.
    if argv and argv[0] not in _VERBS and argv[0] not in ("-h", "--help"):
        argv = ["update", *argv]

    parser = argparse.ArgumentParser(
        prog="joplin-mdsync",
        description="Round-trip a local .md file ↔ a Joplin note.",
    )
    sub = parser.add_subparsers(dest="verb", required=True)

    p_update = sub.add_parser(
        "update", help="PUT a bound file onto its existing note (default verb)"
    )
    p_update.add_argument("path", help="Markdown file bound via its mdsync block")
    p_update.add_argument(
        "--no-diff",
        action="store_true",
        help="On drift, omit the unified diff from the persisted drift region",
    )
    p_update.add_argument(
        "--dry-run", action="store_true", help="Report without writing"
    )

    p_push = sub.add_parser("push", help="Create a new note from a file")
    p_push.add_argument("path", help="Markdown file to push")
    p_push.add_argument(
        "--notebook", help="Target notebook name or 'Parent/Child' path (create)"
    )
    p_push.add_argument(
        "--title", help="Note title (default: mdsync block title, else filename stem)"
    )
    p_push.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing note in place (prior version saved as revision)",
    )
    p_push.add_argument("--dry-run", action="store_true", help="Report without writing")

    p_pull = sub.add_parser("pull", help="Write a Joplin note to a local file")
    p_pull.add_argument("path", help="Destination markdown file")
    p_pull.add_argument(
        "--note-id", help="Note id (32 hex) for first-time adoption of an unbound file"
    )
    p_pull.add_argument("--dry-run", action="store_true", help="Report without writing")

    args = parser.parse_args(argv)

    try:
        if args.verb == "update":
            output = update_file(args.path, no_diff=args.no_diff, dry_run=args.dry_run)
        elif args.verb == "push":
            output = push_file(
                args.path,
                notebook=args.notebook,
                title=args.title,
                force=args.force,
                dry_run=args.dry_run,
            )
        else:
            output = pull_note(args.path, note_id=args.note_id, dry_run=args.dry_run)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
