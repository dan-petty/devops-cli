"""The requests `devops roadmap intake` makes: the plan a dry run returns, and what a `--plan`
run spends (#742, the dry-run rule of #412).

A dry run makes no request at all. It returns the requests a run makes, in order, as
`PlannedRequest`s (#741): GitHub REST, REST search and GraphQL reads and writes, the embedding
call and the model calls. `method` names the transport and whether it reads or writes, and
`target` what it reads or writes; `argv` is the exact `gh` command where it is known without a
read. A value that needs a read is a placeholder in angle brackets, a request that runs only
when an earlier one returns something names that in `condition`, and a listing read a page at a
time, or a request made for each candidate, says so in `repeat`. Each other line is one store
operation, so a board write counts once though it reads the board's fields and items first.

A `--plan` run makes the reads and the model calls, writes nothing, and reports what it spent:
each `gh` command by the rate-limit resource it spends, as `run_gh` classifies it, and each
embedding and proposal call. GraphQL points are not known: the store's queries ask for no
`rateLimit` cost, and a `gh project` command, counted once, may page. `run_gh`'s retries are not
counted, and a proposal call counts once though the client retries an answer that does not fit
the schema, and an embedding call once though the client may batch it or answer from its cache.
"""

from __future__ import annotations

import subprocess
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from devops_cli.config.constants import CONST_ROADMAP_CONFIG_PATH, CONST_ROADMAP_LABELS_PATH
from devops_cli.dry_run.requests import PlannedRequest, both
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.github_store import (
    issue_count_args,
    issues_endpoint,
    listing_page_args,
    milestones_endpoint,
    repository_file_args,
)
from devops_cli.roadmap.intake_model import IntakeModel, ModelProposal, ProposalRequest
from devops_cli.roadmap.store import GitHubState, IssueQuery

if TYPE_CHECKING:
    from devops_cli.roadmap.github_store import GhRunner


class _Via(StrEnum):
    """What a request goes through."""

    REST = "REST"
    SEARCH = "REST search"
    GRAPHQL = "GraphQL"
    EMBEDDING = "embedding"
    MODEL = "model"


_GH = "gh"
_PAGE = "<n>"


def _method(*via: _Via, write: bool = False) -> str:
    """The transports a request goes through, then, for GitHub, whether it reads or writes."""
    through = " + ".join(transport.value for transport in via)
    if via[0] in (_Via.EMBEDDING, _Via.MODEL):
        return through
    texts = MESSAGES.roadmap
    return f"{through} {texts.intake_request_write if write else texts.intake_request_read}"


@dataclass(frozen=True)
class _Steps:
    """Builds a run's requests: the repository, the ref shown, and the placeholders' text."""

    repo: str
    ref: str | None
    board: str = field(default_factory=lambda: MESSAGES.roadmap.intake_placeholder_board)

    @property
    def at(self) -> str:
        return self.ref or MESSAGES.roadmap.intake_placeholder_default_branch

    def step(
        self,
        key: str,
        *via: _Via,
        write: bool = False,
        argv: Sequence[str] = (),
        when: str = "",
        repeat: str = "",
        **values: str,
    ) -> PlannedRequest:
        """The request `key` names in the messages, its own condition joined to `when`."""
        texts = MESSAGES.roadmap
        values = {"ref": self.at, "board": self.board, **values}
        own = texts.intake_request_conditions.get(key, "").format(**values)
        return PlannedRequest(
            method=_method(*via, write=write),
            target=texts.intake_requests[key].format(**values),
            argv=(_GH, *argv) if argv else (),
            condition=both(when, own),
            repeat=repeat,
        )

    def listing(self, key: str, endpoint: str, *, when: str = "") -> PlannedRequest:
        """A REST listing, read a full page at a time until a page is short."""
        argv = listing_page_args(endpoint, _PAGE)
        repeat = MESSAGES.roadmap.intake_repeat_page
        return self.step(key, _Via.REST, argv=argv, when=when, repeat=repeat)

    def reads(self) -> list[PlannedRequest]:
        """The reads every run makes before it decides any candidate."""
        open_issues = IssueQuery(state=GitHubState.OPEN)
        return [
            self.step(
                "config",
                _Via.REST,
                argv=repository_file_args(self.repo, CONST_ROADMAP_CONFIG_PATH, ref=self.ref),
            ),
            self.listing("milestones", milestones_endpoint(self.repo)),
            self.listing("issues", issues_endpoint(self.repo)),
            self.step("board", _Via.GRAPHQL),
            self.listing("board_issues", issues_endpoint(self.repo)),
            self.listing("quota_milestones", milestones_endpoint(self.repo)),
            self.step("count_open", _Via.SEARCH, argv=issue_count_args(self.repo, open_issues)),
            *(
                self.step(key, _Via.SEARCH, since=MESSAGES.roadmap.intake_placeholder_since)
                for key in ("count_closed", "count_bulk", "count_openings", "count_borrowed")
            ),
        ]

    def decisions(self, subjects: Sequence[str], *, new: bool, repeat: str) -> list[PlannedRequest]:
        """The reads and model calls that decide each candidate, in the order a run makes them."""
        planned = (
            []
            if new
            else [self.step("closures", _Via.GRAPHQL, subject=s, repeat=repeat) for s in subjects]
        )
        planned.append(self.step("embed_new" if new else "embed", _Via.EMBEDDING))
        planned.append(
            self.step(
                "labels",
                _Via.REST,
                argv=repository_file_args(self.repo, CONST_ROADMAP_LABELS_PATH, ref=self.ref),
            )
        )
        for index, subject in enumerate(subjects):
            planned += [
                self.step("propose", _Via.MODEL, subject=subject, repeat=repeat),
                self.step("evidence", _Via.REST, subject=subject, repeat=repeat),
            ]
            planned += [] if index else self._release_state()
            planned += (
                [] if new else [self.step("comments", _Via.REST, subject=subject, repeat=repeat)]
            )
        return planned

    def _release_state(self) -> list[PlannedRequest]:
        """The reads that find the current release, once a run, at the first critical fix."""
        current = MESSAGES.roadmap.intake_request_conditions["release_state"]
        return [
            self.step("default_branch", _Via.GRAPHQL, when=current),
            self.listing("release_milestones", milestones_endpoint(self.repo), when=current),
            self.step("release_prs", _Via.GRAPHQL, when=current),
            self.step("release_published", _Via.REST, when=current),
        ]

    def writes(self, subjects: Sequence[str], *, new: bool, repeat: str) -> list[PlannedRequest]:
        """The writes `--confirm` makes for each candidate it places or closes as a duplicate."""
        texts = MESSAGES.roadmap
        planned: list[PlannedRequest] = []
        for subject in subjects:
            if new:
                planned.append(self.step("file", _Via.REST, write=True, subject=subject))
            planned += self._placement(texts.intake_placeholder_filed if new else subject, repeat)
            planned += [] if new else self._duplicate(subject, repeat)
        return planned

    def _placement(self, subject: str, repeat: str) -> list[PlannedRequest]:
        """The writes that place `subject`, Priority last, when intake places it."""
        texts = MESSAGES.roadmap
        when = texts.intake_request_conditions["placed"].format(subject=subject)
        steps: list[tuple[str, tuple[_Via, ...], bool, dict[str, str]]] = [
            ("label", (_Via.REST,), True, {}),
            ("add", (_Via.REST, _Via.GRAPHQL), True, {}),
            ("item", (_Via.GRAPHQL, _Via.REST), False, {}),
            ("release", (_Via.GRAPHQL, _Via.REST), True, {}),
            *(
                ("field", (_Via.GRAPHQL,), True, {"field": name})
                for name in texts.intake_placeholder_fields
            ),
            ("comment", (_Via.REST,), True, {}),
            ("priority", (_Via.GRAPHQL,), True, {}),
        ]
        return [
            self.step(key, *via, write=write, when=when, repeat=repeat, subject=subject, **values)
            for key, via, write, values in steps
        ]

    def _duplicate(self, subject: str, repeat: str) -> list[PlannedRequest]:
        """The reads and writes that close `subject` as a duplicate, when it is one."""
        when = MESSAGES.roadmap.intake_request_conditions["duplicate"].format(subject=subject)
        steps = (
            ("duplicate_read", _Via.REST, False),
            ("duplicate_comment", _Via.REST, True),
            ("duplicate_close", _Via.GRAPHQL, True),
        )
        return [
            self.step(key, via, write=write, when=when, repeat=repeat, subject=subject)
            for key, via, write in steps
        ]


def planned_requests(
    subjects: Sequence[str], *, repo: str, ref: str | None, new: bool, each: bool = False
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """The requests a run over `subjects` makes, as reads and model calls, then the writes
    `--confirm` adds; `new` when the one subject is a candidate that is not an issue yet, and
    `each` when the one subject stands for every candidate, its requests repeated for each."""
    steps = _Steps(repo=repo, ref=ref)
    repeat = MESSAGES.roadmap.intake_repeat_candidate if each else ""
    reads = steps.reads() + steps.decisions(subjects, new=new, repeat=repeat)
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
