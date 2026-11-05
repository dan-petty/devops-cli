"""`devops roadmap plan-check`: the stage gates and the pull request checks of a plan (#3201)."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from devops_cli.github.check_verdict import CheckBucket, CheckVerdictSummary, PRCheckItem
from devops_cli.github.client import CommitRef, IssueView, PullRequest
from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import OpenSpecTool
from devops_cli.roadmap.plan_check import PlanCheckResult, plan_check
from devops_cli.roadmap.stage_change import (
    StageProposal,
    render_change,
)
from tests.support.builders import make_stage_proposal
from tests.support.roadmap_stage import VALID_REPORT, StageRepo

ISSUE = 1
PULL = 7
CHANGE = f"{ISSUE}-keep-the-last-comment"
CREATED = datetime(2026, 11, 4, tzinfo=UTC).date()
TITLE = "docs(openspec): plan #1 Stop the job dropping a comment"
BODY = "Plans #1\n\nThe job keeps every comment it reads.\n\nChange: `openspec/changes/1-keep-the-last-comment/`"


class _Tool:
    """An OpenSpec that accepts every change."""

    def __init__(self, report: str = VALID_REPORT) -> None:
        self.report = report

    def run(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        del args, cwd
        return subprocess.CompletedProcess([], 0, self.report, "")


@dataclass
class _Reads:
    pull: PullRequest
    bodies: Mapping[int, str]

    def get_pull(self, repo: str, number: int) -> PullRequest:
        del repo, number
        return self.pull

    def get_issue(self, repo: str, number: int) -> IssueView:
        del repo
        return IssueView(
            number=number,
            title="An issue",
            state="open",
            body=self.bodies.get(number),
        )


def _checks(
    *, conclusion: str | None = "success", name: str = "Semantic PR title"
) -> CheckVerdictSummary:
    if conclusion is None:
        return CheckVerdictSummary()
    item = PRCheckItem(
        name=name,
        state=conclusion,
        bucket=CheckBucket.PASS if conclusion == "success" else CheckBucket.FAIL,
    )
    return CheckVerdictSummary(items=[item])


def _facts(repo: StageRepo, *, sha: str, title: str = TITLE, body: str = BODY) -> _Reads:
    base = repo.git("rev-parse", "main")
    pull = PullRequest(
        title=title,
        head=CommitRef(sha=sha, ref="plan", repository="example/roadmap"),
        base=CommitRef(sha=base, ref="main", repository="example/roadmap"),
    )
    return _Reads(pull=pull, bodies={PULL: body, ISSUE: ""})


def _push(repo: StageRepo, files: Mapping[str, str], *, branch: str = "plan") -> str:
    repo.git("switch", "-q", "-c", branch)
    for path, text in files.items():
        (repo.clone / path).parent.mkdir(parents=True, exist_ok=True)
        (repo.clone / path).write_text(text, encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "plan the change")
    sha = repo.git("rev-parse", "HEAD")
    repo.git("push", "-q", "origin", f"HEAD:refs/pull/{PULL}/head")
    repo.git("switch", "-q", "main")
    return sha


def _change(
    proposal: StageProposal | None = None, *, known: set[str] | None = None
) -> dict[str, str]:
    return render_change(
        CHANGE, proposal or make_stage_proposal(), known or {"comment-thread"}, created=CREATED
    )


def _run(
    repo: StageRepo,
    reads: _Reads,
    *,
    checks: CheckVerdictSummary | None = None,
    tool: _Tool | None = None,
) -> PlanCheckResult:
    return plan_check(
        "example/roadmap",
        PULL,
        repo.clone,
        tool=cast("OpenSpecTool", tool or _Tool()),
        client=reads,
        check_reader=lambda owner, name, sha: checks or _checks(),
    )


def test_a_valid_plan_has_no_problem(stage_repo: StageRepo) -> None:
    sha = _push(stage_repo, _change())

    result = _run(stage_repo, _facts(stage_repo, sha=sha))

    assert result.problems == ()


def test_a_missing_path_gives_the_stage_message(stage_repo: StageRepo) -> None:
    group = (
        make_stage_proposal()
        .groups[0]
        .model_copy(
            update={
                "changes": ["src/devops_cli/roadmap/missing.py"],
                "creates": [],
                "creates_lines": {},
            }
        )
    )
    proposal = make_stage_proposal(groups=[group])
    sha = _push(stage_repo, _change(proposal))

    result = _run(stage_repo, _facts(stage_repo, sha=sha))

    problem = next(p for p in result.problems if "src/devops_cli/roadmap/missing.py" in p.message)
    assert problem.rule == "stage"
    assert MESSAGES.roadmap.stage_problem_path.split("{")[0].strip() in problem.message


def test_a_wrong_title_is_reported(stage_repo: StageRepo) -> None:
    sha = _push(stage_repo, _change())

    result = _run(stage_repo, _facts(stage_repo, sha=sha, title="feat(roadmap): add plan-check"))

    assert [(p.rule, p.message) for p in result.problems] == [
        ("title", MESSAGES.roadmap.plan_check_title.format(number=ISSUE))
    ]


def test_a_body_with_no_plan_reference_is_reported(stage_repo: StageRepo) -> None:
    sha = _push(stage_repo, _change())

    result = _run(stage_repo, _facts(stage_repo, sha=sha, body="The plan does a thing."))

    assert [p.rule for p in result.problems] == ["body-plans"]


def test_a_body_with_a_closing_keyword_is_reported(stage_repo: StageRepo) -> None:
    sha = _push(stage_repo, _change())
    body = f"{BODY}\n\nCloses #1"

    result = _run(stage_repo, _facts(stage_repo, sha=sha, body=body))

    assert [p.rule for p in result.problems] == ["body-closing"]


def test_a_failed_semantic_title_check_is_reported(stage_repo: StageRepo) -> None:
    sha = _push(stage_repo, _change())

    result = _run(stage_repo, _facts(stage_repo, sha=sha), checks=_checks(conclusion="failure"))

    assert [p.rule for p in result.problems] == ["semantic-pr-title"]


def test_a_missing_semantic_title_check_is_reported(stage_repo: StageRepo) -> None:
    sha = _push(stage_repo, _change())

    result = _run(stage_repo, _facts(stage_repo, sha=sha), checks=_checks(conclusion=None))

    assert [p.rule for p in result.problems] == ["semantic-pr-title"]


def test_a_base_spec_that_moved_since_the_plan_is_reported(stage_repo: StageRepo) -> None:
    spec_path = "openspec/specs/roadmap-refine/spec.md"
    old = "# roadmap-refine Specification\n\n## Requirements\n\n### Requirement: The job stages one item.\nThe job SHALL stage one item.\n"
    new = old.replace("one item.", "two items.")
    (stage_repo.clone / spec_path).write_text(old, encoding="utf-8")
    stage_repo.git("add", "-A")
    stage_repo.git("commit", "-q", "-m", "old spec")
    stage_repo.git("push", "-q", "origin", "main")

    proposal = make_stage_proposal(
        specs=[
            {
                "capability": "roadmap-refine",
                "modified": [
                    {
                        "name": "The job stages one item.",
                        "text": "The job SHALL stage one item now.",
                        "scenarios": [
                            {"name": "One item", "when": "the job runs", "then": "it stages one"}
                        ],
                    }
                ],
            }
        ]
    )
    sha = _push(stage_repo, _change(proposal, known={"roadmap-refine"}))
    (stage_repo.clone / spec_path).write_text(new, encoding="utf-8")
    stage_repo.git("add", "-A")
    stage_repo.git("commit", "-q", "-m", "move the base spec")
    stage_repo.git("push", "-q", "origin", "main")

    result = _run(stage_repo, _facts(stage_repo, sha=sha))

    assert [p.rule for p in result.problems] == ["spec-moved"]


def test_an_unreadable_tasks_file_is_reported(stage_repo: StageRepo) -> None:
    files = _change()
    tasks = files[f"openspec/changes/{CHANGE}/tasks.md"]
    files[f"openspec/changes/{CHANGE}/tasks.md"] = tasks.replace(
        "Reads: `src/devops_cli/sample.py`. Changes:", "Changes:"
    )
    sha = _push(stage_repo, files)

    result = _run(stage_repo, _facts(stage_repo, sha=sha))

    assert [(p.path, p.rule) for p in result.problems] == [("tasks.md", "read")]


@pytest.mark.parametrize(
    "changes",
    [
        "each module that names an old path",
        f"`openspec/changes/{CHANGE}/proposal.md`",
    ],
    ids=["3187-no-file", "3308-change-folder"],
)
def test_a_plan_that_the_model_refuses_is_reported_as_a_read_problem(
    stage_repo: StageRepo, changes: str
) -> None:
    files = _change()
    tasks = files[f"openspec/changes/{CHANGE}/tasks.md"]
    files[f"openspec/changes/{CHANGE}/tasks.md"] = re.sub(
        r"Changes: .*?\.\n", f"Changes: {changes}.\n", tasks, count=1
    )
    sha = _push(stage_repo, files)

    result = _run(stage_repo, _facts(stage_repo, sha=sha))

    assert [(p.path, p.rule) for p in result.problems] == [("tasks.md", "read")]


def test_a_group_of_the_kind_other_reads_back(stage_repo: StageRepo) -> None:
    proposal = make_stage_proposal(
        skip_specs=True,
        specs=[],
        groups=[
            {
                "title": "Write the page",
                "kind": "other",
                "changes": ["docs/roadmap/plan-check.md"],
                "creates": ["docs/roadmap/plan-check.md"],
                "creates_lines": {"docs/roadmap/plan-check.md": 1},
                "implementation": "Write the page about the plan check",
                "verify": "uv run devops ci docs",
            }
        ],
    )
    sha = _push(stage_repo, _change(proposal, known={"comment-thread"}))

    result = _run(stage_repo, _facts(stage_repo, sha=sha))

    assert result.problems == ()


def test_a_long_title_is_reported(stage_repo: StageRepo) -> None:
    sha = _push(stage_repo, _change())
    title = f"{TITLE} {'word ' * 20}"

    result = _run(stage_repo, _facts(stage_repo, sha=sha, title=title))

    assert [p.rule for p in result.problems] == ["title-length"]


def test_a_long_body_is_reported(stage_repo: StageRepo) -> None:
    sha = _push(stage_repo, _change())
    body = f"{BODY}\n\n{'text ' * 200}"

    result = _run(stage_repo, _facts(stage_repo, sha=sha, body=body))

    assert [p.rule for p in result.problems] == ["body-length"]


def test_an_unread_check_is_reported(stage_repo: StageRepo) -> None:
    sha = _push(stage_repo, _change())

    result = _run(
        stage_repo,
        _facts(stage_repo, sha=sha),
        checks=CheckVerdictSummary(unread_reason="GitHub is not reachable"),
    )

    assert [p.rule for p in result.problems] == ["semantic-pr-title"]


def test_a_head_with_no_change_folder_is_reported(stage_repo: StageRepo) -> None:
    sha = _push(stage_repo, {"README.md": "No plan here.\n"})

    result = _run(stage_repo, _facts(stage_repo, sha=sha))

    assert [p.rule for p in result.problems] == ["change-folder"]


def test_an_openspec_problem_is_reported(stage_repo: StageRepo) -> None:
    sha = _push(stage_repo, _change())
    report = (
        '{"items": [{"issues": [{"path": "tasks.md", "message": "The tasks are not valid."}]}]}'
    )

    result = _run(stage_repo, _facts(stage_repo, sha=sha), tool=_Tool(report))

    assert [(p.path, p.rule) for p in result.problems] == [(CHANGE, "openspec")]
