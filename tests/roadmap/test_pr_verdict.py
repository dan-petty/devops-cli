"""The verdict of each bot pull request and the verdict score of stage and implement (#5968).

The verdict labels are workflow labels. A plan uses `verdict/fix-plan` for the verdict needs fix,
and a delivery uses `verdict/fix-implementation`. The first label event of a verdict label gives the
verdict, a first label of the other kind leaves the pull request unscored, and GitHub's GraphQL
search gives the label events of each pull request of the window.
"""

from __future__ import annotations

import ast
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
from devops_cli.roadmap.stage.stage_verify import FIX_PLAN_LABEL
from devops_cli.roadmap.workflow_labels import WORKFLOW_LABELS
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.paths import REPO_ROOT
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


def test_plan_prefix_and_kind_support_spec_and_legacy_openspec() -> None:
    """Plan titles use `docs(spec): plan #`, and `pull_kind` classifies both `docs(spec)` and
    legacy `docs(openspec)` plan titles as `PullKind.PLAN` (#6007)."""
    assert PLAN_TITLE_PREFIX == "docs(spec): plan #"
    assert (
        pull_kind("docs(spec): plan #12 Add the apply command"),
        pull_kind("docs(openspec): plan #12 Add the apply command"),
        pull_kind("docs(spec): archive the change of #12"),
    ) == (PullKind.PLAN, PullKind.PLAN, PullKind.DELIVERY)


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
                pull_node(5, "docs(spec): plan #1 Add x", ["type/docs", "verdict/fix-plan"]),
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


def test_the_verdict_query_selects_renamed_title_events_and_timeline_page_info(
    github_api: GitHubApiFake,
) -> None:
    """The verdict GraphQL query selects `RENAMED_TITLE_EVENT`, `previousTitle`, and timeline
    `pageInfo.hasNextPage` (#5984)."""
    hold_graphql_quota()
    github_api.route("POST", "/graphql", _page([], total=0))

    read_bot_pulls(get_github_session().client, "is:pr author:app/example-bot")

    query = json.loads(github_api.sent[0].content)["query"]
    for token in ("LABELED_EVENT", "RENAMED_TITLE_EVENT", "previousTitle", "hasNextPage"):
        assert token in query


def test_renamed_bot_pull_requests_score_by_the_kind_at_their_first_verdict_label(
    github_api: GitHubApiFake,
) -> None:
    """A verdict label before a rename uses `previousTitle`, a label after uses the current title,
    a cross-kind label stays unscored, and an unlabeled renamed PR keeps its current kind (#5984)."""
    hold_graphql_quota()
    github_api.route(
        "POST",
        "/graphql",
        _page(
            [
                pull_node(41, "feat(cli): Implement alpha (#1)", [])
                | {
                    "timelineItems": {
                        "pageInfo": {"hasNextPage": False},
                        "nodes": [
                            {"label": {"name": "verdict/mergeable"}},
                            {"previousTitle": "docs(openspec): plan #1 Alpha"},
                        ],
                    }
                },
                pull_node(42, "feat(cli): Implement beta (#2)", [])
                | {
                    "timelineItems": {
                        "pageInfo": {"hasNextPage": False},
                        "nodes": [
                            {"previousTitle": "docs(openspec): plan #2 Beta"},
                            {"label": {"name": "verdict/fix-implementation"}},
                        ],
                    }
                },
                pull_node(43, "feat(cli): Implement gamma (#3)", [])
                | {
                    "timelineItems": {
                        "pageInfo": {"hasNextPage": False},
                        "nodes": [
                            {"previousTitle": "docs(openspec): plan #3 Gamma"},
                            {"label": {"name": FIX_PLAN_LABEL}},
                        ],
                    }
                },
                pull_node(44, "feat(cli): Implement delta (#4)", [])
                | {
                    "timelineItems": {
                        "pageInfo": {"hasNextPage": False},
                        "nodes": [{"previousTitle": "docs(openspec): plan #4 Delta"}],
                    }
                },
            ],
            total=4,
        ),
    )

    pulls = read_bot_pulls(get_github_session().client, "is:pr author:app/example-bot")

    assert [(p.number, p.kind, p.verdict, p.unscored) for p in pulls] == [
        (41, PullKind.PLAN, Verdict.MERGEABLE, None),
        (42, PullKind.DELIVERY, Verdict.NEEDS_FIX, None),
        (43, PullKind.DELIVERY, None, FIX_PLAN_LABEL),
        (44, PullKind.DELIVERY, None, None),
    ]
    stage = grade_verdicts(
        RoadmapJob.STAGE,
        [p.verdict for p in pulls if p.kind is PullKind.PLAN and p.unscored is None],
        partial_score=0.5,
        unscored=sum(p.kind is PullKind.PLAN and p.unscored is not None for p in pulls),
    )
    implement = grade_verdicts(
        RoadmapJob.IMPLEMENT,
        [p.verdict for p in pulls if p.kind is PullKind.DELIVERY and p.unscored is None],
        partial_score=0.5,
        unscored=sum(p.kind is PullKind.DELIVERY and p.unscored is not None for p in pulls),
    )
    assert stage.counts[Verdict.MERGEABLE] == 1
    assert implement.counts[Verdict.NEEDS_FIX] == 1
    assert implement.unscored == 1


def test_more_than_one_page_of_timeline_events_stops_the_read(github_api: GitHubApiFake) -> None:
    """When `timelineItems.pageInfo.hasNextPage` is true, `read_bot_pulls` raises
    `GitHubUnreadError` with the PR number and timeline page reason (#5984)."""
    hold_graphql_quota()
    github_api.route(
        "POST",
        "/graphql",
        _page(
            [
                pull_node(77, "feat(cli): Implement omega", [])
                | {"timelineItems": {"pageInfo": {"hasNextPage": True}, "nodes": []}}
            ],
            total=1,
        ),
    )

    with pytest.raises(GitHubUnreadError, match=r"#77.*timeline"):
        read_bot_pulls(get_github_session().client, "is:pr author:app/example-bot")


def test_fix_plan_label_constant_matches_plan_verdict_and_has_single_source() -> None:
    """`FIX_PLAN_LABEL` matches `VERDICT_LABELS[PullKind.PLAN]` for `Verdict.NEEDS_FIX`, and only
    `workflow_labels.py` defines the literal `"verdict/fix-plan"` in `src/devops_cli/roadmap`
    (#5984)."""
    assert VERDICT_LABELS[PullKind.PLAN][FIX_PLAN_LABEL] is Verdict.NEEDS_FIX
    roadmap_dir = REPO_ROOT / "src" / "devops_cli" / "roadmap"
    workflow_labels_path = roadmap_dir / "workflow_labels.py"
    duplicates: list[str] = []
    for py_path in sorted(roadmap_dir.rglob("*.py")):
        if py_path == workflow_labels_path:
            continue
        tree = ast.parse(py_path.read_text("utf-8"), filename=str(py_path))
        docstring_nodes = {
            id(node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstring_nodes
                and FIX_PLAN_LABEL in node.value
            ):
                duplicates.append(f"{py_path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert duplicates == []


def test_adr_0021_and_kb_name_all_six_verdict_labels() -> None:
    """ADR 0021 Status History and the GitHub project management knowledge-base page list every
    verdict label, and Status History supersedes `plan/needs-fix` without altering the accepted
    body hash (#5984)."""
    labels = sorted({name for mapping in VERDICT_LABELS.values() for name in mapping})
    adr_path = (
        REPO_ROOT
        / "docs"
        / "adr"
        / "0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md"
    )
    kb_path = (
        REPO_ROOT
        / "src"
        / "devops_cli"
        / "ai"
        / "knowledge_base"
        / "devops_cli"
        / "tasks"
        / "github_project_management.md"
    )
    adr_text = adr_path.read_text("utf-8")
    _, _, status_history = adr_text.partition("## Status History")
    kb_text = kb_path.read_text("utf-8")
    assert [label for label in labels if label not in status_history] == []
    assert [label for label in labels if label not in kb_text] == []
    assert "Fact out of date:" in status_history
    assert "plan/needs-fix" in status_history
