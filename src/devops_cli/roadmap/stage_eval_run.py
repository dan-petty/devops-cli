"""The live run of the golden set: the real stage code on each case with a chosen model (#3028).

For each case the run checks out the tracked files of the staging commit, makes the `Item` from the
issue text of the case, and calls `plan_item`, which is the planner of the job: the planner call,
the checks of the reply (`check_proposal`), one return of a refused reply, the measure of the
groups and `openspec validate`. A recording client keeps the replies that the job saw. The first
reply is judged by the gates again, against the tree of the checkout, so the score shows what the
model did before the gates sent a reply back.

The client sends a reply that breaks the schema back to the model inside one call, so the run
cannot see it. A run that ends on a schema failure counts as a `kind` problem of the first reply.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from devops_cli.ai.client.models import (
    AIClientError,
    AICredentialsError,
    StructuredOutputValidationError,
)
from devops_cli.exceptions import RoadmapStageError, ToolExecutionError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import git
from devops_cli.roadmap.stage import OverBudget, StageClient, plan_item
from devops_cli.roadmap.stage_change import StageProposal, render_change
from devops_cli.roadmap.stage_eval_cases import GateName, StageCase
from devops_cli.roadmap.stage_eval_gates import PlanUnderTest, run_gates
from devops_cli.roadmap.stage_paths import StagedTree
from devops_cli.roadmap.store import Item
from devops_cli.security.sanitizer import mask_secrets

_OPERATION = "roadmap.eval.stage"
# Where the issues of the cases link to: the run reads no issue from GitHub.
_ISSUE_URL = "https://example.com/issues/{number}"


class Outcome(StrEnum):
    """How a case ended. `refused` is a plan that the checks refused after the one return."""

    STAGED = "staged"
    REFUSED = "refused"
    OVER_BUDGET = "over_budget"
    FAILED = "failed"


@dataclass(frozen=True)
class CaseRun:
    """The run of one case: how it ended and why, the model calls that the planner made, and the
    problems that each gate found in the first reply (None when no reply came)."""

    name: str
    outcome: Outcome
    reason: str
    calls: int
    first: dict[GateName, list[str]] | None


class RecordingClient:
    """A stage client that keeps the replies of the model and counts the calls."""

    def __init__(self, inner: StageClient) -> None:
        self._inner = inner
        self.replies: list[StageProposal] = []
        self.calls = 0

    def chat_structured[M: BaseModel](
        self, system: str, prompt: str, schema: type[M], *, max_retries: int
    ) -> M:
        """The reply of the inner client, kept when it is a plan."""
        self.calls += 1
        reply = self._inner.chat_structured(system, prompt, schema, max_retries=max_retries)
        if isinstance(reply, StageProposal):
            self.replies.append(reply)
        return reply


def item_of(case: StageCase) -> Item:
    """The item the job plans for the case: the title and the body of the issue."""
    return Item(
        number=case.issue,
        title=case.title,
        url=_ISSUE_URL.format(number=case.issue),
        body=case.issue_body,
    )


@contextmanager
def checkout_at(repository: Path, commit: str) -> Iterator[Path]:
    """The tracked files of `commit` in a new detached worktree of `repository`, removed after.
    A commit the repository lacks raises `GitOperationError`."""
    parent = Path(tempfile.mkdtemp(prefix="stage-eval-"))
    tree = parent / "tree"
    try:
        git(repository, "worktree", "add", "--detach", str(tree), commit, operation=_OPERATION)
        try:
            yield tree
        finally:
            git(repository, "worktree", "remove", "--force", str(tree), operation=_OPERATION)
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def _first_reply_problems(
    case: StageCase, reply: StageProposal, source: Path
) -> dict[GateName, list[str]]:
    """What each gate finds in the first reply, against the files of the checkout and the change
    folder that the reply would write."""
    files = render_change(case.change, reply, frozenset(), created=datetime.now(UTC).date())
    tree = StagedTree.read(source, operation=_OPERATION).with_files(files)
    return run_gates(PlanUnderTest.of_reply(reply.groups, tree))


def _ended(exc: Exception) -> tuple[Outcome, str]:
    """How a case that raised ended, and the reason, never the model's text."""
    if isinstance(exc, RoadmapStageError):
        return Outcome.REFUSED, mask_secrets(str(exc))
    reason = type(exc).__name__
    if isinstance(exc, ToolExecutionError):
        reason = f"{reason}: {mask_secrets(str(exc))}"
    return Outcome.FAILED, reason


def run_case(
    case: StageCase, client: StageClient, repository: Path, *, step_tokens: int | None = None
) -> CaseRun:
    """Plan one case in a checkout of its staging commit. Rejected credentials stop the run; any
    other error of the planner ends the case as a `refused` or `failed` case."""
    recorder = RecordingClient(client)
    with checkout_at(repository, case.base_commit) as source:
        try:
            planned = plan_item(
                item_of(case),
                client=recorder,
                checkout=source,
                sha=case.base_commit,
                step_tokens=step_tokens,
            )
            outcome, reason = (
                (Outcome.OVER_BUDGET, MESSAGES.roadmap.stage_eval_over_budget)
                if isinstance(planned, OverBudget)
                else (Outcome.STAGED, "")
            )
        except AICredentialsError:
            raise
        except (AIClientError, RoadmapStageError, ToolExecutionError) as exc:
            outcome, reason = _ended(exc)
            if isinstance(exc, StructuredOutputValidationError) and not recorder.replies:
                return CaseRun(case.name, outcome, reason, recorder.calls, _schema_failure())
        first = (
            _first_reply_problems(case, recorder.replies[0], source) if recorder.replies else None
        )
    return CaseRun(case.name, outcome, reason, recorder.calls, first)


def _schema_failure() -> dict[GateName, list[str]]:
    """The problems of a first reply that the schema refused twice: the `kind` gate fails."""
    return {GateName.PATHS: [], GateName.KIND: [MESSAGES.roadmap.stage_eval_schema_failed]}


def run_cases(
    cases: Sequence[StageCase],
    client: StageClient,
    repository: Path,
    *,
    step_tokens: int | None = None,
) -> list[CaseRun]:
    """Plan each case, one at a time."""
    return [run_case(case, client, repository, step_tokens=step_tokens) for case in cases]
