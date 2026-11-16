"""The verdict of each bot pull request and the verdict score of stage and implement (#5968).

The verdict labels are workflow labels. A plan uses `plan/needs-fix` for the verdict needs fix,
and a delivery uses `verdict/needs-fix`. The first label event of a verdict label gives the verdict,
and GitHub's GraphQL search gives the label events of each pull request of the window.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from devops_cli.exceptions.git import GitHubUnreadError
from devops_cli.github.repo_ref import RepoRef
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.job_grade import GradeWindow
from devops_cli.roadmap.job_result import RoadmapJob
from devops_cli.roadmap.pr_verdict import (
    PLAN_TITLE_PREFIX,
    VERDICT_LABELS,
    BotPull,
    PullKind,
    Verdict,
    first_verdict,
    grade_verdicts,
    pull_kind,
    read_bot_pulls,
    verdict_search,
)
from devops_cli.roadmap.stage.stage_change import STAGING_TYPE
from devops_cli.roadmap.workflow_labels import WORKFLOW_LABELS
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.roadmap_job_grades import hold_graphql_quota, pull_node

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)


def _page(nodes: list[dict[str, Any]], *, total: int, cursor: str | None = None) -> Any:
    return github_json(
        {
            "data": {
                "search": {
                    "issueCount": total,
                    "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor},
                    "nodes": nodes,
                }
            }
        }
    )


def test_each_kind_reads_one_label_for_each_verdict() -> None:
    """A plan reads `plan/needs-fix` and a delivery `verdict/needs-fix`, and each verdict label is
    a workflow label."""
    assert VERDICT_LABELS[PullKind.PLAN] == {
        "verdict/mergeable": Verdict.MERGEABLE,
        "plan/needs-fix": Verdict.NEEDS_FIX,
        "verdict/discard-plan": Verdict.DISCARD_PLAN,
        "verdict/issue-changed": Verdict.ISSUE_CHANGED,
    }
    assert VERDICT_LABELS[PullKind.DELIVERY] == {
        "verdict/mergeable": Verdict.MERGEABLE,
        "verdict/needs-fix": Verdict.NEEDS_FIX,
        "verdict/discard-plan": Verdict.DISCARD_PLAN,
        "verdict/discard-implementation": Verdict.DISCARD_IMPLEMENTATION,
        "verdict/issue-changed": Verdict.ISSUE_CHANGED,
    }
    declared = {spec.name for spec in WORKFLOW_LABELS}
    assert sorted({name for labels in VERDICT_LABELS.values() for name in labels} - declared) == []


def test_the_plan_prefix_is_the_title_of_the_stage_job() -> None:
    lead = MESSAGES.roadmap.stage_title_lead.partition("{number}")[0]
    assert PLAN_TITLE_PREFIX == f"{STAGING_TYPE}: {lead}"


@pytest.mark.parametrize(
    ("title", "kind"),
    [
        ("docs(openspec): plan #12 Add the apply command", PullKind.PLAN),
        ("feat(roadmap): Count kept work by failure class", PullKind.DELIVERY),
        ("docs(openspec): archive the change of #12", PullKind.DELIVERY),
    ],
)
def test_the_title_gives_the_kind(title: str, kind: PullKind) -> None:
    assert pull_kind(title) is kind


@pytest.mark.parametrize(
    ("kind", "events", "verdict"),
    [
        (PullKind.PLAN, ["type/docs", "plan/needs-fix", "verdict/mergeable"], Verdict.NEEDS_FIX),
        (PullKind.PLAN, ["verdict/needs-fix", "verdict/mergeable"], Verdict.MERGEABLE),
        (PullKind.DELIVERY, ["type/feature", "plan/needs-fix"], None),
        (PullKind.DELIVERY, ["verdict/needs-fix", "verdict/mergeable"], Verdict.NEEDS_FIX),
        (PullKind.DELIVERY, ["verdict/mergeable", "verdict/issue-changed"], Verdict.MERGEABLE),
    ],
)
def test_the_first_verdict_label_event_gives_the_verdict(
    kind: PullKind, events: list[str], verdict: Verdict | None
) -> None:
    assert first_verdict(kind, events) is verdict


def test_the_score_of_stage() -> None:
    """2 mergeable, 1 needs fix, 1 discard plan, 1 issue changed and 1 open plan: the share of
    mergeable is 2/5 and the score (2 + 0.5) / 4."""
    grade = grade_verdicts(
        RoadmapJob.STAGE,
        [
            Verdict.MERGEABLE,
            Verdict.MERGEABLE,
            Verdict.NEEDS_FIX,
            Verdict.DISCARD_PLAN,
            Verdict.ISSUE_CHANGED,
            None,
        ],
        partial_score=0.5,
    )

    assert (grade.pulls, grade.open, grade.score) == (6, 1, 0.625)
    assert grade.counts == {
        Verdict.MERGEABLE: 2,
        Verdict.NEEDS_FIX: 1,
        Verdict.DISCARD_PLAN: 1,
        Verdict.DISCARD_IMPLEMENTATION: 0,
        Verdict.ISSUE_CHANGED: 1,
    }
    assert grade.shares[Verdict.MERGEABLE] == 0.4


def test_a_delivery_discarded_for_its_plan_has_no_score() -> None:
    """Discard plan is a failure of stage, so the implement score leaves it out."""
    grade = grade_verdicts(RoadmapJob.IMPLEMENT, [Verdict.DISCARD_PLAN, None], partial_score=0.5)

    assert (grade.counts[Verdict.DISCARD_PLAN], grade.open, grade.score) == (1, 1, None)


def test_discard_implementation_is_a_failure_of_implement() -> None:
    grade = grade_verdicts(
        RoadmapJob.IMPLEMENT,
        [Verdict.MERGEABLE, Verdict.DISCARD_IMPLEMENTATION],
        partial_score=0.5,
    )

    assert grade.score == 0.5


def test_the_partial_score_weighs_needs_fix() -> None:
    grade = grade_verdicts(
        RoadmapJob.STAGE, [Verdict.MERGEABLE, Verdict.NEEDS_FIX], partial_score=1.0
    )

    assert grade.score == 1.0


def test_no_pull_request_gives_no_share_and_no_score() -> None:
    grade = grade_verdicts(RoadmapJob.STAGE, [], partial_score=0.5)

    assert (grade.pulls, grade.open, grade.score, set(grade.shares.values())) == (
        0,
        0,
        None,
        {None},
    )


def test_the_search_names_the_bot_the_window_and_the_repository() -> None:
    assert (
        verdict_search(GradeWindow.D7, RepoRef("example/app"), "example-bot", NOW)
        == "is:pr author:app/example-bot created:>=2026-11-02T12:00:00Z repo:example/app"
    )
    assert (
        verdict_search(GradeWindow.H6, None, "example-bot", NOW)
        == "is:pr author:app/example-bot created:>=2026-11-09T06:00:00Z"
    )


def test_the_read_sends_one_search_for_each_page_and_reads_the_label_events(
    github_api: GitHubApiFake,
) -> None:
    """Two pages of the search give the pull requests of the window, each with its first
    verdict."""
    hold_graphql_quota()
    github_api.route(
        "POST",
        "/graphql",
        _page(
            [
                pull_node(5, "docs(openspec): plan #1 Add x", ["type/docs", "plan/needs-fix"]),
                pull_node(6, "feat(roadmap): Add x", ["verdict/mergeable"], repo="Example/Infra"),
            ],
            total=3,
            cursor="page-2",
        ),
        _page([pull_node(7, "fix(roadmap): Mend y", ["type/bug"])], total=3),
    )

    pulls = read_bot_pulls(get_github_session().client, "is:pr author:app/example-bot")

    assert pulls == [
        BotPull(repo="example/app", number=5, kind=PullKind.PLAN, verdict=Verdict.NEEDS_FIX),
        BotPull(repo="Example/Infra", number=6, kind=PullKind.DELIVERY, verdict=Verdict.MERGEABLE),
        BotPull(repo="example/app", number=7, kind=PullKind.DELIVERY, verdict=None),
    ]
    variables = [json.loads(request.content)["variables"] for request in github_api.sent]
    assert variables == [
        {"search": "is:pr author:app/example-bot", "cursor": None},
        {"search": "is:pr author:app/example-bot", "cursor": "page-2"},
    ]


def test_a_search_with_more_results_than_github_returns_stops_the_read(
    github_api: GitHubApiFake,
) -> None:
    hold_graphql_quota()
    github_api.route("POST", "/graphql", _page([], total=1001))

    with pytest.raises(GitHubUnreadError, match="1001"):
        read_bot_pulls(get_github_session().client, "is:pr author:app/example-bot")


def test_a_graphql_error_stops_the_read(github_api: GitHubApiFake) -> None:
    hold_graphql_quota()
    github_api.route(
        "POST", "/graphql", github_json({"errors": [{"message": "Something went wrong"}]})
    )

    with pytest.raises(GitHubUnreadError, match="Something went wrong"):
        read_bot_pulls(get_github_session().client, "is:pr author:app/example-bot")
