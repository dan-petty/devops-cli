"""The fact catalog of the project review and its JSON Schema (#4692): the loader refuses a fact
with no id or section, an unknown section, placeholder or fact, two facts with one id, a Service
metric query with no `{repo}`, a query by node, a rows fact by namespace or pod outside the
project namespaces (#6615), a base metric that the query does not read, a `not_before` that is not
UTC and a `no_series_reason` with a base (#6612); fills the placeholders of a window; gives the
stage SLI by the outcomes of the stage items; and counts the runner Jobs that start in the window
(#6612)."""

from __future__ import annotations

import copy
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.exceptions.roadmap import RoadmapReviewError
from devops_cli.roadmap.project_review.catalog import (
    Catalog,
    Shape,
    load_catalog,
    render_query,
    window_placeholders,
)
from devops_cli.roadmap.project_review.data import ReviewWindow, WindowKind
from tests.support.promtool import promtool

NAMESPACES = ("devops", "llm")
WINDOW = ReviewWindow(
    kind=WindowKind.PERIOD,
    id="w",
    base_sha="a" * 40,
    head_sha="b" * 40,
    start=datetime(2026, 11, 4, 14, 51, 23, tzinfo=UTC),
    end=datetime(2026, 11, 11, 14, 51, 23, tzinfo=UTC),
    previous_id=None,
)
VALKEY_PODS = 'max by (namespace, pod) (redis_memory_max_bytes{namespace=~"{namespaces}"} == 0)'
# A `by (...)` or `on (...)` clause that names a workload label, and a positive namespace matcher.
WORKLOAD_GROUPING = re.compile(r"\b(?:by|on)\s*\([^)]*\b(?:namespace|pod)\b")
POSITIVE_NAMESPACE = re.compile(r'\bnamespace\s*=~?\s*"')
STAGE = 'sum(increase(devops_cli_service_jobs_total{{row="stage"{repo}}}[{{range}}]))'
VALID: dict[str, Any] = {
    "version": 1,
    "sections": [{"id": "service", "title": "Service"}, {"id": "activity", "title": "Activity"}],
    "readers": {"prometheus": {"retention": "30d", "requires": ["setting:prometheus.url"]}},
    "facts": [
        {
            "id": "prometheus.example",
            "reader": "prometheus",
            "section": "service",
            "query": STAGE.format(repo=', repo="{repo}"'),
            "shape": "scalar",
            "unit": "runs",
            "definition": "The stage rounds of the repository.",
        },
        {
            "id": "github.example",
            "reader": "github",
            "section": "activity",
            "query": "repos/{repo}/releases",
            "value": "length",
            "unit": "releases",
            "definition": "The releases.",
        },
    ],
    "disagreements": [],
}


def _load(tmp_path: Path, change: Any) -> Catalog:
    """Load `VALID` after `change` edits a copy of it."""
    document = copy.deepcopy(VALID)
    change(document)
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return load_catalog(path)


def _refusal(tmp_path: Path, change: Any) -> str:
    with pytest.raises(RoadmapReviewError) as raised:
        _load(tmp_path, change)
    return str(raised.value)


def test_a_valid_catalog_loads_its_sections_readers_and_facts(tmp_path: Path) -> None:
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(VALID), encoding="utf-8")

    catalog = load_catalog(path)

    assert (
        [section.id for section in catalog.sections],
        [fact.id for fact in catalog.facts],
        catalog.readers["prometheus"].retention_days,
        catalog.readers["prometheus"].requires,
    ) == (
        ["service", "activity"],
        ["prometheus.example", "github.example"],
        30,
        ("setting:prometheus.url",),
    )


def test_a_fact_with_no_id_names_its_index_and_the_field(tmp_path: Path) -> None:
    text = _refusal(tmp_path, lambda doc: doc["facts"][1].pop("id"))

    assert "fact 2" in text
    assert "`id`" in text


def test_a_fact_with_no_section_names_the_fact_and_the_field(tmp_path: Path) -> None:
    text = _refusal(tmp_path, lambda doc: doc["facts"][0].pop("section"))

    assert "prometheus.example" in text
    assert "`section`" in text


def test_a_section_that_the_catalog_does_not_list_is_refused(tmp_path: Path) -> None:
    text = _refusal(tmp_path, lambda doc: doc["facts"][0].update(section="unknown"))

    assert "prometheus.example" in text
    assert "unknown" in text


def test_two_facts_with_one_id_are_refused(tmp_path: Path) -> None:
    text = _refusal(tmp_path, lambda doc: doc["facts"][1].update(id="prometheus.example"))

    assert "prometheus.example" in text
    assert "two facts" in text


def test_a_disagreement_that_names_an_unknown_fact_is_refused(tmp_path: Path) -> None:
    pair = {
        "id": "spend",
        "left": "prometheus.example",
        "right": "prometheus.unknown",
        "tolerance": 0.1,
        "definition": "Two counters of one spend.",
    }
    text = _refusal(tmp_path, lambda doc: doc["disagreements"].append(pair))

    assert "spend" in text
    assert "prometheus.unknown" in text


def test_an_unknown_placeholder_names_the_fact_and_the_query(tmp_path: Path) -> None:
    text = _refusal(tmp_path, lambda doc: doc["facts"][1].update(query="repos/{owner}/releases"))

    assert "github.example" in text
    assert "`query`" in text
    assert "{owner}" not in text


def test_a_service_metric_query_with_no_repo_names_the_fact(tmp_path: Path) -> None:
    query = 'sum(increase(devops_cli_service_jobs_total{row="stage"}[{range}]))'

    text = _refusal(
        tmp_path, lambda doc: doc["facts"][0].update(id="prometheus.stage_runs", query=query)
    )

    assert "prometheus.stage_runs" in text
    assert "{repo}" in text


@pytest.mark.parametrize(
    "query",
    [
        'sum(increase(devops_cli_service_jobs_total{row="stage", result="success"}[{range}])) / '
        'sum(increase(devops_cli_service_jobs_total{repo="{repo}", row="stage"}[{range}]))',
        'sum(devops_cli_service_jobs_total) / sum(devops_cli_service_jobs_total{repo="{repo}"})',
        'sum(devops_cli_service_jobs_total{repo="x", row="{repo}"})',
    ],
)
def test_each_service_metric_selector_of_a_query_must_name_the_repository(
    tmp_path: Path, query: str
) -> None:
    """A ratio whose numerator has no repository matcher adds the repositories together, the error
    that gave the SLO 1 of the Service 0.927 for 0.372 (#4692)."""
    text = _refusal(
        tmp_path, lambda doc: doc["facts"][0].update(id="prometheus.service_slo1", query=query)
    )

    assert ("prometheus.service_slo1" in text, "devops_cli_service_jobs_total" in text) == (
        True,
        True,
    )


def test_a_base_metric_of_the_service_must_name_the_repository(tmp_path: Path) -> None:
    text = _refusal(
        tmp_path,
        lambda doc: doc["facts"][0].update(base='devops_cli_service_jobs_total{row="stage"}'),
    )

    assert ("prometheus.example" in text, "`base`" in text) == (True, True)


def test_a_github_fact_with_a_base_metric_is_refused(tmp_path: Path) -> None:
    text = _refusal(tmp_path, lambda doc: doc["facts"][1].update(base="up"))

    assert ("github.example" in text, "`base`" in text) == (True, True)


def test_a_query_by_node_names_the_fact(tmp_path: Path) -> None:
    query = 'sum by (node) (kube_pod_container_resource_requests{resource="memory"})'

    text = _refusal(
        tmp_path,
        lambda doc: doc["facts"][0].update(id="prometheus.memory_requests", query=query),
    )

    assert "prometheus.memory_requests" in text
    assert "`query`" in text


def test_a_github_fact_with_no_value_program_is_refused(tmp_path: Path) -> None:
    text = _refusal(tmp_path, lambda doc: doc["facts"][1].pop("value"))

    assert "github.example" in text
    assert "`value`" in text


def test_the_placeholders_of_a_seven_day_window_keep_the_label_braces() -> None:
    window = ReviewWindow(
        kind=WindowKind.PERIOD,
        id="w",
        base_sha="a" * 40,
        head_sha="b" * 40,
        start=datetime(2026, 11, 4, 14, 51, 23, tzinfo=UTC),
        end=datetime(2026, 11, 11, 14, 51, 23, tzinfo=UTC),
        previous_id=None,
    )
    template = 'sum(increase(devops_cli_service_jobs_total{repo="{repo}"}[{range}]))'

    sent = render_query(template, window_placeholders(window, "example/project", NAMESPACES))

    assert sent == ('sum(increase(devops_cli_service_jobs_total{repo="example/project"}[604800s]))')
    assert render_query(
        "{start}..{end} {base} {head}", window_placeholders(window, "x/y", NAMESPACES)
    ) == (f"2026-11-04T14:51:23Z..2026-11-11T14:51:23Z {'a' * 40} {'b' * 40}")


def test_the_name_slug_placeholder_matches_the_job_names_of_the_repository() -> None:
    """kube-state-metrics gives a Job by its name only, `devops-cli-<row>-<name slug>-...`."""
    window = ReviewWindow(
        kind=WindowKind.PERIOD,
        id="w",
        base_sha="a" * 40,
        head_sha="b" * 40,
        start=datetime(2026, 11, 4, 14, 51, 23, tzinfo=UTC),
        end=datetime(2026, 11, 11, 14, 51, 23, tzinfo=UTC),
        previous_id=None,
    )
    template = 'kube_job_status_start_time{job_name=~"devops-cli-implement-{name_slug}-.+"}'

    sent = render_query(template, window_placeholders(window, "Example/My.Project", NAMESPACES))

    assert sent == 'kube_job_status_start_time{job_name=~"devops-cli-implement-my-project-.+"}'


def test_a_rows_fact_in_the_project_namespaces_loads(tmp_path: Path) -> None:
    def add(doc: dict[str, Any]) -> None:
        doc["facts"][0].update(id="prometheus.valkey_pods", query=VALKEY_PODS, shape="rows")

    catalog = _load(tmp_path, add)

    assert catalog.facts[0].query == VALKEY_PODS


def test_the_namespaces_placeholder_gives_the_project_namespaces_as_one_alternation() -> None:
    sent = render_query(VALKEY_PODS, window_placeholders(WINDOW, "example/project", NAMESPACES))

    assert sent == 'max by (namespace, pod) (redis_memory_max_bytes{namespace=~"devops|llm"} == 0)'


def _rows_fact(fact_id: str, query: str) -> Any:
    return lambda doc: doc["facts"][0].update(id=fact_id, query=query, shape="rows")


def test_a_rows_fact_by_namespace_with_no_matcher_names_the_fact_and_the_label(
    tmp_path: Path,
) -> None:
    query = "max by (namespace, pod) (redis_memory_max_bytes == 0)"

    text = _refusal(tmp_path, _rows_fact("prometheus.valkey_pods", query))

    assert ("prometheus.valkey_pods" in text, "`query`" in text, "`namespace`" in text) == (
        True,
        True,
        True,
    )


def test_a_rows_fact_that_joins_on_pod_with_no_matcher_names_the_label(tmp_path: Path) -> None:
    query = (
        "sum by (resource) (kube_pod_container_resource_requests * on (pod) group_left() "
        "kube_pod_status_ready)"
    )

    text = _refusal(tmp_path, _rows_fact("prometheus.requests", query))

    assert ("prometheus.requests" in text, "`pod`" in text) == (True, True)


def test_a_negative_namespace_matcher_does_not_scope_a_rows_fact(tmp_path: Path) -> None:
    query = 'max by (namespace, pod) (redis_memory_max_bytes{namespace!="kube-system"} == 0)'

    text = _refusal(tmp_path, _rows_fact("prometheus.valkey_pods", query))

    assert "prometheus.valkey_pods" in text


def test_a_scalar_fact_by_namespace_loads_because_its_answer_has_no_label(tmp_path: Path) -> None:
    query = "count(count by (namespace, pod) (kube_pod_info))"

    catalog = _load(tmp_path, lambda doc: doc["facts"][0].update(id="prometheus.pods", query=query))

    assert (catalog.facts[0].shape, catalog.facts[0].query) == (Shape.SCALAR, query)


def test_a_rows_fact_whose_base_reads_all_namespaces_names_the_base(tmp_path: Path) -> None:
    """The probe of the base reads the namespaces of the query, else a series of another project
    makes an empty answer of the project `ok` (#6615)."""

    def add(doc: dict[str, Any]) -> None:
        doc["facts"][0].update(
            id="prometheus.valkey_pods",
            query=VALKEY_PODS,
            shape="rows",
            base="redis_memory_max_bytes",
        )

    text = _refusal(tmp_path, add)

    assert ("prometheus.valkey_pods" in text, "`base`" in text, "`namespace`" in text) == (
        True,
        True,
        True,
    )


def test_a_rows_fact_whose_base_holds_the_project_namespaces_loads(tmp_path: Path) -> None:
    base = 'redis_memory_max_bytes{namespace=~"{namespaces}"}'

    def add(doc: dict[str, Any]) -> None:
        doc["facts"][0].update(
            id="prometheus.valkey_pods", query=VALKEY_PODS, shape="rows", base=base
        )

    catalog = _load(tmp_path, add)

    assert catalog.facts[0].base == base


def _cuts(query: str = "sum(increase(x_cuts_total[{range}]))", **fields: str) -> Any:
    """Make the first fact `prometheus.cuts` with `query`, the base `x_calls_total` and `fields`."""
    return lambda doc: doc["facts"][0].update(
        id="prometheus.cuts", query=query, base="x_calls_total", **fields
    )


def test_a_base_metric_that_the_query_does_not_read_names_the_fact_and_base_reason(
    tmp_path: Path,
) -> None:
    """A probe of another metric makes an empty answer `ok` for a window in which the queried
    metric did not exist (#6612)."""
    text = _refusal(tmp_path, _cuts())

    assert ("prometheus.cuts" in text, "x_calls_total" in text, "`base_reason`" in text) == (
        True,
        True,
        True,
    )


def test_a_base_metric_of_another_metric_with_a_reason_loads(tmp_path: Path) -> None:
    catalog = _load(tmp_path, _cuts(base_reason="The cut counter has no series before a cut."))

    assert (catalog.facts[0].base, catalog.facts[0].base_reason) == (
        "x_calls_total",
        "The cut counter has no series before a cut.",
    )


def test_a_base_metric_inside_a_longer_metric_name_of_the_query_is_refused(
    tmp_path: Path,
) -> None:
    text = _refusal(tmp_path, _cuts("sum(increase(x_calls_total_bucket[{range}]))"))

    assert "prometheus.cuts" in text


def test_a_base_reason_with_no_base_names_the_fact_and_the_field(tmp_path: Path) -> None:
    text = _refusal(tmp_path, lambda doc: doc["facts"][0].update(base_reason="A reason."))

    assert ("prometheus.example" in text, "`base_reason`" in text, "`base`" in text) == (
        True,
        True,
        True,
    )


def test_the_shipped_catalog_scopes_each_rows_fact_that_names_workloads() -> None:
    values = window_placeholders(WINDOW, "example/project", ("devops",))
    catalog = load_catalog()
    grouped = [
        fact
        for fact in catalog.facts
        if fact.shape is Shape.ROWS and WORKLOAD_GROUPING.search(fact.query)
    ]

    unscoped = [
        f"{fact.id} {field}"
        for fact in grouped
        for field, text in (("query", fact.query), ("base", fact.base))
        if text is not None and not POSITIVE_NAMESPACE.search(render_query(text, values))
    ]

    assert (bool(grouped), unscoped) == (True, [])
    filled = [render_query(fact.query, values) for fact in catalog.facts]
    assert [query for query in filled if "{namespaces}" in query] == []


def test_a_first_time_that_is_not_utc_names_the_fact_and_the_field(tmp_path: Path) -> None:
    text = _refusal(
        tmp_path, lambda doc: doc["facts"][0].update(not_before="2026-11-14T22:29:00+01:00")
    )

    assert (
        "prometheus.example" in text,
        "`not_before`" in text,
        "YYYY-MM-DDTHH:MM:SSZ" in text,
    ) == (
        True,
        True,
        True,
    )


def test_a_reason_of_a_missing_series_with_a_base_names_the_fact(tmp_path: Path) -> None:
    """A fact with a base names the base metric in the reason of an empty answer."""

    def add(doc: dict[str, Any]) -> None:
        doc["facts"][0].update(
            base='devops_cli_service_jobs_total{repo="{repo}"}', no_series_reason="A reason."
        )

    text = _refusal(tmp_path, add)

    assert ("prometheus.example" in text, "`no_series_reason`" in text, "`base`" in text) == (
        True,
        True,
        True,
    )


def _stage_items(repo: str, result: str, count: int) -> dict[str, str]:
    """A counter of stage items that adds `count` in the hour to 60m: its first sample in the
    range is 0 and its last is at the end, so `increase` gives `count` with no extrapolation."""
    return {
        "series": f'devops_cli_roadmap_stage_total{{repo="{repo}", result="{result}"}}',
        "values": f"0 0 {count}x59",
    }


@pytest.mark.live("promtool")
def test_the_stage_sli_is_the_share_of_good_stage_item_outcomes_of_the_repository(
    tmp_path: Path,
) -> None:
    """SLO 1 of the stage row counts the outcomes of the stage items (owner decision of
    2026-11-21 on #4692): `staged` and `needs_split` are good, `failed` and `degenerate` are bad,
    and a `skipped` item is not an outcome. 0 is a measured value; no outcome gives no value."""
    hour = ReviewWindow(
        kind=WindowKind.PERIOD,
        id="w",
        base_sha="a" * 40,
        head_sha="b" * 40,
        start=datetime(2026, 11, 21, tzinfo=UTC),
        end=datetime(2026, 11, 21, 1, tzinfo=UTC),
        previous_id=None,
    )
    [fact] = [fact for fact in load_catalog().facts if fact.id == "prometheus.stage_sli"]
    query = render_query(fact.query, window_placeholders(hour, "example/project", NAMESPACES))
    project = "example/project"
    groups = [
        (
            [
                _stage_items(project, "staged", 6),
                _stage_items(project, "needs_split", 2),
                _stage_items(project, "failed", 1),
                _stage_items(project, "degenerate", 1),
                _stage_items(project, "skipped", 5),
                _stage_items("example/other", "failed", 10),
            ],
            [{"labels": "{}", "value": 0.8}],
        ),
        ([_stage_items(project, "failed", 3)], [{"labels": "{}", "value": 0}]),
        ([_stage_items(project, "skipped", 5)], []),
    ]
    tests = [
        {
            "name": f"stage items {index}",
            "interval": "1m",
            "input_series": series,
            "promql_expr_test": [{"expr": query, "eval_time": "60m", "exp_samples": samples}],
        }
        for index, (series, samples) in enumerate(groups)
    ]
    unit_tests = tmp_path / "stage_sli.yaml"
    unit_tests.write_text(yaml.safe_dump({"tests": tests}, sort_keys=False), encoding="utf-8")

    result = promtool("test", "rules", unit_tests)

    assert result.returncode == 0, result.stdout + result.stderr


def _job_start(name: str, started: int, first_minute: int) -> dict[str, str]:
    """The start time gauge of the Job `name` that started at `started` (Unix seconds), as
    kube-state-metrics gives it from `first_minute` to the minute 120: the series stays after the
    Job ends, for the `ttlSecondsAfterFinished` of the Job."""
    return {
        "series": f'kube_job_status_start_time{{namespace="devops", job_name="{name}"}}',
        "values": " ".join(["_"] * first_minute + [str(started)] * (121 - first_minute)),
    }


@pytest.mark.live("promtool")
def test_the_runner_jobs_started_are_the_implement_jobs_that_start_in_the_window(
    tmp_path: Path,
) -> None:
    """`prometheus.runner_jobs_started` counts the implement Jobs of the repository that start in
    the window. A Job that started before the window still has a series in it for the
    `ttlSecondsAfterFinished` of the Job (24 h), so a count of the series in the window would
    count it too (#6612)."""
    hour = ReviewWindow(
        kind=WindowKind.PERIOD,
        id="w",
        base_sha="a" * 40,
        head_sha="b" * 40,
        start=datetime(1970, 1, 1, 1, tzinfo=UTC),
        end=datetime(1970, 1, 1, 2, tzinfo=UTC),
        previous_id=None,
    )
    [fact] = [fact for fact in load_catalog().facts if fact.id == "prometheus.runner_jobs_started"]
    query = render_query(fact.query, window_placeholders(hour, "example/project", NAMESPACES))
    before = _job_start("devops-cli-implement-project-11-aaaaaa", 1800, 0)
    groups = [
        (
            [
                before,
                _job_start("devops-cli-implement-project-12-bbbbbb", 5400, 90),
                _job_start("devops-cli-implement-other-13-cccccc", 5400, 90),
            ],
            [{"labels": "{}", "value": 1}],
        ),
        ([before], []),
    ]
    tests = [
        {
            "name": f"runner jobs {index}",
            "interval": "1m",
            "input_series": series,
            "promql_expr_test": [{"expr": query, "eval_time": "120m", "exp_samples": samples}],
        }
        for index, (series, samples) in enumerate(groups)
    ]
    unit_tests = tmp_path / "runner_jobs.yaml"
    unit_tests.write_text(yaml.safe_dump({"tests": tests}, sort_keys=False), encoding="utf-8")

    result = promtool("test", "rules", unit_tests)

    assert result.returncode == 0, result.stdout + result.stderr
