"""The verdict of each pull request that the bot opened, and the verdict score of stage and
implement (#5968).

The pull request review gate gives each plan and delivery pull request of the bot one verdict
(owner, 2026-11-16): mergeable (success), needs fix (partial success), discard plan (failure of
stage), discard implementation (failure of implement) and issue changed (not scored). A workflow
label records the verdict (`roadmap/workflow_labels.py`). Needs fix has one label for each kind:
`verdict/fix-plan` on a plan, which the step fix-plan also reads, and `verdict/fix-implementation`
on a delivery. Discard plan belongs to a plan and discard implementation to a delivery. A person or
an agent vet sets the label, and the stage review and the row `plan_drift` set `verdict/fix-plan`.
A first verdict label of the other kind, such as `verdict/fix-plan` on a delivery, leaves the pull
request unscored, and the read logs why.

The first verdict scores the pull request. The step fix-plan removes `verdict/fix-plan` after a
repair, and a later verdict can follow a fix, so the labels of today can lose the first verdict.
The read takes the label events of the timeline, which GitHub keeps after an unlabel. One GraphQL
search gives the pull requests that changed in the window with their label events: one request for
each 100 pull requests. The search also gives the head branch, the state and the draft flag of
each pull request: the item of a delivery comes from its head branch (`parse_branch`), and its
forge outcome (`forge_outcome`) scores the implement attempts that ended at its draft (#6559). The
verdicts count only the pull requests that the bot opened in the window.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from devops_cli.config.constants import (
    CONST_GH_API_GRAPHQL_ENDPOINT,
    CONST_GITHUB_SEARCH_MAX_RESULTS,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_URL_GITHUB_API_BASE,
)
from devops_cli.dry_run import PlannedRequest
from devops_cli.exceptions.git import GitHubUnreadError
from devops_cli.git.branch_form import parse_branch
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.job_result import RoadmapJob
from devops_cli.roadmap.workflow_labels import FIX_PLAN_LABEL

if TYPE_CHECKING:
    from devops_cli.github.repo_ref import RepoRef
    from devops_cli.roadmap.job_grade import GradeWindow


class PullKind(StrEnum):
    """The kind of a bot pull request: a plan of the stage job, or a delivery of implement."""

    PLAN = "plan"
    DELIVERY = "delivery"


class PullState(StrEnum):
    """The state of a pull request in the GraphQL API of GitHub."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    MERGED = "MERGED"


class ForgeOutcome(StrEnum):
    """The forge outcome of a delivery: the work reached a person or the default branch, or the
    pull request closed with no merge (#6559)."""

    SUCCESS = "success"
    FAILURE = "failure"


class Verdict(StrEnum):
    """The verdict of the pull request review gate on a bot pull request."""

    MERGEABLE = "mergeable"
    NEEDS_FIX = "needs_fix"
    DISCARD_PLAN = "discard_plan"
    DISCARD_IMPLEMENTATION = "discard_implementation"
    ISSUE_CHANGED = "issue_changed"


# The title of a plan pull request: `STAGING_TYPE` of `roadmap/stage/stage_change.py` and the lead
# of the stage title. A test holds the two equal; the import of that module costs about 1 s.
PLAN_TITLE_PREFIX: Final = "docs(spec): plan #"
LEGACY_PLAN_TITLE_PREFIX: Final = "docs(openspec): plan #"
SCOPED_PLAN_PREFIX: Final = "docs(spec): plan"
UNSCOPED_PLAN_PREFIX: Final = "docs: plan"
LEGACY_PLAN_PREFIX: Final = "docs(openspec): plan"
PLAN_TITLE_PREFIXES: Final[tuple[str, ...]] = (
    PLAN_TITLE_PREFIX,
    "docs: plan #",
    LEGACY_PLAN_TITLE_PREFIX,
)


def plan_title_prefix(has_spec_scope: bool) -> str:
    """Return the plan PR title prefix for whether a repository declares `scope/spec`."""
    return SCOPED_PLAN_PREFIX if has_spec_scope else UNSCOPED_PLAN_PREFIX


def is_plan_title(title: str, *, has_spec_scope: bool | None = None) -> bool:
    """Whether `title` begins with a plan pull-request prefix (with `#`)."""
    stripped = title.strip()
    if has_spec_scope is None:
        return stripped.startswith(PLAN_TITLE_PREFIXES)
    return stripped.startswith((f"{plan_title_prefix(has_spec_scope)} #", LEGACY_PLAN_TITLE_PREFIX))


def is_plan_title_prefix(title: str, *, has_spec_scope: bool = True) -> bool:
    """Whether `title` begins like a plan pull request (`docs(spec): plan` / `docs: plan` or legacy)."""
    return title.strip().startswith((plan_title_prefix(has_spec_scope), LEGACY_PLAN_PREFIX))


logger = logging.getLogger(__name__)

# The label of each verdict that a kind of pull request reads.
VERDICT_LABELS: Final[Mapping[PullKind, Mapping[str, Verdict]]] = {
    PullKind.PLAN: {
        "verdict/mergeable": Verdict.MERGEABLE,
        FIX_PLAN_LABEL: Verdict.NEEDS_FIX,
        "verdict/discard-plan": Verdict.DISCARD_PLAN,
        "verdict/issue-changed": Verdict.ISSUE_CHANGED,
    },
    PullKind.DELIVERY: {
        "verdict/mergeable": Verdict.MERGEABLE,
        "verdict/fix-implementation": Verdict.NEEDS_FIX,
        "verdict/discard-implementation": Verdict.DISCARD_IMPLEMENTATION,
        "verdict/issue-changed": Verdict.ISSUE_CHANGED,
    },
}
# Each verdict label of either kind.
VERDICT_LABEL_NAMES: Final = frozenset(
    name for labels in VERDICT_LABELS.values() for name in labels
)

# The job that each kind of pull request scores, and the discard that is a failure of that job.
KIND_JOBS: Final[Mapping[PullKind, RoadmapJob]] = {
    PullKind.PLAN: RoadmapJob.STAGE,
    PullKind.DELIVERY: RoadmapJob.IMPLEMENT,
}
_FAILURES: Final[Mapping[RoadmapJob, Verdict]] = {
    RoadmapJob.STAGE: Verdict.DISCARD_PLAN,
    RoadmapJob.IMPLEMENT: Verdict.DISCARD_IMPLEMENTATION,
}

# GitHub gives 100 nodes of a connection at most.
_PAGE_SIZE: Final = 100
_SEARCH_QUERY: Final = f"""
query($search: String!, $cursor: String) {{
  search(query: $search, type: ISSUE, first: {_PAGE_SIZE}, after: $cursor) {{
    issueCount
    pageInfo {{ hasNextPage endCursor }}
    nodes {{
      ... on PullRequest {{
        number
        title
        headRefName
        state
        isDraft
        createdAt
        repository {{ nameWithOwner }}
        timelineItems(itemTypes: [LABELED_EVENT, RENAMED_TITLE_EVENT], first: {_PAGE_SIZE}) {{
          pageInfo {{ hasNextPage }}
          nodes {{
            ... on LabeledEvent {{ label {{ name }} }}
            ... on RenamedTitleEvent {{ previousTitle }}
          }}
        }}
      }}
    }}
  }}
}}
"""
_GRAPHQL_URL: Final = f"{CONST_URL_GITHUB_API_BASE}/{CONST_GH_API_GRAPHQL_ENDPOINT}"


@dataclass(frozen=True)
class BotPull:
    """One pull request of the bot: its repository, its number, its kind and its first verdict,
    or None while it has no verdict. `unscored` is its first verdict label when that label is a
    label of the other kind. `item` is the issue that its head branch names, or None; `state`,
    `draft` and `created` are its state, whether it is a draft, and when it was opened."""

    repo: str
    number: int
    kind: PullKind
    verdict: Verdict | None
    unscored: str | None = None
    item: int | None = None
    state: PullState = PullState.OPEN
    draft: bool = False
    created: datetime | None = None


def forge_outcome(pull: BotPull) -> ForgeOutcome | None:
    """The forge outcome of `pull` (#6559): a success when it merged or is open and out of draft,
    a failure when it closed with no merge, and None while it is a draft."""
    if pull.state is PullState.MERGED:
        return ForgeOutcome.SUCCESS
    if pull.state is PullState.CLOSED:
        return ForgeOutcome.FAILURE
    return None if pull.draft else ForgeOutcome.SUCCESS


class VerdictGrade(BaseModel):
    """The verdicts of the bot pull requests of one job and repository in the window."""

    model_config = ConfigDict(frozen=True)

    pulls: int = Field(description="Bot pull requests of the job that were opened in the window")
    open: int = Field(description="Pull requests with no verdict yet")
    unscored: int = Field(
        default=0,
        description="Pull requests whose first verdict label is a label of the other kind",
    )
    counts: dict[Verdict, int] = Field(description="Pull requests with each first verdict")
    shares: dict[Verdict, float | None] = Field(
        description="The count of each verdict over the pull requests with a verdict"
    )
    score: float | None = Field(
        description="(mergeable + w x needs fix) / (mergeable + needs fix + failures of the job); "
        "None with no scored verdict"
    )


def pull_kind(title: str) -> PullKind:
    """A plan when the title is the title of the stage job, else a delivery."""
    return PullKind.PLAN if is_plan_title(title) else PullKind.DELIVERY


def first_verdict_label(labels: Iterable[str]) -> str | None:
    """The first label of `labels`, in the order of their events, that is a verdict label of
    either kind; None when no label is one."""
    return next((name for name in labels if name in VERDICT_LABEL_NAMES), None)


def verdict_of(kind: PullKind, label: str) -> Verdict | None:
    """The verdict that `label` gives a pull request of `kind`; None for a label of the other
    kind, such as `verdict/fix-plan` on a delivery."""
    return VERDICT_LABELS[kind].get(label)


def verdict_label(kind: PullKind, verdict: Verdict) -> str | None:
    """The label that records `verdict` on a pull request of `kind`, the one that `verdict_of`
    reads back; None for a verdict of the other kind, such as discard plan on a delivery. The step
    review writes it (#5969)."""
    return next((name for name, held in VERDICT_LABELS[kind].items() if held is verdict), None)


def _share(count: int, total: int) -> float | None:
    return round(count / total, 4) if total else None


def grade_verdicts(
    job: RoadmapJob,
    verdicts: Sequence[Verdict | None],
    *,
    partial_score: float,
    unscored: int = 0,
) -> VerdictGrade:
    """The counts, the shares and the score of the first verdicts of the pull requests of `job`.
    A verdict of None is an open pull request, and `unscored` counts the pull requests whose first
    verdict label is of the other kind. Needs fix scores `partial_score`, and only the discard of
    the work of `job` is a failure."""
    counted = Counter(verdict for verdict in verdicts if verdict is not None)
    judged = sum(counted.values())
    failures = counted[_FAILURES[job]]
    scored = counted[Verdict.MERGEABLE] + counted[Verdict.NEEDS_FIX] + failures
    points = counted[Verdict.MERGEABLE] + partial_score * counted[Verdict.NEEDS_FIX]
    return VerdictGrade(
        pulls=len(verdicts) + unscored,
        open=len(verdicts) - judged,
        unscored=unscored,
        counts={verdict: counted[verdict] for verdict in Verdict},
        shares={verdict: _share(counted[verdict], judged) for verdict in Verdict},
        score=round(points / scored, 4) if scored else None,
    )


def verdict_search(window: GradeWindow, repo: RepoRef | None, slug: str, now: datetime) -> str:
    """The GitHub search of the pull requests of the App of `slug` that changed in `window` up to
    `now`, in the repository `repo` or in each repository. A delivery opened before the window and
    marked ready or merged in it gives the forge outcome of its attempt (#6559)."""
    start = (now - window.span).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    search = f"is:pr author:app/{slug} updated:>={start}"
    return f"{search} repo:{repo.display}" if repo is not None else search


def plan_verdict_request(search: str) -> PlannedRequest:
    """The GraphQL search of the verdicts, as a dry run prints it."""
    return PlannedRequest(
        method="POST",
        target=_GRAPHQL_URL,
        stdin=MESSAGES.roadmap.grades_verdict_request.format(search=search),
        repeat=MESSAGES.roadmap.grades_verdict_repeat.format(size=_PAGE_SIZE),
    )


class GraphQLReads(Protocol):
    """The GitHub read that the verdicts take: one GraphQL request."""

    def graphql(self, query: str, variables: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Send one GraphQL request and return its answer."""
        ...


class _Answered(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True, frozen=True)


class _Name(_Answered):
    name: str


class _TimelineItem(_Answered):
    label: _Name | None = None
    previous_title: str | None = None


class _TimelinePageInfo(_Answered):
    has_next_page: bool = False


class _Events(_Answered):
    page_info: _TimelinePageInfo = Field(default_factory=_TimelinePageInfo)
    nodes: list[_TimelineItem] = Field(default_factory=list)


class _Repository(_Answered):
    name_with_owner: str


class _Pull(_Answered):
    number: int
    title: str
    repository: _Repository
    head_ref_name: str = ""
    state: PullState = PullState.OPEN
    is_draft: bool = False
    created_at: datetime | None = None
    timeline_items: _Events = Field(default_factory=_Events)


class _PageInfo(_Answered):
    has_next_page: bool
    end_cursor: str | None = None


class _Search(_Answered):
    issue_count: int
    page_info: _PageInfo
    nodes: list[_Pull]


class _Data(_Answered):
    search: _Search


class _Error(_Answered):
    message: str = ""


class _SearchAnswer(_Answered):
    data: _Data | None = None
    errors: list[_Error] = Field(default_factory=list)


def _search_page(reads: GraphQLReads, search: str, cursor: str | None) -> _Search:
    """One page of the search, raising `GitHubUnreadError` for an answer with an error, an
    answer that is no page, or a search with more results than GitHub returns."""
    answer = reads.graphql(_SEARCH_QUERY, {"search": search, "cursor": cursor})
    try:
        page = _SearchAnswer.model_validate(answer)
    except ValidationError as exc:
        raise GitHubUnreadError(
            f"GitHub's answer to the search of the verdicts is no page: "
            f"{exc.error_count()} invalid field(s)",
            details={"search": search},
        ) from exc
    if page.errors or page.data is None:
        reason = page.errors[0].message if page.errors else "no data"
        raise GitHubUnreadError(
            f"GitHub refused the search of the verdicts: {reason[:CONST_MAX_ERROR_DETAIL_LENGTH]}",
            details={"search": search},
        )
    found = page.data.search
    if found.issue_count > CONST_GITHUB_SEARCH_MAX_RESULTS:
        raise GitHubUnreadError(
            f"The search of the verdicts has {found.issue_count} results, and GitHub returns "
            f"{CONST_GITHUB_SEARCH_MAX_RESULTS} at most",
            details={"search": search, "total_count": found.issue_count},
        )
    return found


def _kind_and_label(node: _Pull, repo: str) -> tuple[PullKind, str | None]:
    """The pull request kind at its first verdict label event and that verdict label name, raising
    `GitHubUnreadError` when the timeline has more than one page."""
    if node.timeline_items.page_info.has_next_page:
        raise GitHubUnreadError(
            f"Pull request {repo}#{node.number} has more than one timeline page of label or "
            "rename events",
            details={"repo": repo, "pull": node.number},
        )
    nodes = node.timeline_items.nodes
    for index, event in enumerate(nodes):
        if event.label is not None and event.label.name in VERDICT_LABEL_NAMES:
            later_rename = next(
                (
                    item.previous_title
                    for item in nodes[index + 1 :]
                    if item.previous_title is not None
                ),
                None,
            )
            title = later_rename if later_rename is not None else node.title
            return pull_kind(title), event.label.name
    return pull_kind(node.title), None


def _bot_pull(node: _Pull) -> BotPull:
    """The kind and the first verdict of one pull request of the search. A first verdict label of
    the other kind leaves it unscored, and the read logs why."""
    repo = node.repository.name_with_owner
    kind, label = _kind_and_label(node, repo)
    verdict = verdict_of(kind, label) if label is not None else None
    unscored = label if label is not None and verdict is None else None
    if unscored is not None:
        logger.warning(
            "Pull request %s#%d is a %s, and its first verdict label %s is a label of the other "
            "kind, so the grade does not score it.",
            repo,
            node.number,
            kind,
            unscored,
        )
    branch = parse_branch(node.head_ref_name)
    return BotPull(
        repo=repo,
        number=node.number,
        kind=kind,
        verdict=verdict,
        unscored=unscored,
        item=branch.issue if branch is not None else None,
        state=node.state,
        draft=node.is_draft,
        created=node.created_at,
    )


def read_bot_pulls(reads: GraphQLReads, search: str) -> list[BotPull]:
    """Each pull request that `search` finds, with its kind and its first verdict, from one
    GraphQL request for each page of 100."""
    pulls: list[BotPull] = []
    cursor: str | None = None
    while True:
        page = _search_page(reads, search, cursor)
        pulls.extend(_bot_pull(node) for node in page.nodes)
        cursor = page.page_info.end_cursor if page.page_info.has_next_page else None
        if not cursor:
            return pulls


__all__ = [
    "KIND_JOBS",
    "PLAN_TITLE_PREFIX",
    "VERDICT_LABELS",
    "VERDICT_LABEL_NAMES",
    "BotPull",
    "ForgeOutcome",
    "GraphQLReads",
    "PullKind",
    "PullState",
    "Verdict",
    "VerdictGrade",
    "first_verdict_label",
    "forge_outcome",
    "grade_verdicts",
    "is_plan_title_prefix",
    "plan_title_prefix",
    "plan_verdict_request",
    "pull_kind",
    "read_bot_pulls",
    "verdict_label",
    "verdict_of",
    "verdict_search",
]
