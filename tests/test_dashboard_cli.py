"""Tests for joplin_mcp.dashboard.cli — argparse, dry-run, file output, exits."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from joplin_mcp.dashboard import cli as cli_module
from joplin_mcp.dashboard.config import SectionConfig
from joplin_mcp.dashboard.types import NoteRecord


class FakeLoader:
    """Test double for the Loader interface."""

    def __init__(self, by_section_title: dict[str, list[NoteRecord]]):
        self._by_section = by_section_title

    def load_section(self, section: SectionConfig) -> list[NoteRecord]:
        return self._by_section.get(section.title, [])


def _note(title: str) -> NoteRecord:
    return NoteRecord(
        id="abc",
        title=title,
        notebook_path="N",
        tags=[],
        created_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_time=datetime(2026, 5, 7, tzinfo=timezone.utc),
    )


def _write_config(path: Path, output: Path) -> Path:
    cfg = path / "config.yaml"
    cfg.write_text(
        f"""
output: {output}
header: "# Header"
sections:
  - title: People
    notebook: "1-Job Search/People"
"""
    )
    return cfg


class TestCliMain:
    def test_writes_output_file(self, tmp_path):
        output = tmp_path / "DASHBOARD.md"
        cfg = _write_config(tmp_path, output)
        loader = FakeLoader({"People": [_note("David Chen")]})

        with patch.object(cli_module, "JoplinRestLoader", return_value=loader):
            rc = cli_module.main([str(cfg)])

        assert rc == 0
        text = output.read_text()
        assert "# Header" in text
        assert "## People" in text
        assert "David Chen" in text

    def test_dry_run_writes_to_stdout_and_skips_file(self, tmp_path, capsys):
        output = tmp_path / "DASHBOARD.md"
        cfg = _write_config(tmp_path, output)
        loader = FakeLoader({"People": [_note("David Chen")]})

        with patch.object(cli_module, "JoplinRestLoader", return_value=loader):
            rc = cli_module.main([str(cfg), "--dry-run"])

        assert rc == 0
        assert not output.exists()
        captured = capsys.readouterr()
        assert "David Chen" in captured.out

    def test_creates_parent_directories_for_output(self, tmp_path):
        output = tmp_path / "deep" / "nested" / "DASHBOARD.md"
        cfg = _write_config(tmp_path, output)
        loader = FakeLoader({"People": []})

        with patch.object(cli_module, "JoplinRestLoader", return_value=loader):
            rc = cli_module.main([str(cfg)])

        assert rc == 0
        assert output.exists()

    def test_missing_config_returns_nonzero(self, tmp_path, capsys):
        rc = cli_module.main([str(tmp_path / "does-not-exist.yaml")])
        assert rc == 2
        assert "error" in capsys.readouterr().err.lower()

    def test_invalid_config_returns_nonzero(self, tmp_path, capsys):
        bad = tmp_path / "bad.yaml"
        bad.write_text("not a mapping\n")
        rc = cli_module.main([str(bad)])
        assert rc == 2

    def test_validation_errors_use_json_pointer_paths(self, tmp_path, capsys):
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "output: /tmp/x.md\n"
            "sections:\n"
            "  - title: A\n"
            "    sort_dir: sideways\n"
        )
        rc = cli_module.main([str(bad)])
        err = capsys.readouterr().err
        assert rc == 2
        # JSON Pointer to the offending field, not a Python traceback
        assert "/sections/0/sort_dir" in err
        assert "sideways" in err

    def test_validation_reports_multiple_errors_in_one_pass(self, tmp_path, capsys):
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "output: /tmp/x.md\n"
            "sections:\n"
            "  - title: A\n"
            "    sort_dir: sideways\n"
            "  - notebook: Y\n"
        )
        rc = cli_module.main([str(bad)])
        err = capsys.readouterr().err
        assert rc == 2
        assert "sideways" in err
        assert "title" in err  # missing-title error from second section

    def test_section_with_no_notes_renders_placeholder(self, tmp_path):
        output = tmp_path / "DASHBOARD.md"
        cfg = _write_config(tmp_path, output)
        loader = FakeLoader({})  # no notes for any section

        with patch.object(cli_module, "JoplinRestLoader", return_value=loader):
            rc = cli_module.main([str(cfg)])

        assert rc == 0
        text = output.read_text()
        assert "_No matching notes._" in text


class TestValidateMode:
    def test_validate_mode_pass(self, tmp_path, capsys):
        output = tmp_path / "DASHBOARD.md"
        cfg = _write_config(tmp_path, output)
        rc = cli_module.main([str(cfg), "--validate"])
        assert rc == 0
        # No Joplin REST call attempted
        assert not output.exists()
        captured = capsys.readouterr()
        assert "valid" in captured.out

    def test_validate_mode_fail_exits_nonzero(self, tmp_path, capsys):
        bad = tmp_path / "bad.yaml"
        bad.write_text("output: /tmp/x.md\nsections:\n  - notebook: Y\n")
        rc = cli_module.main([str(bad), "--validate"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "title" in err

    def test_validate_and_dry_run_are_mutually_exclusive(self, tmp_path):
        output = tmp_path / "DASHBOARD.md"
        cfg = _write_config(tmp_path, output)
        with pytest.raises(SystemExit):
            cli_module.main([str(cfg), "--validate", "--dry-run"])


class TestSymlinkDiscovery:
    """Bare-name positional args resolve via <package-dir>/configs/<name>.yaml."""

    def test_bare_name_resolves_via_configs_dir(self, tmp_path, monkeypatch, capsys):
        """A name with no path separator and no .yaml extension is looked up in configs/."""
        # Author a real config we'll symlink into the configs/ dir
        output = tmp_path / "DASHBOARD.md"
        real_cfg = _write_config(tmp_path, output)

        # Redirect the CLI's configs/ dir to a tmp location
        fake_configs = tmp_path / "fake_configs"
        fake_configs.mkdir()
        symlink = fake_configs / "testname.yaml"
        symlink.symlink_to(real_cfg)
        monkeypatch.setattr(cli_module, "_CONFIGS_DIR", fake_configs)

        loader = FakeLoader({"People": [_note("Alice")]})
        with patch.object(cli_module, "JoplinRestLoader", return_value=loader):
            rc = cli_module.main(["testname", "--dry-run"])

        assert rc == 0
        assert "Alice" in capsys.readouterr().out

    def test_bare_name_unknown_errors_cleanly(self, tmp_path, monkeypatch, capsys):
        fake_configs = tmp_path / "fake_configs"
        fake_configs.mkdir()
        monkeypatch.setattr(cli_module, "_CONFIGS_DIR", fake_configs)

        rc = cli_module.main(["does-not-exist"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "no config found" in err.lower()

    def test_broken_symlink_errors_cleanly(self, tmp_path, monkeypatch, capsys):
        fake_configs = tmp_path / "fake_configs"
        fake_configs.mkdir()
        broken = fake_configs / "broken.yaml"
        broken.symlink_to(tmp_path / "nonexistent_target.yaml")
        monkeypatch.setattr(cli_module, "_CONFIGS_DIR", fake_configs)

        rc = cli_module.main(["broken"])
        assert rc == 2
        err = capsys.readouterr().err.lower()
        # Clean error, not a traceback
        assert "broken symlink" in err
