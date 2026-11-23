"""Database backup tools for Joplin MCP — SQLite snapshot management."""
import datetime
import logging
import platform
import re
import subprocess
from pathlib import Path
from typing import Annotated, Optional

from pydantic import Field

from joplin_mcp.fastmcp_server import create_tool

logger = logging.getLogger(__name__)

_BACKUP_RETENTION = 10
_LABEL_MAX_LEN = 40


def _slugify_label(label: str) -> str:
    """Sanitize a free-text backup label into a filename-safe slug.

    Lowercases, collapses any run of non-alphanumeric characters to a single
    dash, trims leading/trailing dashes, and caps length. Raises ValueError if
    nothing usable remains — manual backups require an informative label so the
    accumulated snapshots stay self-describing.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    slug = slug[:_LABEL_MAX_LEN].strip("-")
    if not slug:
        raise ValueError(
            "Backup label must contain at least one alphanumeric character "
            "(it becomes the backup filename slug)."
        )
    return slug


def _get_joplin_db_path() -> Path:
    """Return the platform-appropriate path to Joplin's SQLite database.

    Raises:
        FileNotFoundError: If the database file does not exist at the
            expected location.
    """
    system = platform.system()
    if system == "Windows":
        base = Path.home() / "AppData" / "Roaming"
    else:
        # macOS and Linux both use ~/.config
        base = Path.home() / ".config"

    db_path = base / "joplin-desktop" / "database.sqlite"
    if not db_path.exists():
        raise FileNotFoundError(
            f"Joplin database not found at {db_path}. "
            "Is Joplin Desktop installed?"
        )
    return db_path


_BACKUP_DIR = Path.home() / "JoplinBackup" / "default" / "mcp-backups"


def backup_joplin_database(
    force: bool = False, label: Optional[str] = None
) -> Optional[str]:
    """Create a SQLite backup of the Joplin database.

    Uses sqlite3's .backup command for a safe, consistent snapshot even
    while Joplin Desktop is running. Each backup is a full copy of the Joplin
    database, written to ~/JoplinBackup/default/mcp-backups/.

    By default (force=False): creates auto-backup with once-per-calendar-day
    guard, subject to automatic retention cleanup (last _BACKUP_RETENTION
    kept). The label is ignored on this path.

    With force=True: creates a manual backup that is never auto-deleted,
    requiring explicit user cleanup. When a label is supplied it is slugified
    into the filename (joplin_manual_backup_{timestamp}_{slug}.sqlite) so the
    accumulated manual snapshots stay self-describing.

    Args:
        force: If True, create manual backup (no daily guard, no
            auto-cleanup).
        label: Short reason/slug for a manual (force=True) backup; appended to
            the filename. Ignored when force=False.

    Returns:
        Backup file path on success, None on skip or failure.
    """
    try:
        db_path = _get_joplin_db_path()
    except FileNotFoundError:
        logger.warning("Joplin database not found — skipping backup")
        return None

    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if force:
        # Manual backup — never auto-deleted. An informative label (slug)
        # keeps the accumulated snapshots self-describing.
        if label:
            slug = _slugify_label(label)
            backup_path = (
                _BACKUP_DIR
                / f"joplin_manual_backup_{timestamp}_{slug}.sqlite"
            )
        else:
            backup_path = (
                _BACKUP_DIR / f"joplin_manual_backup_{timestamp}.sqlite"
            )
    else:
        # Auto backup — once-per-day guard
        today = datetime.date.today().strftime("%Y%m%d")
        existing = list(
            _BACKUP_DIR.glob(f"joplin_auto_backup_{today}_*.sqlite")
        )
        if existing:
            logger.info(
                f"Daily auto-backup already exists: {existing[0].name}"
            )
            return str(existing[0])
        backup_path = _BACKUP_DIR / f"joplin_auto_backup_{timestamp}.sqlite"

    try:
        result = subprocess.run(
            ["sqlite3", str(db_path), f".backup '{backup_path}'"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning(f"SQLite backup failed: {result.stderr}")
            return None

        logger.info(f"Database backup created: {backup_path}")

        # Enforce retention on auto-backups only
        # (manual backups are never auto-deleted)
        if not force:
            auto_backups = sorted(
                _BACKUP_DIR.glob("joplin_auto_backup_*.sqlite"),
                reverse=True,
            )
            for old_backup in auto_backups[_BACKUP_RETENTION:]:
                old_backup.unlink()
                logger.info(f"Removed old auto-backup: {old_backup.name}")

        return str(backup_path)

    except Exception as e:
        logger.warning(f"Database backup failed: {e}")
        return None


@create_tool("backup_database", "Backup Joplin database")
async def backup_database(
    label: Annotated[
        str,
        Field(
            description=(
                "Required short reason for this backup (e.g. "
                "'pre-archive-sweep'). Slugified into the filename so the "
                "snapshot is self-describing. Must contain at least one "
                "alphanumeric character."
            )
        ),
    ],
) -> str:
    """Create a full, manual SQLite backup of the Joplin database.

    Writes a complete copy of the Joplin database using SQLite's .backup
    command, safe even while Joplin Desktop is running. Use before large
    reorganization operations or as a manual safety checkpoint. The required
    `label` becomes a filename slug
    (joplin_manual_backup_{timestamp}_{slug}.sqlite).

    Backup mechanism — two distinct paths, both writing to
    ~/JoplinBackup/default/mcp-backups/ (each a full DB copy):

    - AUTO: bulk operations (bulk_move_notes,
      search_and_bulk_update_execute) take backup="daily" by default — one
      backup per calendar day, retained to the last 10
      (joplin_auto_backup_*.sqlite). Older auto-backups are pruned
      automatically.
    - MANUAL: this tool (and the bulk tools' backup="force" path) — never
      pruned (joplin_manual_backup_*.sqlite). They accumulate until you
      delete them by hand, which is why an informative label is required.

    Distinct from manually_backup_note, which writes NO file — it saves an
    in-Joplin revision of a single note, recoverable via get_note_history /
    Joplin Desktop's Note History.

    Returns:
        str: Success message with backup path, or failure details.
    """
    try:
        slug = _slugify_label(label)
    except ValueError as exc:
        return (
            "OPERATION: BACKUP_DATABASE\n"
            "STATUS: FAILED\n"
            f"MESSAGE: {exc}"
        )

    try:
        db_path = _get_joplin_db_path()
    except FileNotFoundError:
        db_path = Path("~/.config/joplin-desktop/database.sqlite")

    backup_path = backup_joplin_database(force=True, label=slug)
    if backup_path:
        size_mb = Path(backup_path).stat().st_size / (1024 * 1024)
        return (
            "OPERATION: BACKUP_DATABASE\n"
            "STATUS: SUCCESS\n"
            f"LABEL: {slug}\n"
            f"BACKUP_PATH: {backup_path}\n"
            f"SIZE: {size_mb:.1f} MB\n"
            f"MESSAGE: Full Joplin database backup created (manual — never "
            f"auto-pruned). Restore by replacing {db_path} with this file "
            f"(while Joplin Desktop is closed)."
        )
    else:
        return (
            "OPERATION: BACKUP_DATABASE\n"
            "STATUS: FAILED\n"
            f"MESSAGE: Could not create database backup. Joplin database "
            f"may not exist at {db_path}. Check server logs."
        )
