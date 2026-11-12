"""`devops roadmap eval grades` (#5165): the command layer of the job grade report.

The grade rules are tested in `tests/roadmap/test_job_grade.py` and the report on recorded Loki
replies in `tests/roadmap/test_job_grade_report.py`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from devops_cli.github.repo_ref import RepoRef
from devops_cli.roadmap.job_grade_report import GradeWindow, plan_grade_queries
from tests.support.fakes.http import WebFake
from tests.support.roadmap_job_grades import LOKI_URL, QUERY_PATH, serve_grade_replies

Cli = Callable[..., Any]


def test_the_dry_run_sends_no_request_and_prints_each_query(
    cli: Cli, config: Callable[..., Path], web: WebFake
) -> None:
    """`--dry-run` sends 0 requests and prints each LogQL query with the Loki of `loki.url`."""
    config(loki={"url": LOKI_URL})

    result = cli("roadmap", "eval", "grades", "--dry-run")

    assert (result.exit_code, web.sent) == (0, [])
    assert [
        query.key
        for query in plan_grade_queries(GradeWindow.D7)
        if f"GET {LOKI_URL}{QUERY_PATH}?query={query.expr}" not in result.output
    ] == []


def test_json_gives_one_object_for_each_workflow_and_repository(
    cli: Cli, config: Callable[..., Path], web: WebFake
) -> None:
    """`--format json` prints the report with the window, the Loki address and each row."""
    config(loki={"url": LOKI_URL})
    serve_grade_replies(web)

    result = cli("roadmap", "eval", "grades", "--format", "json")

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert (report["window"], report["repo"], report["loki_url"]) == ("7d", None, LOKI_URL)
    assert [(row["job"], row["repo"], row["measure"]["grade"]) for row in report["workflows"]] == [
        ("stage", "example/app", "too few"),
        ("stage", "example/infra", "too few"),
        ("implement", "example/app", "too few"),
        ("refine", "example/app", "too few"),
        ("refine_judge", None, "too few"),
        ("alternatives", None, "too few"),
        ("intake", "example/app", "60"),
        ("fix_plan", None, "too few"),
    ]


def test_the_options_choose_the_window_the_repository_and_the_loki(cli: Cli, web: WebFake) -> None:
    """`--window`, `--repo` and `--loki-url` reach the queries and the address."""
    serve_grade_replies(web, window=GradeWindow.H6, repo=RepoRef("example/app"))

    result = cli(
        "roadmap",
        "eval",
        "grades",
        "--window",
        "6h",
        "--repo",
        "example/app",
        "--loki-url",
        LOKI_URL,
        "--json",
    )

    report = json.loads(result.output)
    assert (report["window"], report["repo"], len(web.sent)) == ("6h", "example/app", 12)


def test_a_repository_that_is_no_owner_and_name_is_refused(cli: Cli, web: WebFake) -> None:
    """`--repo` takes `owner/name` and refuses another text before any request."""
    result = cli("roadmap", "eval", "grades", "--repo", "not a repo", "--dry-run")

    assert (result.exit_code != 0, web.sent) == (True, [])
