"""Tests for global CLI dry-run behavior."""

from __future__ import annotations

from typer.testing import CliRunner

import devops_cli.main as main_module

runner = CliRunner()


def test_global_dry_run_skips_delegated_proxy(monkeypatch) -> None:
    called = False

    def _fake_delegate(module_path: str, command_name: str, args: list[str]) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(main_module, "_delegate", _fake_delegate)

    result = runner.invoke(main_module.app, ["--dry-run", "repos", "--unknown-option"])

    assert result.exit_code == 0
    assert not called
    assert "Would run delegated command" in result.output
    assert "devops repos --unknown-option" in result.output
