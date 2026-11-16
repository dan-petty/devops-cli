"""The facts that the step `review` reads of a bot pull request, and what its model reads (#5969).

`read_facts` reads the facts that the rules of `review.py` decide on, with no model: the check runs
of the head, the files of the diff since the merge base (the compare of the base branch and the
head), one GraphQL request for the unresolved review threads and for the merged pull requests of
the base branch since the merge base with the files that they share with the diff, the login that
last marked the pull request ready, the open
findings of the last plan comment of a plan, and the `tasks.md` of the change folder of a delivery
for `draft_readiness`. The text of the issue changed when its hash is not the hash that the stage
job recorded for the plan (`stage.text_hash`), and no Issue changed verdict answered that text yet
(`review.text`). The update time of an issue is no such fact: each label and each record write
moves it.

`read_case` reads what the model reads: the diff since the merge base, the Markdown files of the
change folder of the item at the head, and the text of the issue.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from devops_cli.config.constants import (
    CONST_OPENSPEC_ARCHIVED_FOLDER_RE,
    CONST_OPENSPEC_CHANGE_FOLDER_RE,
)
from devops_cli.exceptions.git import GitHubUnreadError
from devops_cli.github.check_verdict import CheckVerdictSummary, read_check_runs
from devops_cli.github.repo_ref import RepoRef
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.body_hash import body_hashes
from devops_cli.roadmap.implement.implement_pull import Answer, ChangeFacts, Draft, DraftKind
from devops_cli.roadmap.pr_verdict import PullKind, pull_kind
from devops_cli.roadmap.stage.stage_change import safe_text
from devops_cli.roadmap.steps.fix_plan import comment_open_findings, plan_comment
from devops_cli.roadmap.steps.ready import draft_readiness
from devops_cli.roadmap.stores.store import (
    GitHubState,
    ImplementRecordKey,
    Item,
    ReviewRecordKey,
    RoadmapStore,
    StageRecordKey,
)
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from devops_cli.github.client import GitHubClient, PullStatus

# The most characters of one text of the model in a comment, and the most evidence lines.
TEXT_CHARS: Final[int] = 600
EVIDENCE_LINES: Final[int] = 10
# The commits of the base branch that the read of the related work walks back to the merge base.
_HISTORY_DEPTH: Final[int] = 50
_PAGE: Final[int] = 100
_GRAPH_QUERY: Final[str] = f"""
query($owner: String!, $name: String!, $number: Int!, $base: String!) {{
  repository(owner: $owner, name: $name) {{
    pullRequest(number: $number) {{
      reviewThreads(first: {_PAGE}) {{ nodes {{ isResolved isOutdated path line }} }}
      timelineItems(itemTypes: [READY_FOR_REVIEW_EVENT], last: 1) {{
        nodes {{ ... on ReadyForReviewEvent {{ actor {{ login }} }} }}
      }}
    }}
    ref(qualifiedName: $base) {{
      target {{
        ... on Commit {{
          history(first: {_HISTORY_DEPTH}) {{
            nodes {{
              oid
              associatedPullRequests(first: 1) {{
                nodes {{ number merged files(first: {_PAGE}) {{ nodes {{ path }} }} }}
              }}
            }}
          }}
        }}
      }}
    }}
  }}
}}
"""


def safe(text: str, limit: int = TEXT_CHARS) -> str:
    """A text of the model or of a comment as a comment of the step can hold it: secrets masked,
    on one line, with no ping, no link and no tag (`safe_text`), and at most `limit` characters."""
    return safe_text(mask_secrets(text))[:limit]


@dataclass(frozen=True)
class RelatedPull:
    """A pull request that merged into the base branch after the merge base of the reviewed pull
    request, and the files of the reviewed diff that it changed too."""

    number: int
    files: tuple[str, ...]


@dataclass(frozen=True)
class ReviewFacts:
    """The facts of a pull request that the rules read. `item_number` is the item of its branch,
    `own_plan` the plan pull request of the item (`stage.pr`), `text_changed` whether the text of
    the item is not the text that the plan came from, `folder` the change folder of the item in the
    diff, `findings` the open findings of the last plan comment, `threads` the place of each
    unresolved review thread, `incomplete` the reason of `draft_readiness` when it refuses, and
    `ready_by` the login that last marked the pull request ready for review, or None."""

    pull: int
    kind: PullKind
    head: str
    item_number: int
    labels: tuple[str, ...] = ()
    mergeable: bool | None = True
    mergeable_state: str = "clean"
    checks: CheckVerdictSummary | None = None
    item_open: bool = True
    text_changed: bool = False
    own_plan: int | None = None
    files: tuple[str, ...] = ()
    folder: str | None = None
    related: tuple[RelatedPull, ...] = ()
    related_truncated: bool = False
    findings: tuple[str, ...] = ()
    threads: tuple[str, ...] = ()
    incomplete: str | None = None
    ready_by: str | None = None


class ReplyVerdict(StrEnum):
    """The verdicts that the model may give. The kind of the pull request picks the discard."""

    MERGEABLE = "mergeable"
    NEEDS_FIX = "needs_fix"
    DISCARD = "discard"
    ISSUE_CHANGED = "issue_changed"


class ReplyEvidence(BaseModel):
    """One place of the diff that the verdict of the model rests on."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(max_length=300, description="A file of the diff, as the diff names it")
    line: int | None = Field(default=None, ge=1, description="The line in the new file, if any")
    note: str = Field(max_length=300, description="What this place shows, in one sentence")


class ReviewReply(BaseModel):
    """The structured reply of the model of the task `review`."""

    model_config = ConfigDict(extra="forbid")

    verdict: ReplyVerdict = Field(description="The one verdict of the pull request")
    reason: str = Field(
        min_length=1, max_length=TEXT_CHARS, description="Why, in at most three sentences"
    )
    evidence: list[ReplyEvidence] = Field(
        default_factory=list,
        max_length=EVIDENCE_LINES,
        description="The places of the diff that show the reason; a discard needs at least one",
    )


@dataclass(frozen=True)
class ReviewCase:
    """What the model reads: the kind and the title of the pull request, the text of the issue,
    the plan, the diff since the merge base, the files of the diff, and the merged related work."""

    kind: PullKind
    pull: int
    title: str
    issue: str
    plan: str
    diff: str
    files: tuple[str, ...]
    related: tuple[RelatedPull, ...] = ()


# ── The GraphQL read ─────────────────────────────────────────────────────────────────────────


class _Answered(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True, frozen=True)


class _Path(_Answered):
    path: str


class _Paths(_Answered):
    nodes: list[_Path] = Field(default_factory=list)


class _Associated(_Answered):
    number: int
    merged: bool = False
    files: _Paths = Field(default_factory=_Paths)


class _AssociatedPage(_Answered):
    nodes: list[_Associated] = Field(default_factory=list)


class _Commit(_Answered):
    oid: str
    associated_pull_requests: _AssociatedPage = Field(default_factory=_AssociatedPage)


class _Commits(_Answered):
    nodes: list[_Commit] = Field(default_factory=list)


class _History(_Answered):
    history: _Commits = Field(default_factory=_Commits)


class _Ref(_Answered):
    target: _History | None = None


class _Thread(_Answered):
    is_resolved: bool = False
    is_outdated: bool = False
    path: str = ""
    line: int | None = None


class _Threads(_Answered):
    nodes: list[_Thread] = Field(default_factory=list)


class _Actor(_Answered):
    login: str = ""


class _ReadyEvent(_Answered):
    actor: _Actor | None = None


class _ReadyEvents(_Answered):
    nodes: list[_ReadyEvent] = Field(default_factory=list)


class _Pull(_Answered):
    review_threads: _Threads = Field(default_factory=_Threads)
    timeline_items: _ReadyEvents = Field(default_factory=_ReadyEvents)


class _Repository(_Answered):
    pull_request: _Pull | None = None
    ref: _Ref | None = None


class _Data(_Answered):
    repository: _Repository | None = None


class _GraphAnswer(_Answered):
    data: _Data | None = None
    errors: list[dict[str, Any]] = Field(default_factory=list)


@dataclass(frozen=True)
class _Graph:
    threads: tuple[str, ...]
    related: tuple[RelatedPull, ...]
    truncated: bool
    ready_by: str | None = None


def _read_graph(
    client: GitHubClient, ref: RepoRef, pull: int, base: str, merge_base: str, files: set[str]
) -> _Graph:
    """The unresolved review threads of the pull request, and the merged pull requests of the base
    branch after `merge_base` that share a file with `files`, from one GraphQL request. A merge
    base that is not in the last `_HISTORY_DEPTH` commits of the base branch makes the list
    `truncated`."""
    variables = {"owner": ref.owner, "name": ref.name, "number": pull, "base": f"refs/heads/{base}"}
    try:
        answer = _GraphAnswer.model_validate(client.graphql(_GRAPH_QUERY, variables))
    except ValidationError as exc:
        raise GitHubUnreadError(
            f"GitHub's answer to the review read of pull request #{pull} is no answer: "
            f"{exc.error_count()} invalid field(s)",
            details={"pull": pull},
        ) from exc
    repository = answer.data.repository if answer.data else None
    if answer.errors or repository is None:
        raise GitHubUnreadError(
            f"GitHub refused the review read of pull request #{pull}",
            details={"pull": pull, "errors": len(answer.errors)},
        )
    nodes = repository.pull_request.review_threads.nodes if repository.pull_request else []
    threads = tuple(
        f"{thread.path}:{thread.line}" if thread.line else thread.path
        for thread in nodes
        if not thread.is_resolved and not thread.is_outdated
    )
    events = repository.pull_request.timeline_items.nodes if repository.pull_request else []
    actors = [event.actor.login for event in events if event.actor and event.actor.login]
    ready_by = actors[-1] if actors else None
    target = repository.ref.target if repository.ref else None
    related: list[RelatedPull] = []
    for commit in target.history.nodes if target else []:
        if commit.oid == merge_base:
            return _Graph(threads, tuple(related), truncated=False, ready_by=ready_by)
        for merged in commit.associated_pull_requests.nodes:
            shared = tuple(sorted(files & {node.path for node in merged.files.nodes}))
            if merged.merged and merged.number != pull and shared:
                related.append(RelatedPull(merged.number, shared))
    return _Graph(threads, tuple(related), truncated=True, ready_by=ready_by)


# ── The facts ────────────────────────────────────────────────────────────────────────────────


def issue_of_path(path: str) -> int | None:
    """The issue of the change folder that `path` is in, active or archived; None for a path
    outside a change folder."""
    for pattern in (CONST_OPENSPEC_ARCHIVED_FOLDER_RE, CONST_OPENSPEC_CHANGE_FOLDER_RE):
        if match := re.fullmatch(pattern, path):
            return int(match.group("issue"))
    return None


def _change_folder(files: Sequence[str], issue: int) -> tuple[str | None, bool]:
    """The change folder of `issue` that the diff holds, archived first, and whether it is the
    archived one: `openspec/changes/archive/<date>-<name>` or `openspec/changes/<name>`."""
    for pattern, depth in (
        (CONST_OPENSPEC_ARCHIVED_FOLDER_RE, 4),
        (CONST_OPENSPEC_CHANGE_FOLDER_RE, 3),
    ):
        for path in files:
            match = re.fullmatch(pattern, path)
            if match and int(match.group("issue")) == issue:
                return "/".join(path.split("/")[:depth]), depth == 4
    return None, False


def _plan_findings(store: RoadmapStore, item: int, pull: int) -> tuple[str, ...]:
    """The open findings of the last plan comment of the item that names `pull`."""
    body = plan_comment(store, item, pull)
    found = comment_open_findings(body) if body else ()
    return tuple(safe(f"{f.severity.value} `{f.type.value}`: {f.problem}", 300) for f in found)


def pull_kind_of(item: Item, pull: int, title: str) -> PullKind:
    """A delivery when the item records `pull` as its delivery, a plan when it records it as its
    plan, else the kind of the title."""
    record = item.job_record
    if record.get(ImplementRecordKey.PR) == str(pull):
        return PullKind.DELIVERY
    if record.get(StageRecordKey.PR) == str(pull):
        return PullKind.PLAN
    return pull_kind(title)


def record_number(item: Item, key: StageRecordKey | ImplementRecordKey) -> int | None:
    """The number that the record of `item` holds at `key`, or None."""
    value = item.job_record.get(key) or ""
    return int(value) if value.isdigit() else None


def _incomplete(
    client: GitHubClient,
    repo: str,
    status: PullStatus,
    item: Item,
    kind: PullKind,
    folder: tuple[str | None, bool],
) -> str | None:
    """The reason of `draft_readiness` when it refuses the pull request, judged with no checks."""
    path, archived = folder
    change = None
    if kind is PullKind.DELIVERY and path is not None:
        tasks = client.get_file_at(repo, f"{path}/tasks.md", status.head_sha) or ""
        change = ChangeFacts(archived=archived, tasks_text=tasks)
    draft = Draft(
        kind=DraftKind.STAGE_PLAN if kind is PullKind.PLAN else DraftKind.IMPLEMENT,
        pull=status,
        item=item,
        change=change,
    )
    readiness = draft_readiness(draft)
    return str(readiness.reason) if readiness.answer is Answer.REFUSE else None


def read_facts(
    store: RoadmapStore, repo: str, pull: int, status: PullStatus, item: Item
) -> ReviewFacts:
    """The facts of pull request `pull` of `status`, as the module text says."""
    client = get_github_session().client
    ref = RepoRef(repo)
    kind = pull_kind_of(item, pull, status.title)
    checks = read_check_runs(ref.owner, ref.name, status.head_sha)
    compared = client.get_compare_files(repo, status.base_ref, status.head_sha)
    files = tuple(changed.filename for changed in compared.files)
    graph = _read_graph(client, ref, pull, status.base_ref, compared.merge_base, set(files))
    folder = _change_folder(files, item.number)
    recorded = item.job_record.get(StageRecordKey.TEXT_HASH)
    text = body_hashes(item.body)[0]
    # An Issue changed verdict answered this text already, so the updated work is judged (#6024).
    answered = item.job_record.get(ReviewRecordKey.TEXT) == text
    return ReviewFacts(
        pull=pull,
        kind=kind,
        head=status.head_sha,
        item_number=item.number,
        labels=status.labels,
        mergeable=status.mergeable,
        mergeable_state=status.mergeable_state,
        checks=checks,
        item_open=item.state is GitHubState.OPEN,
        text_changed=bool(recorded) and recorded != text and not answered,
        own_plan=record_number(item, StageRecordKey.PR),
        files=files,
        folder=folder[0],
        related=graph.related,
        related_truncated=graph.truncated,
        findings=_plan_findings(store, item.number, pull) if kind is PullKind.PLAN else (),
        threads=graph.threads,
        incomplete=_incomplete(client, repo, status, item, kind, folder),
        ready_by=graph.ready_by,
    )


def read_case(repo: str, status: PullStatus, item: Item, facts: ReviewFacts) -> ReviewCase:
    """What the model reads, as the module text says."""
    client = get_github_session().client
    diff = client.get_compare_diff(repo, status.base_ref, status.head_sha)
    folder = f"{facts.folder}/" if facts.folder else None
    plan_files = [
        path
        for path in facts.files
        if folder is not None and path.startswith(folder) and path.endswith(".md")
    ]
    plan = "\n\n".join(
        f"=== {path} ===\n{client.get_file_at(repo, path, status.head_sha) or ''}"
        for path in plan_files
    )
    return ReviewCase(
        kind=facts.kind,
        pull=facts.pull,
        title=status.title,
        issue=f"#{item.number} {item.title}\n\n{item.body}",
        plan=plan,
        diff=diff,
        files=facts.files,
        related=facts.related,
    )


__all__ = [
    "EVIDENCE_LINES",
    "TEXT_CHARS",
    "RelatedPull",
    "ReplyEvidence",
    "ReplyVerdict",
    "ReviewCase",
    "ReviewFacts",
    "ReviewReply",
    "issue_of_path",
    "pull_kind_of",
    "read_case",
    "read_facts",
    "record_number",
    "safe",
]
