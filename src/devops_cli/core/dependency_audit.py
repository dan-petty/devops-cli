"""What a dependency audit's exit status and output say: clean, vulnerable, or not run.

Each audit tool tells a finding from an audit that could not run by its own signal, so each
command is read by its kind:

- `uv audit` exits 1 for a finding and 2 when it could not run, such as with no network.
- `npm audit` exits 1 for both, an unreachable registry or one with no advisories endpoint as much
  as a vulnerable package. Its `--json` report tells them apart: a report of findings counts them
  under `metadata.vulnerabilities`, and a failure carries an `error` object and no counts.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, Field, ValidationError

from devops_cli.config.commands import BIN_NPM, BIN_UV
from devops_cli.config.constants import CONST_EXIT_SUCCESS, CONST_UV_EXIT_FAILURE


class AuditVerdict(StrEnum):
    """What one audit command's run says about the dependencies it audits."""

    CLEAN = "clean"
    VULNERABLE = "vulnerable"
    NOT_RUN = "not_run"


class _NpmVulnerabilityCounts(BaseModel):
    """The `metadata.vulnerabilities` counts of an `npm audit --json` report."""

    total: int = 0


class _NpmAuditMetadata(BaseModel):
    vulnerabilities: _NpmVulnerabilityCounts = Field(default_factory=_NpmVulnerabilityCounts)


class _NpmAuditReport(BaseModel):
    """The part of an `npm audit --json` report that tells a finding from a failure."""

    metadata: _NpmAuditMetadata = Field(default_factory=_NpmAuditMetadata)
    error: object | None = None


def _read_uv_failure(returncode: int, _stdout: str) -> AuditVerdict:
    """uv's own split: 1 is a finding, any other failure an audit that could not run."""
    return AuditVerdict.VULNERABLE if returncode == CONST_UV_EXIT_FAILURE else AuditVerdict.NOT_RUN


def _read_npm_failure(_returncode: int, stdout: str) -> AuditVerdict:
    """A failed `npm audit --json` is a finding when its report counts vulnerabilities and carries
    no error, and an audit that could not run for anything else: an error object, no report, or a
    report of none."""
    try:
        report = _NpmAuditReport.model_validate_json(stdout)
    except ValidationError:
        return AuditVerdict.NOT_RUN
    found = report.error is None and report.metadata.vulnerabilities.total > 0
    return AuditVerdict.VULNERABLE if found else AuditVerdict.NOT_RUN


_FAILURE_READERS: Final[Mapping[str, Callable[[int, str], AuditVerdict]]] = {
    BIN_UV: _read_uv_failure,
    BIN_NPM: _read_npm_failure,
}


def audit_verdict(cmd: Sequence[str], returncode: int, stdout: str) -> AuditVerdict:
    """The verdict of one audit command that exited `returncode` and printed `stdout`, read by the
    kind of command it is, the program it starts. Every audit exits 0 when it is clean."""
    if returncode == CONST_EXIT_SUCCESS:
        return AuditVerdict.CLEAN
    return _FAILURE_READERS[cmd[0]](returncode, stdout)
