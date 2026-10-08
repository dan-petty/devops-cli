"""The requests `devops roadmap intake` makes: the plan a dry run returns, and what a `--plan`
run spends (#742, the dry-run rule of #412).

A dry run makes no request at all. It returns the requests a run makes, in order, as
`PlannedRequest`s (#741): GitHub REST, REST search and GraphQL reads and writes, the embedding
call and the model calls. `method` names the transport and whether it reads or writes, and
`target` what it reads or writes. Every `gh` command shows its exact argv and stdin, built by
the store's own argument builders (`roadmap/request_plan.py`, #1125), one line per command, so a
board write shows the read of its one card it makes first (#1361). A value that needs a read is
a placeholder in angle brackets, a request that runs only when an earlier one returns something
names that in `condition`, and a listing read a page at a time, or a request made for each
candidate, says so in `repeat`. The reads end with the GraphQL budget read the run's spend line
comes from.

A `--plan` run makes the reads and the model calls, writes nothing, and reports what it spent:
each `gh` command by the rate-limit resource it spends, as `run_gh` classifies it, and each
embedding and proposal call, and the run ends with the GraphQL points it spent, read from
GraphQL itself (#1125). `run_gh`'s retries are not
counted, and a proposal call counts once though the client retries an answer that does not fit
the schema, and an embedding call once though the client may batch it or answer from its cache.
"""

from __future__ import annotations

import subprocess
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from devops_cli.config.constants import (
    CONST_ROADMAP_BORROWED_LABEL,
    CONST_ROADMAP_CONFIG_PATH,
    CONST_ROADMAP_INTAKE_BOARD_FILTER,
    CONST_ROADMAP_LABELS_PATH,
    CONST_ROADMAP_SOURCE_AGENT_LABEL,
)
from devops_cli.dry_run.requests import PlannedRequest, both
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.intake_model import IntakeModel, ModelProposal, ProposalRequest
from devops_cli.roadmap.request_plan import StoreRequests, within
from devops_cli.roadmap.store import CloseReason, GitHubState, IssueQuery

if TYPE_CHECKING:
    from devops_cli.roadmap.github_store import GhRunner


class _Via(StrEnum):
    """What a request that is not a `gh` command goes through."""

    EMBEDDING = "embedding"
    MODEL = "model"


# REST search's time qualifiers for a time only a read gives: built with this stand-in, which
# the plan then shows as the placeholder.
_SINCE = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class _Steps:
    """Builds a run's requests: the repository, the ref shown, and the placeholders' text.

    Each step is one store or model operation, named by its key in the messages; a store
    operation lists each `gh` command it runs, built by the store's own argument builders, so
    the plan shows the exact command of every request (#1125)."""

    repo: str
    ref: str | None
    board: str = field(default_factory=lambda: MESSAGES.roadmap.intake_placeholder_board)

    @property
    def at(self) -> str:
        return self.ref or MESSAGES.roadmap.intake_placeholder_default_branch

    @property
    def store(self) -> StoreRequests:
        return StoreRequests(self.repo, CONST_ROADMAP_INTAKE_BOARD_FILTER)

    def _text(self, key: str, values: dict[str, str]) -> tuple[str, str]:
        texts = MESSAGES.roadmap
        values = {"ref": self.at, "board": self.board, **values}
        own = texts.intake_request_conditions.get(key, "").format(**values)
        return texts.intake_requests[key].format(**values), own

    def step(
        self,
        key: str,
        requests: Sequence[PlannedRequest],
        *,
        when: str = "",
        repeat: str = "",
        **values: str,
    ) -> list[PlannedRequest]:
        """The `gh` commands of the operation `key` names, its own condition joined to `when`."""
        target, own = self._text(key, values)
        return [
            replace(planned, target=target) for planned in within(requests, both(when, own), repeat)
        ]

    def call(self, key: str, via: _Via, *, repeat: str = "", **values: str) -> PlannedRequest:
        """An embedding or model call, which no `gh` command makes."""
        target, own = self._text(key, values)
        return PlannedRequest(method=via.value, target=target, condition=own, repeat=repeat)

    def _count(self, key: str, query: IssueQuery) -> list[PlannedRequest]:
        since = MESSAGES.roadmap.intake_placeholder_since
        stand_in = _SINCE.isoformat(timespec="seconds")
        counted = [
            replace(r, argv=tuple(arg.replace(stand_in, since) for arg in r.argv))
            for r in self.store.count_issues(query)
        ]
        return self.step(key, counted, since=since)

    def reads(self) -> list[PlannedRequest]:
        """The reads every run makes before it decides any candidate."""
        store = self.store
        closed = {"state": GitHubState.CLOSED, "closed_since": _SINCE}
        agent = (CONST_ROADMAP_SOURCE_AGENT_LABEL,)
        return [
            *self.step("config", store.file(CONST_ROADMAP_CONFIG_PATH, self.ref)),
            *self.step("milestones", store.releases()),
            *self.step("issues", store.issues()),
            *self.step("board", store.board_read()),
            *self.step("board_issues", store.issues()),
            *self.step("quota_milestones", store.releases()),
            *self.step("count_open", store.count_issues(IssueQuery(state=GitHubState.OPEN))),
            *self._count("count_closed", IssueQuery.model_validate(closed)),
            *self._count(
                "count_bulk",
                IssueQuery.model_validate(
                    closed | {"reason": CloseReason.NOT_PLANNED, "uncommented": True}
                ),
            ),
            *self._count("count_openings", IssueQuery(labels=agent, created_since=_SINCE)),
            *self._count(
                "count_borrowed",
                IssueQuery(labels=(*agent, CONST_ROADMAP_BORROWED_LABEL), created_since=_SINCE),
            ),
        ]

    def decisions(self, subjects: Sequence[str], *, new: bool, repeat: str) -> list[PlannedRequest]:
        """The reads and model calls that decide each candidate, in the order a run makes them."""
        store = self.store
        planned: list[PlannedRequest] = []
        for s in [] if new else subjects:
            planned += self.step("closures", store.closures(s), subject=s, repeat=repeat)
        planned.append(self.call("embed_new" if new else "embed", _Via.EMBEDDING))
        planned += self.step("labels", store.file(CONST_ROADMAP_LABELS_PATH, self.ref))
        for index, subject in enumerate(subjects):
            planned.append(self.call("propose", _Via.MODEL, subject=subject, repeat=repeat))
            planned += self.step(
                "evidence", store.evidence(subject), subject=subject, repeat=repeat
            )
            planned += [] if index else self._release_state()
            if not new:
                planned += self.step(
                    "comments", store.comments_on(subject), subject=subject, repeat=repeat
                )
        return planned

    def _release_state(self) -> list[PlannedRequest]:
        """The reads that find the current release, once a run, at the first critical fix."""
        current = MESSAGES.roadmap.intake_request_conditions["release_state"]
        store = self.store
        return [
            *self.step("default_branch", store.default_branch(), when=current),
            *self.step("release_milestones", store.releases(), when=current),
            *self.step("release_prs", store.release_pull_requests()[-1:], when=current),
            *self.step("release_published", store.release_published(), when=current),
        ]

    def writes(self, subjects: Sequence[str], *, new: bool, repeat: str) -> list[PlannedRequest]:
        """The writes `--confirm` makes for each candidate it places or closes as a duplicate."""
        texts = MESSAGES.roadmap
        planned: list[PlannedRequest] = []
        for subject in subjects:
            if new:
                filing = self.store.create_issue(subject, (texts.plan_placeholders["label"],))
                planned += self.step("file", filing, subject=subject, repeat=repeat)
            planned += self._placement(texts.intake_placeholder_filed if new else subject, repeat)
            planned += [] if new else self._duplicate(subject, repeat)
        return planned

    def _placement(self, subject: str, repeat: str) -> list[PlannedRequest]:
        """The writes that place `subject`, Priority last, when intake places it."""
        texts = MESSAGES.roadmap
        store = self.store
        when = texts.intake_request_conditions["placed"].format(subject=subject)
        names = [name.split(" ", 1)[0] for name in texts.intake_placeholder_fields]
        steps: list[tuple[str, list[PlannedRequest], dict[str, str]]] = [
            ("label", store.label_issue(subject), {}),
            ("add", store.add_item(subject), {}),
            ("release", store.set_field(subject, "Release"), {}),
            *(
                ("field", store.set_field(subject, name), {"field": shown})
                for name, shown in zip(names, texts.intake_placeholder_fields, strict=True)
            ),
            ("comment", store.comment(subject), {}),
            ("priority", store.set_field(subject, "Priority"), {}),
        ]
        return [
            planned
            for key, requests, values in steps
            for planned in self.step(
                key, requests, when=when, repeat=repeat, subject=subject, **values
            )
        ]

    def _duplicate(self, subject: str, repeat: str) -> list[PlannedRequest]:
        """The reads and writes that close `subject` as a duplicate, when it is one."""
        when = MESSAGES.roadmap.intake_request_conditions["duplicate"].format(subject=subject)
        store = self.store
        original = store.issue(MESSAGES.roadmap.plan_placeholders["number"])
        steps = (
            ("duplicate_read", [*store.issue(subject), *original]),
            ("duplicate_comment", store.comment(subject)),
            ("duplicate_close", store.close_as_duplicate(subject)),
        )
        return [
            planned
            for key, requests in steps
            for planned in self.step(key, requests, when=when, repeat=repeat, subject=subject)
        ]


def planned_requests(
    subjects: Sequence[str], *, repo: str, ref: str | None, new: bool, each: bool = False
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """The requests a run over `subjects` makes, as reads and model calls ending with the
    closing GraphQL budget read, then the writes `--confirm` adds before that read; `new` when
    the one subject is a candidate that is not an issue yet, and `each` when the one subject
    stands for every candidate, its requests repeated for each."""
    steps = _Steps(repo=repo, ref=ref)
    repeat = MESSAGES.roadmap.intake_repeat_candidate if each else ""
    reads = steps.reads() + steps.decisions(subjects, new=new, repeat=repeat)
    reads += steps.store.budget()
    return tuple(reads), tuple(steps.writes(subjects, new=new, repeat=repeat))


# ── What a run spends ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Spend:
    """The requests a run made: `gh` commands by the rate-limit resource they spend, and
    embedding and proposal calls."""

    rest: int = 0
    search: int = 0
    graphql: int = 0
    embedding_calls: int = 0
    embedded_texts: int = 0
    model_calls: int = 0

    def render(self) -> str:
        return MESSAGES.roadmap.intake_spend.format(
            github=self.rest + self.search + self.graphql,
            rest=self.rest,
            search=self.search,
            graphql=self.graphql,
            embeddings=self.embedding_calls,
            texts=self.embedded_texts,
            proposals=self.model_calls,
        )


@dataclass
class _MeteredModel:
    """An intake model that counts each call before it makes it, a failed one included."""

    model: IntakeModel
    counts: Counter[str]

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.counts["embedding_calls"] += 1
        self.counts["embedded_texts"] += len(texts)
        return self.model.embed(texts)

    def propose(self, request: ProposalRequest) -> ModelProposal:
        self.counts["model_calls"] += 1
        return self.model.propose(request)


_RESOURCE_FIELDS = {"graphql": "graphql", "search": "search"}


@dataclass
class SpendMeter:
    """Counts what a run spends: `run` is the `gh` runner the store is opened with, and `model`
    wraps the intake model. `gh` is the runner each command goes on to, `run_gh` by default."""

    gh: GhRunner | None = None
    counts: Counter[str] = field(default_factory=Counter)

    def run(
        self,
        args: list[str],
        *,
        input: str | None = None,
        check: bool = False,
        quiet: bool = False,
        use_cache: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        from devops_cli.github.rate_limiter import gh_request_resource, run_gh

        self.counts[_RESOURCE_FIELDS.get(gh_request_resource(args), "rest")] += 1
        runner = self.gh or run_gh
        return runner(args, input=input, check=check, quiet=quiet, use_cache=use_cache)

    def model(self, model: IntakeModel) -> IntakeModel:
        return _MeteredModel(model, self.counts)

    def spend(self) -> Spend:
        return Spend(**self.counts)


__all__ = ["Spend", "SpendMeter", "planned_requests"]
