"""The merge readiness of a pull request, as data (#998, #2442).

`assess_merge_readiness` judges a pull request that GitHub has read: its mergeable state, its
draft state, its checks, its review threads and the item rules of `roadmap/grounding.py`. It
returns what blocks the merge, what only advises, the checks still running and the facts the
item rules judged. It prints nothing and exits nothing: `devops pr check-readiness` renders it.

Each `gh` call goes through `runner`, and each read of the GitHub session through `session`, so
a caller (and a test) gives both, as `GitHubRoadmapStore` takes them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from http import HTTPStatus
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import urlencode

from pydantic import AliasPath, BaseModel, ConfigDict, Field
from pydantic import ValidationError as MalformedPayloadError

from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_PR_CLOSING_ISSUE_LABELS_PAGE,
    CONST_PR_CLOSING_ISSUES_PAGE,
)
from devops_cli.core.repo import find_repo_root
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.check_verdict import CheckBucket, read_commit_checks
from devops_cli.github.client import GitHubClient, PullRequestFile
from devops_cli.github.error_classifier import gh_http_status
from devops_cli.github.pr_threads import (
    GhRun,
    ReviewThread,
    graphql_args,
    has_non_opener_reply,
    list_pr_review_threads,
)
from devops_cli.github.rate_limiter import run_gh
from devops_cli.github.session import GitHubSession, get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.grounding import (
    ChangedFilesRead,
    ClosingIssue,
    ClosingRead,
    Grounding,
    grounding_blockers,
)


@dataclass(frozen=True)
class ReadinessOptions:
    """What a caller excuses: each option turns its blocker into an advisory."""

    allow_draft: bool = False
    allow_blocked_state: bool = False
    allow_replied_threads: bool = False
    allow_pending_checks: bool = False


class AdvisoryLevel(StrEnum):
    """How an advisory is shown; no advisory changes an exit code."""

    WARNING = "warning"
    INFO = "info"


class Advisory(NamedTuple):
    """A fact a person sees beside the verdict, which blocks nothing."""

    level: AdvisoryLevel
    text: str


@dataclass(frozen=True)
class MergeReadiness:
    """The merge-readiness verdict of one pull request.

    `blockers` is what keeps it from merging, in the order it was found. `pending_checks` names
    the checks still running, a blocker unless `allow_pending_checks` excused them.
    `threads_to_show` are the review threads that block it, for a caller to list. `grounding` is
    what the item rules judged, None where they do not apply.
    """

    blockers: tuple[str, ...] = ()
    advisories: tuple[Advisory, ...] = ()
    pending_checks: tuple[str, ...] = ()
    threads_to_show: tuple[ReviewThread, ...] = ()
    grounding: Grounding | None = None

    @property
    def is_ready(self) -> bool:
        """Whether nothing blocks the merge."""
        return not self.blockers


@dataclass
class _Verdict:
    """The verdict being assembled, one concern at a time."""

    blockers: list[str] = field(default_factory=list)
    advisories: list[Advisory] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    threads: list[ReviewThread] = field(default_factory=list)
    grounding: Grounding | None = None

    def warn(self, text: str) -> None:
        self.advisories.append(Advisory(AdvisoryLevel.WARNING, text))

    def inform(self, text: str) -> None:
        self.advisories.append(Advisory(AdvisoryLevel.INFO, text))

    def frozen(self) -> MergeReadiness:
        return MergeReadiness(
            blockers=tuple(self.blockers),
            advisories=tuple(self.advisories),
            pending_checks=tuple(self.pending),
            threads_to_show=tuple(self.threads),
            grounding=self.grounding,
        )


def _judge_mergeable(
    verdict: _Verdict, pr_data: dict[str, Any], pr_num: int, allow_blocked_state: bool
) -> None:
    """Judge GitHub's mergeable state: closed, conflicting, unknown and blocked block."""
    if pr_data.get("state", "").lower() == "closed":
        verdict.blockers.append(f"PR #{pr_num} is closed without being merged.")
        return

    mergeable = pr_data.get("mergeable")
    mergeable_state = pr_data.get("mergeable_state", "")
    base_ref = pr_data.get("base", {}).get("ref", "")

    if mergeable is False or mergeable_state in ("dirty", "conflicting"):
        verdict.blockers.append(f"PR #{pr_num} has merge conflicts with base branch '{base_ref}'.")
    elif mergeable is None or mergeable_state in ("unknown", ""):
        verdict.blockers.append(
            f"PR #{pr_num} mergeability is unresolved or still calculating on GitHub "
            f"(mergeable: {mergeable}, state: '{mergeable_state}')."
        )
    elif mergeable_state == "blocked" and allow_blocked_state:
        verdict.warn(
            f"PR #{pr_num} merge state is currently 'blocked' by branch protection or pending checks."
        )
    elif mergeable_state == "blocked":
        verdict.blockers.append(
            f"PR #{pr_num} merge state is blocked by GitHub branch protection or checks "
            "(state: 'blocked')."
        )


def _judge_draft(verdict: _Verdict, pr_data: dict[str, Any], pr_num: int, allow: bool) -> None:
    """A draft cannot be merged, so it is a blocker rather than a warning.

    GitHub still reports `mergeable_state: clean` for one, which is how a draft passed this check
    and was reported ready.
    """
    if not pr_data.get("draft", False):
        return
    if allow:
        verdict.warn(f"PR #{pr_num} is in draft status and cannot be merged as-is.")
    else:
        verdict.blockers.append(
            f"PR #{pr_num} is in draft status; GitHub refuses to merge a draft."
        )


def _judge_checks(
    verdict: _Verdict,
    head_sha: str,
    pr_num: int,
    owner: str,
    repo_name: str,
    reads: _Reads,
) -> None:
    """Failing or unread checks block; running ones block unless excused."""
    if not head_sha:
        return
    checks = read_commit_checks(
        owner, repo_name, head_sha, runner=reads.runner, session=reads.session
    )
    if checks.unread_reason:
        verdict.blockers.append(
            f"PR #{pr_num} check verification failed closed: {checks.unread_reason}"
        )
        return

    failing = sorted(
        item.name
        for item in checks.items
        if item.bucket in (CheckBucket.FAIL, CheckBucket.CANCEL, CheckBucket.UNREAD)
    )
    pending = sorted(item.name for item in checks.items if item.bucket == CheckBucket.PENDING)
    if failing:
        verdict.blockers.append(
            f"PR #{pr_num} has {len(failing)} failing check(s): {', '.join(failing)}."
        )
    verdict.pending.extend(pending)
    if not pending:
        return
    message = f"PR #{pr_num} has {len(pending)} check(s) still running: {', '.join(pending)}."
    if reads.options.allow_pending_checks:
        verdict.warn(message)
    else:
        verdict.blockers.append(message)


def _judge_threads(
    verdict: _Verdict, pr_num: int, owner: str, repo_name: str, reads: _Reads
) -> None:
    """Unresolved review threads block; with `allow_replied_threads`, only unreplied ones do.

    A thread read that fails is a blocker that names it (#797).
    """
    try:
        unresolved = list_pr_review_threads(
            owner, repo_name, pr_num, unresolved_only=True, runner=reads.runner
        )
    except GitHubOperationError as exc:
        verdict.blockers.append(f"Could not retrieve review threads for PR #{pr_num}: {exc}")
        return
    if not unresolved:
        return
    if not reads.options.allow_replied_threads:
        verdict.threads.extend(unresolved)
        verdict.blockers.append(
            f"PR #{pr_num} has {len(unresolved)} unresolved review discussion thread(s)."
        )
        return
    replied = [thread for thread in unresolved if has_non_opener_reply(thread)]
    unreplied = [thread for thread in unresolved if not has_non_opener_reply(thread)]
    if replied:
        verdict.inform(
            f"PR #{pr_num} has {len(replied)} review discussion thread(s) with replies "
            "awaiting reviewer resolution."
        )
    if unreplied:
        verdict.threads.extend(unreplied)
        verdict.blockers.append(
            f"PR #{pr_num} has {len(unreplied)} unreplied review discussion thread(s)."
        )


def _gh_failure(res: Any) -> str:
    """Name a failed `gh` call by its own message, bounded for the blocker that repeats it."""
    return ((res.stderr or "").strip() or f"exit code {res.returncode}")[
        :CONST_MAX_ERROR_DETAIL_LENGTH
    ]


def read_changed_files(
    owner: str, repo_name: str, pr_num: int, *, session: GitHubSession | None = None
) -> ChangedFilesRead:
    """Read the files a pull request changes, every page, keeping a failure for the caller."""
    try:
        client = GitHubClient(session or get_github_session())
        return ChangedFilesRead(client.get_pull_files(f"{owner}/{repo_name}", pr_num))
    except GitHubOperationError as exc:
        return ChangedFilesRead([], str(exc))


def _base_has_change_folders(
    pr_data: dict[str, Any], owner: str, repo_name: str, runner: GhRun
) -> bool:
    """Whether the base commit holds the OpenSpec change directory, raising when GitHub can't say.

    A 404 means the repository keeps no change folders. Only the answer matters, so `--silent`
    drops the listing.
    """
    base = pr_data.get("base") or {}
    query = urlencode({"ref": str(base.get("sha") or base.get("ref") or "")})
    res = runner(
        [
            CONST_GH_CLI,
            "api",
            "--silent",
            f"repos/{owner}/{repo_name}/contents/{CONST_OPENSPEC_CHANGES_DIR}?{query}",
        ],
        check=False,
        quiet=True,
    )
    if res.returncode == 0:
        return True
    if gh_http_status(res.stderr or "") == HTTPStatus.NOT_FOUND:
        return False
    raise GitHubOperationError(_gh_failure(res))


class _ClosingReferences(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    total_count: int = Field(alias="totalCount")
    nodes: list[ClosingIssue] = Field(default_factory=list)


class _ClosingIssuesPayload(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    references: _ClosingReferences = Field(
        validation_alias=AliasPath("data", "repository", "pullRequest", "closingIssuesReferences")
    )


# GitHub fills `closingIssuesReferences` from the closing keywords of a PR into the default
# branch and from the issues linked to it by hand; it closes each one when the PR merges.
_CLOSING_ISSUES_QUERY = (
    "query($owner: String!, $name: String!, $number: Int!, $issues: Int!, $labels: Int!) {"
    " repository(owner: $owner, name: $name) { pullRequest(number: $number) {"
    " closingIssuesReferences(first: $issues) { totalCount nodes { number state"
    " repository { nameWithOwner } labels(first: $labels) { nodes { name } } } } } } }"
)


def closing_issues_args(owner: str, repo_name: str, pr_num: int) -> list[str]:
    """The `gh api graphql` arguments that read the issues PR `pr_num` closes when it merges."""
    variables = {
        "owner": owner,
        "name": repo_name,
        "number": pr_num,
        "issues": CONST_PR_CLOSING_ISSUES_PAGE,
        "labels": CONST_PR_CLOSING_ISSUE_LABELS_PAGE,
    }
    return [CONST_GH_CLI, *graphql_args(_CLOSING_ISSUES_QUERY, variables)]


def _graphql_error(reply: Any) -> str:
    """The first error a GraphQL reply names; empty when it names none."""
    errors = reply.get("errors") if isinstance(reply, dict) else None
    if not isinstance(errors, list) or not errors:
        return ""
    first = errors[0]
    message = first.get("message") if isinstance(first, dict) else first
    return str(message or "GraphQL error")[:CONST_MAX_ERROR_DETAIL_LENGTH]


def read_closing_issues(
    owner: str, repo_name: str, pr_num: int, *, runner: GhRun = run_gh
) -> ClosingRead:
    """Read the issues the PR closes when it merges, in one GraphQL request."""
    res = runner(closing_issues_args(owner, repo_name, pr_num), check=False, quiet=True)
    if res.returncode != 0:
        return ClosingRead(error=_gh_failure(res))
    try:
        reply = json.loads(res.stdout or "null")
        if error := _graphql_error(reply):
            return ClosingRead(error=error)
        references = _ClosingIssuesPayload.model_validate(reply).references
    except (json.JSONDecodeError, MalformedPayloadError) as exc:
        return ClosingRead(error=f"malformed reply: {exc}"[:CONST_MAX_ERROR_DETAIL_LENGTH])
    return ClosingRead(tuple(references.nodes), references.total_count)


def _branch_ref(pr_data: dict[str, Any], side: str) -> str:
    """The branch name on one side (`head` or `base`) of a pull request."""
    return str((pr_data.get(side) or {}).get("ref") or "")


def _default_branch(pr_data: dict[str, Any]) -> str:
    """The default branch of the PR's base repository; empty when the payload names none."""
    base = pr_data.get("base") or {}
    return str((base.get("repo") or {}).get("default_branch") or "")


def _judge_grounding(
    verdict: _Verdict,
    pr_data: dict[str, Any],
    pr_num: int,
    owner: str,
    repo_name: str,
    changed: ChangedFilesRead,
    runner: GhRun,
) -> None:
    """Hold a PR to the one Item it delivers, where the base holds `openspec/changes/`.

    A lookup of the change directory that fails for any reason but a 404 can't rule grounding
    out, so the rules still apply and the failure is a blocker. Where grounding does not apply,
    an unread file list is a warning, since only the perimeter advisory reads it.
    """
    try:
        applies = _base_has_change_folders(pr_data, owner, repo_name, runner)
    except GitHubOperationError as exc:
        applies = True
        verdict.blockers.append(
            MESSAGES.pr.grounding_changes_dir_unread.format(
                number=pr_num, path=CONST_OPENSPEC_CHANGES_DIR, error=exc
            )
        )
    if not applies:
        if changed.error:
            verdict.warn(
                MESSAGES.pr.changed_files_unread.format(number=pr_num, error=changed.error)
            )
        return
    repo = f"{owner}/{repo_name}"
    grounding = Grounding(
        pr_num, owner, repo, _branch_ref(pr_data, "base"), _default_branch(pr_data), changed
    )
    if grounding.into_default:
        grounding = grounding._replace(
            closing=read_closing_issues(owner, repo_name, pr_num, runner=runner)
        )
    verdict.grounding = grounding
    verdict.blockers.extend(grounding_blockers(grounding))


def perimeter_advisory(files: list[PullRequestFile], repo_root: Path) -> Advisory | None:
    """A warning naming the unexpired review.toml suppressions of `repo_root` whose path one of
    `files` touches, for a person to re-check each reason; None when none does."""
    from devops_cli.ai.review.path_classes import load_review_config
    from devops_cli.review.suppression import (
        covering_suppressions,
        format_covering_suppressions,
        load_review_suppressions,
    )

    if not files:
        return None
    config = load_review_config(repo_root=repo_root)
    covering = covering_suppressions(
        [entry.filename for entry in files], load_review_suppressions(config)
    )
    if not covering:
        return None
    return Advisory(AdvisoryLevel.WARNING, format_covering_suppressions(covering))


@dataclass(frozen=True)
class _Reads:
    """How the verdict reads GitHub, and what its caller excuses."""

    options: ReadinessOptions
    runner: GhRun
    session: GitHubSession | None


def assess_merge_readiness(
    pr_data: dict[str, Any],
    owner: str,
    repo_name: str,
    pr_num: int,
    *,
    options: ReadinessOptions | None = None,
    runner: GhRun = run_gh,
    session: GitHubSession | None = None,
    review_root: Path | None = None,
) -> MergeReadiness:
    """Judge pull request `pr_num`, whose REST payload is `pr_data`, for merge readiness.

    It reads the head commit's checks, the unresolved review threads, the changed files and,
    where the item rules apply, the base's change directory and the issues the PR closes.
    `review_root` is the checkout whose review.toml suppressions the perimeter advisory reads;
    without it, the repository of the working directory, found only when the PR changes a file.
    A merged PR is ready and nothing is read.
    """
    if pr_data.get("merged") is True:
        return MergeReadiness()
    reads = _Reads(options or ReadinessOptions(), runner, session)
    verdict = _Verdict()
    _judge_mergeable(verdict, pr_data, pr_num, reads.options.allow_blocked_state)
    _judge_draft(verdict, pr_data, pr_num, reads.options.allow_draft)
    head_sha = str(pr_data.get("head", {}).get("sha") or "")
    _judge_checks(verdict, head_sha, pr_num, owner, repo_name, reads)
    _judge_threads(verdict, pr_num, owner, repo_name, reads)
    changed = read_changed_files(owner, repo_name, pr_num, session=session)
    _judge_grounding(verdict, pr_data, pr_num, owner, repo_name, changed, runner)
    if changed.files:
        advisory = perimeter_advisory(changed.files, review_root or find_repo_root())
        if advisory is not None:
            verdict.advisories.append(advisory)
    return verdict.frozen()
