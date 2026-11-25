"""The dispatcher of the project review catalog (#4692): the status of each fact past a retention,
with an unset address, with no series and after a failed read; the Service SLI of one repository;
one read for the facts of one query; the disagreements of the catalog; the guard that keeps the
rows of a workload outside the project namespaces out of the review (#6615); and the probe at the
window end, the first time of a series, the path condition at the commits of the window and the
reason of a missing series (#6612)."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx2
import pytest
import yaml

from devops_cli.config.settings import load_settings
from devops_cli.roadmap.project_review.catalog import (
    Catalog,
    Shape,
    load_catalog,
    window_placeholders,
)
from devops_cli.roadmap.project_review.data import FactStatus, ReviewWindow, WindowKind
from devops_cli.roadmap.project_review.dispatch import (
    ReadContext,
    plan_catalog,
    read_catalog,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.git import GitFake
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

    assert (fact.status, fact.value, "no series" in fact.reason.lower()) == (
        FactStatus.SKIPPED,
        None,
        True,
    )


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


def test_the_slo1_of_the_service_is_the_value_of_the_repository_of_the_review(
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
    catalog = _catalog(tmp_path, [_prometheus_fact("prometheus.service_slo1", query)])

    [fact] = read_catalog(catalog, _context(tmp_path)).facts

    assert (fact.status, fact.value) == (FactStatus.OK, 0.372)
    assert f'repo="{REPO}"' in fact.query


def test_two_facts_on_one_query_share_one_read(tmp_path: Path, github_api: GitHubApiFake) -> None:
    releases = [{"id": 2, "prerelease": True}, {"id": 1, "prerelease": False}]
    github_api.route("GET", f"/repos/{REPO}/releases?per_page=100", github_json(releases))
    common = {
        "reader": "github",
        "section": "service",
        "query": "repos/{repo}/releases",
        "definition": "The releases.",
    }
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


def test_a_window_as_long_as_the_retention_is_read_not_expired(
    tmp_path: Path, web: WebFake, config: Callable[..., Path]
) -> None:
    """`--last 30d` starts at the whole minute before the time now less 30 days, a few seconds
    before the retention limit; Prometheus still holds those samples."""
    config(prometheus={"url": PROMETHEUS})
    web.serve(lambda request: _vector(({}, 3)))
    catalog = _catalog(tmp_path, [_prometheus_fact("prometheus.up", "sum(up)")])
    now = datetime(2026, 11, 21, 2, 2, 41, tzinfo=UTC)
    end = now.replace(second=0)
    window = ReviewWindow(
        kind=WindowKind.PERIOD,
        id="w",
        base_sha="a" * 40,
        head_sha="b" * 40,
        start=end - timedelta(days=30),
        end=end,
        previous_id=None,
    )
    context = ReadContext(
        checkout=tmp_path, repo=REPO, window=window, settings=load_settings(), now=now
    )

    [fact] = read_catalog(catalog, context).facts

    assert (fact.status, fact.value) == (FactStatus.OK, 3.0)


def test_an_unreachable_prometheus_gets_one_read_and_marks_each_of_its_facts_error(
    tmp_path: Path, web: WebFake, clock: ClockFake, config: Callable[..., Path]
) -> None:
    """A network error ends the reads of its reader kind: the later facts take its reason and
    send no request, so one address that does not answer costs one read, not one for each fact."""
    config(prometheus={"url": PROMETHEUS})

    def refuse(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("Connection refused", request=request)

    web.serve(refuse)
    facts = [_prometheus_fact(f"prometheus.f{index}", f"sum(up{index})") for index in range(3)]
    catalog = _catalog(tmp_path, facts)

    result = read_catalog(catalog, _context(tmp_path))

    assert {request.url.params["query"] for request in web.sent} == {"sum(up0)"}
    assert [fact.status for fact in result.facts] == [FactStatus.ERROR] * 3
    assert len({fact.reason for fact in result.facts}) == 1
    assert result.collection.reads == {"prometheus": 1}


def test_a_loki_answer_that_is_not_json_marks_its_fact_error_and_the_review_reads_the_others(
    tmp_path: Path, web: WebFake, config: Callable[..., Path]
) -> None:
    config(prometheus={"url": PROMETHEUS}, loki={"url": LOKI})
    web.serve(
        lambda request: (
            httpx2.Response(200, headers={"content-type": "text/html"}, text="<html>Sign in")
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

    assert (facts["loki.lines"].status, "loki.url" in facts["loki.lines"].reason) == (
        FactStatus.ERROR,
        True,
    )
    assert (facts["prometheus.up"].status, facts["prometheus.up"].value) == (FactStatus.OK, 3.0)


def _probe(present: bool) -> Callable[[str], httpx2.Response]:
    """Prometheus that gives no series to each fact query, and a series to the probe of the base
    metric of a fact when `present`."""

    def answer(query: str) -> httpx2.Response:
        return _vector(({}, 1)) if present and query.startswith("group(") else _vector()

    return answer


def test_a_fact_with_no_series_gives_its_own_reason_of_a_missing_series(
    tmp_path: Path, web: WebFake, config: Callable[..., Path]
) -> None:
    """A gauge that no code emits yet is not a gauge that stopped (#6612)."""
    config(prometheus={"url": PROMETHEUS})
    web.serve(lambda request: _vector())
    reason = "No code emits this gauge before #4911."
    fact = {**_prometheus_fact("prometheus.oldest", "max(x_seconds)"), "no_series_reason": reason}

    [read] = read_catalog(_catalog(tmp_path, [fact]), _context(tmp_path)).facts

    assert (read.status, read.value, read.reason) == (FactStatus.SKIPPED, None, reason)


def test_a_rows_fact_with_no_series_and_no_base_metric_is_skipped(
    tmp_path: Path, web: WebFake, config: Callable[..., Path]
) -> None:
    config(prometheus={"url": PROMETHEUS})
    web.serve(_by_query(_probe(present=True)))
    fact = _prometheus_fact("prometheus.spend", "sum by (row) (x_total)", "rows")
    catalog = _catalog(tmp_path, [fact])

    [read] = read_catalog(catalog, _context(tmp_path)).facts

    assert (read.status, read.value, "no series" in read.reason.lower()) == (
        FactStatus.SKIPPED,
        None,
        True,
    )


@pytest.mark.parametrize(
    ("shape", "present", "status", "value", "n"),
    [
        ("rows", True, FactStatus.OK, [], 0),
        ("scalar", True, FactStatus.OK, 0.0, None),
        ("rows", False, FactStatus.SKIPPED, None, None),
        ("scalar", False, FactStatus.SKIPPED, None, None),
    ],
)
def test_a_fact_with_no_series_is_none_only_when_its_base_metric_has_a_series(
    tmp_path: Path,
    web: WebFake,
    config: Callable[..., Path],
    shape: str,
    present: bool,
    status: FactStatus,
    value: object,
    n: int | None,
) -> None:
    """A missing metric is never 0: an empty answer says "none" only when the base metric of the
    fact has a series in the window (one more read, sent only for an empty answer)."""
    config(prometheus={"url": PROMETHEUS})
    web.serve(_by_query(_probe(present)))
    query = "sum by (row) (increase(x_total[{range}])) > 0"
    fact = {**_prometheus_fact("prometheus.spend", query, shape)}
    fact["base"] = 'x_total{repo="{repo}"}'
    catalog = _catalog(tmp_path, [fact])

    [read] = read_catalog(catalog, _context(tmp_path)).facts

    assert (read.status, read.value, read.n) == (status, value, n)
    assert [request.url.params["query"] for request in web.sent] == [
        "sum by (row) (increase(x_total[604800s])) > 0",
        f'group(last_over_time(x_total{{repo="{REPO}"}}[604800s]))',
    ]
    assert present or "x_total" in read.reason


@pytest.mark.parametrize("shape", ["scalar", "rows"])
def test_an_end_instant_fact_whose_base_has_no_series_at_the_end_is_skipped(
    tmp_path: Path, web: WebFake, config: Callable[..., Path], shape: str
) -> None:
    """A query with no `{range}` reads the window end, so its probe reads the end too: a series
    earlier in the window does not make an empty answer "none" (#6612)."""
    config(prometheus={"url": PROMETHEUS})
    window_probe = f'group(last_over_time(x_total{{repo="{REPO}"}}[604800s]))'
    web.serve(_by_query(lambda query: _vector(({}, 1)) if query == window_probe else _vector()))
    fact = {**_prometheus_fact("prometheus.states", "sum by (state) (x_total)", shape)}
    fact["base"] = 'x_total{repo="{repo}"}'
    catalog = _catalog(tmp_path, [fact])

    [read] = read_catalog(catalog, _context(tmp_path)).facts

    assert (read.status, read.value, "x_total" in read.reason) == (FactStatus.SKIPPED, None, True)
    assert "2026-11-11T14:51:23Z" in read.reason
    assert [request.url.params["query"] for request in web.sent] == [
        "sum by (state) (x_total)",
        f'group(x_total{{repo="{REPO}"}})',
    ]


def test_a_path_that_the_base_commit_does_not_hold_skips_the_fact_whatever_the_working_tree(
    tmp_path: Path, git_fake: GitFake
) -> None:
    """A window from before the commit that added `openspec/specs` has no requirements to count,
    though the working tree holds the folder (#6612). The base does not hold the path, so the
    review reads no head and no other git command."""
    git_fake.replay("review_spec_path")
    checkout = tmp_path / "spec-path"
    (checkout / "openspec" / "specs").mkdir(parents=True)
    fact = {
        "id": "openspec.requirements",
        "reader": "openspec",
        "section": "service",
        "query": "git grep -c '^### Requirement:' {base} {head} -- openspec/specs",
        "value": ".requirements",
        "unit": "requirements",
        "definition": "The requirements at the base and at the head.",
        "requires": ["path:openspec/specs"],
    }
    window = ReviewWindow(
        kind=WindowKind.VERSION,
        id="v0.9.0..v1.0.0",
        base_sha="v0.9.0",
        head_sha="v1.0.0",
        start=END - timedelta(days=7),
        end=END,
        previous_id=None,
    )
    context = ReadContext(
        checkout=checkout, repo=REPO, window=window, settings=load_settings(), now=END
    )

    [read] = read_catalog(_catalog(tmp_path, [fact]), context).facts

    assert (read.status, read.value) == (FactStatus.SKIPPED, None)
    assert ("openspec/specs" in read.reason, "v0.9.0" in read.reason) == (True, True)
    assert [call.argv[3:] for call in git_fake.calls] == [
        ("ls-tree", "--name-only", "--end-of-options", "v0.9.0", "openspec/specs")
    ]


RENAMED = "2026-11-14T22:29:00Z"
RENAME_END = datetime(2026, 11, 16, tzinfo=UTC)


def _renamed_pair(tmp_path: Path) -> Catalog:
    """`prometheus.left` and `prometheus.right`, whose series starts at RENAMED, and their pair."""
    right = {**_prometheus_fact("prometheus.right", "sum(right_total)"), "not_before": RENAMED}
    pair = {
        "id": "jobs",
        "left": "prometheus.left",
        "right": "prometheus.right",
        "tolerance": 0.1,
        "definition": "Two counts of the same Jobs.",
    }
    return _catalog(
        tmp_path, [_prometheus_fact("prometheus.left", "sum(left_total)"), right], [pair]
    )


def _days_to(end: datetime, days: int, tmp_path: Path) -> ReadContext:
    window = ReviewWindow(
        kind=WindowKind.PERIOD,
        id="w",
        base_sha="a" * 40,
        head_sha="b" * 40,
        start=end - timedelta(days=days),
        end=end,
        previous_id=None,
    )
    return ReadContext(
        checkout=tmp_path,
        repo=REPO,
        window=window,
        settings=load_settings(),
        now=end + timedelta(hours=1),
    )


def test_a_window_that_starts_before_the_first_time_of_a_series_skips_the_fact_and_its_pair(
    tmp_path: Path, web: WebFake, config: Callable[..., Path]
) -> None:
    """The Jobs had other names before #5739, so a window across the rename counts only the later
    Jobs: a false disagreement of about 69 % (#6612)."""
    config(prometheus={"url": PROMETHEUS})
    web.serve(lambda request: _vector(({}, 48.43)))

    result = read_catalog(_renamed_pair(tmp_path), _days_to(RENAME_END, 7, tmp_path))

    left, right = result.facts
    assert (left.status, left.value) == (FactStatus.OK, 48.43)
    assert (right.status, right.value, RENAMED in right.reason) == (FactStatus.SKIPPED, None, True)
    assert [request.url.params["query"] for request in web.sent] == ["sum(left_total)"]
    assert result.disagreements == []


def test_a_window_after_the_first_time_of_a_series_reads_the_fact_and_its_pair(
    tmp_path: Path, web: WebFake, config: Callable[..., Path]
) -> None:
    config(prometheus={"url": PROMETHEUS})
    answers = {"sum(left_total)": 48.43, "sum(right_total)": 15}
    web.serve(_by_query(lambda query: _vector(({}, answers[query]))))

    result = read_catalog(_renamed_pair(tmp_path), _days_to(RENAME_END, 1, tmp_path))

    assert [(fact.status, fact.value) for fact in result.facts] == [
        (FactStatus.OK, 48.43),
        (FactStatus.OK, 15.0),
    ]
    assert [(row.id, row.left_value, row.right_value) for row in result.disagreements] == [
        ("jobs", 48.43, 15.0)
    ]


def test_the_plan_of_a_fact_with_a_first_time_names_that_time(tmp_path: Path) -> None:
    values = window_placeholders(_window(RENAME_END), REPO, ("devops",))

    plan = plan_catalog(_renamed_pair(tmp_path), values, tmp_path)

    [right] = [read for read in plan if read.target.startswith("prometheus.right: ")]
    assert RENAMED in right.condition


def test_a_workload_query_reads_only_the_namespaces_of_the_setting(
    tmp_path: Path, web: WebFake, config: Callable[..., Path]
) -> None:
    """The names of the workloads of other projects never reach the review (#6615)."""
    config(
        prometheus={"url": PROMETHEUS},
        roadmap={"project_review": {"namespaces": ["devops", "llm"]}},
    )
    web.serve(_by_query(lambda _query: _vector(({"namespace": "devops", "pod": "valkey-0"}, 1.0))))
    query = 'max by (namespace, pod) (redis_memory_max_bytes{namespace=~"{namespaces}"} == 0)'
    catalog = _catalog(tmp_path, [_prometheus_fact("prometheus.valkey_pods", query, "rows")])

    read_catalog(catalog, _context(tmp_path))

    assert [request.url.params["query"] for request in web.sent] == [
        'max by (namespace, pod) (redis_memory_max_bytes{namespace=~"devops|llm"} == 0)'
    ]


# A query that the loader accepts, but whose rows keep every label of the series: the guard on the
# result rows does not depend on the form of the query (#6615).
EVERY_LABEL = "sort_desc(sum without (instance) (redis_memory_used_bytes))"


@pytest.mark.parametrize(
    ("labels", "label"),
    [
        ({"namespace": "other-project", "pod": "database-0"}, "namespace"),
        ({"pod": "database-0"}, "pod"),
        ({"container": "database"}, "container"),
        # A scrape that keeps the labels of its target as exported_* (kube-state-metrics with
        # honor_labels false, a Pushgateway).
        (
            {"namespace": "devops", "exported_namespace": "other-project", "exported_pod": "db-0"},
            "exported_namespace",
        ),
        ({"exported_pod": "database-0"}, "exported_pod"),
        ({"exported_container": "database"}, "exported_container"),
        # An Argo CD application in a project namespace that deploys to another namespace.
        (
            {"namespace": "devops", "name": "app", "dest_namespace": "other-project"},
            "dest_namespace",
        ),
        # A Traefik service: its name holds the namespace, and the series has no namespace label.
        ({"service": "other-project-database-5432@kubernetes"}, "service"),
        ({"persistentvolumeclaim": "data-database-0"}, "persistentvolumeclaim"),
    ],
)
def test_a_row_of_a_workload_outside_the_project_namespaces_marks_the_fact_error(
    tmp_path: Path,
    web: WebFake,
    config: Callable[..., Path],
    labels: Mapping[str, str],
    label: str,
) -> None:
    """The reason names the fact and the label, never a label value, so no name of a workload of
    another project reaches the review."""
    config(prometheus={"url": PROMETHEUS}, roadmap={"project_review": {"namespaces": ["devops"]}})
    web.serve(
        lambda request: _vector(({"namespace": "devops", "pod": "valkey-0"}, 2.0), (labels, 1.0))
    )
    catalog = _catalog(tmp_path, [_prometheus_fact("prometheus.valkey_rows", EVERY_LABEL, "rows")])

    [read] = read_catalog(catalog, _context(tmp_path)).facts

    assert (read.status, read.value, read.n) == (FactStatus.ERROR, None, None)
    assert ("prometheus.valkey_rows" in read.reason, f"`{label}`" in read.reason) == (True, True)
    assert [value for value in (*labels.values(), "valkey-0") if value in read.reason] == []


def test_a_loki_row_of_another_namespace_marks_the_fact_error(
    tmp_path: Path, web: WebFake, config: Callable[..., Path]
) -> None:
    config(loki={"url": LOKI}, roadmap={"project_review": {"namespaces": ["devops"]}})
    web.serve(lambda request: _vector(({"namespace": "other-project", "container": "app"}, 4.0)))
    query = 'sum by (namespace, container) (count_over_time({namespace=~".+"}[{range}]))'
    loki = {**_prometheus_fact("loki.lines", query, "rows"), "reader": "loki"}

    [read] = read_catalog(_catalog(tmp_path, [loki]), _context(tmp_path)).facts

    assert (read.status, "loki.lines" in read.reason, "other-project" in read.reason) == (
        FactStatus.ERROR,
        True,
        False,
    )


@pytest.mark.parametrize(
    "labels",
    [
        {"resource": "cpu"},
        {"namespace": "devops", "pod": "valkey-0"},
        {"namespace": "devops", "service": "valkey"},
        {"namespace": "devops", "exported_namespace": "devops", "exported_pod": "valkey-0"},
        {},
    ],
)
def test_a_row_with_no_workload_label_or_of_a_project_namespace_is_kept(
    tmp_path: Path, web: WebFake, config: Callable[..., Path], labels: Mapping[str, str]
) -> None:
    config(prometheus={"url": PROMETHEUS}, roadmap={"project_review": {"namespaces": ["devops"]}})
    web.serve(lambda request: _vector((labels, 0.25)))
    catalog = _catalog(tmp_path, [_prometheus_fact("prometheus.share", EVERY_LABEL, "rows")])

    [read] = read_catalog(catalog, _context(tmp_path)).facts

    assert (read.status, read.value, read.n) == (
        FactStatus.OK,
        [{"labels": dict(labels), "value": 0.25}],
        1,
    )


def test_a_row_with_an_unknown_label_and_no_namespace_marks_the_fact_error(
    tmp_path: Path, web: WebFake, config: Callable[..., Path]
) -> None:
    """Default refusal: a non-namespaced row with a label outside the safe list fails (#6632)."""
    config(prometheus={"url": PROMETHEUS}, roadmap={"project_review": {"namespaces": ["devops"]}})
    web.serve(lambda _request: _vector(({"name": "other-app", "zebra": "secret"}, 1.0)))
    catalog = _catalog(tmp_path, [_prometheus_fact("prometheus.argocd_rows", EVERY_LABEL, "rows")])

    [read] = read_catalog(catalog, _context(tmp_path)).facts

    assert (read.status, read.value, read.n) == (FactStatus.ERROR, None, None)
    assert (
        "prometheus.argocd_rows" in read.reason,
        "`name`" in read.reason,
        "other-app" in read.reason,
        "secret" in read.reason,
    ) == (True, True, False, False)


@pytest.mark.parametrize(
    "labels",
    [
        {"namespace": "devops", "name": "app"},
        {"__name__": "http_requests_total", "resource": "cpu", "le": "0.5"},
        {"code_class": "2xx", "quantile": "0.99"},
    ],
)
def test_a_row_of_a_project_namespace_or_safe_labels_passes(
    tmp_path: Path, web: WebFake, config: Callable[..., Path], labels: Mapping[str, str]
) -> None:
    config(prometheus={"url": PROMETHEUS}, roadmap={"project_review": {"namespaces": ["devops"]}})
    web.serve(lambda _request: _vector((labels, 1.0)))
    catalog = _catalog(tmp_path, [_prometheus_fact("prometheus.safe_rows", EVERY_LABEL, "rows")])

    [read] = read_catalog(catalog, _context(tmp_path)).facts

    assert read.status == FactStatus.OK


def _shipped_outer_labels(query: str) -> dict[str, str]:
    by_clause = re.compile(r"\bby\s*\(([^)]*)\)")
    matches = [
        (query[: match.start()].count("(") - query[: match.start()].count(")"), match.group(1))
        for match in by_clause.finditer(query)
    ]
    min_depth = min((depth for depth, _ in matches), default=0)
    labels = [
        raw.strip()
        for depth, clause in matches
        if depth == min_depth
        for raw in clause.split(",")
        if raw.strip()
    ]
    return {
        "__name__": "metric",
        **{label: ("devops" if "namespace" in label else "val") for label in labels},
    }


def test_shipped_rows_facts_keep_only_safe_or_namespaced_labels(
    tmp_path: Path, web: WebFake, config: Callable[..., Path]
) -> None:
    """Every shipped `rows` fact in `catalog.yaml` passes the row guard through `read_catalog`
    (#6632)."""
    config(prometheus={"url": PROMETHEUS}, roadmap={"project_review": {"namespaces": ["devops"]}})
    rows_facts = [fact for fact in load_catalog().facts if fact.shape is Shape.ROWS]
    assert rows_facts
    labels_by_query = {
        f"shipped_row_metric_{index}": _shipped_outer_labels(fact.query)
        for index, fact in enumerate(rows_facts)
    }
    facts = [
        _prometheus_fact(fact.id, f"shipped_row_metric_{index}", "rows")
        for index, fact in enumerate(rows_facts)
    ]

    web.serve(_by_query(lambda query: _vector((labels_by_query[query], 1.0))))
    catalog = _catalog(tmp_path, facts)
    read = read_catalog(catalog, _context(tmp_path))

    assert [(f.id, f.status) for f in read.facts] == [(f.id, FactStatus.OK) for f in read.facts]
