"""The requests that intake sends to GitHub over `GitHubFake`: a few requests for a placement, and
no Projects request (#1361).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from devops_cli.roadmap.intake.intake import (
    NewCandidate,
)
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.store import (
    Evidence,
    EvidenceKind,
    split_record,
)
from tests.support.fakes.github import API, RunnerSession
from tests.support.fakes.github_repository import GitHubFake
from tests.support.roadmap_intake import REGRESSION, REPO, FakeModel, intake_on_github, on_github

CRITICAL_FIX = NewCandidate(
    title="fix: crash on start",
    body="Introduced by abc1234.",
    evidence=(Evidence(kind=EvidenceKind.REGRESSION_COMMIT, value="abc1234"),),
)


def _record(github: GitHubFake, number: int) -> dict[str, Any]:
    """The job record that the body of issue `number` holds."""
    return split_record(github.body(number))[1]


def _patches(github: GitHubFake, start: int) -> list[dict[str, Any]]:
    """The fields of each issue `PATCH` from call `start` on, as their stdin sent them."""
    return [
        json.loads(stdin or "{}")
        for args, stdin in zip(github.calls[start:], github.stdins[start:], strict=True)
        if args[:3] == ["api", "-X", "PATCH"]
    ]


def test_intake_places_a_critical_fix_with_labels_and_sends_no_projects_request() -> None:
    """Intake files a critical fix in the backlog and labels it with its type, Status, Value,
    Effort and Priority; the issue body holds the job record of the four fields. No request
    names a project board or `.github/roadmap.toml` (ADR 0016)."""
    github, store = on_github(items=3)
    model = FakeModel(proposals={CRITICAL_FIX.title: REGRESSION})
    _, apply = intake_on_github(store, model, new=CRITICAL_FIX)
    applied = apply()
    (number,) = applied.filed
    assert (
        github.labels(number),
        _record(github, number),
        github.issues[number]["milestone"],
        github.project_calls(),
    ) == (
        [
            "source/agent",
            "type/bug",
            "status/new",
            "value/medium",
            "effort/low",
            "priority/p0-critical",
        ],
        {"Effort": "Low", "Priority": "P0-Critical", "Status": "New", "Value": "Medium"},
        None,
        [],
    )


@pytest.mark.parametrize("items", [120, 1_080])
def test_a_placement_sends_the_same_few_requests_whatever_the_number_of_items(
    items: int,
) -> None:
    """Filing and placing a critical fix: the file, the type label, a read and one `PATCH` for
    each of four fields, and the reason comment, 11 requests, none of them GraphQL, on a
    repository of 120 items or of 1,080."""
    github, store = on_github(items=items)
    model = FakeModel(proposals={CRITICAL_FIX.title: REGRESSION})
    _, apply = intake_on_github(store, model, new=CRITICAL_FIX)
    start = len(github.calls)
    apply()
    sent = github.calls[start:]
    assert (len(sent), [args for args in sent if "graphql" in args]) == (11, [])


def test_a_candidate_with_status_and_value_labels_gets_only_effort_and_priority() -> None:
    """#1336's state: a placement that stopped left Status and Value labels and their job
    record. Intake labels the type, then writes Effort, then Priority, each in one `PATCH` that
    keeps the record of the fields written before."""
    github, store = on_github()
    record = '<!-- devops-roadmap-record {"Status": "New", "Value": "Medium"} -->'
    github.seed_issue(
        1,
        "feat: export the board as CSV",
        body=f"Text.\n\n{record}",
        labels=("status/new", "value/medium"),
    )
    _, apply = intake_on_github(store, FakeModel())
    start = len(github.calls)
    apply()
    assert (
        [patch["labels"][-1] for patch in _patches(github, start)],
        github.labels(1),
        _record(github, 1),
        split_record(github.body(1))[0],
    ) == (
        ["effort/low", "priority/p2-medium"],
        ["status/new", "value/medium", "type/feature", "effort/low", "priority/p2-medium"],
        {"Effort": "Low", "Priority": "P2-Medium", "Status": "New", "Value": "Medium"},
        "Text.",
    )


def test_a_priority_a_person_sets_between_the_plan_and_its_write_stays() -> None:
    """A person labels the candidate `priority/p1-high` between `plan_intake` and
    `apply_intake`. The Priority write sees the change and refuses before it writes, so the
    person's Priority stays, the job record claims none, and the run counts no failure: the
    candidate stays a candidate (ADR 0002, #4042)."""
    github, store = on_github()
    github.seed_issue(1, "feat: issue one", labels=("type/feature",))
    _, apply = intake_on_github(store, FakeModel())
    github.issues[1]["labels"].append({"name": "priority/p1-high"})
    applied = apply()
    assert (
        applied.placed,
        applied.failed,
        [label for label in github.labels(1) if label.startswith("priority/")],
        "Priority" in _record(github, 1),
    ) == (0, (), ["priority/p1-high"], False)


def test_a_value_a_person_sets_between_the_plan_and_its_write_stays_and_the_next_run_finishes() -> (
    None
):
    """A person labels the candidate `value/high` between the plan and the writes: the Value
    write refuses without a failure, so the candidate keeps the person's Value and no Priority. The next run
    finds it a candidate again and writes only Effort, its reason comment, which gives no
    Value, and Priority. The job record claims no Value (#1404, ADR 0002)."""
    github, store = on_github()
    github.seed_issue(1, "feat: issue one", labels=("type/feature",))
    _, apply = intake_on_github(store, FakeModel())
    github.issues[1]["labels"].append({"name": "value/high"})
    first = apply()
    later = GitHubRoadmapStore(REPO, runner=github, session=RunnerSession(github))
    _, apply_again = intake_on_github(later, FakeModel())
    second = apply_again()
    comments = github.comments.get(1, [])
    assert (
        first.failed,
        second.placed,
        github.labels(1),
        _record(github, 1),
        len(comments),
        "- Value:" in comments[0],
    ) == (
        (),
        1,
        ["type/feature", "value/high", "status/new", "effort/low", "priority/p2-medium"],
        {"Effort": "Low", "Priority": "P2-Medium", "Status": "New"},
        1,
        False,
    )


def test_an_intake_of_three_placements_reads_every_issue_once() -> None:
    """Of 250 items and three candidates: one listing of every issue for the whole run, its
    three placements included."""
    github, store = on_github(items=250)
    for number in (251, 252, 253):
        github.seed_issue(number, f"feat: new idea {number}")
    _, apply = intake_on_github(store, FakeModel())
    applied = apply()
    listings = [args for args in github.calls if args[0].startswith(f"{API}/repos/{REPO}/issues?")]
    assert (
        applied.placed,
        len(listings),
        [label for n in (251, 252, 253) for label in github.labels(n) if "priority" in label],
    ) == (3, 1, ["priority/p2-medium"] * 3)
