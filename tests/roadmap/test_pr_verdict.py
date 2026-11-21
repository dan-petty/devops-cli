"""The verdict of each bot pull request and the verdict score of stage and implement (#5968).

The verdict labels are workflow labels. A plan uses `verdict/fix-plan` for the verdict needs fix,
and a delivery uses `verdict/fix-implementation`. The first label event of a verdict label gives the
verdict, a first label of the other kind leaves the pull request unscored, and GitHub's GraphQL
search gives the label events of each pull request of the window.
"""

from __future__ import annotations

import json
import logging
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
    ForgeOutcome,
    PullKind,
    PullState,
    Verdict,
    first_verdict_label,
    forge_outcome,
    grade_verdicts,
    pull_kind,
    read_bot_pulls,
    verdict_of,
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
    """A plan reads `verdict/fix-plan` and a delivery `verdict/fix-implementation`, and each
    verdict label is a workflow label."""
    assert VERDICT_LABELS[PullKind.PLAN] == {
        "verdict/mergeable": Verdict.MERGEABLE,
        "verdict/fix-plan": Verdict.NEEDS_FIX,
        "verdict/discard-plan": Verdict.DISCARD_PLAN,
        "verdict/issue-changed": Verdict.ISSUE_CHANGED,
    }
    assert VERDICT_LABELS[PullKind.DELIVERY] == {
        "verdict/mergeable": Verdict.MERGEABLE,
        "verdict/fix-implementation": Verdict.NEEDS_FIX,
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
        (PullKind.PLAN, ["type/docs", "verdict/fix-plan", "verdict/mergeable"], Verdict.NEEDS_FIX),
        (PullKind.PLAN, ["plan/needs-fix", "verdict/mergeable"], Verdict.MERGEABLE),
        (PullKind.DELIVERY, ["verdict/fix-implementation", "verdict/mergeable"], Verdict.NEEDS_FIX),
        (PullKind.DELIVERY, ["verdict/mergeable", "verdict/issue-changed"], Verdict.MERGEABLE),
        (PullKind.DELIVERY, ["type/feature"], None),
    ],
)
def test_the_first_verdict_label_event_gives_the_verdict(
    kind: PullKind, events: list[str], verdict: Verdict | None
) -> None:
    label = first_verdict_label(events)
    assert (verdict_of(kind, label) if label is not None else None) is verdict


@pytest.mark.parametrize(
    ("kind", "label"),
    [
        (PullKind.DELIVERY, "verdict/fix-plan"),
        (PullKind.DELIVERY, "verdict/discard-plan"),
        (PullKind.PLAN, "verdict/fix-implementation"),
        (PullKind.PLAN, "verdict/discard-implementation"),
    ],
)
def test_a_label_of_the_other_kind_gives_no_verdict(kind: PullKind, label: str) -> None:
    assert (
        first_verdict_label(["type/docs", label, "verdict/mergeable"]),
        verdict_of(kind, label),
    ) == (
        label,
        None,
    )


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


def test_an_unscored_pull_request_counts_and_stays_out_of_the_score() -> None:
    """A delivery whose first verdict label is of the other kind counts as unscored."""
    grade = grade_verdicts(
        RoadmapJob.IMPLEMENT, [Verdict.MERGEABLE, None], partial_score=0.5, unscored=1
    )

    assert (grade.pulls, grade.open, grade.unscored, grade.score) == (3, 1, 1, 1.0)
    assert grade.shares[Verdict.MERGEABLE] == 1.0


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
        == "is:pr author:app/example-bot updated:>=2026-11-02T12:00:00Z repo:example/app"
    )
    assert (
        verdict_search(GradeWindow.H6, None, "example-bot", NOW)
        == "is:pr author:app/example-bot updated:>=2026-11-09T06:00:00Z"
    )


def test_the_read_sends_one_search_for_each_page_and_reads_the_label_events(
    github_api: GitHubApiFake, caplog: pytest.LogCaptureFixture
) -> None:
    """Two pages of the search give the pull requests of the window, each with its first
    verdict."""
    hold_graphql_quota()
    github_api.route(
        "POST",
        "/graphql",
        _page(
            [
                pull_node(5, "docs(openspec): plan #1 Add x", ["type/docs", "verdict/fix-plan"]),
                pull_node(6, "feat(roadmap): Add x", ["verdict/mergeable"], repo="Example/Infra"),
            ],
            total=4,
            cursor="page-2",
        ),
        _page(
            [
                pull_node(7, "fix(roadmap): Mend y", ["type/bug"]),
                pull_node(8, "fix(roadmap): Mend z", ["verdict/fix-plan", "verdict/mergeable"]),
            ],
            total=4,
        ),
    )

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.pr_verdict"):
        pulls = read_bot_pulls(get_github_session().client, "is:pr author:app/example-bot")

    assert pulls == [
        BotPull(repo="example/app", number=5, kind=PullKind.PLAN, verdict=Verdict.NEEDS_FIX),
        BotPull(repo="Example/Infra", number=6, kind=PullKind.DELIVERY, verdict=Verdict.MERGEABLE),
        BotPull(repo="example/app", number=7, kind=PullKind.DELIVERY, verdict=None),
        BotPull(
            repo="example/app",
            number=8,
            kind=PullKind.DELIVERY,
            verdict=None,
            unscored="verdict/fix-plan",
        ),
    ]
    assert [record.getMessage() for record in caplog.records] == [
        "Pull request example/app#8 is a delivery, and its first verdict label verdict/fix-plan "
        "is a label of the other kind, so the grade does not score it."
    ]
    variables = [json.loads(request.content)["variables"] for request in github_api.sent]
    assert variables == [
        {"search": "is:pr author:app/example-bot", "cursor": None},
        {"search": "is:pr author:app/example-bot", "cursor": "page-2"},
    ]


def test_the_read_gives_the_item_the_state_and_the_draft_of_each_pull_request(
    github_api: GitHubApiFake,
) -> None:
    """The head branch gives the item of a delivery, so the grade can link an implement attempt to
    its pull request (#6559)."""
    hold_graphql_quota()
    github_api.route(
        "POST",
        "/graphql",
        _page(
            [
                pull_node(
                    9,
                    "feat(roadmap): Add x",
                    [],
                    head="feat/12-add-x",
                    state="MERGED",
                    created="2026-10-20T08:00:00Z",
                ),
                pull_node(10, "feat(roadmap): Add y", [], head="not-a-branch", draft=True),
            ],
            total=2,
        ),
    )

    pulls = read_bot_pulls(get_github_session().client, "is:pr author:app/example-bot")

    assert [(p.number, p.item, p.state, p.draft, p.created) for p in pulls] == [
        (9, 12, PullState.MERGED, False, datetime(2026, 10, 20, 8, 0, tzinfo=UTC)),
        (10, None, PullState.OPEN, True, None),
    ]


@pytest.mark.parametrize(
    ("state", "draft", "outcome"),
    [
        (PullState.MERGED, False, ForgeOutcome.SUCCESS),
        (PullState.OPEN, False, ForgeOutcome.SUCCESS),
        (PullState.CLOSED, False, ForgeOutcome.FAILURE),
        (PullState.OPEN, True, None),
    ],
    ids=["merged", "ready", "closed", "draft"],
)
def test_the_forge_state_gives_the_outcome_of_a_delivery(
    state: PullState, draft: bool, outcome: ForgeOutcome | None
) -> None:
    """A merged or ready delivery is a success, a delivery closed with no merge a failure, and a
    draft has no outcome yet (#6559)."""
    pull = BotPull("example/app", 1, PullKind.DELIVERY, None, item=3, state=state, draft=draft)

    assert forge_outcome(pull) is outcome


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
