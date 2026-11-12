"""A plan pull request with the label `plan/needs-fix`, for the tests of the step `fix-plan` (#5061).

`needs_fix_plan` seeds the Staged item #1 and its draft plan pull request #5 in the store, pushes
the change folder of `make_stage_proposal()` as one commit by the clone identity to the branch of
the plan on `origin`, and answers the read of the pull request with that head. The verifier is a
model apart from the planner, as in the stage tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

from devops_cli.roadmap.stage.stage_change import render_change
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.roadmap.stage.stage_verify import PLAN_NEEDS_FIX_LABEL, Finding
from devops_cli.roadmap.stores.store import StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.roadmap_stage import STAGE_REPO, VALID_REPORT, seed_stageable, validate_args

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
    from tests.support.roadmap_stage import StageRepo

PLAN_PULL = 5
PLAN_BRANCH = "fix/1-the-job-drops-a-comment"
PLAN_CHANGE = "1-the-job-drops-a-comment"
PLAN_TITLE = "docs(openspec): plan #1 Stop the job dropping a comment"
PLAN_PATH = f"/repos/{STAGE_REPO}/pulls/{PLAN_PULL}"
# A text of the issue body, so a finding that quotes it is open (`VerificationInput.contains`).
ISSUE_QUOTE = "The job drops the last comment of a thread."
# A text of the file that the plan cites.
SAMPLE_QUOTE = "return comments[:-1]"
# The `why` of the revision that the planner answers, so the pushed proposal shows the repair.
REPAIRED_WHY = "Issue #1: the job drops the last comment of a thread, and the repair keeps it."


@dataclass(frozen=True)
class PlanPull:
    """The item, its plan pull request and the head commit of the plan branch."""

    number: int
    pull: int
    head: str


def finding(kind: DefectType, quote: str = ISSUE_QUOTE, where: str = "group 1") -> Finding:
    """A finding of `kind` whose quote is a text of the input, so an open type makes it open."""
    return Finding(type=kind, where=where, problem=f"Problem of {kind.value}.", quote=quote)


def push_plan(repo: StageRepo) -> str:
    """Push the change folder of `make_stage_proposal()` as one commit by the clone identity to
    `PLAN_BRANCH` of `origin`, from `main`, and return the head commit."""
    files = render_change(
        PLAN_CHANGE, make_stage_proposal(), ("roadmap-refine",), created=date(2026, 11, 12)
    )
    repo.git("switch", "-q", "-c", PLAN_BRANCH)
    for name, text in files.items():
        (repo.clone / name).parent.mkdir(parents=True, exist_ok=True)
        (repo.clone / name).write_text(text, encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", PLAN_TITLE, "-m", "Plans #1.")
    repo.git("push", "-q", "origin", PLAN_BRANCH)
    head = repo.git("rev-parse", "HEAD")
    repo.git("switch", "-q", "main")
    repo.git("branch", "-q", "-D", PLAN_BRANCH)
    return head


def route_plan_pull(
    api: GitHubApiFake,
    head: str,
    *,
    labels: tuple[str, ...] = (PLAN_NEEDS_FIX_LABEL,),
    draft: bool = True,
    state: str = "open",
) -> None:
    """GitHub's answer to the read of the plan pull request, and to the write of its title and
    body."""
    payload: dict[str, Any] = {
        "number": PLAN_PULL,
        "state": state,
        "draft": draft,
        "merged": False,
        "title": PLAN_TITLE,
        "body": "Plans #1.",
        "head": {"sha": head, "ref": PLAN_BRANCH},
        "base": {"ref": "main", "repo": {"default_branch": "main"}},
        "labels": [{"name": name} for name in labels],
    }
    api.route("GET", PLAN_PATH, github_json(payload))
    api.route("PATCH", PLAN_PATH, github_json(payload))


def needs_fix_plan(
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    api: GitHubApiFake,
    *,
    labels: tuple[str, ...] = (PLAN_NEEDS_FIX_LABEL,),
    draft: bool = True,
    marks: Mapping[Any, str | None] | None = None,
) -> PlanPull:
    """Seed the Staged item #1 with the record of its draft plan pull request #5, which holds
    `labels`, push its plan branch, and answer the read of the pull request."""
    number = seed_stageable(store)
    for placeholder in range(2, PLAN_PULL):
        store.seed_issue(f"placeholder {placeholder}")
    pull = store.seed_pull(PLAN_TITLE, head_ref=PLAN_BRANCH, draft=draft)
    assert pull == PLAN_PULL
    for label in labels:
        store.label_issue(pull, label)
    item = store.item(number)
    assert item is not None
    store.set_marks(
        item,
        {StageRecordKey.BRANCH: PLAN_BRANCH, StageRecordKey.PR: str(pull), **(marks or {})},
    )
    head = push_plan(repo)
    route_plan_pull(api, head, labels=labels, draft=draft)
    return PlanPull(number, pull, head)


def valid_changes(openspec: OpenSpecFake, count: int = 6) -> None:
    """Answer `count` validations of the change of the plan as valid."""
    openspec.script_sequence(validate_args(PLAN_CHANGE), *((0, VALID_REPORT) for _ in range(count)))


def planner_requests(fake: ModelFake) -> list[dict[str, Any]]:
    """The JSON requests of the planner, in order."""
    return [json.loads(call.prompt) for call in fake.calls]
