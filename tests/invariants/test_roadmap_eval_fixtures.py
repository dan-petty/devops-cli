"""The committed fixtures of `devops roadmap eval implement` (#3030): the set loads against its
schema, holds the items the baseline needs, keeps every recorded result as recorded, and stays
small."""

from __future__ import annotations

import re
from collections import Counter

import pytest

from devops_cli.roadmap.implement.implement_eval import LoadedCase, load_cases
from devops_cli.roadmap.implement.implement_eval_properties import Status
from devops_cli.roadmap.implement.implement_eval_run import check_recorded
from tests.support.paths import FIXTURES

ROOT = FIXTURES / "roadmap_eval" / "implement"
MAX_BYTES = 1_000_000
_SCOPE_RE = re.compile(r"^[a-z]+\(([^)]+)\):")

# Merged delivery pull requests of the last 90 days with complete three-file OpenSpec archives.
DELIVERY_COUNTS_90D: dict[str, int] = {
    "roadmap": 615,
    "k8s": 177,
    "ai": 113,
    "security": 85,
    "ci": 77,
    "telemetry": 42,
    "review": 41,
    "monitoring": 37,
    "github": 36,
    "cli": 35,
    "service": 31,
    "config": 27,
    "tests": 25,
    "infra": 23,
    "pr": 20,
    "devcontainer": 19,
    "openspec": 15,
    "repos": 15,
    "deps": 11,
    "mcp": 11,
    "docs": 9,
    "research": 9,
    "agents": 8,
    "git": 8,
    "docker": 7,
    "gh": 7,
    "sandbox": 7,
    "argo": 6,
    "rag": 6,
    "adr": 5,
    "scan": 5,
    "sdlc": 5,
    "terraform": 5,
    "valkey": 5,
    "argocd": 3,
    "cloudflare": 3,
    "contributing": 3,
    "design": 3,
    "release": 3,
    "gate": 2,
    "output": 2,
    "ui": 2,
    "vault": 2,
    "agent": 1,
    "cache": 1,
    "dashboard": 1,
    "exceptions": 1,
    "lint": 1,
    "llm": 1,
}

# Proportional target counts (minimum 1 per scope with deliveries, retaining existing baseline).
EXPECTED_SCOPE_COUNTS: dict[str, int] = {
    "roadmap": 11,
    "security": 7,
    "k8s": 4,
    "ai": 3,
    "cli": 3,
    "argo": 2,
    "ci": 2,
    "config": 2,
    "github": 2,
    "monitoring": 2,
    "review": 2,
    "service": 2,
    "telemetry": 2,
    "tests": 2,
    "adr": 1,
    "agent": 1,
    "agents": 1,
    "argocd": 1,
    "cache": 1,
    "cloudflare": 1,
    "contributing": 1,
    "dashboard": 1,
    "deps": 1,
    "design": 1,
    "devcontainer": 1,
    "docker": 1,
    "docs": 1,
    "exceptions": 1,
    "gate": 1,
    "gh": 1,
    "git": 1,
    "infra": 1,
    "lint": 1,
    "llm": 1,
    "mcp": 1,
    "openspec": 1,
    "output": 1,
    "pr": 1,
    "rag": 1,
    "release": 1,
    "repos": 1,
    "research": 1,
    "sandbox": 1,
    "scan": 1,
    "sdlc": 1,
    "terraform": 1,
    "ui": 1,
    "valkey": 1,
    "vault": 1,
}


@pytest.fixture(scope="module")
def cases() -> list[LoadedCase]:
    return load_cases(ROOT)


def test_the_set_holds_at_least_forty_fixtures_with_the_items_of_the_baseline(
    cases: list[LoadedCase],
) -> None:
    issues = {case.case.issue for case in cases}

    assert len(cases) >= 40
    assert {2175, 2735} <= issues


def test_the_scope_counts_match_the_delivery_mix(cases: list[LoadedCase]) -> None:
    counts: Counter[str] = Counter()
    for case in cases:
        match = _SCOPE_RE.match(case.case.title)
        assert match is not None, f"{case.name}: title lacks Conventional Commit scope"
        counts[match.group(1)] += 1

    for scope, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"{scope}: {count}")

    assert sum(counts.values()) == len(cases)
    assert set(counts) == set(DELIVERY_COUNTS_90D)
    assert dict(counts) == EXPECTED_SCOPE_COUNTS


def test_the_names_are_unique_and_every_base_is_a_full_sha(cases: list[LoadedCase]) -> None:
    names = [case.name for case in cases]

    assert len(names) == len(set(names))
    assert all(len(case.case.base) == 40 for case in cases)


def test_the_set_holds_a_result_that_fails_no_diff_property_and_one_that_fails_some(
    cases: list[LoadedCase],
) -> None:
    fails = [result.fails for case in cases for result in case.case.results]

    assert () in fails
    assert any(fails)


def test_the_set_holds_a_deletion_item_with_a_corrected_plan_and_a_scratch_file_result(
    cases: list[LoadedCase],
) -> None:
    by_name = {case.name: case for case in cases}
    scratch = by_name["2175-dead-code-first-plan-group-2"].case.results

    assert "2175-dead-code" in by_name
    assert [(result.name, [p.value for p in result.fails]) for result in scratch] == [
        ("stopped-with-scratch-file", ["diff_scope", "no_scratch"])
    ]


@pytest.mark.parametrize(
    "name", ["2735-less-env-guard-corrected-plan", "2739-gh-telemetry-url-corrected-plan"]
)
def test_a_merged_delivery_with_a_corrected_plan_scores_clean_on_every_property(
    cases: list[LoadedCase], name: str
) -> None:
    by_name = {case.name: case for case in cases}
    case = by_name[name]
    (delivered,) = case.case.results
    (report,) = check_recorded(case)

    assert (delivered.name, delivered.fails) == ("delivered", ())
    assert case.case.tests_pass
    assert report.count(Status.FAIL) == 0
    assert report.matches is True


def test_every_recorded_result_fails_the_diff_properties_it_is_recorded_to_fail(
    cases: list[LoadedCase],
) -> None:
    reports = [report for case in cases for report in check_recorded(case)]

    assert reports
    assert [(r.fixture, r.result) for r in reports if r.matches is not True] == []


def test_the_set_stays_small() -> None:
    size = sum(path.stat().st_size for path in ROOT.rglob("*") if path.is_file())

    assert size < MAX_BYTES
