"""The requests `devops roadmap intake` makes: the plan a dry run returns, and what a `--plan`
run spends (#742, the dry-run rule of #412).

A dry run makes no request at all. It returns the requests a run makes, in order, as
`PlannedRequest`s (#741): GitHub REST and GraphQL reads and writes, the embedding call and the
model calls. `method` names the transport and whether it reads or writes, and
`target` what it reads or writes. Every `gh` command shows its exact argv and stdin, built by
the store's own argument builders (`roadmap/request_plan.py`, #1125), one line per command, so a
field write shows the read of its issue it makes first (#1361). A value that needs a read is a
placeholder in angle brackets, a request that runs only when an earlier one returns something
names that in `condition`, and a listing read a page at a time, or a request made for each
candidate, says so in `repeat`. No request reaches a project board (ADR 0016).

A `--plan` run makes the reads and the model calls, writes nothing, and reports what it spent:
each GitHub request the identity's ledger paced during the run, a gh command and a request the
GitHub session sends alike, by the rate-limit resource it spends, each attempt and so each retry
counted (#983), and each embedding and proposal call. A proposal call counts once though the
client retries an answer that does not fit the schema, and an embedding call once though the
client may batch it or answer from its cache.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum

from devops_cli.config.constants import CONST_ROADMAP_LABELS_PATH
from devops_cli.dry_run.requests import PlannedRequest, both
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.intake_model import IntakeModel, ModelProposal, ProposalRequest
from devops_cli.roadmap.request_plan import StoreRequests, within


class _Via(StrEnum):
    """What a request that is not a `gh` command goes through."""

    EMBEDDING = "embedding"
    MODEL = "model"


@dataclass(frozen=True)
class _Steps:
    """Builds a run's requests: the repository, the ref shown, and the placeholders' text.

    Each step is one store or model operation, named by its key in the messages; a store
    operation lists each `gh` command it runs, built by the store's own argument builders, so
    the plan shows the exact command of every request (#1125)."""

    repo: str
    ref: str | None

    @property
    def at(self) -> str:
        return self.ref or MESSAGES.roadmap.intake_placeholder_default_branch

    @property
    def store(self) -> StoreRequests:
        return StoreRequests(self.repo)

    def _text(self, key: str, values: dict[str, str]) -> tuple[str, str]:
        texts = MESSAGES.roadmap
        values = {"ref": self.at, **values}
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

    def reads(self) -> list[PlannedRequest]:
        """The reads every run makes before it decides any candidate: every issue, once, which
        gives the candidates and the items alike."""
        return self.step("issues", self.store.issues())

    def decisions(self, subjects: Sequence[str], *, new: bool, repeat: str) -> list[PlannedRequest]:
        """The reads and model calls that decide each candidate, in the order a run makes them."""
        store = self.store
        candidate = "" if new else MESSAGES.roadmap.intake_request_conditions["candidate"]
        planned = self.step(
            "labels", store.file(CONST_ROADMAP_LABELS_PATH, self.ref), when=candidate
        )
        for s in [] if new else subjects:
            planned += self.step("closures", store.closures(s), subject=s, repeat=repeat)
        planned.append(self.call("embed_new" if new else "embed", _Via.EMBEDDING))
        for subject in subjects:
            planned.append(self.call("propose", _Via.MODEL, subject=subject, repeat=repeat))
            planned += self.step(
                "evidence", store.evidence(subject), subject=subject, repeat=repeat
            )
            if not new:
                planned += self.step(
                    "comments", store.comments_on(subject), subject=subject, repeat=repeat
                )
        return planned

    def writes(self, subjects: Sequence[str], *, new: bool, repeat: str) -> list[PlannedRequest]:
        """The writes `--confirm` makes for each candidate it places."""
        texts = MESSAGES.roadmap
        planned: list[PlannedRequest] = []
        for subject in subjects:
            if new:
                filing = self.store.create_issue(subject, (texts.plan_placeholders["label"],))
                planned += self.step("file", filing, subject=subject, repeat=repeat)
            planned += self._placement(texts.intake_placeholder_filed if new else subject, repeat)
        return planned

    def _placement(self, subject: str, repeat: str) -> list[PlannedRequest]:
        """The writes that place `subject`, Priority last, when intake places it."""
        texts = MESSAGES.roadmap
        store = self.store
        when = texts.intake_request_conditions["placed"].format(subject=subject)
        names = [name.split(" ", 1)[0] for name in texts.intake_placeholder_fields]
        steps: list[tuple[str, list[PlannedRequest], dict[str, str]]] = [
            ("label", store.label_issue(subject), {}),
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


def planned_requests(
    subjects: Sequence[str],
    *,
    repo: str,
    ref: str | None,
    new: bool,
    each: bool = False,
    limit: int | None = None,
) -> tuple[tuple[PlannedRequest, ...], tuple[PlannedRequest, ...]]:
    """The requests a run over `subjects` makes, as reads and model calls, then the writes
    `--confirm` adds after them; `new` when the one subject is a candidate that is not an issue
    yet, and `each` when the one subject stands for every candidate, its requests repeated for
    each, or for the `limit` oldest."""
    steps = _Steps(repo=repo, ref=ref)
    texts = MESSAGES.roadmap
    limited = texts.intake_repeat_limited.format(limit=limit) if limit is not None else ""
    repeat = (limited or texts.intake_repeat_candidate) if each else ""
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


def _paced() -> dict[str, int]:
    """The requests the process identity's ledger has paced so far, by resource."""
    from devops_cli.github.rate_limiter import get_github_rate_limiter

    return get_github_rate_limiter().requests_paced()


@dataclass
class SpendMeter:
    """Counts what a run spends from the moment it is made: the GitHub requests the process
    identity's ledger paces, where a gh command through `run_gh` and a request the GitHub
    session sends both wait their turn (#983), by the resource they spend, and each embedding
    and proposal call through `model`."""

    counts: Counter[str] = field(default_factory=Counter)
    start: dict[str, int] = field(default_factory=_paced)

    def model(self, model: IntakeModel) -> IntakeModel:
        return _MeteredModel(model, self.counts)

    def spend(self) -> Spend:
        paced = Counter(
            {
                _RESOURCE_FIELDS.get(resource, "rest"): count - self.start.get(resource, 0)
                for resource, count in _paced().items()
            }
        )
        return Spend(**(paced + self.counts))


__all__ = ["Spend", "SpendMeter", "planned_requests"]
