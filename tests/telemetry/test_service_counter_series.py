"""The label sets of the Service counters exist at zero from the start (#3495).

A labelled counter has no series until its first count, and `increase()` loses that first count,
so each pod of the Service starts each bounded label set at zero. The tests read the registry of
the process, as the `/metrics` scrape does, and start no thread.
"""

from __future__ import annotations

from datetime import UTC, datetime

from devops_cli.config.constants import (
    CONST_ROADMAP_WEBHOOK_EVENTS,
    CONST_SERVICE_EVENT_OTHER,
    CONST_SERVICE_METRIC_BUDGET_HOLDS,
    CONST_SERVICE_METRIC_CHAT_COMMANDS,
    CONST_SERVICE_METRIC_IMPLEMENT_FAILURES,
    CONST_SERVICE_METRIC_JOBS,
    CONST_SERVICE_METRIC_TRIGGERS,
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES,
    CONST_SERVICE_OUTCOME_ACCEPTED,
    CONST_SERVICE_OUTCOME_IGNORED,
    CONST_SERVICE_OUTCOME_NO_SUBSCRIBER,
    CONST_SERVICE_OUTCOME_REJECTED,
    CONST_SERVICE_OUTCOME_SELF,
    CONST_SERVICE_SOURCE_POLL,
    CONST_SERVICE_SOURCE_WEBHOOK,
)
from devops_cli.config.settings import GitHubAppConfig, ServiceConfig
from devops_cli.roadmap.failure import FailureClass
from devops_cli.server.routes.webhooks import create_webhook_router
from devops_cli.server.service import ServiceManager
from devops_cli.telemetry.metrics import GLOBAL_METRICS

REPOS = ["example/app", "example/tools"]


def _manager(repos: list[str]) -> ServiceManager:
    """A Service manager with two lanes of dummy jobs, which starts no thread. The registry of
    the process starts empty, so a series that another test counted is not read here."""
    GLOBAL_METRICS.reset()
    config = ServiceConfig(repos=repos, github_app=GitHubAppConfig(bot_login="test-bot[bot]"))
    now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)
    return ServiceManager(
        config=config,
        secrets={},
        jobs={"status": lambda _batch: None, "model": lambda _batch: None},
        clock=lambda: now,
        sleep_func=lambda _seconds: _noop(),
    )


async def _noop() -> None:
    """A sleep that returns at once: the manager's tick loop never runs in these tests."""


def _series(name: str) -> dict[frozenset[tuple[str, str]], float]:
    """Each sample of the counter `name` in the registry, keyed by its label set."""
    return {
        frozenset(sample.labels.items()): sample.value
        for family in GLOBAL_METRICS.registry.collect()
        for sample in family.samples
        if sample.name == name
    }


def _label_values(name: str, label: str) -> set[str]:
    """Every value of the label `label` of the counter `name` in the registry."""
    return {value for labels in _series(name) for key, value in labels if key == label}


def test_each_failure_class_exists_at_zero_for_each_repository() -> None:
    _manager(REPOS)

    series = _series(CONST_SERVICE_METRIC_IMPLEMENT_FAILURES)
    expected = {
        frozenset({("class", klass.value), ("repo", repo)}): 0.0
        for klass in FailureClass
        for repo in REPOS
    }

    assert {key: series.get(key) for key in expected} == expected


def test_repo_label_holds_only_service_repos() -> None:
    _manager(REPOS)

    assert _label_values(CONST_SERVICE_METRIC_IMPLEMENT_FAILURES, "repo") == set(REPOS)


def test_jobs_total_carries_row_label() -> None:
    _manager(REPOS)

    label_sets = [dict(key) for key in _series(CONST_SERVICE_METRIC_JOBS)]

    assert all(set(labels) == {"repo", "lane", "row", "result"} for labels in label_sets)
    assert {"repo": "example/app", "lane": "status", "row": "metrics", "result": "success"} in (
        label_sets
    )


def test_jobs_total_exists_at_zero_for_each_result_of_a_row() -> None:
    _manager(REPOS)

    series = _series(CONST_SERVICE_METRIC_JOBS)
    expected = {
        frozenset(
            {("repo", "example/app"), ("lane", "status"), ("row", "metrics"), ("result", result)}
        )
        for result in ("success", "error", "stopped")
    }

    assert {key: series.get(key) for key in expected} == dict.fromkeys(expected, 0.0)


def test_webhook_counter_exists_at_zero_for_each_declared_event_and_outcome() -> None:
    create_webhook_router(_manager(REPOS))

    series = _series(CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES)
    outcomes = (
        CONST_SERVICE_OUTCOME_ACCEPTED,
        CONST_SERVICE_OUTCOME_IGNORED,
        CONST_SERVICE_OUTCOME_REJECTED,
        CONST_SERVICE_OUTCOME_NO_SUBSCRIBER,
        CONST_SERVICE_OUTCOME_SELF,
    )
    expected = {
        frozenset({("provider", "github"), ("event", event), ("outcome", outcome)})
        for event in (*CONST_ROADMAP_WEBHOOK_EVENTS, CONST_SERVICE_EVENT_OTHER)
        for outcome in outcomes
    }

    assert {key: series.get(key) for key in expected} == dict.fromkeys(expected, 0.0)


def test_trigger_counter_exists_at_zero_for_each_repository_and_source() -> None:
    _manager(REPOS)

    series = _series(CONST_SERVICE_METRIC_TRIGGERS)
    expected = {
        frozenset({("repo", repo), ("source", source)})
        for repo in REPOS
        for source in (CONST_SERVICE_SOURCE_WEBHOOK, CONST_SERVICE_SOURCE_POLL)
    }

    assert {key: series.get(key) for key in expected} == dict.fromkeys(expected, 0.0)


def test_chat_command_counter_exists_at_zero_for_each_result() -> None:
    _manager(REPOS)

    series = _series(CONST_SERVICE_METRIC_CHAT_COMMANDS)
    expected = {
        frozenset({("command", "/roadmap"), ("result", result)})
        for result in ("usage", "status", "unknown_repo", "error")
    }

    assert {key: series.get(key) for key in expected} == dict.fromkeys(expected, 0.0)


def test_budget_hold_counter_exists_at_zero() -> None:
    """The hold counter has no label, and it has no series until its first count without a
    prime, so its first hold does not show in `increase()`."""
    _manager(REPOS)

    assert _series(CONST_SERVICE_METRIC_BUDGET_HOLDS) == {frozenset(): 0.0}
