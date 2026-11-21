"""The fact catalog of the project review and its JSON Schema (#4692): the loader refuses a fact
with no id or section, an unknown section, placeholder or fact, two facts with one id, a Service
metric query with no `{repo}` and a query by node, and fills the placeholders of a window."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from devops_cli.roadmap.project_review.catalog import (
    load_catalog,
    render_query,
    window_placeholders,
)

from devops_cli.exceptions.roadmap import RoadmapReviewError
from devops_cli.roadmap.project_review.data import ReviewWindow, WindowKind

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


def _load(tmp_path: Path, change: Any) -> None:
    """Load `VALID` after `change` edits a copy of it."""
    document = copy.deepcopy(VALID)
    change(document)
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    load_catalog(path)


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

    sent = render_query(template, window_placeholders(window, "example/project"))

    assert sent == ('sum(increase(devops_cli_service_jobs_total{repo="example/project"}[604800s]))')
    assert render_query("{start}..{end} {base} {head}", window_placeholders(window, "x/y")) == (
        f"2026-11-04T14:51:23Z..2026-11-11T14:51:23Z {'a' * 40} {'b' * 40}"
    )
