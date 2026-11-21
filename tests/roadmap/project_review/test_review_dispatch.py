"""The dispatcher of the project review catalog (#4692): the status of each fact past a retention,
with an unset address, with no series and after a failed read; the Service SLI of one repository;
one read for the facts of one query; and the disagreements of the catalog."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx2
import yaml
from devops_cli.roadmap.project_review.dispatch import ReadContext, read_catalog

from devops_cli.config.settings import load_settings
from devops_cli.roadmap.project_review.catalog import Catalog, load_catalog
from devops_cli.roadmap.project_review.data import FactStatus, ReviewWindow, WindowKind
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.github import API, GitHubApiFake, github_json
from tests.support.fakes.http import WebFake

REPO = "example/project"
END = datetime(2026, 11, 11, 14, 51, 23, tzinfo=UTC)
PROMETHEUS = "http://prometheus.example.com:9090"
LOKI = "http://loki.example.com:3100"
READERS = {
    "prometheus": {"retention": "30d", "requires": ["setting:prometheus.url"]},
    "loki": {"retention": "30d", "requires": ["setting:loki.url"]},
}


def _window(end: datetime = END) -> ReviewWindow:
    return ReviewWindow(
        kind=WindowKind.PERIOD,
        id="w",
        base_sha="a" * 40,
        head_sha="b" * 40,
        start=end - timedelta(days=7),
        end=end,
        previous_id=None,
    )


def _prometheus_fact(fact_id: str, query: str, shape: str = "scalar") -> dict[str, Any]:
    return {
        "id": fact_id,
        "reader": "prometheus",
        "section": "service",
        "query": query,
        "shape": shape,
        "unit": "count",
        "definition": "A value.",
    }


def _catalog(
    tmp_path: Path,
    facts: Sequence[Mapping[str, Any]],
    disagreements: Sequence[Mapping[str, Any]] = (),
) -> Catalog:
    path = tmp_path / "catalog.yaml"
    document = {
        "version": 1,
        "sections": [{"id": "service", "title": "Service"}],
        "readers": READERS,
        "facts": list(facts),
        "disagreements": list(disagreements),
    }
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return load_catalog(path)


def _context(tmp_path: Path, *, now: datetime = END + timedelta(days=1)) -> ReadContext:
    return ReadContext(
        checkout=tmp_path,
        repo=REPO,
        window=_window(now - timedelta(days=1)),
        settings=load_settings(),
        now=now,
    )


def _vector(*samples: tuple[Mapping[str, str], float]) -> httpx2.Response:
    result = [{"metric": dict(labels), "value": [1, str(value)]} for labels, value in samples]
    return httpx2.Response(
        200, json={"status": "success", "data": {"resultType": "vector", "result": result}}
    )


def _by_query(answers: Callable[[str], httpx2.Response]) -> Callable[..., httpx2.Response]:
    return lambda request: answers(request.url.params["query"])


def test_a_window_that_ended_forty_days_ago_marks_each_prometheus_fact_expired(
    tmp_path: Path, web: WebFake, config: Callable[..., Path]
) -> None:
    config(prometheus={"url": PROMETHEUS})
    catalog = _catalog(tmp_path, [_prometheus_fact("prometheus.up", "sum(up)")])
    now = END + timedelta(days=40)
    context = ReadContext(
        checkout=tmp_path, repo=REPO, window=_window(), settings=load_settings(), now=now
    )

    [fact] = read_catalog(catalog, context).facts

    assert (fact.status, fact.value, "30 days" in fact.reason, web.sent) == (
        FactStatus.EXPIRED,
        None,
        True,
        [],
    )


def test_an_unset_address_skips_each_prometheus_fact_and_names_the_setting(
    tmp_path: Path, web: WebFake
) -> None:
    catalog = _catalog(tmp_path, [_prometheus_fact("prometheus.up", "sum(up)")])

    [fact] = read_catalog(catalog, _context(tmp_path)).facts

    assert (fact.status, fact.value, "prometheus.url" in fact.reason, web.sent) == (
        FactStatus.SKIPPED,
        None,
        True,
        [],
    )


def test_a_scalar_query_with_no_series_is_skipped_not_zero(
    tmp_path: Path, web: WebFake, config: Callable[..., Path]
) -> None:
    config(prometheus={"url": PROMETHEUS})
    web.serve(lambda request: _vector())
    catalog = _catalog(tmp_path, [_prometheus_fact("prometheus.up", "sum(up)")])

    [fact] = read_catalog(catalog, _context(tmp_path)).facts

    assert (fact.status, fact.value, "no series" in fact.reason) == (FactStatus.SKIPPED, None, True)


def test_a_failed_loki_read_marks_its_fact_and_the_review_reads_the_others(
    tmp_path: Path, web: WebFake, clock: ClockFake, config: Callable[..., Path]
) -> None:
    config(prometheus={"url": PROMETHEUS}, loki={"url": LOKI})
    web.serve(
        lambda request: (
            httpx2.Response(500, text="Internal Server Error")
            if request.url.path.startswith("/loki/")
            else _vector(({}, 3))
        )
    )
    loki = {
        **_prometheus_fact("loki.lines", 'sum(count_over_time({app="x"}[{range}]))'),
        "reader": "loki",
    }
    catalog = _catalog(tmp_path, [loki, _prometheus_fact("prometheus.up", "sum(up)")])

    facts = {fact.id: fact for fact in read_catalog(catalog, _context(tmp_path)).facts}

    assert (facts["loki.lines"].status, facts["loki.lines"].value) == (FactStatus.ERROR, None)
    assert "Loki" in facts["loki.lines"].reason
    assert (facts["prometheus.up"].status, facts["prometheus.up"].value) == (FactStatus.OK, 3.0)


def test_the_stage_sli_is_the_value_of_the_repository_of_the_review(
    tmp_path: Path, web: WebFake, config: Callable[..., Path]
) -> None:
    config(prometheus={"url": PROMETHEUS})

    def answer(query: str) -> httpx2.Response:
        if f'repo="{REPO}"' in query:
            return _vector(({}, 0.372))
        return _vector(({}, 0.555)) if "repo=" in query else _vector(({}, 0.927))

    web.serve(_by_query(answer))
    query = (
        'sum(increase(devops_cli_service_jobs_total{row="stage", repo="{repo}", '
        'result="success"}[{range}])) / sum(increase(devops_cli_service_jobs_total{row="stage", '
        'repo="{repo}"}[{range}]))'
    )
    catalog = _catalog(tmp_path, [_prometheus_fact("prometheus.stage_sli", query)])

    [fact] = read_catalog(catalog, _context(tmp_path)).facts

    assert (fact.status, fact.value) == (FactStatus.OK, 0.372)
    assert f'repo="{REPO}"' in fact.query


def test_two_facts_on_one_query_share_one_read(tmp_path: Path, github_api: GitHubApiFake) -> None:
    releases = [{"id": 2, "prerelease": True}, {"id": 1, "prerelease": False}]
    github_api.route("GET", f"/repos/{REPO}/releases?per_page=100", github_json(releases))
    common = {"reader": "github", "section": "service", "query": "repos/{repo}/releases"}
    catalog = _catalog(
        tmp_path,
        [
            {**common, "id": "github.releases", "value": "length", "unit": "releases"},
            {
                **common,
                "id": "github.prereleases",
                "value": "[.[] | select(.prerelease)] | length",
                "unit": "releases",
            },
        ],
    )

    result = read_catalog(catalog, _context(tmp_path))

    assert [(fact.id, fact.value) for fact in result.facts] == [
        ("github.releases", 2),
        ("github.prereleases", 1),
    ]
    assert (github_api.requested, result.collection.reads) == (
        [f"GET {API}/repos/{REPO}/releases?per_page=100"],
        {"github": 1},
    )


def test_three_pairs_that_differ_are_disagreements_and_a_pair_within_the_tolerance_is_not(
    tmp_path: Path, web: WebFake, config: Callable[..., Path]
) -> None:
    config(prometheus={"url": PROMETHEUS})
    values = {"a1": 48.8, "a2": 0, "b1": 12, "b2": 30, "c1": 77.22, "c2": 118.74}
    values |= {"d1": 10, "d2": 10.5}
    web.serve(_by_query(lambda query: _vector(({}, values[query.removeprefix("v_")]))))
    facts = [_prometheus_fact(f"prometheus.{name}", f"v_{name}") for name in values]
    pairs = [
        {
            "id": pair,
            "left": f"prometheus.{pair}1",
            "right": f"prometheus.{pair}2",
            "tolerance": 0.1,
            "definition": "Two counters of one measure.",
        }
        for pair in ("a", "b", "c", "d")
    ]
    catalog = _catalog(tmp_path, facts, pairs)

    rows = read_catalog(catalog, _context(tmp_path)).disagreements

    assert [(row.id, row.left_value, row.right_value) for row in rows] == [
        ("a", 48.8, 0.0),
        ("b", 12.0, 30.0),
        ("c", 77.22, 118.74),
    ]
