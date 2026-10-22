"""Unit tests for devops ci maintain command."""

from __future__ import annotations

import subprocess

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ci import app, get_check_spec
from tests.support.paths import FIXTURES

runner = CliRunner()


def _answer_audits(
    monkeypatch: pytest.MonkeyPatch,
    *,
    uv: tuple[int, str] = (0, ""),
    npm: tuple[int, str] = (0, ""),
) -> list[list[str]]:
    """Answer `uv audit` and `npm audit` with an exit status and output, any other command with
    success; the commands started, in order."""
    ran: list[list[str]] = []

    def run(cmd: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        ran.append(cmd)
        status, output = {"uv": uv, "npm": npm}[cmd[0]] if "audit" in cmd else (0, "")
        return subprocess.CompletedProcess(cmd, status, output, "")

    monkeypatch.setattr("subprocess.run", run)
    return ran


def _recorded_npm_audit(name: str) -> str:
    return (FIXTURES / "npm_audit" / f"{name}.json").read_text(encoding="utf-8")


def _said(output: str) -> str:
    return " ".join(output.split())


def test_ci_maintain_dry_run() -> None:
    result = runner.invoke(app, ["maintain", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY_RUN" in result.stdout


def test_maintain_runs_both_audits_of_the_audit_check_and_passes_when_both_are_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The audit runs through the audit check's own commands, never a real `uv audit` (#1697)."""
    ran = _answer_audits(monkeypatch)

    result = runner.invoke(app, ["maintain", "--fix"])

    audits = [cmd for cmd in ran if "audit" in cmd]
    assert (result.exit_code, audits) == (
        0,
        [
            ["uv", "--preview-features", "malware-check,check-command", "audit"],
            *get_check_spec("audit").commands[1:],
        ],
    )


@pytest.mark.parametrize(
    ("returncode", "reported", "not_reported"),
    [
        (1, "found vulnerabilities (uv audit exited 1)", "could not run"),
        (2, "could not run (uv audit exited 2)", "found vulnerabilities"),
    ],
    ids=["vulnerable", "could-not-run"],
)
def test_maintain_says_whether_uv_audit_found_vulnerabilities_or_could_not_run(
    monkeypatch: pytest.MonkeyPatch, returncode: int, reported: str, not_reported: str
) -> None:
    """uv exits 1 when a check fails and 2 when it cannot run, such as with no network: only the
    first means vulnerabilities (#861)."""
    ran = _answer_audits(monkeypatch, uv=(returncode, ""))

    result = runner.invoke(app, ["maintain"])

    said = _said(result.output)
    assert (
        result.exit_code,
        reported in said,
        not_reported in said,
        any("pip-audit" in part for cmd in ran for part in cmd),
    ) == (1, True, False, False)


@pytest.mark.parametrize(
    ("recording", "reported", "not_reported"),
    [
        ("vulnerable", "found vulnerabilities (npm audit exited 1)", "could not run"),
        ("registry_unreachable", "could not run (npm audit exited 1)", "found vulnerabilities"),
        (
            "advisory_endpoint_missing",
            "could not run (npm audit exited 1)",
            "found vulnerabilities",
        ),
    ],
)
def test_maintain_says_whether_npm_audit_found_vulnerabilities_or_could_not_run_by_its_report(
    monkeypatch: pytest.MonkeyPatch, recording: str, reported: str, not_reported: str
) -> None:
    """npm exits 1 for a finding and for an audit that could not run, such as a registry that is
    unreachable or answers no advisory request; its `--json` report says which, and the report is
    shown above the verdict."""
    report = _recorded_npm_audit(recording)
    _answer_audits(monkeypatch, npm=(1, report))

    result = runner.invoke(app, ["maintain"])

    said = _said(result.output)
    assert (
        result.exit_code,
        reported in said,
        not_reported in said,
        _said(report) in said,
    ) == (1, True, False, True)


def test_maintain_reports_every_audit_that_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A vulnerable Python dependency does not hide an npm audit that could not run."""
    _answer_audits(monkeypatch, uv=(1, ""), npm=(1, _recorded_npm_audit("registry_unreachable")))

    result = runner.invoke(app, ["maintain"])

    said = _said(result.output)
    assert (
        result.exit_code,
        "found vulnerabilities (uv audit exited 1)" in said,
        "could not run (npm audit exited 1)" in said,
    ) == (1, True, True)
