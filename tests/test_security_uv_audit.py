"""The uv audit adapter audits the lockfile of the project as it is, and reads each vulnerability and
each adverse project status of its JSON report as a finding (#2106).

The report has the layout of `crates/uv-audit-operations/src/json.rs` of uv: a `vulnerabilities`
list, each with its `dependency`, ids, summary, link and fix versions, and an `adverse_statuses`
list, each with a project name, its status and a reason. uv gives neither a severity.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli.ai.review_schema import DefectClass
from devops_cli.security.base import ScanOutcome
from devops_cli.security.uv_audit import run_uv_audit_scan
from tests.support.builders import make_finding
from tests.support.fakes.scanners import ScannerFake, ScannerRun
from tests.support.fakes.tool_executor import ToolAnswer

# The command the adapter starts: the lockfile as it is, no preview warning on stderr, a JSON report.
_UV_AUDIT = ["uv", "audit", "--frozen", "--quiet", "--output-format", "json"]

# The start of the reason of a scan whose report does not have the layout of a project report.
_INVALID_REPORT = "Scanner execution failed: 2 validation errors for _Report"

_REPORT = {
    "schema": {"version": "preview"},
    "summary": {"audited_packages": 3, "vulnerabilities": 2, "adverse_statuses": 2},
    "vulnerabilities": [
        {
            "dependency": {"name": "urllib3", "version": "1.26.5"},
            "id": "GHSA-34jh-p97f-mpxf",
            "display_id": "GHSA-34jh-p97f-mpxf",
            "aliases": ["CVE-2024-37891"],
            "summary": "Proxy-Authorization request header is not stripped during cross-origin redirects",
            "description": "urllib3 keeps the header when it follows a redirect to another origin.",
            "link": "https://example.com/advisories/GHSA-34jh-p97f-mpxf",
            "fix_versions": ["1.26.19", "2.2.2"],
            "published": "2024-06-17T19:09:05Z",
            "modified": "2026-09-10T03:49:48Z",
        },
        {
            "dependency": {"name": "idna", "version": "3.6"},
            "id": "PYSEC-2024-60",
            "display_id": "PYSEC-2024-60",
            "aliases": ["CVE-2024-3651"],
            "summary": None,
            "description": None,
            "link": None,
            "fix_versions": [],
            "published": None,
            "modified": None,
        },
    ],
    "adverse_statuses": [
        {"name": "legacy-lib", "status": "archived", "reason": "The project moved to new-lib."},
        {"name": "suspect-lib", "status": "quarantined", "reason": None},
    ],
}


def test_uv_audit_audits_the_lockfile_as_it_is_and_reads_each_finding_of_its_report(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """The adapter starts uv audit in the project directory, and gives a finding for each
    vulnerability and each adverse status, at the default severity, since uv gives none."""
    project = tmp_path.resolve()
    scanner_fake.script("uv", ToolAnswer(exit_code=1, stdout=json.dumps(_REPORT)))

    outcome = run_uv_audit_scan(project)

    supply_chain = DefectClass.SUPPLY_CHAIN.value
    assert (scanner_fake.runs, outcome) == (
        [ScannerRun(_UV_AUDIT, str(project))],
        ScanOutcome(
            "ran",
            [
                make_finding(
                    severity="MEDIUM",
                    location="uv.lock:urllib3",
                    title="[GHSA-34jh-p97f-mpxf] Proxy-Authorization request header is not "
                    "stripped during cross-origin redirects",
                    description="urllib3 keeps the header when it follows a redirect to another "
                    "origin.",
                    fix="Upgrade urllib3 from 1.26.5 to 1.26.19 or 2.2.2",
                    references=["https://example.com/advisories/GHSA-34jh-p97f-mpxf"],
                    category=supply_chain,
                ),
                make_finding(
                    severity="MEDIUM",
                    location="uv.lock:idna",
                    title="[PYSEC-2024-60] idna 3.6 has a known vulnerability",
                    description="",
                    fix="No known release of idna fixes PYSEC-2024-60. Replace or remove idna.",
                    category=supply_chain,
                ),
                make_finding(
                    severity="MEDIUM",
                    location="uv.lock:legacy-lib",
                    title="[archived] legacy-lib is archived on its index",
                    description="The project moved to new-lib.",
                    fix="Replace legacy-lib with a maintained project.",
                    category=supply_chain,
                ),
                make_finding(
                    severity="MEDIUM",
                    location="uv.lock:suspect-lib",
                    title="[quarantined] suspect-lib is quarantined on its index",
                    description="",
                    fix="Replace suspect-lib with a maintained project.",
                    category=supply_chain,
                ),
            ],
        ),
    )


def test_uv_audit_that_finds_nothing_is_a_clean_scan(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """uv exits 0 with a report of no vulnerability and no adverse status."""
    clean = {**_REPORT, "vulnerabilities": [], "adverse_statuses": []}
    scanner_fake.script("uv", ToolAnswer(stdout=json.dumps(clean)))

    assert run_uv_audit_scan(tmp_path) == ScanOutcome("ran", [])


@pytest.mark.parametrize(
    "target", [Path("services", "api-typo"), Path("uv.lock")], ids=["missing", "file"]
)
def test_uv_audit_of_a_path_that_is_not_a_directory_gives_no_result(
    target: Path, scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """uv finds the project from the directory that it starts in and from each parent directory. A
    scan of a path that is not a directory, such as a directory that does not exist, does not start
    uv, so it does not audit the project of a parent directory as the project of that path."""
    project = tmp_path.resolve()
    (project / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    scanner_fake.script("uv", ToolAnswer(stdout=json.dumps(_REPORT)))
    path = project / target

    assert (run_uv_audit_scan(path), scanner_fake.runs) == (
        ScanOutcome(
            "not_applicable",
            [],
            f"{path} is not a directory. uv audit audits the project of a directory.",
        ),
        [],
    )


def test_uv_audit_with_no_lockfile_is_a_failed_scan_that_names_the_cause(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """uv audits only a lockfile that exists: with none, it exits 1 with no report, and the scan
    fails with what uv wrote on stderr, not as a scan that found vulnerabilities."""
    missing = (
        "error: Unable to find lockfile at `uv.lock`, but `--frozen` was provided. To create a "
        "lockfile, run `uv lock` or `uv sync` without the flag."
    )
    scanner_fake.script("uv", ToolAnswer(exit_code=1, stderr=f"{missing}\n"))

    assert run_uv_audit_scan(tmp_path) == ScanOutcome(
        "failed", [], f"Scanner exited with code 1: {missing}"
    )


def test_a_uv_audit_report_of_another_layout_is_a_failed_scan_and_not_a_clean_one(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """uv writes both lists in each project report. A report with neither, such as the layout
    that uv writes for each tool, fails the scan, so a change of the preview layout of uv does not
    read as a scan that found nothing."""
    other_layout = {"schema": {"version": "preview"}, "tools": []}
    scanner_fake.script("uv", ToolAnswer(stdout=json.dumps(other_layout)))

    outcome = run_uv_audit_scan(tmp_path)

    assert (outcome.status, outcome.findings, outcome.reason.startswith(_INVALID_REPORT)) == (
        "failed",
        [],
        True,
    )
