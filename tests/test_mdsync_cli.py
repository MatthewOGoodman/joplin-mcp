"""Tests for joplin_mcp.mdsync.cli — verb dispatch, default verb, exit codes."""

from unittest.mock import patch

import pytest

import joplin_mcp.mdsync.cli as cli_module


class TestCliUpdate:
    def test_bare_path_dispatches_to_update(self, capsys):
        with patch.object(cli_module, "update_file", return_value="OK") as fn:
            rc = cli_module.main(["some/file.md"])
        assert rc == 0
        fn.assert_called_once_with("some/file.md", no_diff=False, dry_run=False)
        assert "OK" in capsys.readouterr().out

    def test_explicit_update_with_flags(self):
        with patch.object(cli_module, "update_file", return_value="OK") as fn:
            rc = cli_module.main(["update", "f.md", "--no-diff", "--dry-run"])
        assert rc == 0
        fn.assert_called_once_with("f.md", no_diff=True, dry_run=True)

    def test_transport_error_prints_error_exit_2(self, capsys):
        with patch.object(
            cli_module, "update_file", side_effect=ValueError("not bound")
        ):
            rc = cli_module.main(["f.md"])
        assert rc == 2
        captured = capsys.readouterr()
        assert captured.err.startswith("error: not bound")
        assert captured.out == ""


class TestCliPush:
    def test_push_passes_all_flags(self):
        with patch.object(cli_module, "push_file", return_value="OK") as fn:
            rc = cli_module.main(
                ["push", "f.md", "--notebook", "NB/Sub", "--title", "T", "--force"]
            )
        assert rc == 0
        fn.assert_called_once_with(
            "f.md", notebook="NB/Sub", title="T", force=True, dry_run=False
        )

    def test_push_refusal_is_clean_error(self, capsys):
        with patch.object(
            cli_module, "push_file", side_effect=ValueError("note already exists")
        ):
            rc = cli_module.main(["push", "f.md"])
        assert rc == 2
        assert "error: note already exists" in capsys.readouterr().err


class TestCliPull:
    def test_pull_passes_note_id(self):
        with patch.object(cli_module, "pull_note", return_value="OK") as fn:
            rc = cli_module.main(["pull", "f.md", "--note-id", "a" * 32])
        assert rc == 0
        fn.assert_called_once_with("f.md", note_id="a" * 32, dry_run=False)

    def test_pull_dry_run(self):
        with patch.object(cli_module, "pull_note", return_value="OK") as fn:
            cli_module.main(["pull", "f.md", "--dry-run"])
        fn.assert_called_once_with("f.md", note_id=None, dry_run=True)


class TestCliParsing:
    def test_no_args_errors_with_usage(self):
        with pytest.raises(SystemExit):
            cli_module.main([])

    def test_unknown_flag_errors(self):
        with pytest.raises(SystemExit):
            cli_module.main(["update", "f.md", "--bogus"])
