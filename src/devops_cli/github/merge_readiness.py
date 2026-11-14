"""The merge readiness of a pull request, as data (#998, #2442, #2443).

`assess_merge_readiness` judges a pull request that GitHub has read: its mergeable state, its
draft state, its checks, its review threads and the item rules of `roadmap/grounding.py`. It
returns what blocks the merge, each blocker with its kind, what only advises, the checks it read
and the facts the item rules judged. It prints nothing and exits nothing: `devops pr
check-readiness` renders it, and `devops pr ready` and `devops pr monitor` map its kinds to their
own exit codes.

Each `gh` call goes through `runner`, and each read of the GitHub session through `session`, so
a caller (and a test) gives both, as `GitHubRoadmapStore` takes them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final, NamedTuple
from urllib.parse import urlencode

from pydantic import AliasPath, BaseModel, ConfigDict, Field
from pydantic import ValidationError as MalformedPayloadError

from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_GITHUB_COMPARE_FILES_LIMIT,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_OPENSPEC_CHANGES_DIR,
    CONST_PR_CLOSING_ISSUE_LABELS_PAGE,
    CONST_PR_CLOSING_ISSUES_PAGE,
)
from devops_cli.core.repo import find_repo_root
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.check_verdict import (
    CheckBucket,
    CheckVerdictSummary,
    read_check_runs,
    read_commit_checks,
)
from devops_cli.github.client import PullRequestFile
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
    plan_blockers,
    plan_issue,
)
from devops_cli.roadmap.pull_form import body_problems


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


class BlockerKind(StrEnum):
    """What keeps a pull request from merging; each command maps it to its own exit code."""

    CLOSED = "closed"
    CONFLICT = "conflict"
    MERGEABILITY = "mergeability"
    BRANCH_PROTECTION = "branch_protection"
    DRAFT = "draft"
    CHECKS_FAILING = "checks_failing"
    CHECKS_UNREAD = "checks_unread"
    CHECKS_PENDING = "checks_pending"
    THREADS = "threads"
    THREADS_UNREAD = "threads_unread"
    GROUNDING = "grounding"
    BODY_FORM = "body_form"
    STAGE_EVAL = "stage_eval"
    READINESS = "readiness"


CHECK_FAILURE_KINDS = frozenset({BlockerKind.CHECKS_FAILING, BlockerKind.CHECKS_UNREAD})


class Blocker(NamedTuple):
    """One thing that keeps a pull request from merging, as `check-readiness` prints it."""

    kind: BlockerKind
    text: str


class Advisory(NamedTuple):
    """A fact a person sees beside the verdict, which blocks nothing."""

    level: AdvisoryLevel
    text: str


@dataclass(frozen=True)
class MergeReadiness:
    """The merge-readiness verdict of one pull request.

    `blocking` is what keeps it from merging, in the order it was found, each with its kind.
    `pending_checks` names the checks still running, a blocker unless `allow_pending_checks`
    excused them. `checks` is the read of the head commit's checks, None when the payload names
    no head commit. `threads_to_show` are the review threads that block it, for a caller to list.
    `grounding` is what the item rules judged, None where they do not apply.
    """

    blocking: tuple[Blocker, ...] = ()
    advisories: tuple[Advisory, ...] = ()
    pending_checks: tuple[str, ...] = ()
    checks: CheckVerdictSummary | None = None
    threads_to_show: tuple[ReviewThread, ...] = ()
    grounding: Grounding | None = None

    @property
    def blockers(self) -> tuple[str, ...]:
        """The text of each blocker, as `check-readiness` prints it."""
        return tuple(blocker.text for blocker in self.blocking)

    @property
    def kinds(self) -> frozenset[BlockerKind]:
        """The kinds of blocker the verdict holds."""
        return frozenset(blocker.kind for blocker in self.blocking)

    @property
    def is_ready(self) -> bool:
        """Whether nothing blocks the merge."""
        return not self.blocking


@dataclass
class _Verdict:
    """The verdict being assembled, one concern at a time."""

    blocking: list[Blocker] = field(default_factory=list)
    advisories: list[Advisory] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    checks: CheckVerdictSummary | None = None
    threads: list[ReviewThread] = field(default_factory=list)
    grounding: Grounding | None = None

    def block(self, kind: BlockerKind, text: str) -> None:
        self.blocking.append(Blocker(kind, text))

    def warn(self, text: str) -> None:
        self.advisories.append(Advisory(AdvisoryLevel.WARNING, text))

    def inform(self, text: str) -> None:
        self.advisories.append(Advisory(AdvisoryLevel.INFO, text))

    def frozen(self) -> MergeReadiness:
        return MergeReadiness(
            blocking=tuple(self.blocking),
            advisories=tuple(self.advisories),
            pending_checks=tuple(self.pending),
            checks=self.checks,
            threads_to_show=tuple(self.threads),
            grounding=self.grounding,
        )


CONFLICT_STATES = frozenset({"dirty", "conflicting"})
"""The mergeable states of a pull request whose branch conflicts with its base: `dirty` in REST,
`conflicting` in GraphQL."""


def merge_conflict(mergeable: bool | None, mergeable_state: str) -> bool | None:
    """Whether GitHub reports a merge conflict between a pull request and its base: True for a
    conflict, None while GitHub has not computed the state, and False else. A branch that is only
    behind its base has no conflict. `devops pr check-readiness` and the Service row
    `pr_conflicts` judge a conflict with this one function (#4027)."""
    if mergeable is False or mergeable_state in CONFLICT_STATES:
        return True
    if mergeable is None or mergeable_state in ("unknown", ""):
        return None
    return False


def _judge_mergeable(
    verdict: _Verdict, pr_data: dict[str, Any], pr_num: int, allow_blocked_state: bool
) -> None:
    """Judge GitHub's mergeable state: closed, conflicting, unknown and blocked block.

    `behind` blocks nothing: GitHub merges a branch behind its base unless a ruleset requires an
    up-to-date branch, and then it reports `blocked`.
    """
    if pr_data.get("state", "").lower() == "closed":
        verdict.block(BlockerKind.CLOSED, f"PR #{pr_num} is closed without being merged.")
        return

    mergeable = pr_data.get("mergeable")
    mergeable_state = pr_data.get("mergeable_state", "")
    base_ref = pr_data.get("base", {}).get("ref", "")

    conflict = merge_conflict(mergeable, mergeable_state)
    if conflict:
        verdict.block(
            BlockerKind.CONFLICT,
            f"PR #{pr_num} has merge conflicts with base branch '{base_ref}'.",
        )
    elif conflict is None:
        verdict.block(
            BlockerKind.MERGEABILITY,
            f"PR #{pr_num} mergeability is unresolved or still calculating on GitHub "
            f"(mergeable: {mergeable}, state: '{mergeable_state}').",
        )
    elif mergeable_state == "blocked" and allow_blocked_state:
        verdict.warn(
            f"PR #{pr_num} merge state is currently 'blocked' by branch protection or pending checks."
        )
    elif mergeable_state == "blocked":
        verdict.block(
            BlockerKind.BRANCH_PROTECTION,
            f"PR #{pr_num} merge state is blocked by GitHub branch protection or checks "
            "(state: 'blocked').",
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
        verdict.block(
            BlockerKind.DRAFT, f"PR #{pr_num} is in draft status; GitHub refuses to merge a draft."
        )


def _judge_checks(
    verdict: _Verdict,
    head_sha: str,
    pr_num: int,
    owner: str,
    repo_name: str,
    reads: _Reads,
) -> None:
    """Failing or unread checks block; running ones block unless excused.

    With `commit_statuses` off, the checks are the check runs only: a token without the `statuses`
    permission reads them, and no request goes to the commit status endpoint (#2877)."""
    if not head_sha:
        return
    if reads.commit_statuses:
        checks = read_commit_checks(
            owner, repo_name, head_sha, runner=reads.runner, session=reads.session
        )
    else:
        checks = read_check_runs(owner, repo_name, head_sha, session=reads.session)
    verdict.checks = checks
    if checks.unread_reason:
        verdict.block(
            BlockerKind.CHECKS_UNREAD,
            f"PR #{pr_num} check verification failed closed: {checks.unread_reason}",
        )
        return

    failing = sorted(
        item.name
        for item in checks.items
        if item.bucket in (CheckBucket.FAIL, CheckBucket.CANCEL, CheckBucket.UNREAD)
    )
    pending = sorted(item.name for item in checks.items if item.bucket == CheckBucket.PENDING)
    if failing:
        verdict.block(
            BlockerKind.CHECKS_FAILING,
            f"PR #{pr_num} has {len(failing)} failing check(s): {', '.join(failing)}.",
        )
    verdict.pending.extend(pending)
    if not pending:
        return
    message = f"PR #{pr_num} has {len(pending)} check(s) still running: {', '.join(pending)}."
    if reads.options.allow_pending_checks:
        verdict.warn(message)
    else:
        verdict.block(BlockerKind.CHECKS_PENDING, message)


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
        verdict.block(
            BlockerKind.THREADS_UNREAD,
            f"Could not retrieve review threads for PR #{pr_num}: {exc}",
        )
        return
    if not unresolved:
        return
    if not reads.options.allow_replied_threads:
        verdict.threads.extend(unresolved)
        verdict.block(
            BlockerKind.THREADS,
            f"PR #{pr_num} has {len(unresolved)} unresolved review discussion thread(s).",
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
        verdict.block(
            BlockerKind.THREADS,
            f"PR #{pr_num} has {len(unreplied)} unreplied review discussion thread(s).",
        )


def _gh_failure(res: Any) -> str:
    """Name a failed `gh` call by its own message, bounded for the blocker that repeats it."""
    return ((res.stderr or "").strip() or f"exit code {res.returncode}")[
        :CONST_MAX_ERROR_DETAIL_LENGTH
    ]


def read_changed_files(
    owner: str, repo_name: str, base: str, head: str, *, session: GitHubSession | None = None
) -> ChangedFilesRead:
    """Read the files a pull request changes, keeping a failure for the caller.

    The files are the compare of the base branch `base` and the head commit `head`. GitHub
    compares from the merge base of the two, so this is the diff a squash merge applies. The
    payload's `base.sha` is not used: GitHub does not move it when a merge commit moves the merge
    base, and the pull request's own file list keeps that stale base too (#2530). GitHub keeps the
    head commit of a fork's pull request in the base repository, so `head` is a commit sha for a
    fork too.
    """
    try:
        client = (session or get_github_session()).client
        compared = client.get_compare_files(f"{owner}/{repo_name}", base, head)
        return ChangedFilesRead(compared.files, compared.truncated)
    except GitHubOperationError as exc:
        return ChangedFilesRead([], truncated=False, error=str(exc))


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


# The paths that change the stage prompt or a check of the stage job. A pull request that changes
# one states the stage eval evidence of the change (#3398).
STAGE_CHANGE_TRIGGER_PATHS: frozenset[str] = frozenset(
    {
        "src/devops_cli/ai/tasks/roadmap_stage_change.md",
        "src/devops_cli/roadmap/stage_change.py",
        "src/devops_cli/roadmap/stage_form.py",
        "src/devops_cli/roadmap/stage_paths.py",
        "src/devops_cli/roadmap/stage_criteria.py",
        "src/devops_cli/roadmap/stage_eval_gates.py",
        "src/devops_cli/roadmap/stage_move.py",
    }
)
_REPLAY_COMMAND: Final[re.Pattern[str]] = re.compile(r"uv run devops roadmap eval stage\b[^\n`]*")
_MODEL_FLAG: Final[re.Pattern[str]] = re.compile(r"--model(?:=|\s+)(\S+)")
_MODEL_WORD: Final[re.Pattern[str]] = re.compile(r"--model\b")
_NUMBER: Final[str] = r"\d+(?:[./]\d+)?%?"


def _score_after(word: str, body: str) -> bool:
    """Whether a number stands beside `word` on its line, within the text that states a score."""
    pattern = re.compile(rf"\b{word}\b[^\n]{{0,60}}?{_NUMBER}", re.IGNORECASE)
    return pattern.search(body) is not None


def stage_eval_problems(body: str) -> tuple[str, ...]:
    """The problems of the stage eval evidence in `body`, or none (#3398).

    A body that changes a stage trigger path gives one of two forms. A replay holds
    `uv run devops roadmap eval stage --replay` and a number before and after. A live run holds a
    score before and after and one `--model` name. A number must stand beside its word, and two
    different models do not pass."""
    commands = _REPLAY_COMMAND.findall(body)
    if not commands:
        return ("the body holds no `uv run devops roadmap eval stage` command",)
    replays = [command for command in commands if "--replay" in command]
    if replays and _score_after("before", body) and _score_after("after", body):
        return ()
    live = [command for command in commands if "--replay" not in command]
    problems: list[str] = []
    models = [name for command in live for name in _MODEL_FLAG.findall(command)]
    if any(_MODEL_WORD.search(command) and not _MODEL_FLAG.search(command) for command in live):
        problems.append("the `--model` flag names no model")
    if len(set(models)) > 1:
        problems.append("the body names more than one model")
    if not problems and models and _score_after("before", body) and _score_after("after", body):
        return ()
    if not _score_after("before", body) or not _score_after("after", body):
        problems.append("the body states no number before and after")
    return tuple(problems) or ("the body holds no live `--model` name",)


def _judge_stage_eval(
    verdict: _Verdict, pr_data: dict[str, Any], pr_num: int, changed: ChangedFilesRead
) -> None:
    """Hold a pull request that changes a stage trigger path to its stage eval evidence (#3398)."""
    if changed.error or changed.truncated:
        return
    path = next(
        (entry.filename for entry in changed.files if entry.filename in STAGE_CHANGE_TRIGGER_PATHS),
        None,
    )
    if path is None:
        return
    problems = stage_eval_problems(str(pr_data.get("body") or ""))
    if problems:
        verdict.block(
            BlockerKind.STAGE_EVAL,
            MESSAGES.pr.stage_eval_evidence_missing.format(
                number=pr_num, path=path, problem=problems[0]
            ),
        )


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

    A delivery's body must keep the form of `body_problems`, one blocker for each problem (#3259).

    A lookup of the change directory that fails for any reason but a 404 can't rule grounding
    out, so the rules still apply and the failure is a blocker. Where grounding does not apply,
    an unread or a truncated file list is a warning, since only the perimeter advisory reads it.

    A compare answer that holds GitHub's limit of files can be truncated, so no rule that reads
    the file list judges it: one blocker names the limit, and the rules of the body and of the
    issues the PR closes still apply (#2530).
    """
    try:
        applies = _base_has_change_folders(pr_data, owner, repo_name, runner)
    except GitHubOperationError as exc:
        applies = True
        verdict.block(
            BlockerKind.GROUNDING,
            MESSAGES.pr.grounding_changes_dir_unread.format(
                number=pr_num, path=CONST_OPENSPEC_CHANGES_DIR, error=exc
            ),
        )
    if not applies:
        if changed.error:
            verdict.warn(
                MESSAGES.pr.changed_files_unread.format(number=pr_num, error=changed.error)
            )
        elif changed.truncated:
            verdict.warn(
                MESSAGES.pr.changed_files_truncated.format(
                    number=pr_num, limit=CONST_GITHUB_COMPARE_FILES_LIMIT
                )
            )
        return
    repo = f"{owner}/{repo_name}"
    grounding = Grounding(
        pr_num, owner, repo, _branch_ref(pr_data, "base"), _default_branch(pr_data), changed
    )
    if (planned := plan_issue(str(pr_data.get("title") or ""))) is not None:
        # A plan delivers no item: it closes nothing, so no closing issue is read (#3280).
        verdict.grounding = grounding
        texts = (
            [MESSAGES.pr.grounding_files_unread.format(number=pr_num, error=changed.error)]
            if changed.error
            else plan_blockers(
                pr_num, planned, str(pr_data.get("body") or ""), changed, grounding.base
            )
        )
        for text in texts:
            verdict.block(BlockerKind.GROUNDING, text)
        return
    for problem in body_problems(str(pr_data.get("body") or "")):
        verdict.block(
            BlockerKind.BODY_FORM,
            MESSAGES.pr.body_form_problem.format(number=pr_num, problem=problem),
        )
    if grounding.into_default:
        grounding = grounding._replace(
            closing=read_closing_issues(owner, repo_name, pr_num, runner=runner)
        )
    verdict.grounding = grounding
    for text in grounding_blockers(grounding):
        verdict.block(BlockerKind.GROUNDING, text)


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
    commit_statuses: bool = True


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
    commit_statuses: bool = True,
) -> MergeReadiness:
    """Judge pull request `pr_num`, whose REST payload is `pr_data`, for merge readiness.

    It reads the head commit's checks, the unresolved review threads, the changed files and,
    where the item rules apply, the base's change directory and the issues the PR closes.
    `review_root` is the checkout whose review.toml suppressions the perimeter advisory reads;
    without it, the repository of the working directory, found only when the PR changes a file.
    The advisory does not judge a file list that holds GitHub's limit of files (#2530).
    With `commit_statuses` off, the checks are the check runs only, for a token that holds no
    `statuses` permission. A merged PR is ready and nothing is read.
    """
    if pr_data.get("merged") is True:
        return MergeReadiness()
    reads = _Reads(options or ReadinessOptions(), runner, session, commit_statuses)
    verdict = _Verdict()
    _judge_mergeable(verdict, pr_data, pr_num, reads.options.allow_blocked_state)
    _judge_draft(verdict, pr_data, pr_num, reads.options.allow_draft)
    head_sha = str(pr_data.get("head", {}).get("sha") or "")
    _judge_checks(verdict, head_sha, pr_num, owner, repo_name, reads)
    _judge_threads(verdict, pr_num, owner, repo_name, reads)
    changed = read_changed_files(
        owner, repo_name, _branch_ref(pr_data, "base"), head_sha, session=session
    )
    _judge_stage_eval(verdict, pr_data, pr_num, changed)
    _judge_grounding(verdict, pr_data, pr_num, owner, repo_name, changed, runner)
    if changed.files and not changed.truncated:
        advisory = perimeter_advisory(changed.files, review_root or find_repo_root())
        if advisory is not None:
            verdict.advisories.append(advisory)
    return verdict.frozen()
