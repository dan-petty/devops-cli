"""The sweep files one intake candidate for each actionable finding that no issue carries (#3899).

GitHub, the roadmap store, the model and the collector are faked at their edges. The findings are
built by hand for the rules of the sweep, and `devops research sweep` runs over the recorded
answers of OSV for the command.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import pytest

from devops_cli.config.settings import AIConfig
from devops_cli.exceptions.security import SecurityError
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.research.models import (
    AdvisoryFinding,
    AdvisoryReport,
    AdvisorySummary,
    Component,
    ComponentKind,
    Ecosystem,
    LookupFailure,
    SweepResult,
)
from devops_cli.research.sweep import (
    digest_lines,
    finding_candidate,
    finding_marker,
    is_actionable,
    open_findings,
    record_open_findings,
    run_sweep,
    source_id,
)
from devops_cli.roadmap.intake.intake import Filer
from devops_cli.roadmap.intake.intake_model import GatewayIntakeModel
from devops_cli.telemetry.instruments import RESEARCH_OPEN_FINDINGS
from tests.research.osv_recording import RECORDED_REPO, serve_recorded_osv_on_github
from tests.support.fakes.github import github_json, quota_headers
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.paths import REPO_ROOT

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.otlp import FakeCollector

_REPO = "octo/repo"
_PROPOSAL: dict[str, Any] = {
    "type": "type/bug",
    "type_reason": "a pin has an advisory.",
    "priority": "P2-Medium",
    "priority_reason": "it is not urgent.",
    "value": "Medium",
    "value_reason": "it removes a defect.",
    "effort": "Low",
    "effort_reason": "one line.",
}


def _finding(
    advisory: str = "GHSA-aaaa-bbbb-cccc",
    *,
    severity: str = "HIGH",
    name: str = "pyyaml",
    version: str = "5.3",
    file: str = "pyproject.toml",
) -> AdvisoryFinding:
    component = Component(
        kind=ComponentKind.PYTHON_PACKAGE,
        ecosystem=Ecosystem.PYPI,
        name=name,
        version=version,
        file=file,
        line=7,
    )
    return AdvisoryFinding(
        component=component,
        locations=[f"{file}:7"],
        advisory_id=advisory,
        aliases=["CVE-2026-0001"],
        severity=severity,
        summary="Arbitrary code execution while a file loads.",
        affected_range=">=0 <5.4",
        fixed_version="5.4",
    )


def _report(
    *findings: AdvisoryFinding, failures: list[LookupFailure] | None = None
) -> AdvisoryReport:
    return AdvisoryReport(
        findings=list(findings),
        failures=failures or [],
        summary=AdvisorySummary(
            components=len(findings),
            queried=len(findings),
            with_findings=len(findings),
            findings=len(findings),
            unpinned=0,
            failed=len(failures or []),
            not_covered={},
        ),
    )


def _search_path() -> str:
    query = f'"research-finding" in:body is:issue repo:{_REPO}'
    return f"/search/issues?{urlencode({'q': query, 'per_page': 100, 'page': 1})}"


def _route_search(api: GitHubApiFake, *carried: AdvisoryFinding) -> None:
    """Answer the issue search with one open issue for each finding in `carried`."""
    get_github_rate_limiter().update_quota(
        "search", remaining=30, limit=30, reset_epoch=time.time() + 60.0
    )
    items = [
        {"number": n, "state": "open", "state_reason": None, "body": finding_marker(finding)}
        for n, finding in enumerate(carried, start=40)
    ]
    payload = {"total_count": len(items), "incomplete_results": False, "items": items}
    api.route(
        "GET",
        _search_path(),
        github_json(payload, headers=quota_headers(29, resource="search", limit=30)),
    )


def _roadmap() -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore()
    store.seed_file(
        ".github/labels.yml", (REPO_ROOT / ".github/labels.yml").read_text(encoding="utf-8")
    )
    return store


def _model(model_fake: ModelFake, answer: str | None = None) -> GatewayIntakeModel:
    model_fake.answer(answer if answer is not None else json.dumps(_PROPOSAL))
    return GatewayIntakeModel(AIConfig(), embedder=model_fake)


def _sweep(
    report: AdvisoryReport, store: InMemoryRoadmapStore, model: GatewayIntakeModel, *, confirm: bool
) -> Any:
    return run_sweep(report, repo=_REPO, store=store, model=model, confirm=confirm)


def test_a_new_actionable_finding_files_one_candidate_with_its_marker(
    github_api: GitHubApiFake, model_fake: ModelFake
) -> None:
    finding = _finding()
    _route_search(github_api)
    store = _roadmap()

    swept = _sweep(_report(finding), store, _model(model_fake), confirm=True)

    (issue,) = store.issues()
    (entry,) = swept.entries
    assert (
        issue.title,
        issue.body.rstrip().splitlines()[-1] == finding_marker(finding),
        entry.result,
        entry.issue,
        model_fake.call_count,
    ) == (
        "fix(deps): update pyyaml for GHSA-aaaa-bbbb-cccc",
        True,
        SweepResult.FILED,
        issue.number,
        1,
    )


def test_a_second_sweep_of_a_filed_finding_files_nothing_and_says_so(
    github_api: GitHubApiFake, model_fake: ModelFake
) -> None:
    finding = _finding()
    _route_search(github_api, finding)
    store = _roadmap()

    swept = _sweep(_report(finding), store, _model(model_fake), confirm=True)

    lines = digest_lines(swept)
    assert (
        store.issues(),
        swept.entries[0].result,
        swept.entries[0].issue,
        model_fake.call_count,
    ) == (
        [],
        SweepResult.FILED_BEFORE,
        40,
        0,
    )
    assert "filed before in #40" in lines[0]


def test_a_non_actionable_finding_gives_a_digest_line_and_no_intake_call(
    model_fake: ModelFake,
) -> None:
    low = _finding("GHSA-low", severity="LOW")
    store = _roadmap()

    swept = _sweep(_report(low), store, _model(model_fake), confirm=True)

    lines = digest_lines(swept)
    assert (store.issues(), model_fake.call_count, is_actionable(low), len(lines)) == (
        [],
        0,
        False,
        2,
    )
    assert "LOW pyyaml 5.3 GHSA-low: not actionable" in lines[0]


def test_a_plan_decides_the_candidate_and_writes_nothing(
    github_api: GitHubApiFake, model_fake: ModelFake
) -> None:
    _route_search(github_api)
    store = _roadmap()

    swept = _sweep(_report(_finding()), store, _model(model_fake), confirm=False)

    assert (store.issues(), swept.entries[0].result, swept.entries[0].issue) == (
        [],
        SweepResult.PLANNED,
        None,
    )


def test_a_candidate_that_intake_skips_stays_in_the_digest(
    github_api: GitHubApiFake, model_fake: ModelFake
) -> None:
    """The sweep never drops a candidate: when intake skips it, the digest says so."""
    _route_search(github_api)
    store = _roadmap()

    swept = _sweep(_report(_finding()), store, _model(model_fake, "not json"), confirm=True)

    (entry,) = swept.entries
    assert (store.issues(), entry.result, bool(entry.reason)) == ([], SweepResult.SKIPPED, True)
    assert "intake skipped it" in digest_lines(swept)[0]


def test_the_candidate_holds_advisory_ids_and_urls_and_no_private_host_or_address() -> None:
    finding = _finding(file="hosts/node-a.lan/10.1.2.3/pyproject.toml")

    candidate = finding_candidate(finding)

    text = f"{candidate.title}\n{candidate.body}"
    assert (candidate.filed_by, candidate.title.startswith("fix(deps): ")) == (Filer.AGENT, True)
    for public in (
        "GHSA-aaaa-bbbb-cccc",
        "CVE-2026-0001",
        "https://osv.dev/vulnerability/GHSA-aaaa-bbbb-cccc",
        "https://osv.dev/vulnerability/CVE-2026-0001",
        "pyyaml 5.3",
    ):
        assert public in text
    for private in ("node-a.lan", "10.1.2.3", "hosts/", "pyproject.toml"):
        assert private not in text


def test_a_long_package_name_leaves_the_name_out_of_the_title() -> None:
    finding = _finding(name="@scope/a-package-with-a-name-that-is-too-long-for-a-title")

    candidate = finding_candidate(finding)

    assert candidate.title == "fix(deps): update pypi package for GHSA-aaaa-bbbb-cccc"
    assert "a-package-with-a-name-that-is-too-long" in candidate.body


def test_the_source_id_names_the_package_version_and_advisory() -> None:
    assert source_id(_finding()) == "pypi:pyyaml@5.3:GHSA-aaaa-bbbb-cccc"
    assert source_id(_finding(version="5.4")) != source_id(_finding())


def test_a_candidate_that_looks_like_a_secret_stops_the_sweep_before_any_request(
    github_api: GitHubApiFake, model_fake: ModelFake
) -> None:
    secret = "ghp_" + "a" * 36
    finding = _finding().model_copy(update={"summary": f"Leaks {secret}."})

    with pytest.raises(SecurityError, match="GHSA-aaaa-bbbb-cccc"):
        _sweep(_report(finding), _roadmap(), _model(model_fake), confirm=True)

    assert (github_api.requested, model_fake.call_count) == ([], 0)


def test_open_findings_count_each_severity_with_zero_for_a_clean_one() -> None:
    findings = [
        _finding("A", severity="HIGH"),
        _finding("B", severity="HIGH"),
        _finding("C", severity="LOW"),
    ]

    assert open_findings(findings) == {
        "CRITICAL": 0,
        "HIGH": 2,
        "MEDIUM": 0,
        "LOW": 1,
        "INFO": 0,
    }


def test_the_gauge_is_set_for_each_severity(otlp: FakeCollector) -> None:
    swept = run_sweep_report(_finding("A", severity="CRITICAL"), _finding("B", severity="LOW"))

    record_open_findings(swept)
    from devops_cli.telemetry import tracer as tracer_module

    tracer_module.get_tracer().flush()

    points = otlp.points(RESEARCH_OPEN_FINDINGS.name)
    assert {a["severity"]: value for a, value in points} == {
        "critical": 1.0,
        "high": 0.0,
        "medium": 0.0,
        "low": 1.0,
        "info": 0.0,
    }


def run_sweep_report(*findings: AdvisoryFinding) -> Any:
    from devops_cli.research.models import SweepReport

    return SweepReport(open_findings=open_findings(findings))


def test_the_command_files_the_critical_findings_of_the_recorded_repository(
    cli: Callable[..., Any],
    github_api: GitHubApiFake,
    roadmap_store: Any,
    model_fake: ModelFake,
    embedder: Any,
    keyring_store: Any,
) -> None:
    serve_recorded_osv_on_github(github_api)
    _route_search(github_api)
    roadmap_store.seed_file(
        ".github/labels.yml", (REPO_ROOT / ".github/labels.yml").read_text("utf-8")
    )
    for _ in range(2):
        model_fake.answer(json.dumps(_PROPOSAL))

    result = cli(
        "research", "sweep", "--root", str(RECORDED_REPO), "--repo", _REPO, "--confirm", "--json"
    )

    payload = json.loads(result.output)
    filed = {entry["advisory_id"] for entry in payload["entries"] if entry["result"] == "filed"}
    markers = {issue.body.rstrip().splitlines()[-1] for issue in roadmap_store.issues()}
    assert (result.exit_code, payload["dry_run"], payload["failed"]) == (0, False, 0), result.output
    assert filed == {"GHSA-8q59-q68h-6hv4", "GHSA-6757-jp84-gxfx"}
    assert markers == {
        f"<!-- research-finding: pypi:pyyaml@5.3:{advisory} -->" for advisory in filed
    }
    assert payload["open_findings"]["CRITICAL"] == 2


def test_the_dry_run_of_the_command_makes_no_request(
    cli: Callable[..., Any], github_api: GitHubApiFake, model_fake: ModelFake
) -> None:
    result = cli("research", "sweep", "--root", RECORDED_REPO, "--repo", _REPO, "--dry-run")

    assert result.exit_code == 0, result.output
    for planned in ("api.osv.dev/v1/querybatch", "search/issues", "research"):
        assert planned in result.output
    assert (github_api.requested, model_fake.call_count) == ([], 0)


def test_the_dry_run_json_is_a_sweep_report_with_the_requests(
    cli: Callable[..., Any], github_api: GitHubApiFake
) -> None:
    result = cli(
        "research", "sweep", "--root", RECORDED_REPO, "--repo", _REPO, "--dry-run", "--json"
    )

    payload = json.loads(result.output)
    assert (result.exit_code, payload["dry_run"], payload["entries"], github_api.requested) == (
        0,
        True,
        [],
        [],
    )
    assert any("search/issues" in line for line in payload["requests"])


def test_a_lookup_without_an_answer_exits_1_and_sets_no_gauge(
    cli: Callable[..., Any],
    github_api: GitHubApiFake,
    roadmap_store: Any,
    model_fake: ModelFake,
    embedder: Any,
    keyring_store: Any,
    otlp: FakeCollector,
) -> None:
    from devops_cli.security.vulnerability_lookup import OSVClient
    from devops_cli.telemetry import tracer as tracer_module

    github_api.route("POST", OSVClient.BATCH_URL, github_json({}, status=503))

    result = cli("research", "sweep", "--root", str(RECORDED_REPO), "--repo", _REPO, "--json")

    tracer_module.get_tracer().flush()
    assert (result.exit_code, otlp.points(RESEARCH_OPEN_FINDINGS.name)) == (1, [])
