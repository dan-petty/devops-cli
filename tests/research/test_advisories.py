"""Tests for the advisories of the pins of a repository, from recorded answers of OSV, GitHub and
CISA KEV (#3898, #3987)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx2
import pytest

from devops_cli.research.advisories import advisory_requests, find_advisories
from devops_cli.research.github_advisories import GitHubAdvisoryClient
from devops_cli.research.inventory import read_inventory, summarize
from devops_cli.research.kev import KevClient
from devops_cli.research.models import (
    AdvisoryFinding,
    Component,
    ComponentKind,
    Ecosystem,
    Inventory,
)
from devops_cli.research.watch import WatchEntry, WatchList, read_watch_list
from devops_cli.security.vulnerability_lookup import OSVClient
from tests.research.github_recording import (
    GITHUB_REPO,
    QDRANT_URL,
    recorded,
    serve_recorded_github,
    serve_recorded_kev,
)
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
    serve_recorded_github(web)

    report = find_advisories(read_inventory(MINI_REPO))

    asked = [
        (query["package"]["ecosystem"], query["package"]["name"], query["version"])
        for query in web.recorded[0].json["queries"]
    ]
    hosts = [request.url.split("/")[2] for request in web.recorded]
    assert (sorted(asked), hosts, report.findings, report.summary.model_dump()) == (
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
        ["api.osv.dev", "api.github.com"],
        [],
        {
            "components": 27,
            "queried": 11,
            "with_findings": 0,
            "findings": 0,
            "unpinned": 2,
            "failed": 0,
            "exploited": 0,
            "not_covered": {
                "devcontainer-feature": 1,
                "docker": 7,
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
    assert (len(report.findings), reads) == (
        2,
        [RECORD_URL.format("GHSA-8q59-q68h-6hv4"), KevClient.URL],
    )


def test_the_requests_of_a_run_are_one_batch_per_chunk_the_records_and_the_kev_list(
    web: WebFake,
) -> None:
    planned = advisory_requests(read_inventory(RECORDED_REPO))

    assert [(r.method, r.target, r.repeat, r.condition) for r in planned] == [
        ("POST", OSVClient.BATCH_URL, "for each 1000 packages", ""),
        (
            "GET",
            RECORD_URL.format("<advisory id>"),
            "for each advisory id that the batch names",
            "",
        ),
        ("GET", KevClient.URL, "", "when a finding names a CVE"),
    ]
    assert web.recorded == []


def _answer_without_advisories(request: httpx2.Request) -> httpx2.Response | None:
    """The answer of OSV to a batch of packages that have no advisory."""
    if request.url.path != "/v1/querybatch":
        return None
    queries = json.loads(request.read())["queries"]
    return httpx2.Response(200, json={"results": [{} for _ in queries]})


def _github_report(
    web: WebFake, *, kev: bool = True
) -> tuple[list[AdvisoryFinding], dict[str, object]]:
    serve_recorded_github(web)
    if kev:
        serve_recorded_kev(web)
    report = find_advisories(
        read_inventory(GITHUB_REPO),
        watch=read_watch_list(GITHUB_REPO),
        github=GitHubAdvisoryClient(),
    )
    return report.findings, report.model_dump()


def test_a_github_advisory_of_an_action_gives_a_finding_where_osv_gives_none(
    web: WebFake,
) -> None:
    findings, report = _github_report(web)

    action = [f for f in findings if f.component.name == "tj-actions/changed-files"]
    assert [
        (f.component.version, f.advisory_id, f.aliases, f.severity, f.source) for f in action
    ] == [("v45.0.0", "GHSA-mrrh-fwg8-r2c3", ["CVE-2025-30066"], "HIGH", "GitHub")]
    assert (action[0].affected_range, action[0].fixed_version, action[0].locations) == (
        "<= 45.0.7",
        "46.0.1",
        [".github/workflows/ci.yml:8"],
    )
    assert report["summary"] == {
        "components": 4,
        "queried": 3,
        "with_findings": 2,
        "findings": 3,
        "unpinned": 1,
        "failed": 0,
        "exploited": 1,
        "not_covered": {},
    }
    assert not [r for r in web.recorded if "osv.dev" in r.url]


def test_a_cve_in_the_kev_list_sets_the_exploited_flag(web: WebFake) -> None:
    findings, _ = _github_report(web)

    assert {f.advisory_id: f.exploited for f in findings} == {
        "GHSA-mrrh-fwg8-r2c3": True,
        "GHSA-frc7-44gm-99qq": False,
        "GHSA-3gph-6c29-p29v": False,
    }


@pytest.mark.parametrize(
    ("advisory_id", "severity", "affected", "fixed"),
    [
        ("GHSA-3gph-6c29-p29v", "HIGH", ">= 1.18.0, < 1.19.2", "1.19.2"),
        ("GHSA-frc7-44gm-99qq", "CRITICAL", "< 1.20.0", "1.20.0"),
    ],
)
def test_the_qdrant_server_advisories_that_osv_misses_are_findings(
    web: WebFake, advisory_id: str, severity: str, affected: str, fixed: str
) -> None:
    """OSV has neither advisory, and `GET /advisories` answers 404 for both (2026-11-07): the
    repository published them, so the chart 1.19.1 is matched to the ranges of the repository."""
    findings, _ = _github_report(web)

    [finding] = [f for f in findings if f.advisory_id == advisory_id]
    assert (
        finding.component.name,
        finding.component.version,
        finding.severity,
        finding.affected_range,
        finding.fixed_version,
        finding.source,
    ) == ("qdrant", "1.19.1", severity, affected, fixed, "GitHub")


def test_a_release_after_the_fix_and_a_package_of_another_ecosystem_give_no_finding(
    web: WebFake,
) -> None:
    findings, _ = _github_report(web)

    assert not [f for f in findings if f.component.version == "v46.0.1"]
    assert "GHSA-f632-vm87-2m2f" not in {f.advisory_id for f in findings}


def test_the_kev_list_is_not_read_when_no_finding_names_a_cve(web: WebFake) -> None:
    serve_recorded_github(web)
    inventory = read_inventory(GITHUB_REPO)
    only_chart = inventory.model_copy(
        update={"components": [c for c in inventory.components if c.kind.value == "chart"]}
    )

    report = find_advisories(
        only_chart, watch=read_watch_list(GITHUB_REPO), github=GitHubAdvisoryClient()
    )

    assert (len(report.findings), KevClient.URL in web.requested, report.kev_failure) == (
        2,
        False,
        "",
    )


def test_a_kev_list_that_cannot_be_read_is_reported_and_flags_nothing(web: WebFake) -> None:
    web.respond("GET", KevClient.URL, 503, {})

    findings, report = _github_report(web, kev=False)

    assert (len(findings), [f.exploited for f in findings], report["kev_failure"]) == (
        3,
        [False] * 3,
        "CISA KEV returned status 503",
    )


def test_a_github_read_that_fails_is_reported_for_its_component_and_is_not_clean(
    web: WebFake,
) -> None:
    serve_recorded_kev(web)
    web.respond("GET", QDRANT_URL + "?per_page=100", 500, {})
    web.serve(lambda request: httpx2.Response(503) if request.url.path == "/advisories" else None)

    report = find_advisories(
        read_inventory(GITHUB_REPO),
        watch=read_watch_list(GITHUB_REPO),
        github=GitHubAdvisoryClient(),
    )

    assert (
        report.findings,
        sorted((f.name, f.version, f.reason) for f in report.failures),
    ) == (
        [],
        [
            ("qdrant", "1.19.1", "GitHub returned status 500"),
            ("tj-actions/changed-files", "v45.0.0", "GitHub returned status 503"),
            ("tj-actions/changed-files", "v46.0.1", "GitHub returned status 503"),
        ],
    )


def test_an_advisory_with_a_range_that_cannot_be_read_is_a_failure_that_names_it(
    web: WebFake,
) -> None:
    broken = recorded("qdrant_security_advisories.json")[:1]
    broken[0]["vulnerabilities"][0]["vulnerable_version_range"] = "since the start"
    web.serve(
        lambda request: (
            httpx2.Response(200, json=broken)
            if request.url.path.startswith("/repos/")
            else httpx2.Response(200, json=[])
        )
    )

    report = find_advisories(
        read_inventory(GITHUB_REPO),
        watch=read_watch_list(GITHUB_REPO),
        github=GitHubAdvisoryClient(),
    )

    assert (
        [f.advisory_id for f in report.findings],
        [(f.name, f.advisory_id) for f in report.failures],
    ) == (
        [],
        [("qdrant", "GHSA-frc7-44gm-99qq")],
    )


def test_the_requests_of_a_run_with_actions_and_a_watch_list_name_each_repository() -> None:
    planned = advisory_requests(read_inventory(GITHUB_REPO), read_watch_list(GITHUB_REPO))

    assert [(r.method, r.target, r.repeat) for r in planned] == [
        (
            "GET",
            "https://api.github.com/advisories?ecosystem=actions&affects=<names>",
            "for each 50 action names",
        ),
        ("GET", QDRANT_URL, ""),
        ("GET", KevClient.URL, ""),
    ]


def test_a_component_that_the_watch_list_does_not_map_is_counted_as_not_covered(
    web: WebFake,
) -> None:
    serve_recorded_github(web)
    serve_recorded_kev(web)

    report = find_advisories(read_inventory(GITHUB_REPO), github=GitHubAdvisoryClient())

    assert (report.summary.not_covered, report.summary.queried, len(report.findings)) == (
        {"helm": 1},
        2,
        1,
    )


def test_a_run_sends_requests_to_api_github_com_and_www_cisa_gov_only(web: WebFake) -> None:
    _github_report(web)

    assert {request.url.split("/")[2] for request in web.recorded} == {
        "api.github.com",
        "www.cisa.gov",
    }


@pytest.mark.parametrize(
    ("package", "expected"),
    [("example.com/app/v3", []), (None, ["GHSA-test-0000-0000"])],
    ids=["package-of-the-pin", "any-package"],
)
def test_the_package_of_a_watch_entry_selects_the_vulnerabilities_that_name_it(
    web: WebFake, package: str | None, expected: list[str]
) -> None:
    """A repository lists one vulnerability for each major version of its module: the open range of
    the v2 module is no range of the v3 pin."""
    advisory = {
        "ghsa_id": "GHSA-test-0000-0000",
        "severity": "high",
        "summary": "An advisory of two modules",
        "vulnerabilities": [
            {
                "package": {"ecosystem": "go", "name": "example.com/app/v2"},
                "vulnerable_version_range": ">= 2.7.0",
                "patched_versions": "",
            },
            {
                "package": {"ecosystem": "go", "name": "example.com/app/v3"},
                "vulnerable_version_range": ">= 3.0.0, < 3.5.4",
                "patched_versions": "3.5.4",
            },
        ],
    }
    web.serve(lambda request: httpx2.Response(200, json=[advisory]))
    component = Component(
        kind=ComponentKind.TOOL,
        ecosystem=Ecosystem.GITHUB_RELEASE,
        name="app",
        version="3.5.4",
        file="tools.lock",
        line=1,
    )
    watch = WatchList(
        watch=[
            WatchEntry(
                ecosystem=Ecosystem.GITHUB_RELEASE,
                name="app",
                repo="example/app",
                package=package,
            )
        ]
    )

    report = find_advisories(
        Inventory(components=[component], summary=summarize([component])),
        watch=watch,
        github=GitHubAdvisoryClient(),
    )

    assert [f.advisory_id for f in report.findings] == expected
