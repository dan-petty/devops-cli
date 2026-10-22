"""What a dependency audit's exit status and output say: clean, vulnerable, or not run.

`uv audit` and `npm audit` both exit 1 on a finding, but only uv keeps a failure to run apart by
its status (2). npm exits 1 for an unreachable registry too, and says which it was in its `--json`
report, recorded in `tests/fixtures/npm_audit/` from npm 11 against loopback registries: `clean`
and `vulnerable` answer the advisory request, `registry_unreachable` refuses the connection and
`advisory_endpoint_missing` answers it 404.
"""

from __future__ import annotations

import pytest

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
