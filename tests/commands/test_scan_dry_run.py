"""Tests for dry-run request plans and classifications across 12 scan commands.

Issue #2250: The dry-run rule (#412) states that a dry run makes zero external requests and
returns the requests that the real run would make.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.scan import (
    callback as scan_callback,
)
from devops_cli.commands.scan import (
    scan_aibom,
    scan_complexity,
    scan_fix,
    scan_injection,
    scan_report,
    scan_sarif,
    scan_sast,
    scan_sbom,
    scan_secrets,
    scan_trivy,
    scan_workflows,
)
from devops_cli.main import app
from tests.support.dry_run_classes import misclassified

runner = CliRunner()

REQUEST_PLAN_COMMANDS = [
    ("scan", scan_callback, ["scan", "--dry-run"]),
    ("scan trivy", scan_trivy, ["scan", "trivy", "--dry-run"]),
    ("scan fix", scan_fix, ["scan", "fix", "--dry-run"]),
    ("scan report", scan_report, ["scan", "report", "--dry-run"]),
    ("scan sast", scan_sast, ["scan", "sast", "--dry-run"]),
]

NO_EXTERNAL_REQUEST_COMMANDS = [
    ("scan aibom", scan_aibom, ["scan", "aibom"]),
    ("scan complexity", scan_complexity, ["scan", "complexity"]),
    ("scan injection", scan_injection, ["scan", "injection"]),
    ("scan sarif", scan_sarif, ["scan", "sarif"]),
    ("scan sbom", scan_sbom, ["scan", "sbom"]),
    ("scan secrets", scan_secrets, ["scan", "secrets"]),
    ("scan workflows", scan_workflows, ["scan", "workflows"]),
]


def test_commands_carry_their_dry_run_class() -> None:
    """Criteria 2 and 3: external-request scan commands carry request-plan, local ones no-external-request."""
    assert misclassified(REQUEST_PLAN_COMMANDS, "request-plan") == {}
    assert misclassified(NO_EXTERNAL_REQUEST_COMMANDS, "no-external-request") == {}


@pytest.mark.parametrize("name,_callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_commands_make_no_external_request(
    name: str,
    _callback: Any,
    argv: list[str],
    refuse_requests: list[str],
    tmp_path: Path,
) -> None:
    """Criterion 2: dry-run on request-plan commands sends no request and prints requests."""
    cmd_args = list(argv)
    if name in ("scan trivy", "scan sast", "scan report", "scan fix"):
        cmd_args.insert(2 if len(cmd_args) > 2 and cmd_args[1] != "--dry-run" else 1, str(tmp_path))

    result = runner.invoke(app, cmd_args)
    assert result.exit_code == 0, f"Command '{name}' failed with: {result.output}"
    assert "Plan for" in result.output or "Planned" in result.output or "1." in result.output, (
        f"Command '{name}' must output planned requests. Output:\n{result.output}"
    )


def test_scan_trivy_json_dry_run(tmp_path: Path, refuse_requests: list[str]) -> None:
    """Criterion 3: scan trivy --dry-run --json returns structured dry-run payload."""
    result = runner.invoke(app, ["scan", "trivy", str(tmp_path), "--dry-run", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data.get("dry_run") is True
    assert isinstance(data.get("requests"), list)
    assert len(data["requests"]) > 0


def test_scan_sast_json_dry_run(tmp_path: Path, refuse_requests: list[str]) -> None:
    """Criterion 3: scan sast --dry-run --json returns structured dry-run payload."""
    result = runner.invoke(app, ["scan", "sast", str(tmp_path), "--dry-run", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data.get("dry_run") is True
    assert isinstance(data.get("requests"), list)
    assert len(data["requests"]) > 0


def test_scan_report_json_dry_run(tmp_path: Path, refuse_requests: list[str]) -> None:
    """Criterion 3: scan report --dry-run --json returns structured dry-run payload."""
    result = runner.invoke(
        app,
        ["scan", "report", str(tmp_path), "--scanner", "trivy", "--dry-run", "--json"],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data.get("dry_run") is True
    assert isinstance(data.get("requests"), list)
    assert len(data["requests"]) > 0


def test_scan_fix_json_dry_run(tmp_path: Path, refuse_requests: list[str]) -> None:
    """Criterion 3: scan fix --dry-run --json returns structured remediation result."""
    result = runner.invoke(app, ["scan", "fix", str(tmp_path), "--dry-run", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data.get("dry_run") is True
    assert isinstance(data.get("requests"), list)
    assert len(data["requests"]) > 0


def test_no_external_request_commands_have_no_dry_run_option() -> None:
    """Criterion 4: local inspection commands declare no redundant --dry-run option."""
    for name, callback, _argv in NO_EXTERNAL_REQUEST_COMMANDS:
        param_names = [param.name for param in getattr(callback, "__click_params__", [])]
        assert "dry_run" not in param_names, (
            f"Command '{name}' should not declare redundant --dry-run option"
        )
