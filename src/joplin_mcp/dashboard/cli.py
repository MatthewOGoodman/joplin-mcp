"""CLI entry point for the dashboard.

Usage:
  joplin-dashboard <config.yaml|name> [--dry-run|--validate]

If the positional arg has no path separator and no `.yaml` extension and does
not exist as a path, it's treated as a bare name and resolved against
`<package-dir>/configs/<name>.yaml` (typically a symlink into a consumer repo).

`--validate` parses and validates without rendering; exits 0 on success, 2 on
validation failure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jsonschema.exceptions import ValidationError

from joplin_mcp.dashboard.config import ConfigValidationError, load_config
from joplin_mcp.dashboard.loader import JoplinRestLoader, Loader
from joplin_mcp.dashboard.render import assemble_dashboard, render_section

_CONFIGS_DIR = Path(__file__).parent / "configs"


def _resolve_config_arg(arg: str) -> Path:
    """Resolve positional config arg to a concrete path.

    Order: existing path → bare-name lookup in configs/ → raise FileNotFoundError.
    Broken symlinks surface as a clean error, not a traceback.
    """
    direct = Path(arg).expanduser()
    if direct.exists():
        return direct.resolve(strict=True)

    looks_like_bare_name = "/" not in arg and not arg.endswith((".yaml", ".yml"))
    if looks_like_bare_name:
        candidate = _CONFIGS_DIR / f"{arg}.yaml"
        if candidate.is_symlink() and not candidate.exists():
            raise FileNotFoundError(
                f"broken symlink: {candidate} -> {candidate.readlink()}"
            )
        if candidate.exists():
            return candidate.resolve(strict=True)
        raise FileNotFoundError(
            f"no config found: tried {direct} and {candidate}"
        )

    raise FileNotFoundError(f"no such config: {direct}")


def format_validation_errors(errors: list[ValidationError]) -> str:
    """Render schema validation errors as one line per error.

    Format: `<json-pointer>: <message>`
    """
    lines = []
    for err in errors:
        pointer = "/" + "/".join(str(p) for p in err.absolute_path)
        lines.append(f"{pointer}: {err.message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="joplin-dashboard",
        description="Render a Joplin-backed Markdown dashboard from a YAML config.",
    )
    parser.add_argument(
        "config",
        help="Path to the dashboard YAML config, or a bare name resolved via configs/<name>.yaml",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Print rendered Markdown to stdout instead of writing the output file",
    )
    mode.add_argument(
        "--validate",
        action="store_true",
        help="Parse and validate the config without rendering; exit 0 on success, 2 on failure",
    )
    args = parser.parse_args(argv)

    try:
        config_path = _resolve_config_arg(args.config)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        config = load_config(config_path)
    except ConfigValidationError as exc:
        print(format_validation_errors(exc.errors), file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.validate:
        print(f"valid: {config_path}")
        return 0

    loader: Loader = JoplinRestLoader()
    return _run(config, loader, dry_run=args.dry_run)


def _run(config, loader: Loader, dry_run: bool) -> int:
    section_blocks = []
    for section in config.sections:
        notes = loader.load_section(section)
        section_blocks.append(render_section(notes, section))

    output = assemble_dashboard(section_blocks, header=config.header, footer=config.footer)

    if dry_run:
        sys.stdout.write(output)
        return 0

    config.output.parent.mkdir(parents=True, exist_ok=True)
    config.output.write_text(output)
    print(f"wrote {config.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
