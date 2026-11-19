"""What a dependency audit's exit status and output say: clean, vulnerable, or not run.

Each audit tool tells a finding from an audit that could not run by its own signal, so each
command is read by its kind:

- `uv audit` exits 1 for a finding and 2 when it could not run, such as with no network.
- `npm audit` exits 1 for both, an unreachable registry or one with no advisories endpoint as much
  as a vulnerable package. Its `--json` report tells them apart: a report of findings counts them
  under `metadata.vulnerabilities`, and a failure carries an `error` object and no counts.

`npm audit` reads no ignore file, so `.npm-audit-ignore.yaml` holds the advisories that no released
version fixes yet, in the form of `.trivyignore.yaml`: the advisory ID, the lockfiles, a statement
with the tracking issue, and `expired_at`. A report of findings passes only when an entry that has
not expired ignores each of its advisories in that lockfile (SECURITY.md, A Finding with No Fix;
#6204).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Final

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from devops_cli.config.commands import BIN_NPM, BIN_OSV_SCANNER, BIN_UV
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


class _NpmAdvisory(BaseModel):
    """One advisory that a vulnerable package of an `npm audit --json` report names in `via`."""

    url: str = ""
    source: int | None = None

    @property
    def id(self) -> str:
        """The advisory ID, such as `GHSA-fc5q-39xc-vjpf`: the last part of its URL."""
        return self.url.rstrip("/").rsplit("/", 1)[-1] if self.url else str(self.source)


class _NpmVulnerablePackage(BaseModel):
    """A package of the report. `via` names its advisories, or the packages it gets them from."""

    via: list[_NpmAdvisory | str] = Field(default_factory=list)


class _NpmAuditReport(BaseModel):
    """The part of an `npm audit --json` report that tells a finding from a failure."""

    metadata: _NpmAuditMetadata = Field(default_factory=_NpmAuditMetadata)
    vulnerabilities: dict[str, _NpmVulnerablePackage] = Field(default_factory=dict)
    error: object | None = None

    def advisory_ids(self) -> frozenset[str]:
        """The IDs of every advisory in the report."""
        return frozenset(
            via.id
            for package in self.vulnerabilities.values()
            for via in package.via
            if isinstance(via, _NpmAdvisory)
        )


_TRACKING_ISSUE: Final[re.Pattern[str]] = re.compile(r"#\d+")


class NpmAuditIgnore(BaseModel):
    """One entry of `.npm-audit-ignore.yaml`: one advisory, the lockfiles it is ignored in, why with
    its tracking issue, and the day on which the entry stops applying (Trivy's `expired_at`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    paths: tuple[str, ...] = Field(min_length=1)
    statement: str
    expired_at: date

    @field_validator("id")
    @classmethod
    def _one_advisory(cls, value: str) -> str:
        if "*" in value:
            raise ValueError("an ignore names one advisory, never a wildcard")
        return value

    @field_validator("paths")
    @classmethod
    def _named_lockfiles(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any("*" in path for path in value):
            raise ValueError("an ignore names each lockfile, never a wildcard")
        return value

    @field_validator("statement")
    @classmethod
    def _tracked(cls, value: str) -> str:
        if not _TRACKING_ISSUE.search(value):
            raise ValueError("the statement names the tracking issue as #N")
        return value


class _NpmAuditIgnoreFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vulnerabilities: tuple[NpmAuditIgnore, ...] = ()


def load_npm_audit_ignores(path: Path) -> tuple[NpmAuditIgnore, ...]:
    """The entries of the ignore file at `path`; none when there is no file."""
    if not path.is_file():
        return ()
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _NpmAuditIgnoreFile.model_validate(loaded).vulnerabilities


AuditIgnore = NpmAuditIgnore
load_osv_audit_ignores = load_npm_audit_ignores


class AppliedIgnores(BaseModel):
    """The entries of one lockfile: those that apply today by advisory ID, and those that expired."""

    active: dict[str, NpmAuditIgnore] = Field(default_factory=dict)
    expired: list[NpmAuditIgnore] = Field(default_factory=list)


def active_npm_ignores(
    entries: Iterable[NpmAuditIgnore], lockfile: str, today: date
) -> AppliedIgnores:
    """The entries that name `lockfile`, split as Trivy reads `expired_at`: an entry applies before
    that day and not on it."""
    applied = AppliedIgnores()
    for entry in entries:
        if lockfile not in entry.paths:
            continue
        if today < entry.expired_at:
            applied.active[entry.id] = entry
        else:
            applied.expired.append(entry)
    return applied


def npm_advisory_ids(stdout: str) -> frozenset[str]:
    """The advisory IDs of an `npm audit --json` report; none when it is no report."""
    try:
        return _NpmAuditReport.model_validate_json(stdout).advisory_ids()
    except ValidationError:
        return frozenset()


def _read_uv_failure(returncode: int, _stdout: str, _ignored: Collection[str]) -> AuditVerdict:
    """uv's own split: 1 is a finding, any other failure an audit that could not run."""
    return AuditVerdict.VULNERABLE if returncode == CONST_UV_EXIT_FAILURE else AuditVerdict.NOT_RUN


def _read_npm_failure(_returncode: int, stdout: str, ignored: Collection[str]) -> AuditVerdict:
    """A failed `npm audit --json` is a finding when its report counts vulnerabilities and carries
    no error, and an audit that could not run for anything else: an error object, no report, or a
    report of none. A finding passes when `ignored` holds each of its advisories."""
    try:
        report = _NpmAuditReport.model_validate_json(stdout)
    except ValidationError:
        return AuditVerdict.NOT_RUN
    if report.error is not None or report.metadata.vulnerabilities.total == 0:
        return AuditVerdict.NOT_RUN
    advisories = report.advisory_ids()
    if advisories and advisories <= set(ignored):
        return AuditVerdict.CLEAN
    return AuditVerdict.VULNERABLE


def _json_advisory_ids(data: object) -> set[str]:
    if not isinstance(data, dict):
        return set()
    return {
        vuln["id"]
        for res in data.get("results", [])
        for pkg in res.get("packages", [])
        for vuln in pkg.get("vulnerabilities", [])
        if "id" in vuln
    }


def osv_advisory_ids(stdout: str) -> frozenset[str]:
    """The advisory IDs of an `osv-scanner` report; none when it is no report."""
    if not stdout:
        return frozenset()
    try:
        json_ids = _json_advisory_ids(json.loads(stdout))
        if json_ids:
            return frozenset(json_ids)
    except json.JSONDecodeError, ValueError:
        pass
    urls = re.findall(r"https://osv\.dev/([A-Za-z0-9_-]+)", stdout)
    if urls:
        return frozenset(urls)
    return frozenset(re.findall(r"\b(GHSA-[0-9a-zA-Z-]+|CVE-\d{4}-\d+|PYSEC-\d{4}-\d+)\b", stdout))


def _read_osv_failure(returncode: int, stdout: str, ignored: Collection[str]) -> AuditVerdict:
    """An `osv-scanner` run exits 1 on finding vulnerabilities, and another code when it could not
    run. A finding passes when `ignored` covers each of its advisories."""
    if returncode == 1:
        advisories = osv_advisory_ids(stdout)
        if advisories and advisories <= set(ignored):
            return AuditVerdict.CLEAN
        return AuditVerdict.VULNERABLE
    return AuditVerdict.NOT_RUN


_FAILURE_READERS: Final[Mapping[str, Callable[[int, str, Collection[str]], AuditVerdict]]] = {
    BIN_UV: _read_uv_failure,
    BIN_NPM: _read_npm_failure,
    BIN_OSV_SCANNER: _read_osv_failure,
}


def audit_verdict(
    cmd: Sequence[str], returncode: int, stdout: str, *, ignored: Collection[str] = frozenset()
) -> AuditVerdict:
    """The verdict of one audit command that exited `returncode` and printed `stdout`, read by the
    kind of command it is, the program it starts. Every audit exits 0 when it is clean. `ignored`
    holds the advisory IDs that an entry of the ignore file covers for this command."""
    if returncode == CONST_EXIT_SUCCESS:
        return AuditVerdict.CLEAN
    return _FAILURE_READERS[cmd[0]](returncode, stdout, ignored)
