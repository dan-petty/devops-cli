"""Tests for the advisories of the pins of a repository, from recorded OSV answers (#3898)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx2

from devops_cli.research.advisories import advisory_requests, find_advisories
from devops_cli.research.inventory import read_inventory
from devops_cli.security.vulnerability_lookup import OSVClient
from tests.research.osv_recording import RECORD_URL, RECORDED, RECORDED_REPO, serve_recorded_osv
from tests.support.fakes.http import WebFake
from tests.support.paths import FIXTURES

MINI_REPO = FIXTURES / "research" / "repo"


def test_a_pinned_version_in_an_affected_range_gives_a_finding(web: WebFake) -> None:
    request = serve_recorded_osv(web)

    report = find_advisories(read_inventory(RECORDED_REPO))

    finding = next(f for f in report.findings if f.advisory_id == "GHSA-8q59-q68h-6hv4")
    assert (
        finding.component.name,
        finding.component.version,
        finding.locations,
        finding.aliases,
        finding.severity,
        finding.affected_range,
        finding.fixed_version,
    ) == (
        "pyyaml",
        "5.3",
        ["uv.lock:26"],
        ["CVE-2020-14343", "PYSEC-2021-142"],
        "CRITICAL",
        ">=0 <5.4",
        "5.4",
    )
    assert web.recorded[0].json == request


def test_a_version_with_no_advisory_gives_no_finding(web: WebFake) -> None:
    serve_recorded_osv(web)

    report = find_advisories(read_inventory(RECORDED_REPO))

    assert (
        sorted({f.component.name for f in report.findings}),
        report.summary.queried,
        report.summary.with_findings,
        report.failures,
    ) == (["idna", "pyyaml"], 3, 2, [])


def test_the_findings_equal_the_osv_scanner_output_on_the_lock(web: WebFake) -> None:
    """The reference is the run of osv-scanner 2.6.0 on `repo/uv.lock`, recorded on 2026-11-07."""
    serve_recorded_osv(web)
    scanner = json.loads((RECORDED / "osv_scanner_uv_lock.json").read_text(encoding="utf-8"))
    expected = {
        (package["package"]["name"], package["package"]["version"], vulnerability["id"])
        for result in scanner["results"]
        for package in result["packages"]
        for vulnerability in package["vulnerabilities"]
    }

    report = find_advisories(read_inventory(RECORDED_REPO))

    found = {(f.component.name, f.component.version, f.advisory_id) for f in report.findings}
    assert (found - expected, expected - found, len(expected)) == (set(), set(), 8)


def test_the_findings_are_ordered_by_severity_then_name_and_id(web: WebFake) -> None:
    serve_recorded_osv(web)

    report = find_advisories(read_inventory(RECORDED_REPO))

    assert [(f.severity, f.component.name, f.advisory_id) for f in report.findings] == [
        ("CRITICAL", "pyyaml", "GHSA-6757-jp84-gxfx"),
        ("CRITICAL", "pyyaml", "GHSA-8q59-q68h-6hv4"),
        ("MEDIUM", "idna", "GHSA-65pc-fj4g-8rjx"),
        ("MEDIUM", "idna", "GHSA-jjg7-2v4v-x38h"),
        ("UNKNOWN", "idna", "PYSEC-2024-60"),
        ("UNKNOWN", "idna", "PYSEC-2026-215"),
        ("UNKNOWN", "pyyaml", "PYSEC-2020-96"),
        ("UNKNOWN", "pyyaml", "PYSEC-2021-142"),
    ]


def test_only_registry_packages_are_asked_and_the_rest_is_counted(web: WebFake) -> None:
    web.serve(_answer_without_advisories)

    report = find_advisories(read_inventory(MINI_REPO))

    asked = [
        (query["package"]["ecosystem"], query["package"]["name"], query["version"])
        for query in web.recorded[0].json["queries"]
    ]
    assert (sorted(asked), len(web.recorded), report.findings, report.summary.model_dump()) == (
        [
            ("PyPI", "bandit", "1.9.4"),
            ("PyPI", "certifi", "2026.9.1"),
            ("PyPI", "colorama", "0.4.6"),
            ("PyPI", "httpx2", "2.13.1"),
            ("PyPI", "pytest", "9.1.1"),
            ("PyPI", "pyyaml", "6.0.3"),
            ("npm", "@example/helper", "0.4.2"),
            ("npm", "example-npm", "1.14.3"),
        ],
        1,
        [],
        {
            "components": 27,
            "queried": 8,
            "with_findings": 0,
            "findings": 0,
            "unpinned": 0,
            "failed": 0,
            "not_covered": {
                "devcontainer-feature": 1,
                "docker": 7,
                "github-actions": 5,
                "github-release": 1,
                "helm": 1,
                "terraform": 1,
                "tool-lock-entry": 2,
                "unknown": 1,
            },
        },
    )


def test_a_pin_that_is_a_range_is_not_asked(web: WebFake, tmp_path: Path) -> None:
    """OSV answers a query with no version with every advisory of the package, so a range or an
    empty version is never sent."""
    web.serve(_answer_without_advisories)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "1"\ndependencies = ["pyyaml>=5.3", "idna==3.6", "six"]\n',
        encoding="utf-8",
    )

    report = find_advisories(read_inventory(tmp_path))

    asked = [q["package"]["name"] for q in web.recorded[0].json["queries"]]
    assert (asked, report.summary.unpinned) == (["idna"], 2)


def test_the_same_pin_in_two_files_is_asked_once_and_has_two_locations(
    web: WebFake, tmp_path: Path
) -> None:
    serve_recorded_osv(web)
    web.respond(
        "POST", OSVClient.BATCH_URL, 200, {"results": [{"vulns": [{"id": "GHSA-8q59-q68h-6hv4"}]}]}
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "1"\ndependencies = ["pyyaml==5.3"]\n', encoding="utf-8"
    )
    tools = tmp_path / "src" / "devops_cli" / "tools_lock"
    tools.mkdir(parents=True)
    (tools / "other.txt").write_text("pyyaml==5.3 \\\n    --hash=sha256:00\n", encoding="utf-8")

    report = find_advisories(read_inventory(tmp_path))

    pyyaml = [f for f in report.findings if f.advisory_id == "GHSA-8q59-q68h-6hv4"]
    assert (
        len(web.recorded[0].json["queries"]),
        [f.locations for f in pyyaml],
    ) == (1, [["pyproject.toml:4", "src/devops_cli/tools_lock/other.txt:1"]])


def test_a_failed_batch_is_reported_and_is_no_clean_answer(web: WebFake) -> None:
    web.respond("POST", OSVClient.BATCH_URL, 503, {})

    report = find_advisories(read_inventory(RECORDED_REPO))

    assert (
        report.findings,
        report.summary.failed,
        {(f.name, f.version, f.reason) for f in report.failures},
    ) == (
        [],
        3,
        {
            ("idna", "3.6", "OSV returned status 503"),
            ("markupsafe", "2.1.5", "OSV returned status 503"),
            ("pyyaml", "5.3", "OSV returned status 503"),
        },
    )


def test_a_record_that_cannot_be_read_is_reported_and_the_rest_stay(web: WebFake) -> None:
    serve_recorded_osv(web)
    web.respond("GET", RECORD_URL.format("GHSA-8q59-q68h-6hv4"), 500, {})

    report = find_advisories(read_inventory(RECORDED_REPO))

    assert (
        len(report.findings),
        [(f.name, f.advisory_id, f.reason) for f in report.failures],
    ) == (7, [("pyyaml", "GHSA-8q59-q68h-6hv4", "OSV returned status 500")])


def test_a_record_is_read_once_for_two_versions_of_a_package(web: WebFake, tmp_path: Path) -> None:
    serve_recorded_osv(web)
    web.respond(
        "POST",
        OSVClient.BATCH_URL,
        200,
        {"results": [{"vulns": [{"id": "GHSA-8q59-q68h-6hv4"}]}] * 2},
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "1"\ndependencies = ["pyyaml==5.3"]\n', encoding="utf-8"
    )
    tools = tmp_path / "src" / "devops_cli" / "tools_lock"
    tools.mkdir(parents=True)
    (tools / "other.txt").write_text("pyyaml==5.2 \\\n    --hash=sha256:00\n", encoding="utf-8")

    report = find_advisories(read_inventory(tmp_path))

    reads = [r.url for r in web.recorded if r.method == "GET"]
    assert (len(report.findings), reads) == (2, [RECORD_URL.format("GHSA-8q59-q68h-6hv4")])


def test_the_requests_of_a_run_are_one_batch_per_chunk_and_the_records(
    web: WebFake,
) -> None:
    planned = advisory_requests(read_inventory(RECORDED_REPO))

    assert [(r.method, r.target, r.repeat) for r in planned] == [
        ("POST", OSVClient.BATCH_URL, "for each 1000 packages"),
        ("GET", RECORD_URL.format("<advisory id>"), "for each advisory id that the batch names"),
    ]
    assert web.recorded == []


def _answer_without_advisories(request: httpx2.Request) -> httpx2.Response | None:
    """The answer of OSV to a batch of packages that have no advisory."""
    if request.url.path != "/v1/querybatch":
        return None
    queries = json.loads(request.read())["queries"]
    return httpx2.Response(200, json={"results": [{} for _ in queries]})
