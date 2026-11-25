"""`devops roadmap eval grades` (#5165): the command layer of the job grade report, and the
verdicts of the bot pull requests (#5968).

The grade rules are tested in `tests/roadmap/test_job_grade.py`, the report on recorded Loki
replies in `tests/roadmap/test_job_grade_report.py`, and the verdicts in
`tests/roadmap/test_pr_verdict.py`. A test that reads Loki and GitHub serves both on the fake
GitHub API, because a test cannot ask for `web` and `github_api` together.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from devops_cli.github.repo_ref import RepoRef
from devops_cli.roadmap.job_grade_report import GradeWindow, plan_grade_queries
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.http import WebFake
from tests.support.roadmap_job_grades import (
    GRADES_REPO,
    LOKI_URL,
    QUERY_PATH,
    VERDICT_NOW,
    hold_graphql_quota,
    pull_node,
    route_grade_replies,
    serve_grade_replies,
)

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
        ("fix_checks", None, "too few"),
        ("retitle", None, "too few"),
        ("review", None, "too few"),
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
    assert (report["window"], report["repo"], len(web.sent)) == ("6h", "example/app", 13)


def test_a_repository_that_is_no_owner_and_name_is_refused(cli: Cli, web: WebFake) -> None:
    """`--repo` takes `owner/name` and refuses another text before any request."""
    result = cli("roadmap", "eval", "grades", "--repo", "not a repo", "--dry-run")

    assert (result.exit_code != 0, web.sent) == (True, [])


def _plan(number: int, *labels: str) -> dict[str, Any]:
    return pull_node(number, f"docs(spec): plan #{number} Add the part", labels)


def _verdict_replies(github_api: GitHubApiFake, *nodes: dict[str, Any]) -> None:
    hold_graphql_quota()
    github_api.route(
        "POST",
        "/graphql",
        github_json(
            {
                "data": {
                    "search": {
                        "issueCount": len(nodes),
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": list(nodes),
                    }
                }
            }
        ),
    )


def _graphql_searches(github_api: GitHubApiFake) -> list[str]:
    return [
        json.loads(request.content)["variables"]["search"]
        for request in github_api.sent
        if request.url.path == "/graphql"
    ]


def _bot_pulls(github_api: GitHubApiFake) -> None:
    """Six plans with the first verdicts mergeable, mergeable, needs fix, discard plan, issue
    changed and none; one delivery that needs a fix, and one whose first verdict label is the
    label of a plan."""
    _verdict_replies(
        github_api,
        _plan(1, "type/docs", "verdict/mergeable"),
        _plan(2, "verdict/mergeable", "verdict/issue-changed"),
        _plan(3, "verdict/fix-plan", "verdict/mergeable"),
        _plan(4, "verdict/discard-plan"),
        _plan(5, "verdict/issue-changed"),
        _plan(6, "type/docs"),
        pull_node(7, "feat(roadmap): Add the part", ("type/feature", "verdict/fix-plan")),
        pull_node(8, "fix(roadmap): Mend the part", ("verdict/fix-implementation",)),
    )


def test_the_report_scores_the_first_verdict_of_each_bot_pull_request(
    cli: Cli, config: Callable[..., Path], github_api: GitHubApiFake, clock: ClockFake
) -> None:
    """The stage row gives the verdicts of the plans and the score (2 + 0.5) / 4; the implement row
    scores the delivery that needs a fix, and counts the delivery with a plan label as unscored."""
    config(loki={"url": LOKI_URL}, service={"github_app": {"slug": "example-bot"}})
    clock.move_to(VERDICT_NOW)
    route_grade_replies(github_api, repo=RepoRef(GRADES_REPO))
    _bot_pulls(github_api)

    result = cli("roadmap", "eval", "grades", "--repo", GRADES_REPO, "--format", "json")

    assert result.exit_code == 0, result.output
    assert _graphql_searches(github_api) == [
        "is:pr author:app/example-bot updated:>=2026-11-02T12:00:00Z repo:example/app"
    ]
    report = json.loads(result.output)
    assert (report["verdict_bot"], report["verdict_partial_score"]) == ("example-bot[bot]", 0.5)
    rows = {(row["job"], row["repo"]): row["verdicts"] for row in report["workflows"]}
    stage, implement = rows["stage", GRADES_REPO], rows["implement", GRADES_REPO]
    assert (stage["pulls"], stage["open"], stage["score"]) == (6, 1, 0.625)
    assert stage["counts"] == {
        "mergeable": 2,
        "needs_fix": 1,
        "discard_plan": 1,
        "discard_implementation": 0,
        "issue_changed": 1,
    }
    assert stage["shares"]["mergeable"] == 0.4
    assert (
        implement["pulls"],
        implement["unscored"],
        implement["counts"]["needs_fix"],
        implement["score"],
    ) == (2, 1, 1, 0.5)
    assert rows["refine", GRADES_REPO] is None


def test_the_partial_score_setting_weighs_needs_fix(
    cli: Cli, config: Callable[..., Path], github_api: GitHubApiFake, clock: ClockFake
) -> None:
    config(
        loki={"url": LOKI_URL},
        service={"github_app": {"slug": "example-bot"}},
        roadmap={"verdict_partial_score": 1.0},
    )
    clock.move_to(VERDICT_NOW)
    route_grade_replies(github_api)
    _verdict_replies(github_api, _plan(1, "verdict/mergeable"), _plan(2, "verdict/fix-plan"))

    result = cli("roadmap", "eval", "grades", "--json")

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    stage = next(row for row in report["workflows"] if row["job"] == "stage")
    assert (report["verdict_partial_score"], stage["verdicts"]["score"]) == (1.0, 1.0)


def test_the_text_gives_the_verdict_score_beside_the_attempt_ratio(
    cli: Cli, config: Callable[..., Path], github_api: GitHubApiFake, clock: ClockFake
) -> None:
    config(loki={"url": LOKI_URL}, service={"github_app": {"slug": "example-bot"}})
    clock.move_to(VERDICT_NOW)
    route_grade_replies(github_api, repo=RepoRef(GRADES_REPO))
    _bot_pulls(github_api)

    result = cli("roadmap", "eval", "grades", "--repo", GRADES_REPO)

    assert result.exit_code == 0, result.output
    verdicts = result.output[result.output.index("Verdicts of the pull requests") :]
    assert verdicts.splitlines()[2:] == [
        "Workflow   Repository     p     PRs  Open  Unscored  Mergeable  Needs fix  Discard plan  "
        "Discard implementation  Issue changed  Score",
        "stage      example/app    0.67  6    1     0         2 (0.40)   1 (0.20)   1 (0.20)      "
        "0 (0.00)                1 (0.20)       0.62",
        "stage      example/infra  -     0    0     0         0 (-)      0 (-)      0 (-)         "
        "0 (-)                   0 (-)          -",
        "implement  example/app    0.00  2    0     1         0 (0.00)   1 (1.00)   0 (0.00)      "
        "0 (0.00)                0 (0.00)       0.50",
    ]


def test_the_dry_run_prints_the_github_search(
    cli: Cli, config: Callable[..., Path], web: WebFake, clock: ClockFake
) -> None:
    config(loki={"url": LOKI_URL}, service={"github_app": {"slug": "example-bot"}})
    clock.move_to(VERDICT_NOW)

    result = cli("roadmap", "eval", "grades", "--dry-run")

    assert (result.exit_code, web.sent) == (0, [])
    assert "POST https://api.github.com/graphql" in result.output
    assert "is:pr author:app/example-bot updated:>=2026-11-02T12:00:00Z" in result.output


def test_with_no_slug_the_report_reads_no_verdict_and_names_the_setting(
    cli: Cli, config: Callable[..., Path], web: WebFake
) -> None:
    config(loki={"url": LOKI_URL})
    serve_grade_replies(web)

    result = cli("roadmap", "eval", "grades")

    assert result.exit_code == 0, result.output
    assert {request.url.path for request in web.sent} == {QUERY_PATH}
    assert "service.github_app.slug" in result.output


def test_verdict_read_failure_prints_reason_and_keeps_loki_rows(
    cli: Cli, config: Callable[..., Path], github_api: GitHubApiFake, clock: ClockFake
) -> None:
    """When the GitHub verdict read fails with `GitHubUnreadError`, the report prints
    `verdicts not read: <reason>` and keeps its Loki rows (#5984)."""
    config(loki={"url": LOKI_URL}, service={"github_app": {"slug": "example-bot"}})
    clock.move_to(VERDICT_NOW)
    route_grade_replies(github_api, repo=RepoRef(GRADES_REPO))
    hold_graphql_quota()
    github_api.route(
        "POST", "/graphql", github_json({"errors": [{"message": "GraphQL backend unavailable"}]})
    )

    result = cli("roadmap", "eval", "grades", "--repo", GRADES_REPO)

    assert result.exit_code == 0, result.output
    assert "verdicts not read:" in result.output
    assert "GraphQL backend unavailable" in result.output
    assert "stage" in result.output
    assert "implement" in result.output
