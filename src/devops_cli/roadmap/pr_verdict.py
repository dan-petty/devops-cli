"""The verdict of each pull request that the bot opened, and the verdict score of stage and
implement (#5968).

The pull request review gate gives each plan and delivery pull request of the bot one verdict
(owner, 2026-11-16): mergeable (success), needs fix (partial success), discard plan (failure of
stage), discard implementation (failure of implement) and issue changed (not scored). A workflow
label records the verdict (`roadmap/workflow_labels.py`). On a plan, the verdict needs fix is
`plan/needs-fix`, which the step fix-plan reads; on a delivery, it is `verdict/needs-fix`. So each
verdict of each kind of pull request has one label. A person or an agent vet sets the label.

The first verdict scores the pull request. The step fix-plan removes `plan/needs-fix` after a
repair, and a later verdict can follow a fix, so the labels of today can lose the first verdict.
The read takes the label events of the timeline, which GitHub keeps after an unlabel. One GraphQL
search gives the pull requests of the window with their label events: one request for each 100
pull requests.
"""

from __future__ import annotations

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
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.job_result import RoadmapJob

if TYPE_CHECKING:
    from devops_cli.github.repo_ref import RepoRef
    from devops_cli.roadmap.job_grade import GradeWindow


class PullKind(StrEnum):
    """The kind of a bot pull request: a plan of the stage job, or a delivery of implement."""

    PLAN = "plan"
    DELIVERY = "delivery"


class Verdict(StrEnum):
    """The verdict of the pull request review gate on a bot pull request."""

    MERGEABLE = "mergeable"
    NEEDS_FIX = "needs_fix"
    DISCARD_PLAN = "discard_plan"
    DISCARD_IMPLEMENTATION = "discard_implementation"
    ISSUE_CHANGED = "issue_changed"


# The title of a plan pull request: `STAGING_TYPE` of `roadmap/stage/stage_change.py` and the lead
# of the stage title. A test holds the two equal; the import of that module costs about 1 s.
PLAN_TITLE_PREFIX: Final = "docs(openspec): plan #"

# The label of each verdict that a kind of pull request reads.
VERDICT_LABELS: Final[Mapping[PullKind, Mapping[str, Verdict]]] = {
    PullKind.PLAN: {
        "verdict/mergeable": Verdict.MERGEABLE,
        "plan/needs-fix": Verdict.NEEDS_FIX,
        "verdict/discard-plan": Verdict.DISCARD_PLAN,
        "verdict/issue-changed": Verdict.ISSUE_CHANGED,
    },
    PullKind.DELIVERY: {
        "verdict/mergeable": Verdict.MERGEABLE,
        "verdict/needs-fix": Verdict.NEEDS_FIX,
        "verdict/discard-plan": Verdict.DISCARD_PLAN,
        "verdict/discard-implementation": Verdict.DISCARD_IMPLEMENTATION,
        "verdict/issue-changed": Verdict.ISSUE_CHANGED,
    },
}

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
        repository {{ nameWithOwner }}
        timelineItems(itemTypes: [LABELED_EVENT], first: {_PAGE_SIZE}) {{
          nodes {{ ... on LabeledEvent {{ label {{ name }} }} }}
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
    or None while it has no verdict."""

    repo: str
    number: int
    kind: PullKind
    verdict: Verdict | None


class VerdictGrade(BaseModel):
    """The verdicts of the bot pull requests of one job and repository in the window."""

    model_config = ConfigDict(frozen=True)

    pulls: int = Field(description="Bot pull requests of the job that were opened in the window")
    open: int = Field(description="Pull requests with no verdict yet")
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
    return PullKind.PLAN if title.strip().startswith(PLAN_TITLE_PREFIX) else PullKind.DELIVERY


def first_verdict(kind: PullKind, labels: Iterable[str]) -> Verdict | None:
    """The verdict of the first label of `labels`, in the order of their events, that `kind`
    reads as a verdict; None when no label is one."""
    readable = VERDICT_LABELS[kind]
    return next((readable[name] for name in labels if name in readable), None)


def _share(count: int, total: int) -> float | None:
    return round(count / total, 4) if total else None


def grade_verdicts(
    job: RoadmapJob, verdicts: Sequence[Verdict | None], *, partial_score: float
) -> VerdictGrade:
    """The counts, the shares and the score of the first verdicts of the pull requests of `job`.
    A verdict of None is an open pull request. Needs fix scores `partial_score`, and only the
    discard of the work of `job` is a failure."""
    counted = Counter(verdict for verdict in verdicts if verdict is not None)
    judged = sum(counted.values())
    failures = counted[_FAILURES[job]]
    scored = counted[Verdict.MERGEABLE] + counted[Verdict.NEEDS_FIX] + failures
    points = counted[Verdict.MERGEABLE] + partial_score * counted[Verdict.NEEDS_FIX]
    return VerdictGrade(
        pulls=len(verdicts),
        open=len(verdicts) - judged,
        counts={verdict: counted[verdict] for verdict in Verdict},
        shares={verdict: _share(counted[verdict], judged) for verdict in Verdict},
        score=round(points / scored, 4) if scored else None,
    )


def verdict_search(window: GradeWindow, repo: RepoRef | None, slug: str, now: datetime) -> str:
    """The GitHub search of the pull requests that the App of `slug` opened in `window` up to
    `now`, in the repository `repo` or in each repository."""
    start = (now - window.span).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    search = f"is:pr author:app/{slug} created:>={start}"
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


class _LabelEvent(_Answered):
    label: _Name | None = None


class _Events(_Answered):
    nodes: list[_LabelEvent] = Field(default_factory=list)


class _Repository(_Answered):
    name_with_owner: str


class _Pull(_Answered):
    number: int
    title: str
    repository: _Repository
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


def read_bot_pulls(reads: GraphQLReads, search: str) -> list[BotPull]:
    """Each pull request that `search` finds, with its kind and its first verdict, from one
    GraphQL request for each page of 100."""
    pulls: list[BotPull] = []
    cursor: str | None = None
    while True:
        page = _search_page(reads, search, cursor)
        for node in page.nodes:
            kind = pull_kind(node.title)
            labels = (event.label.name for event in node.timeline_items.nodes if event.label)
            pulls.append(
                BotPull(
                    repo=node.repository.name_with_owner,
                    number=node.number,
                    kind=kind,
                    verdict=first_verdict(kind, labels),
                )
            )
        cursor = page.page_info.end_cursor if page.page_info.has_next_page else None
        if not cursor:
            return pulls


__all__ = [
    "KIND_JOBS",
    "PLAN_TITLE_PREFIX",
    "VERDICT_LABELS",
    "BotPull",
    "GraphQLReads",
    "PullKind",
    "Verdict",
    "VerdictGrade",
    "first_verdict",
    "grade_verdicts",
    "plan_verdict_request",
    "pull_kind",
    "read_bot_pulls",
    "verdict_search",
]
