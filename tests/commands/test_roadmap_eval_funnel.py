"""Command tests for `devops roadmap eval funnel` (#5494)."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.roadmap.job_result import RoadmapJob, log_job_result
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.http import WebFake
from tests.support.fakes.loki import LokiFake
from tests.support.roadmap_job_grades import LOKI_URL, STAGE_STREAM

Cli = Callable[..., Any]

_REPO = "example/app"


def _hold_core_quota() -> None:
    get_github_rate_limiter().update_quota(
        "core", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
    )


def _issue_item(
    number: int, *, state: str = "closed", updated_at: str = "2026-11-18T12:00:00Z"
) -> dict[str, Any]:
    return {
        "number": number,
        "title": f"Item {number}",
        "state": state,
        "created_at": "2026-11-17T08:00:00Z",
        "updated_at": updated_at,
    }


def _pull_item(
    number: int,
    title: str,
    head_ref: str,
    *,
    created_at: str,
    updated_at: str,
    draft: bool = False,
    state: str = "closed",
    merged_at: str | None = None,
) -> dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "state": state,
        "draft": draft,
        "head": {"ref": head_ref},
        "created_at": created_at,
        "updated_at": updated_at,
        "merged_at": merged_at,
    }


def test_dry_run_prints_queries_and_sends_no_request(
    cli: Cli, config: Callable[..., Path], web: WebFake, clock: ClockFake
) -> None:
    """`--dry-run` validates inputs, sends 0 HTTP requests, and prints planned queries."""
    config(loki={"url": LOKI_URL})
    clock.move_to(datetime(2026, 11, 20, 12, 0, tzinfo=UTC))

    result = cli(
        "roadmap",
        "eval",
        "funnel",
        "--since",
        "2026-11-01",
        "--repo",
        _REPO,
        "--dry-run",
    )

    assert (result.exit_code, web.sent) == (0, [])
    assert f"/repos/{_REPO}/issues" in result.output
    assert f"/repos/{_REPO}/issues/<number>/timeline" in result.output
    assert "/loki/api/v1/query" in result.output


def test_invalid_repo_refused_before_any_request(cli: Cli, web: WebFake) -> None:
    result = cli(
        "roadmap",
        "eval",
        "funnel",
        "--since",
        "2026-11-01",
        "--repo",
        "not a repo",
        "--dry-run",
    )
    assert (result.exit_code != 0, web.sent) == (True, [])


def test_invalid_since_refused_before_any_request(cli: Cli, web: WebFake) -> None:
    result = cli(
        "roadmap",
        "eval",
        "funnel",
        "--since",
        "not-a-date",
        "--repo",
        _REPO,
        "--dry-run",
    )
    assert (result.exit_code != 0, web.sent) == (True, [])


def test_missing_service_repos_refused_before_any_request(
    cli: Cli, config: Callable[..., Path], web: WebFake
) -> None:
    config(loki={"url": LOKI_URL}, service={"repos": []})
    result = cli("roadmap", "eval", "funnel", "--since", "2026-11-01")
    assert (result.exit_code != 0, web.sent) == (True, [])
    assert "service.repos" in result.output


def test_cli_json_reports_cohorts_paths_loki_and_missing_lines(
    cli: Cli,
    config: Callable[..., Path],
    github_api: GitHubApiFake,
    clock: ClockFake,
    caplog: Any,
) -> None:
    """End-to-end CLI test over `GitHubApiFake` and `LokiFake` for `G1`, `continue`, and missing
    result lines."""
    config(loki={"url": LOKI_URL}, service={"repos": [_REPO]})
    now = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    clock.move_to(now)
    _hold_core_quota()

    loki = LokiFake()
    with caplog.at_level("INFO", logger="devops_cli.roadmap.job_result"):
        caplog.clear()
        log_job_result(
            RoadmapJob.STAGE,
            _REPO,
            10,
            "staged",
            counts={"tokens": 1000, "cost_usd_micros": 2000},
        )
    line = next(r.getMessage() for r in caplog.records if "roadmap job result:" in r.getMessage())
    loki.push(STAGE_STREAM, line, age=timedelta(hours=2))
    github_api.serve(loki._answer)

    github_api.route(
        "GET",
        f"/repos/{_REPO}/issues?state=all&sort=updated&direction=desc&since=2026-11-01T00:00:00Z&per_page=100",
        github_json([_issue_item(10), _issue_item(11)]),
    )
    github_api.route(
        "GET",
        f"/repos/{_REPO}/pulls?state=all&sort=updated&direction=desc&per_page=100",
        github_json(
            [
                _pull_item(
                    200,
                    "docs(spec): plan #10 One",
                    "docs/openspec/10-one",
                    created_at="2026-11-17T12:00:00Z",
                    updated_at="2026-11-17T13:00:00Z",
                    merged_at="2026-11-17T13:00:00Z",
                ),
                _pull_item(
                    201,
                    "feat(roadmap): One",
                    "feat/10-one",
                    created_at="2026-11-17T14:00:00Z",
                    updated_at="2026-11-17T17:00:00Z",
                    merged_at="2026-11-17T17:00:00Z",
                ),
                _pull_item(
                    202,
                    "docs(spec): plan #11 Two",
                    "docs/openspec/11-two",
                    created_at="2026-11-18T12:00:00Z",
                    updated_at="2026-11-18T12:30:00Z",
                    state="open",
                ),
                _pull_item(
                    203,
                    "feat(roadmap): Two",
                    "docs/openspec/11-two",
                    created_at="2026-11-18T13:00:00Z",
                    updated_at="2026-11-18T16:00:00Z",
                    merged_at="2026-11-18T16:00:00Z",
                ),
            ]
        ),
    )
    github_api.route(
        "GET",
        f"/repos/{_REPO}/issues/10/timeline?per_page=100",
        github_json(
            [
                {
                    "event": "labeled",
                    "created_at": "2026-11-17T09:00:00Z",
                    "label": {"name": "status/new"},
                },
                {
                    "event": "labeled",
                    "created_at": "2026-11-17T10:00:00Z",
                    "label": {"name": "status/ready"},
                },
                {
                    "event": "cross-referenced",
                    "created_at": "2026-11-17T12:00:00Z",
                    "source": {
                        "type": "issue",
                        "issue": {
                            "number": 200,
                            "title": "docs(spec): plan #10 One",
                            "state": "closed",
                            "draft": False,
                            "created_at": "2026-11-17T12:00:00Z",
                            "pull_request": {"merged_at": "2026-11-17T13:00:00Z"},
                        },
                    },
                },
                {
                    "event": "cross-referenced",
                    "created_at": "2026-11-17T14:00:00Z",
                    "source": {
                        "type": "issue",
                        "issue": {
                            "number": 201,
                            "title": "feat(roadmap): One",
                            "state": "closed",
                            "draft": False,
                            "created_at": "2026-11-17T14:00:00Z",
                            "pull_request": {"merged_at": "2026-11-17T17:00:00Z"},
                        },
                    },
                },
            ]
        ),
    )
    github_api.route(
        "GET",
        f"/repos/{_REPO}/issues/11/timeline?per_page=100",
        github_json(
            [
                {
                    "event": "labeled",
                    "created_at": "2026-11-18T09:00:00Z",
                    "label": {"name": "status/new"},
                },
                {
                    "event": "labeled",
                    "created_at": "2026-11-18T10:00:00Z",
                    "label": {"name": "status/ready"},
                },
                {
                    "event": "cross-referenced",
                    "created_at": "2026-11-18T12:00:00Z",
                    "source": {
                        "type": "issue",
                        "issue": {
                            "number": 202,
                            "title": "docs(spec): plan #11 Two",
                            "state": "open",
                            "draft": False,
                            "created_at": "2026-11-18T12:00:00Z",
                            "pull_request": {"merged_at": None},
                        },
                    },
                },
                {
                    "event": "cross-referenced",
                    "created_at": "2026-11-18T13:00:00Z",
                    "source": {
                        "type": "issue",
                        "issue": {
                            "number": 203,
                            "title": "feat(roadmap): Two",
                            "state": "closed",
                            "draft": False,
                            "created_at": "2026-11-18T13:00:00Z",
                            "pull_request": {"merged_at": "2026-11-18T16:00:00Z"},
                        },
                    },
                },
            ]
        ),
    )
    github_api.route(
        "GET",
        f"/repos/{_REPO}/issues/201/timeline?per_page=100",
        github_json([{"event": "ready_for_review", "created_at": "2026-11-17T15:00:00Z"}]),
    )
    github_api.route(
        "GET",
        f"/repos/{_REPO}/issues/203/timeline?per_page=100",
        github_json([{"event": "ready_for_review", "created_at": "2026-11-18T14:00:00Z"}]),
    )

    result = cli("roadmap", "eval", "funnel", "--since", "2026-11-01", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["missing_result_lines"] == 1
    assert len(payload["cohorts"]) == 1
    cohort = payload["cohorts"][0]
    assert (cohort["cohort"], cohort["items_count"], cohort["missing_result_lines"]) == (
        "2026-W47",
        2,
        1,
    )
    assert {item["item"]: item["path"] for item in cohort["items"]} == {10: "G1", 11: "continue"}
    assert {item["item"]: item["new_to_staged_tokens"] for item in cohort["items"]} == {
        10: 1000,
        11: 0,
    }
    assert any(req.url.path.endswith("/issues/10/timeline") for req in github_api.sent)


def test_cli_text_report_with_explicit_repo_and_empty_cohorts(
    cli: Cli,
    config: Callable[..., Path],
    github_api: GitHubApiFake,
    clock: ClockFake,
) -> None:
    """Explicit `--repo` without `--json` renders human-readable text output."""
    config(loki={"url": LOKI_URL})
    clock.move_to(datetime(2026, 11, 20, 12, 0, tzinfo=UTC))
    _hold_core_quota()

    loki = LokiFake()
    github_api.serve(loki._answer)
    github_api.route(
        "GET",
        f"/repos/{_REPO}/issues?state=all&sort=updated&direction=desc&since=2026-11-01T00:00:00Z&per_page=100",
        github_json([]),
    )

    result = cli("roadmap", "eval", "funnel", "--since", "2026-11-01", "--repo", _REPO)

    assert result.exit_code == 0, result.output
    assert _REPO in result.output
    assert "No cohort items" in result.output
