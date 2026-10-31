"""zizmor over a repository's GitHub Actions workflows, and the gate `devops ci` runs on it (#861)."""

from __future__ import annotations

import json
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.commands.ci import get_check_spec
from devops_cli.config.commands import BIN_ZIZMOR, build_zizmor_cmd
from devops_cli.config.constants import CONST_EXIT_COMMAND_NOT_FOUND
from devops_cli.exceptions.tools import ToolExecutionError
from devops_cli.security.zizmor import parse_zizmor_json, run_zizmor
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer

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


def _answer_zizmor(process_fake: ProcessFake, findings: list[Any], returncode: int = 0) -> None:
    """Answer each zizmor run with `findings` as its JSON, and `returncode`."""
    process_fake.answer(
        BIN_ZIZMOR, ProcessAnswer(returncode=returncode, stdout=json.dumps(findings))
    )


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
def test_zizmor_that_could_not_run_is_an_error_not_a_clean_result(
    process_fake: ProcessFake, returncode: int
) -> None:
    _answer_zizmor(process_fake, [], returncode)
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
    process_fake: ProcessFake,
    findings: list[Any],
    exit_code: int,
    blocking: bool,
    cli: Callable[..., Any],
) -> None:
    _answer_zizmor(process_fake, findings)
    result = cli(["scan", "workflows"])
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        all(f"{f['ident']}" in output for f in findings),
        "block the gate" in output,
    ) == (exit_code, True, blocking)


def test_scan_workflows_fails_when_zizmor_could_not_run(
    process_fake: ProcessFake, cli: Callable[..., Any]
) -> None:
    _answer_zizmor(process_fake, [], CONST_EXIT_COMMAND_NOT_FOUND)
    result = cli(["scan", "workflows"])
    assert (result.exit_code, "zizmor" in result.output) == (1, True)


def test_the_ci_gate_runs_the_scan_with_the_pinned_dev_zizmor() -> None:
    """`devops ci` runs zizmor through `devops scan workflows`, from the dev group's exact pin."""
    dev = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["dependency-groups"]
    assert (
        get_check_spec("zizmor").cmd,
        [spec for spec in dev["dev"] if spec.startswith("zizmor")],
    ) == (["uv", "run", "devops", "scan", "workflows"], ["zizmor==1.30.1"])


def test_scan_workflows_json_marks_which_findings_block(
    process_fake: ProcessFake, cli: Callable[..., Any]
) -> None:
    _answer_zizmor(
        process_fake, [_finding("template-injection"), _finding("artipacked", "Medium", row=40)]
    )
    result = cli(["scan", "workflows", "--json"])
    rows = json.loads(result.stdout[result.stdout.index("[") :])
    assert (result.exit_code, [(row["rule"], row["blocks"]) for row in rows]) == (
        1,
        [("template-injection", True), ("artipacked", False)],
    )


def test_a_dry_run_names_the_audit_and_runs_nothing(
    process_fake: ProcessFake, cli: Callable[..., Any]
) -> None:
    result = cli(["scan", "workflows", "--dry-run"])
    assert (result.exit_code, process_fake.calls) == (0, [])


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
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scanner_fake: ScannerFake,
    cli: Callable[..., Any],
) -> None:
    repo = _repo_with_workflow(tmp_path / "repo")
    monkeypatch.chdir(repo)
    sarif = tmp_path / "scan.sarif"
    found = [_finding("template-injection"), _finding("artipacked", "Medium", row=40)]
    scanner_fake.script(BIN_ZIZMOR, ToolAnswer(stdout=json.dumps(found)))

    result = cli(["scan", "report", "--scanner", "zizmor", "--sarif", str(sarif)])
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
