"""TFLint: the adapter's run of the pinned tool, and the report it reads (#2427).

Most reports below have the shape that `formatter/json.go` of tflint v0.65.0 writes, with the
severities `error`, `warning` and `info` of `toSeverity` in `formatter/formatter.go`. They are
written from that source. One test reads the run of tflint 0.65.0 that is recorded in
`tests/fixtures/scanner_runs/runs_with_findings.json`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from devops_cli.security.tflint import run_tflint_scan
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer


def _issue(rule: str, severity: str, message: str, filename: str, line: int) -> dict[str, Any]:
    """One issue as `JSONIssue` of tflint is written."""
    position = {"line": line, "column": 1}
    return {
        "rule": {"name": rule, "severity": severity, "link": f"https://example.com/{rule}"},
        "message": message,
        "range": {"filename": filename, "start": position, "end": position},
        "callers": [],
        "fixable": False,
        "fixed": False,
    }


def _report(*issues: dict[str, Any], errors: list[dict[str, Any]] | None = None) -> str:
    """The one object that `tflint --format json` writes."""
    return json.dumps({"issues": list(issues), "errors": errors or []})


def test_a_scan_without_tflint_is_unavailable_and_has_no_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no `tflint` on PATH, no hand-written check stands in for it, whatever the target holds."""
    (tmp_path / "main.tf").write_text(
        'resource "aws_security_group" "web" { cidr_blocks = ["0.0.0.0/0"] }\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("PATH", str(tmp_path / "no-programs"))

    outcome = run_tflint_scan(tmp_path)

    assert (outcome.status, outcome.reason, outcome.findings) == (
        "unavailable",
        "Binary 'tflint' not found on PATH",
        [],
    )


def test_a_scan_maps_each_tflint_severity(tmp_path: Path, scanner_fake: ScannerFake) -> None:
    """The severities `error`, `warning` and `info` become HIGH, MEDIUM and LOW, in report order,
    and a run that exits 2 with issues is a scan that ran."""
    report = _report(
        _issue("terraform_unused_declarations", "error", "variable is unused", "variables.tf", 5),
        _issue("terraform_deprecated_index", "warning", "index syntax is deprecated", "db.tf", 20),
        _issue("terraform_module_pinned_source", "info", "module is not pinned", "main.tf", 12),
    )
    scanner_fake.script("tflint", ToolAnswer(exit_code=2, stdout=report))

    outcome = run_tflint_scan(tmp_path)

    assert (outcome.status, [(f.severity, f.location) for f in outcome.findings]) == (
        "ran",
        [("HIGH", "variables.tf:5"), ("MEDIUM", "db.tf:20"), ("LOW", "main.tf:12")],
    )


def test_a_tflint_issue_becomes_a_finding_with_its_rule_and_message(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """The title of the finding names the rule and carries the message of the issue."""
    issue = _issue(
        "terraform_deprecated_interpolation", "warning", "Interpolation is old", "v.tf", 5
    )
    scanner_fake.script("tflint", ToolAnswer(exit_code=2, stdout=_report(issue)))

    findings = run_tflint_scan(tmp_path)

    assert [(f.title, f.description) for f in findings] == [
        ("[terraform_deprecated_interpolation] Interpolation is old", "Interpolation is old")
    ]


def test_a_scan_starts_tflint_recursive_with_json_output_and_the_config_file(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """tflint takes no path argument: it starts in the directory of the target, lints each
    directory below it (`--recursive`), writes its report as JSON, and reads the config file that
    the caller names (#2427)."""
    scanner_fake.script("tflint", ToolAnswer(stdout=_report()))
    config_file = tmp_path / ".tflint.hcl"
    config_file.write_text("config {}", encoding="utf-8")

    run_tflint_scan(tmp_path, config_file=config_file)

    [run] = scanner_fake.runs
    assert (run.argv[1:], run.cwd) == (
        ["--format", "json", "--recursive", "--config", str(config_file)],
        str(tmp_path),
    )


def test_a_tree_whose_tf_files_are_in_sub_directories_is_linted_there(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """A target with no `.tf` file of its own, such as a repository with a `tf/` directory, is
    linted in its sub-directories: the command asks for the recursive run, and the finding is at
    the file in the sub-directory (#2427). The report is scripted, in the shape of the source."""
    module = tmp_path / "tf" / "network"
    module.mkdir(parents=True)
    (module / "main.tf").write_text('variable "unused" {}\n', encoding="utf-8")
    issue = _issue("terraform_unused_declarations", "warning", "unused", "tf/network/main.tf", 1)
    scanner_fake.script("tflint", ToolAnswer(exit_code=2, stdout=_report(issue)))

    outcome = run_tflint_scan(tmp_path)

    [run] = scanner_fake.runs
    assert (
        "--recursive" in run.argv,
        outcome.status,
        [finding.location for finding in outcome.findings],
    ) == (True, "ran", ["tf/network/main.tf:1"])


def test_the_recorded_tflint_run_gives_one_finding_for_each_issue_with_its_relative_file(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """The run of tflint 0.65.0 over a tree with two `.tf` files, one in `modules/network`,
    exits 2 and writes six issues of the bundled `terraform` ruleset. All are warnings, so each
    finding is MEDIUM. A file name is relative to the directory that tflint started in, and
    `--recursive` gives the file of the module as `modules/network/main.tf` (#2427)."""
    recorded = scanner_fake.script_run_with_findings("tflint", tree=tmp_path)

    outcome = run_tflint_scan(tmp_path)

    assert (scanner_fake.runs, outcome.status) == ([recorded], "ran")
    assert [(f.severity, f.location, f.title) for f in outcome.findings] == [
        ("MEDIUM", "main.tf:1", "[terraform_typed_variables] `unused` variable has no type"),
        (
            "MEDIUM",
            "main.tf:1",
            '[terraform_unused_declarations] variable "unused" is declared but not used',
        ),
        (
            "MEDIUM",
            "main.tf:1",
            '[terraform_required_version] terraform "required_version" attribute is required',
        ),
        (
            "MEDIUM",
            "modules/network/main.tf:1",
            "[terraform_typed_variables] `zone` variable has no type",
        ),
        (
            "MEDIUM",
            "modules/network/main.tf:1",
            '[terraform_unused_declarations] variable "zone" is declared but not used',
        ),
        (
            "MEDIUM",
            "modules/network/main.tf:1",
            '[terraform_required_version] terraform "required_version" attribute is required',
        ),
    ]


def test_a_clean_report_is_a_scan_that_ran_with_no_finding(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """tflint exits 0 and writes no issue and no error."""
    scanner_fake.script("tflint", ToolAnswer(stdout=_report()))

    outcome = run_tflint_scan(tmp_path)

    assert (outcome.status, outcome.findings) == ("ran", [])


def test_a_report_with_an_error_and_no_issue_is_a_failed_scan(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """tflint exits 1 after it prints an error with no issue, such as a file it cannot parse: the
    scan did not lint the target, so it did not run."""
    error = {"severity": "error", "summary": "Invalid block", "message": "Unclosed block"}
    scanner_fake.script("tflint", ToolAnswer(exit_code=1, stdout=_report(errors=[error])))

    outcome = run_tflint_scan(tmp_path)

    assert (outcome.status, outcome.findings) == ("failed", [])


def test_a_tflint_that_cannot_start_is_a_failed_scan_and_not_a_fallback(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """When `tflint` cannot start, the scan has no result and no hand-written check answers."""
    (tmp_path / "main.tf").write_text(
        'resource "aws_security_group" "web" { cidr_blocks = ["0.0.0.0/0"] }\n',
        encoding="utf-8",
    )
    scanner_fake.fail("tflint", RuntimeError("Subprocess failed"))

    outcome = run_tflint_scan(tmp_path)

    assert (outcome.status, outcome.findings) == ("failed", [])
