"""Copilot's review passes on the release pull request, held to the budget `.github/roadmap.toml`
sets in `release_copilot_passes` (#1345).

A pass is one Copilot review of the pull request: every review Copilot has submitted, whoever
asked for it, and one it is still running. A review is Copilot's only by its author's exact login
(`pr_monitor.is_copilot_review`). The budget is read on the default branch, like every roadmap
setting, and nothing is stored: the count comes from the pull request's own reviews, so each
release pull request starts with the whole budget.

`request_copilot_pass` is the one code path that asks for a pass, through gh's documented
`gh pr edit <number> --add-reviewer @copilot`, and only on the release pull request while its
passes are below the budget.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_GH_COPILOT_REVIEWER,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_ROADMAP_CONFIG_PATH,
)
from devops_cli.dry_run.requests import PlannedRequest, both
from devops_cli.exceptions.git import CopilotPassRefusedError, GitHubOperationError
from devops_cli.github.pr_branches import branch_ref, is_release_pr
from devops_cli.github.pr_monitor import (
    _detect_copilot_status,
    _fetch_pr_details,
    _fetch_raw_reviews,
    is_copilot_review,
)
from devops_cli.github.rate_limiter import run_gh
from devops_cli.lang import MESSAGES
from devops_cli.roadmap import store as roadmap_store
from devops_cli.roadmap.config import read_roadmap_config


class CopilotPasses(BaseModel):
    """Copilot's passes on one pull request, and the budget they are held to."""

    model_config = ConfigDict(frozen=True)

    submitted: int = Field(ge=0)
    running: bool
    budget: int = Field(ge=1)

    @property
    def used(self) -> int:
        """The passes spent: each review Copilot submitted, and one it is still running."""
        return self.submitted + int(self.running)

    @property
    def spent(self) -> bool:
        """Whether no pass is left to request."""
        return self.used >= self.budget


def count_copilot_passes(reviews: Iterable[Any], *, running: bool, budget: int) -> CopilotPasses:
    """The passes Copilot's reviews among `reviews`, and a pass still `running`, spend of
    `budget`."""
    submitted = sum(1 for review in reviews if is_copilot_review(review))
    return CopilotPasses(submitted=submitted, running=running, budget=budget)


def read_copilot_budget(repo: str) -> int:
    """`release_copilot_passes` from `repo`'s `.github/roadmap.toml` on its default branch."""
    store = roadmap_store.get_roadmap_store(repo)
    return read_roadmap_config(store, ref=None).release_copilot_passes


def read_copilot_passes(owner: str, repo_name: str, number: int, *, budget: int) -> CopilotPasses:
    """Copilot's passes on pull request `number`, raising when its reviews or its timeline can't
    be read, since the passes are then unknown."""
    reviews = _fetch_raw_reviews(owner, repo_name, number)
    status = _detect_copilot_status(owner, repo_name, number, reviews, reviews_err=reviews.error)
    if status.state == "unread":
        reason = status.unread_reason[:CONST_MAX_ERROR_DETAIL_LENGTH]
        raise GitHubOperationError(
            MESSAGES.pr.copilot_passes_unread.format(number=number, reason=reason),
            operation="copilot_pass.read",
            details={"pull_request": number, "reason": reason},
        )
    return count_copilot_passes(reviews, running=status.is_active, budget=budget)


def copilot_pass_argv(number: int | str, repo: str) -> list[str]:
    """The gh command that requests a Copilot pass on pull request `number` of `repo`."""
    reviewer = ["--add-reviewer", CONST_GH_COPILOT_REVIEWER]
    return [CONST_GH_CLI, "pr", "edit", str(number), *reviewer, "--repo", repo]


def _require_release_pr(pr_data: dict[str, Any], number: int) -> None:
    """Refuse any pull request but the release pull request, naming its two branches."""
    if is_release_pr(pr_data):
        return
    head, base = branch_ref(pr_data, "head"), branch_ref(pr_data, "base")
    raise CopilotPassRefusedError(
        MESSAGES.pr.copilot_pass_not_release_pr.format(number=number, head=head, base=base),
        details={"pull_request": number, "head": head, "base": base},
    )


def _refuse_spent(passes: CopilotPasses, number: int) -> None:
    """Refuse a pass once `passes` has spent the budget."""
    if not passes.spent:
        return
    used, budget = passes.used, passes.budget
    raise CopilotPassRefusedError(
        MESSAGES.pr.copilot_budget_spent.format(used=used, budget=budget, number=number),
        details={"pull_request": number, "used": used, "budget": budget},
    )


def _send_request(number: int, repo: str) -> None:
    """Request the pass, raising with gh's error when it is refused."""
    proc = run_gh(copilot_pass_argv(number, repo), check=False)
    if proc.returncode == 0:
        return
    failure = str(proc.stderr or proc.stdout or f"exit code {proc.returncode}").strip()
    error = failure[:CONST_MAX_ERROR_DETAIL_LENGTH]
    raise GitHubOperationError(
        MESSAGES.pr.copilot_pass_request_failed.format(number=number, error=error),
        operation="copilot_pass.request",
        details={"pull_request": number, "error": error},
    )


def request_copilot_pass(owner: str, repo_name: str, number: int) -> CopilotPasses:
    """Request one Copilot pass on release pull request `number` of `owner/repo_name`, and
    return the passes it had before the request.

    Raises `CopilotPassRefusedError`, having requested nothing, when the pull request is not the
    release pull request or its budget is spent, `GitHubOperationError` when a GitHub read or the
    request fails, and `ConfigurationError` when `.github/roadmap.toml` is not valid.
    """
    repo = f"{owner}/{repo_name}"
    _require_release_pr(_fetch_pr_details(owner, repo_name, number), number)
    passes = read_copilot_passes(owner, repo_name, number, budget=read_copilot_budget(repo))
    _refuse_spent(passes, number)
    _send_request(number, repo)
    return passes


def plan_copilot_pass(repo: str, number: int | None) -> list[PlannedRequest]:
    """The requests `request_copilot_pass` makes on pull request `number`, or on the current
    branch's when there is none, in order and with no value read (#412)."""
    texts = MESSAGES.pr
    pull = "<number>" if number is None else str(number)
    owner = repo.split("/", 1)[0]
    on_release = texts.copilot_pass_plan_release.format(number=pull)
    resolve = [
        PlannedRequest("GET", f"repos/{repo}/pulls?head={owner}:<branch>&state=open"),
        PlannedRequest(
            "GET",
            texts.copilot_pass_plan_branch_pr,
            condition=texts.copilot_pass_plan_branch_pr_unnamed,
        ),
    ]
    per_page = texts.copilot_pass_plan_per_page
    return [
        *(resolve if number is None else []),
        PlannedRequest("GET", f"repos/{repo}/pulls/{pull}"),
        PlannedRequest(
            "GET", f"repos/{repo}/contents/{CONST_ROADMAP_CONFIG_PATH}", condition=on_release
        ),
        PlannedRequest(
            "GET", f"repos/{repo}/pulls/{pull}/reviews", condition=on_release, repeat=per_page
        ),
        PlannedRequest(
            "GET", f"repos/{repo}/issues/{pull}/timeline", condition=on_release, repeat=per_page
        ),
        PlannedRequest(
            "GraphQL write",
            f"{repo} pull request {pull}: request Copilot's review",
            argv=tuple(copilot_pass_argv(pull, repo)),
            condition=both(on_release, texts.copilot_pass_plan_below_budget),
        ),
    ]


__all__ = [
    "CopilotPasses",
    "copilot_pass_argv",
    "count_copilot_passes",
    "plan_copilot_pass",
    "read_copilot_budget",
    "read_copilot_passes",
    "request_copilot_pass",
]
