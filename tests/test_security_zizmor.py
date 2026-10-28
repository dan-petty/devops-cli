"""zizmor over a repository's GitHub Actions workflows, and the gate `devops ci` runs on it (#861)."""

from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ci import get_check_spec
from devops_cli.commands.scan import app as scan_app
from devops_cli.config.commands import BIN_ZIZMOR, build_zizmor_cmd
from devops_cli.config.constants import CONST_EXIT_COMMAND_NOT_FOUND
from devops_cli.exceptions.tools import ToolExecutionError
from devops_cli.security.zizmor import parse_zizmor_json, run_zizmor
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer

runner = CliRunner()
WORKFLOW = ".github/workflows/release.yml"


def _location(kind: str, row: int) -> dict[str, Any]:
    """One of a finding's locations, as zizmor's JSON writes it: rows count from 0."""
    return {
        "symbolic": {"key": {"Local": {"verbatim_path": WORKFLOW}}, "kind": kind},
        "concrete": {"location": {"start_point": {"row": row, "column": 8}}},
    }


def _finding(rule: str, severity: str = "High", *, row: int = 66, ignored: bool = False) -> Any:
    """A zizmor finding whose primary location is at `row`, listed after a hidden one."""
    return {
        "ident": rule,
        "desc": f"{rule} described",
        "url": f"https://docs.zizmor.sh/audits/#{rule}",
        "determinations": {"confidence": "High", "severity": severity, "persona": "Regular"},
        "ignored": ignored,
        "locations": [_location("Hidden", row - 3), _location("Primary", row)],
    }


def _ran(findings: list[Any], returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout=json.dumps(findings), stderr="")


def test_a_finding_is_read_at_its_primary_location_and_an_ignored_one_is_left_out() -> None:
    found = parse_zizmor_json(
        [_finding("template-injection"), _finding("artipacked", ignored=True)]
    )

    assert [(f.rule, f.location, f.severity, f.blocks) for f in found] == [
        ("template-injection", f"{WORKFLOW}:67", "High", True)
    ]


def test_zizmor_runs_offline_and_reports_findings_by_its_output_not_its_exit_code() -> None:
    """With `--no-exit-codes` zizmor exits 0 whatever it finds, so a non-zero exit means it
    could not run."""
    assert build_zizmor_cmd(Path(".github")) == [
        "zizmor",
        "--offline",
        "--no-exit-codes",
        "--format",
        "json",
        ".github",
    ]


@pytest.mark.parametrize("returncode", [CONST_EXIT_COMMAND_NOT_FOUND, 2])
def test_zizmor_that_could_not_run_is_an_error_not_a_clean_result(returncode: int) -> None:
    with patch("devops_cli.security.zizmor.run_subprocess", return_value=_ran([], returncode)):
        with pytest.raises(ToolExecutionError, match="zizmor"):
            run_zizmor(Path(".github"))


@pytest.mark.parametrize(
    ("findings", "exit_code", "blocking"),
    [
        ([_finding("template-injection"), _finding("artipacked", "Medium", row=40)], 1, True),
        ([_finding("excessive-permissions")], 1, True),
        ([_finding("unpinned-uses")], 1, True),
        ([_finding("artipacked", "Medium", row=40), _finding("cache-poisoning")], 0, False),
        ([], 0, False),
    ],
    ids=["injection", "permissions", "unpinned", "other-rules-only", "none"],
)
def test_scan_workflows_fails_only_on_the_gated_rules_and_shows_every_finding(
    findings: list[Any], exit_code: int, blocking: bool
) -> None:
    with patch("devops_cli.security.zizmor.run_subprocess", return_value=_ran(findings)):
        result = runner.invoke(scan_app, ["workflows"])
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        all(f"{f['ident']}" in output for f in findings),
        "block the gate" in output,
    ) == (exit_code, True, blocking)


def test_scan_workflows_fails_when_zizmor_could_not_run() -> None:
    could_not_run = _ran([], CONST_EXIT_COMMAND_NOT_FOUND)
    with patch("devops_cli.security.zizmor.run_subprocess", return_value=could_not_run):
        result = runner.invoke(scan_app, ["workflows"])
    assert (result.exit_code, "zizmor" in result.output) == (1, True)


def test_the_ci_gate_runs_the_scan_with_the_pinned_dev_zizmor() -> None:
    """`devops ci` runs zizmor through `devops scan workflows`, from the dev group's exact pin."""
    dev = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["dependency-groups"]
    assert (
        get_check_spec("zizmor").cmd,
        [spec for spec in dev["dev"] if spec.startswith("zizmor")],
    ) == (["uv", "run", "devops", "scan", "workflows"], ["zizmor==1.30.1"])


def test_scan_workflows_json_marks_which_findings_block() -> None:
    found = [_finding("template-injection"), _finding("artipacked", "Medium", row=40)]
    with patch("devops_cli.security.zizmor.run_subprocess", return_value=_ran(found)):
        result = runner.invoke(scan_app, ["workflows", "--json"])
    rows = json.loads(result.stdout[result.stdout.index("[") :])
    assert (result.exit_code, [(row["rule"], row["blocks"]) for row in rows]) == (
        1,
        [("template-injection", True), ("artipacked", False)],
    )


def test_a_dry_run_names_the_audit_and_runs_nothing() -> None:
    with patch("devops_cli.security.zizmor.run_subprocess") as ran:
        result = runner.invoke(scan_app, ["workflows", "--dry-run"])
    assert (result.exit_code, ran.called) == (0, False)


def _repo_with_workflow(root: Path) -> Path:
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("on: push\njobs: {}\n", encoding="utf-8")
    return root


def test_zizmor_is_a_registered_scanner_that_publishes_without_gating(tmp_path: Path) -> None:
    """`devops scan report`, its SARIF and reviews run every registered scanner; zizmor's
    findings are published there, and `devops scan workflows` stays the gate (#861)."""
    from devops_cli.security.registry import global_scanner_registry

    scanner = global_scanner_registry.get("zizmor")
    repo = _repo_with_workflow(tmp_path / "repo")
    (tmp_path / "bare").mkdir()
    assert scanner is not None
    assert (
        scanner.gating,
        scanner.is_applicable(repo)[0],
        scanner.is_applicable(tmp_path / "bare")[0],
        scanner.build_command(repo)[-1],
        [(f.flag, f.text) for f in scanner.isolation_files],
    ) == (False, True, False, str(repo / ".github"), [("--config", "rules: {}\n")])


def test_scan_report_publishes_zizmor_findings_in_its_sarif_by_rule_and_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scanner_fake: ScannerFake
) -> None:
    repo = _repo_with_workflow(tmp_path / "repo")
    monkeypatch.chdir(repo)
    sarif = tmp_path / "scan.sarif"
    found = [_finding("template-injection"), _finding("artipacked", "Medium", row=40)]
    scanner_fake.script(BIN_ZIZMOR, ToolAnswer(stdout=json.dumps(found)))

    result = runner.invoke(scan_app, ["report", "--scanner", "zizmor", "--sarif", str(sarif)])
    document = json.loads(sarif.read_text(encoding="utf-8"))
    published = sorted(
        (r["ruleId"], r["locations"][0]["physicalLocation"]["region"]["startLine"])
        for run in document["runs"]
        for r in run["results"]
    )
    assert (result.exit_code, published) == (
        0,
        [("artipacked", 41), ("template-injection", 67)],
    )
