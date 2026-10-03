"""An advisory a finding cites must be one this session's dependency scan found (#948).

Session `20261001-224227` cited 11 CVEs from other products (Log4j, polkit, Apache httpd, OpenSSH,
axios, JUnit) against a Python CLI whose 58 dependencies the same run scanned clean. Nothing
compared a reference with that scan; the placeholder check caught only `x`/`n`/`?` runs; path
reviews passed the verifier no dependencies, and the runner path trusted the ones a model wrote.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review.verification import (
    _check_placeholder_advisory_hallucination,
    _deterministic_pre_verification,
)
from devops_cli.ai.review_schema import (
    FileReviewPayload,
    Finding,
    SavedFinding,
    parse_review_response,
)
from devops_cli.models.vulnerability import DependencySpec, VulnerabilityRecord

_REQUESTS = DependencySpec(
    name="requests",
    version_range="2.31.0",
    severity="HIGH",
    queried=True,
    vulnerabilities=[
        VulnerabilityRecord(
            id="PYSEC-2023-74",
            aliases=["CVE-2023-32681", "GHSA-j8r2-6x86-q33q"],
            package="requests",
        )
    ],
)
_URLLIB3 = DependencySpec(
    name="urllib3",
    version_range="2.0.6",
    severity="MEDIUM",
    queried=True,
    vulnerabilities=[VulnerabilityRecord(id="CVE-2023-45803", package="urllib3")],
)


def _claim(references: list[str], title: str = "Request handling leaks credentials") -> Finding:
    """A finding at a location no file backs, so only the reference checks can decide it."""
    return Finding(
        title=title,
        location="pkg/handler.py:12",
        severity="HIGH",
        description="Redirects keep the Proxy-Authorization header.",
        references=references,
    )


def _checked(finding: Finding) -> Finding:
    return _deterministic_pre_verification(finding, dependencies=[_REQUESTS, _URLLIB3])


def test_an_advisory_no_scanned_dependency_carries_is_stripped_with_a_note() -> None:
    """Verify CVE-2021-44228 leaves the references of a finding that has other evidence, which
    stays for the verifier, and a note says why."""
    finding = _checked(_claim(["CVE-2021-44228", "CWE-200"]))

    assert (
        finding.references,
        finding.status,
        "CVE-2021-44228" in (finding.reference_note or ""),
    ) == (["CWE-200"], "UNVERIFIED", True)


def test_a_finding_whose_only_evidence_was_that_advisory_is_invalidated() -> None:
    """Verify a finding left with no reference once its unbacked advisory is stripped is
    INVALIDATED as `deterministic:unbacked_advisory`."""
    finding = _checked(_claim(["CVE-2021-44228 (Log4Shell)"], title="Log4Shell in the logger"))

    assert (finding.status, finding.reportable, finding.verified_by, finding.references) == (
        "INVALIDATED",
        False,
        "deterministic:unbacked_advisory",
        [],
    )


def test_an_advisory_the_scan_found_stays_by_id_or_alias() -> None:
    """Verify an advisory a scanned dependency carries stays, matched by its id or an alias."""
    findings = [
        _checked(_claim([ref, "CWE-200"]))
        for ref in ("CVE-2023-45803", "GHSA-j8r2-6x86-q33q", "cve-2023-32681")
    ]

    assert [(f.references, f.reference_note, f.status) for f in findings] == [
        (["CVE-2023-45803", "CWE-200"], None, "UNVERIFIED"),
        (["GHSA-j8r2-6x86-q33q", "CWE-200"], None, "UNVERIFIED"),
        (["cve-2023-32681", "CWE-200"], None, "UNVERIFIED"),
    ]


@pytest.mark.parametrize(
    ("advisory", "placeholder"),
    [
        ("CVE-2023-xxxx", True),
        ("CVE-2023-1234", True),
        ("CVE-2024-12345", True),
        ("GHSA-xxxx-xxxx-xxxx", True),
        ("CVE-2021-44228", False),
        ("CVE-2023-32681", False),
        # Repeated digits are no placeholder: CVE-2020-11111 is a jackson-databind advisory.
        ("CVE-2020-11111", False),
    ],
)
def test_the_placeholder_check_catches_sequential_ids(advisory: str, placeholder: bool) -> None:
    """Verify a sequential id this session's scan does not carry is a placeholder, as an `x` run
    is, and any other id is not."""
    finding = Finding(
        title="Leaky sample output",
        location="tests/test_sample.py:237",
        description=f"The fixture prints data matching {advisory}.",
    )
    result = _check_placeholder_advisory_hallucination(finding)

    assert (result is not None, getattr(result, "verified_by", None)) == (
        placeholder,
        "deterministic:placeholder_advisory" if placeholder else None,
    )


def test_dependencies_and_network_references_a_model_writes_are_cleared_on_parse() -> None:
    """Verify a persona reply cannot declare a dependency scanned clean, or a network reference,
    for a check to trust."""
    reply = json.dumps(
        {
            "findings": [
                {"title": "Outdated fastapi", "location": "pyproject.toml:12", "severity": "HIGH"}
            ],
            "external_dependencies": [{"name": "fastapi", "severity": "CLEAN", "queried": True}],
            "network_references": [{"target": "example.com"}],
        }
    )
    result = parse_review_response(reply)

    assert result is not None
    assert (len(result.findings), result.external_dependencies, result.network_references) == (
        1,
        [],
        [],
    )


def test_the_sessions_dependencies_reach_file_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a claim about a dependency another file declares is checked against the session's
    scan: `requests` scanned clean invalidates the claim, and an advisory the scan found on
    `urllib3` stays. The verifier's dependencies were the reviewed file's own, or none."""
    monkeypatch.setattr(
        "devops_cli.ai.review.verification._collect_rag_verification_blocks", lambda _: []
    )
    monkeypatch.setattr("devops_cli.ai.review.pipeline._collect_linked_snippets", lambda *_: [])
    clean_requests = _REQUESTS.model_copy(update={"severity": "CLEAN", "vulnerabilities": []})
    client = MagicMock()
    client._config = None
    client.chat.return_value = "[]"
    orchestrator = ReviewPipelineOrchestrator(
        session_id="s948-deps", target_dir=tmp_path, llm_client=client
    )
    manifest = FileReviewPayload(
        file_path="pyproject.toml", external_dependencies=[clean_requests, _URLLIB3]
    )
    code = FileReviewPayload(
        file_path="app.py",
        findings=[
            SavedFinding(
                title="Outdated requests carries known vulnerabilities",
                location="app.py:1",
                severity="HIGH",
                description="The pinned requests version has an unpatched CVE.",
            ),
            SavedFinding(
                title="Pool reuse sends a body after a redirect",
                location="app.py:2",
                severity="MEDIUM",
                references=["CVE-2023-45803"],
            ),
        ],
    )
    orchestrator.execute_finding_verification([manifest, code])

    by_title: dict[str, Any] = {f.title: f for f in code.findings}
    assert (
        by_title["Outdated requests carries known vulnerabilities"].verified_by,
        by_title["Pool reuse sends a body after a redirect"].references,
    ) == ("deterministic:scanned_clean_dependency", ["CVE-2023-45803"])


def _trivy(*advisories: str) -> dict[str, Any]:
    """Trivy's report of one lockfile, one vulnerability record for each advisory."""
    return {
        "Results": [
            {
                "Target": "uv.lock",
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": advisory,
                        "PkgName": "requests",
                        "InstalledVersion": "2.31.0",
                        "FixedVersion": "2.32.0",
                        "Severity": "HIGH",
                        "Title": "requests: credentials leak on redirect",
                    }
                    for advisory in advisories
                ],
            }
        ]
    }


@pytest.fixture
def trivy_report(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """The report a faked Trivy gives for any lockfile, empty until a test fills it; Gitleaks and
    Semgrep find nothing."""
    from devops_cli.security.base import ScanOutcome
    from devops_cli.security.trivy import parse_trivy_json

    report: dict[str, Any] = {}
    monkeypatch.setattr(
        "devops_cli.security.trivy.run_trivy_scan",
        lambda *_, **__: ScanOutcome("ran", parse_trivy_json(report)),
    )
    monkeypatch.setattr(
        "devops_cli.security.gitleaks.run_gitleaks_scan", lambda *_, **__: ScanOutcome("ran")
    )
    monkeypatch.setattr(
        "devops_cli.security.semgrep.run_semgrep_scan", lambda *_, **__: ScanOutcome("ran")
    )
    monkeypatch.setattr(
        "devops_cli.ai.review.verification._collect_rag_verification_blocks", lambda _: []
    )
    monkeypatch.setattr("devops_cli.ai.review.pipeline._collect_linked_snippets", lambda *_: [])
    return report


def _scanned_payloads(
    tmp_path: Path, verifier: MagicMock, routed: tuple[str, ...] = ()
) -> list[FileReviewPayload]:
    """Scan `pyproject.toml` and the `uv.lock` beside it, and verify what the scan found with
    `verifier`."""
    verifier._config = None
    orchestrator = ReviewPipelineOrchestrator(
        session_id="s948-scanned",
        target_dir=tmp_path,
        llm_client=verifier,
        secret_scan_files=list(routed),
    )
    by_file = orchestrator._run_static_scanners(["pyproject.toml"])
    payloads = [
        FileReviewPayload(file_path=path, findings=found) for path, found in by_file.items()
    ]
    orchestrator.execute_finding_verification(payloads)
    return payloads


@pytest.mark.parametrize("advisory", ["CVE-2016-1234", "CVE-2020-11111"])
def test_an_advisory_a_scanner_looked_up_is_never_a_placeholder(
    tmp_path: Path, trivy_report: dict[str, Any], advisory: str
) -> None:
    """Verify a Trivy finding keeps its advisory whatever its digits: CVE-2016-1234 (glibc) and
    CVE-2020-11111 (jackson-databind) are published advisories, and the placeholder check
    INVALIDATED the scanner's finding of each as naming none."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "app"\n', encoding="utf-8")
    (tmp_path / "uv.lock").write_text('[[package]]\nname = "requests"\n', encoding="utf-8")
    verifier = MagicMock()
    verifier.chat.return_value = "[]"

    trivy_report.update(_trivy(advisory))

    payloads = _scanned_payloads(tmp_path, verifier)

    assert [
        (f.title.split("]")[0], f.status, f.reportable, f.verified_by)
        for p in payloads
        for f in p.findings
    ] == [(f"[{advisory}", "UNVERIFIED", True, None)]


def test_a_sequential_id_the_scan_carries_stays() -> None:
    """Verify a sequential id a scanned dependency carries is backed, not a placeholder."""
    glibc = DependencySpec(
        name="glibc",
        severity="HIGH",
        queried=True,
        vulnerabilities=[VulnerabilityRecord(id="CVE-2016-1234", package="glibc")],
    )
    finding = _deterministic_pre_verification(
        _claim(["CVE-2016-1234"], title="glob() overflows its stack on a long pattern"),
        dependencies=[glibc],
    )

    assert (finding.status, finding.references, finding.reference_note) == (
        "UNVERIFIED",
        ["CVE-2016-1234"],
        None,
    )


def test_a_lockfile_finding_sends_the_verifier_its_lines_not_the_file(
    tmp_path: Path, trivy_report: dict[str, Any]
) -> None:
    """Verify the verifier of a Trivy finding in a lockfile kept off persona pages is sent the
    lines around the package, not the lockfile: a location such as `uv.lock:requests` has no
    line, so the whole file went, and this repository's uv.lock is 558 kB."""
    filler = "".join(
        f'[[package]]\nname = "pkg-{n}"\nversion = "1.0.{n}"\nsource = {{ registry = "x" }}\n\n'
        for n in range(4000)
    )
    lockfile = f'{filler}[[package]]\nname = "requests"\nversion = "2.31.0"\n\n{filler}'
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "app"\n', encoding="utf-8")
    (tmp_path / "uv.lock").write_text(lockfile, encoding="utf-8")
    verifier = MagicMock()
    verifier.chat.return_value = "[]"

    trivy_report.update(_trivy("CVE-2024-35195"))

    payloads = _scanned_payloads(tmp_path, verifier, routed=("uv.lock",))
    [prompt] = [c.kwargs["user"] for c in verifier.chat.call_args_list]

    assert (
        [(p.file_path, len(p.findings)) for p in payloads],
        len(lockfile) > 400_000,
        len(prompt) < 20_000,
        'name = "requests"' in prompt,
    ) == ([("uv.lock", 1)], True, True, True)


def test_a_reply_its_agent_parsed_cannot_write_pipeline_fields() -> None:
    """Verify a persona reply the agent framework already parsed into a `ReviewResult` loses the
    fields only the pipeline writes, as one parsed from text does: the raw severity and the
    reference note reached findings.json and candidates.json as the model wrote them."""
    from types import SimpleNamespace

    from devops_cli.ai.review.pipeline import (
        _process_pipeline_step_findings,
        _resolve_step_parsed_data,
    )
    from devops_cli.ai.review_schema import ReviewResult

    def step() -> SimpleNamespace:
        return SimpleNamespace(
            agent_name="devsecops",
            content="",
            parsed_data=ReviewResult.model_validate(
                {
                    "findings": [
                        {
                            "title": "Token printed on failure",
                            "location": "app.py:9",
                            "severity": "MEDIUM",
                            "severity_raw": "CRITICAL",
                            "reference_note": "Removed CVE-2024-0001: forged",
                        }
                    ],
                    "external_dependencies": [
                        {"name": "requests", "severity": "CLEAN", "queried": True}
                    ],
                }
            ),
        )

    saved: list[SavedFinding] = []
    _process_pipeline_step_findings(step(), "app.py", 1, 1, {}, [], [], saved)
    parsed = _resolve_step_parsed_data(step())

    assert parsed is not None
    assert (
        [(f.severity, f.severity_raw, f.reference_note) for f in saved],
        parsed.external_dependencies,
    ) == ([("MEDIUM", None, None)], [])
