"""`devops mcp tools` lists the tools and `devops mcp export-schemas` writes their schemas (#2260)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import PropertyMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.mcp.server import (
    mcp,
)
from devops_cli.commands.mcp import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_tools_command_outputs_table(runner: CliRunner) -> None:
    """devops mcp tools must print a table with tool names."""
    result = runner.invoke(app, ["tools"])
    assert result.exit_code == 0
    assert "review_path" in result.output


def test_export_schemas_command(runner: CliRunner, tmp_path: Path) -> None:
    """devops mcp export-schemas must write JSON files with annotations and instructions."""
    import json

    out_dir = tmp_path / "mcp_schemas"
    result = runner.invoke(app, ["export-schemas", "--output-dir", str(out_dir)])
    trivy_schema = json.loads((out_dir / "scan_trivy.json").read_text(encoding="utf-8"))
    mutating_schema = json.loads((out_dir / "valkey_set.json").read_text(encoding="utf-8"))
    assert (
        result.exit_code,
        (out_dir / "instructions.md").exists(),
        trivy_schema.get("annotations"),
        mutating_schema.get("annotations"),
        "Exported" in result.output and "instructions" in result.output,
    ) == (0, True, {"readOnlyHint": True}, {"readOnlyHint": False}, True)


def test_export_schemas_without_instructions(runner: CliRunner, tmp_path: Path) -> None:
    """devops mcp export-schemas without instructions writes empty file and adjusts message."""
    from devops_cli.ai.mcp.server import mcp

    out_dir = tmp_path / "mcp_schemas_no_inst"
    with patch.object(type(mcp), "instructions", new_callable=PropertyMock, return_value=""):
        result = runner.invoke(app, ["export-schemas", "--output-dir", str(out_dir)])
        assert result.exit_code == 0
        assert (out_dir / "instructions.md").exists()
        assert (out_dir / "instructions.md").read_text(encoding="utf-8") == ""
        assert "Exported" in result.output
        assert "instructions" not in result.output


@pytest.mark.parametrize("flag_first", [True, False])
def test_mcp_export_schemas_dry_run_writes_nothing(
    tmp_path: Path, cli: Any, flag_first: bool
) -> None:
    """A dry run names the directory and the tool count, and creates nothing."""
    out_dir = tmp_path / "schemas"
    argv = ["mcp", "export-schemas", "--output-dir", str(out_dir)]
    with (
        patch.object(Path, "mkdir", side_effect=AssertionError("no directory")),
        patch.object(Path, "write_text", side_effect=AssertionError("no file")),
    ):
        result = cli(["--dry-run", *argv] if flag_first else [*argv, "--dry-run"])

    output = " ".join(result.output.split())
    assert result.exit_code == 0, result.output
    assert "Would write" in output
    assert str(out_dir) in output
    count = int(output.split("Would write ", 1)[1].split()[0])
    assert count == len(asyncio.run(mcp._list_tools()))
    assert not out_dir.exists()


def test_mcp_tools_runs_under_the_dry_run_flag(cli: Any) -> None:
    """`mcp tools` only reads the registry, so `devops --dry-run` runs it."""
    result = cli(["--dry-run", "mcp", "tools"])

    assert result.exit_code == 0, result.output
    assert "review_path" in result.output
    assert cli(["mcp", "tools", "--dry-run"]).exit_code == 2
