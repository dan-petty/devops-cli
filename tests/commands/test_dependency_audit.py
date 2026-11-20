"""What a dependency audit's exit status and output say: clean, vulnerable, or not run.

`uv audit` and `npm audit` both exit 1 on a finding, but only uv keeps a failure to run apart by
its status (2). npm exits 1 for an unreachable registry too, and says which it was in its `--json`
report, recorded in `tests/fixtures/npm_audit/` from npm 11 against loopback registries: `clean`
and `vulnerable` answer the advisory request, `registry_unreachable` refuses the connection and
`advisory_endpoint_missing` answers it 404. `picomatch_redos` is the report of the OpenSpec lockfile on
2026-11-17, with one advisory (GHSA-fc5q-39xc-vjpf) that no released picomatch fixes (#6204).
"""

from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

from devops_cli.commands import ci
from devops_cli.commands.ci import get_check_spec
from devops_cli.config.commands import osv_scanner_lockfile
from devops_cli.core.dependency_audit import AuditVerdict, audit_verdict, osv_advisory_ids
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


_SEMGREP_REQUIREMENTS = "src/devops_cli/tools_lock/semgrep.txt"
_OSV_AUDIT_SEMGREP = ["osv-scanner", "--lockfile", f"requirements.txt:{_SEMGREP_REQUIREMENTS}"]
_SEMGREP_REPORT = """
Total 2 packages affected by 2 known vulnerabilities from 1 ecosystem.
╭─────────────────────────────────────┬──────┬───────────┬─────────╮
│ OSV URL                             │ CVSS │ ECOSYSTEM │ PACKAGE │
├─────────────────────────────────────┼──────┼───────────┼─────────┤
│ https://osv.dev/GHSA-5h93-6whr-6q8j │ 5.9  │ PyPI      │ mcp     │
│ https://osv.dev/GHSA-xcq7-p3pf-p88h │ 5.3  │ PyPI      │ opentelemetry-api │
╰─────────────────────────────────────┴──────┴───────────┴─────────╯
"""


def test_osv_scanner_audit_verdict_tells_clean_from_vulnerable_and_could_not_run() -> None:
    assert audit_verdict(_OSV_AUDIT_SEMGREP, 0, "") == AuditVerdict.CLEAN
    assert audit_verdict(_OSV_AUDIT_SEMGREP, 1, _SEMGREP_REPORT) == AuditVerdict.VULNERABLE
    assert audit_verdict(_OSV_AUDIT_SEMGREP, 127, "") == AuditVerdict.NOT_RUN


def test_osv_scanner_audit_passes_when_every_advisory_of_the_report_is_ignored() -> None:
    ignored = {"GHSA-5h93-6whr-6q8j", "GHSA-xcq7-p3pf-p88h"}
    assert (
        audit_verdict(_OSV_AUDIT_SEMGREP, 1, _SEMGREP_REPORT, ignored=ignored) == AuditVerdict.CLEAN
    )


def test_osv_scanner_audit_fails_when_unignored_advisory_remains() -> None:
    assert (
        audit_verdict(_OSV_AUDIT_SEMGREP, 1, _SEMGREP_REPORT, ignored={"GHSA-5h93-6whr-6q8j"})
        == AuditVerdict.VULNERABLE
    )


def test_the_audit_check_audits_the_requirements_file_of_each_python_tool() -> None:
    assert _OSV_AUDIT_SEMGREP in get_check_spec("audit").commands


def _gate_run_osv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, today: date
) -> subprocess.CompletedProcess[str]:
    """The gate's reading of the recorded osv-scanner report, with one ignore file in a project root."""
    (tmp_path / ".osv-scanner-ignore.yaml").write_text(
        "vulnerabilities:\n"
        "  - id: GHSA-5h93-6whr-6q8j\n"
        f"    paths: [{_SEMGREP_REQUIREMENTS}]\n"
        "    statement: mcp advisory, no released fix (#3988)\n"
        "    expired_at: 2026-11-20\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ci, "_get_project_root", lambda: tmp_path)
    monkeypatch.setattr(ci, "_audit_today", lambda: today)
    single_advisory_report = """
Total 1 package affected by 1 known vulnerability from 1 ecosystem.
╭─────────────────────────────────────┬──────┬───────────┬─────────╮
│ OSV URL                             │ CVSS │ ECOSYSTEM │ PACKAGE │
├─────────────────────────────────────┼──────┼───────────┼─────────┤
│ https://osv.dev/GHSA-5h93-6whr-6q8j │ 5.9  │ PyPI      │ mcp     │
╰─────────────────────────────────────┴──────┴───────────┴─────────╯
"""
    run = subprocess.CompletedProcess(_OSV_AUDIT_SEMGREP, 1, single_advisory_report, "")
    return ci._with_audit_failure_line(_OSV_AUDIT_SEMGREP, run)


def test_the_gate_passes_an_ignored_osv_scanner_report_and_names_the_ignore(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = _gate_run_osv(monkeypatch, tmp_path, date(2026, 11, 17))
    assert run.returncode == 0
    assert "GHSA-5h93-6whr-6q8j" in run.stderr
    assert "2026-11-20" in run.stderr


def test_the_gate_fails_once_the_osv_scanner_ignore_expired_and_says_so(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = _gate_run_osv(monkeypatch, tmp_path, date(2026, 11, 20))
    assert run.returncode == 1
    assert "expired" in run.stderr


def test_osv_scanner_lockfile_extracts_path_and_handles_other_commands() -> None:
    assert (
        osv_scanner_lockfile(["osv-scanner", "--lockfile", "requirements.txt:semgrep.txt"])
        == "semgrep.txt"
    )
    assert osv_scanner_lockfile(["osv-scanner", "--lockfile", "semgrep.txt"]) == "semgrep.txt"
    assert osv_scanner_lockfile(["osv-scanner", "scan"]) is None
    assert osv_scanner_lockfile(["npm", "audit"]) is None
    assert osv_scanner_lockfile([]) is None


def test_osv_advisory_ids_reads_json_and_table_reports() -> None:
    assert osv_advisory_ids("") == frozenset()
    json_report = json.dumps(
        {
            "results": [
                {
                    "packages": [
                        {
                            "vulnerabilities": [
                                {"id": "GHSA-5h93-6whr-6q8j"},
                                {"name": "no-id-field"},
                            ]
                        }
                    ]
                }
            ]
        }
    )
    assert osv_advisory_ids(json_report) == frozenset({"GHSA-5h93-6whr-6q8j"})
    assert osv_advisory_ids("[1, 2, 3]") == frozenset()
    assert osv_advisory_ids('{"results": []}') == frozenset()
    assert osv_advisory_ids(_SEMGREP_REPORT) == frozenset(
        {
            "GHSA-5h93-6whr-6q8j",
            "GHSA-xcq7-p3pf-p88h",
        }
    )
