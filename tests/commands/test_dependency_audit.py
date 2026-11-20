"""What a dependency audit's exit status and output say: clean, vulnerable, or not run.

`uv audit` and `npm audit` both exit 1 on a finding, but only uv keeps a failure to run apart by
its status (2). npm exits 1 for an unreachable registry too, and says which it was in its `--json`
report, recorded in `tests/fixtures/npm_audit/` from npm 11 against loopback registries: `clean`
and `vulnerable` answer the advisory request, `registry_unreachable` refuses the connection and
`advisory_endpoint_missing` answers it 404. `picomatch_redos` is the report of the OpenSpec lockfile on
2026-11-17, with one advisory (GHSA-fc5q-39xc-vjpf) that no released picomatch fixes (#6204).
"""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import pytest

from devops_cli.commands import ci
from devops_cli.commands.ci import get_check_spec
from devops_cli.core.dependency_audit import AuditVerdict, audit_verdict
from tests.support.paths import FIXTURES

_NPM_AUDIT = ["npm", "audit", "--package-lock-only", "--json"]
_UV_AUDIT = ["uv", "audit"]


def _recorded(name: str) -> str:
    return (FIXTURES / "npm_audit" / f"{name}.json").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("recording", "returncode", "verdict"),
    [
        ("clean", 0, AuditVerdict.CLEAN),
        ("vulnerable", 1, AuditVerdict.VULNERABLE),
        ("registry_unreachable", 1, AuditVerdict.NOT_RUN),
        ("advisory_endpoint_missing", 1, AuditVerdict.NOT_RUN),
    ],
)
def test_npm_audit_report_tells_a_finding_from_an_audit_that_could_not_run(
    recording: str, returncode: int, verdict: AuditVerdict
) -> None:
    assert audit_verdict(_NPM_AUDIT, returncode, _recorded(recording)) == verdict


@pytest.mark.parametrize(
    "stdout",
    ["", "npm error something\n", "[]", '{"metadata": {"vulnerabilities": {"total": 0}}}'],
    ids=["no-output", "not-json", "not-a-report", "report-without-findings"],
)
def test_npm_audit_failure_without_a_report_of_findings_is_an_audit_that_could_not_run(
    stdout: str,
) -> None:
    assert audit_verdict(_NPM_AUDIT, 1, stdout) == AuditVerdict.NOT_RUN


def test_npm_audit_missing_from_the_path_is_an_audit_that_could_not_run() -> None:
    assert audit_verdict(_NPM_AUDIT, 127, "") == AuditVerdict.NOT_RUN


@pytest.mark.parametrize(
    ("returncode", "verdict"),
    [(0, AuditVerdict.CLEAN), (1, AuditVerdict.VULNERABLE), (2, AuditVerdict.NOT_RUN)],
)
def test_uv_audit_reads_its_exit_status_and_never_its_output(
    returncode: int, verdict: AuditVerdict
) -> None:
    """uv exits 1 on a finding and 2 when it could not run; a report that looks like npm's error
    changes nothing."""
    assert audit_verdict(_UV_AUDIT, returncode, _recorded("registry_unreachable")) == verdict


def test_every_command_of_the_audit_check_has_a_reading() -> None:
    for audit_cmd in get_check_spec("audit").commands:
        assert audit_verdict(audit_cmd, 1, "") in {AuditVerdict.VULNERABLE, AuditVerdict.NOT_RUN}


# The lockfile at the root of the repository, which pins OpenSpec (#6409): its audit runs with
# `--prefix .`, and an ignore names it by its path from the root.
_ROOT_LOCK = "package-lock.json"
# The ignore file that `devops ci audit` reads from the project root (#6204).
_IGNORE_FILE = ".npm-audit-ignore.yaml"
_PICOMATCH = "GHSA-fc5q-39xc-vjpf"
_NPM_AUDIT_ROOT = [*_NPM_AUDIT, "--prefix", "."]


def test_npm_audit_passes_when_every_advisory_of_the_report_is_ignored() -> None:
    report = _recorded("picomatch_redos")
    assert audit_verdict(_NPM_AUDIT, 1, report, ignored={_PICOMATCH}) == AuditVerdict.CLEAN


def test_npm_audit_finds_an_advisory_that_no_entry_ignores() -> None:
    report = _recorded("picomatch_redos")
    assert audit_verdict(_NPM_AUDIT, 1, report) == AuditVerdict.VULNERABLE
    assert (
        audit_verdict(_NPM_AUDIT, 1, report, ignored={"GHSA-0000-0000-0000"})
        == AuditVerdict.VULNERABLE
    )


def test_an_ignore_never_turns_an_audit_that_could_not_run_into_a_pass() -> None:
    report = _recorded("registry_unreachable")
    assert audit_verdict(_NPM_AUDIT, 1, report, ignored={_PICOMATCH}) == AuditVerdict.NOT_RUN


def _gate_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, today: date
) -> subprocess.CompletedProcess[str]:
    """The gate's reading of the recorded OpenSpec report, with one ignore file in a project root."""
    (tmp_path / _IGNORE_FILE).write_text(
        "vulnerabilities:\n"
        f"  - id: {_PICOMATCH}\n"
        f"    paths: [{_ROOT_LOCK}]\n"
        "    statement: picomatch ReDoS, no released fix (#6202)\n"
        "    expired_at: 2026-11-20\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ci, "_get_project_root", lambda: tmp_path)
    monkeypatch.setattr(ci, "_audit_today", lambda: today)
    run = subprocess.CompletedProcess(_NPM_AUDIT_ROOT, 1, _recorded("picomatch_redos"), "")
    return ci._with_audit_failure_line(_NPM_AUDIT_ROOT, run)


def test_the_gate_passes_an_ignored_report_and_names_the_ignore(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = _gate_run(monkeypatch, tmp_path, date(2026, 11, 17))
    assert run.returncode == 0
    assert _PICOMATCH in run.stderr
    assert "2026-11-20" in run.stderr


def test_the_gate_fails_once_the_ignore_expired_and_says_so(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = _gate_run(monkeypatch, tmp_path, date(2026, 11, 20))
    assert run.returncode == 1
    assert "expired" in run.stderr
