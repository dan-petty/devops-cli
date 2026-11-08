"""The helpers that the `devops roadmap intake` test files share: the roadmap builder, the scripted
model, the fixtures of the command and the candidates of the tests (#1335).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from devops_cli.ai.rag.embeddings import install_embedder
from devops_cli.roadmap.intake.intake import (
    IntakePlan,
    apply_intake,
    plan_intake,
    raise_for_failed_placements,
)
from devops_cli.roadmap.intake.intake_model import (
    ModelProposal,
    Neighbour,
    ProposalRequest,
)
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.store import (
    GitHubState,
    Item,
    ItemField,
    family_prefix,
    install_roadmap_store,
    item_of,
)
from tests.support.fakes.github import RunnerSession
from tests.support.fakes.github_repository import GitHubFake
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.model import ModelFake
from tests.support.fakes.process import ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore, JobWrite
from tests.support.paths import REPO_ROOT

REPO = "example/roadmap"


NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


# The roadmap's milestones, planning buckets a person made: one closed, two open.
DONE = "Docs pass"
PLANNED = "2026-11-05"
LATER = "Q4 hardening"


LABELS_YML = (REPO_ROOT / ".github" / "labels.yml").read_text(encoding="utf-8")


DEFAULT_PROPOSAL: dict[str, Any] = {
    "type": "type/feature",
    "type_reason": "it adds a capability.",
    "priority": "P2-Medium",
    "priority_reason": "useful, not urgent.",
    "value": "Medium",
    "value_reason": "it helps maintainers.",
    "effort": "Low",
    "effort_reason": "one module.",
}


@dataclass
class FakeModel:
    """Embeds by the words a text shares with `topics`, and judges as told: `duplicates` maps a
    candidate's title to the title of the item it duplicates, whose title it names as the
    shared change, and `proposals` maps a title to the fields its proposal changes."""

    duplicates: dict[str, str] = field(default_factory=dict)
    proposals: dict[str, dict[str, Any]] = field(default_factory=dict)
    topics: tuple[str, ...] = ()
    embedded: list[str] = field(default_factory=list)
    requests: list[ProposalRequest] = field(default_factory=list)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.embedded.extend(texts)
        return [[1.0, *(float(topic in text) for topic in self.topics)] for text in texts]

    def propose(self, request: ProposalRequest) -> ModelProposal:
        self.requests.append(request)
        original = self.duplicates.get(request.title)
        duplicate = next((n.number for n in request.shortlist if n.title == original), None)
        shared = {"shared_change": original} if duplicate is not None else {}
        fields = DEFAULT_PROPOSAL | shared | self.proposals.get(request.title, {})
        return ModelProposal.model_validate({"duplicate_of": duplicate, **fields})


class Roadmap:
    """One repository's roadmap: milestone `Docs pass` closed a day ago, and `2026-11-05` and
    `Q4 hardening` are open. Its `.github/labels.yml` holds `labels`, this repository's own by
    default; with None it has none."""

    def __init__(
        self,
        store: InMemoryRoadmapStore | None = None,
        labels: str | None = LABELS_YML,
    ):
        self.now = NOW - timedelta(days=1)
        self.store = store or InMemoryRoadmapStore(clock=self.clock)
        self.person = self.store.as_actor("alice")
        if labels is not None:
            self.store.seed_file(".github/labels.yml", labels)
        self.store.seed_milestone(DONE, state=GitHubState.CLOSED)
        self.store.seed_milestone(PLANNED, due_on=NOW.date() + timedelta(days=32))
        self.store.seed_milestone(LATER)
        self.now = NOW

    def clock(self) -> datetime:
        return self.now

    def issue(
        self,
        title: str,
        body: str = "",
        *,
        author: str = "COLLABORATOR",
        labels: Sequence[str] = (),
        milestone: str | None = None,
        state: GitHubState = GitHubState.OPEN,
        state_reason: str | None = None,
        **seeded: Any,
    ) -> int:
        """Seed an issue; `seeded` holds the other options of `seed_issue`, such as
        `sub_issues` or the `fields` a person set."""
        return self.store.seed_issue(
            title,
            body=body,
            author_association=author,
            labels=labels,
            milestone=milestone,
            state=state,
            state_reason=state_reason,
            **seeded,
        )

    def finished(self, title: str, **options: Any) -> int:
        """An item a job finished: an issue with a Priority."""
        number = self.issue(title, **options)
        self.store.set_field(self.item(number), ItemField.PRIORITY, "P3-Low")
        return number

    def item(self, number: int) -> Item:
        """Issue `number` as an Item, its fields from its labels, whether or not it is one."""
        return item_of(next(issue for issue in self.store.issues() if issue.number == number))

    def fields(self, number: int) -> tuple[str | None, ...]:
        found = self.item(number)
        return (found.status, found.priority, found.value, found.effort, found.milestone)

    def comments(self, number: int) -> list[str]:
        return [comment.body for comment in self.store.comments_on(number)]

    def plan(self, model: FakeModel, **options: Any) -> IntakePlan:
        return plan_intake(self.store, repo=REPO, model=model, **options)

    def run(self, model: FakeModel, **options: Any) -> list[JobWrite]:
        """Apply a plan as the CLI and the Service do: every candidate, then the failures."""
        before = len(self.store.job_writes())
        raise_for_failed_placements(
            apply_intake(self.store, self.plan(model, **options), repo=REPO)
        )
        return self.store.job_writes()[before:]


@pytest.fixture
def roadmap() -> Roadmap:
    return Roadmap()


FIELD_PREFIXES = tuple(family_prefix(item_field) for item_field in ItemField)


def labels_of(roadmap: Roadmap, number: int) -> tuple[str, ...]:
    """The labels of issue `number` that hold no field: its type, its source."""
    labels = next(issue.labels for issue in roadmap.store.issues() if issue.number == number)
    return tuple(label for label in labels if not label.startswith(FIELD_PREFIXES))


# ── Duplicates ────────────────────────────────────────────────────────────────


def possible_duplicate_line(original: int, change: str) -> str:
    """The line of the reason comment that names a possible original."""
    return (
        f"- Possible duplicate: #{original}, which may ask for the same change. The model names "
        f"`{change}` as the change that both ask for. A person closes one of the two if that is "
        "so."
    )


# ── Priority and evidence ─────────────────────────────────────────────────────


REGRESSION = {
    "type": "type/bug",
    "priority": "P1-High",
    "evidence": {"kind": "regression_commit", "value": "abc1234"},
}


def echoing(
    propose: Callable[[ProposalRequest], ModelProposal], echoed: dict[str, Any]
) -> Callable[[ProposalRequest], ModelProposal]:
    """The model echoes the injection whatever its shortlist holds."""

    def echo(request: ProposalRequest) -> ModelProposal:
        propose(request)
        return ModelProposal.model_validate(DEFAULT_PROPOSAL | echoed)

    return echo


# ── The command and its MCP mirror ────────────────────────────────────────────


@pytest.fixture
def opened(roadmap_store: InMemoryRoadmapStore) -> Roadmap:
    """The store every command opens."""
    return Roadmap(roadmap_store)


class _TopicEmbedder:
    """The embedder of every model a command builds: it embeds as `model` does."""

    def __init__(self, model: FakeModel) -> None:
        self._model = model

    def embed_texts(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        return self._model.embed(texts)


@pytest.fixture
def fake_model(model_fake: ModelFake, keyring_store: FakeKeyring) -> FakeModel:
    """The model every command builds: its embeddings come from the installed embedder, and its
    proposals from the model fake, which answers each request as `FakeModel.propose` does."""
    model = FakeModel()
    install_embedder(_TopicEmbedder(model))

    def propose(prompt: str) -> str:
        sent = json.loads(prompt)
        request = ProposalRequest(
            title=sent["title"],
            body=sent["body"],
            shortlist=tuple(Neighbour(**near) for near in sent["shortlist"]),
            types=tuple(sent["types"]),
        )
        return model.propose(request).model_dump_json()

    model_fake.answer(propose)
    return model


@pytest.fixture
def run_intake(cli: Callable[..., Any]) -> Callable[..., str]:
    """Run `devops roadmap intake --repo REPO <flags>`, check its exit code and return its output
    on one line."""

    def run(*flags: str, exit_code: int = 0) -> str:
        result = cli("roadmap", "intake", "--repo", REPO, *flags)
        assert result.exit_code == exit_code, result.output
        return " ".join(result.output.split())

    return run


@pytest.fixture
def no_requests(
    process_fake: ProcessFake, model_fake: ModelFake, fake_model: FakeModel
) -> Iterator[None]:
    """A roadmap store, a model call and a process (`gh` or any other) that fail the test when a
    command opens, makes or starts one; the session's socket guard covers connections."""

    def no_store(*_: object, **__: object) -> InMemoryRoadmapStore:
        raise AssertionError("the dry run opened the roadmap store")

    install_roadmap_store(no_store)
    yield
    assert (process_fake.calls, model_fake.call_count, fake_model.embedded) == ([], 0, [])


class Recorded:
    """Delegates to `inner`, logging the name of each public method called on it."""

    def __init__(self, inner: object, log: list[str]) -> None:
        self._inner, self._log = inner, log

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._inner, name)
        if not callable(attr) or name.startswith("_"):
            return attr

        def called(*args: Any, **kwargs: Any) -> Any:
            self._log.append(name)
            return attr(*args, **kwargs)

        return called


# ── Review fixes ──────────────────────────────────────────────────────────────


class Embedder:
    def embed_texts(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        return [[1.0] for _ in texts]


# ── On the GitHub store, at the `gh` process edge (#1361, #2399) ───────────────
# The store runs every command through `GitHubFake`, which answers as GitHub's REST API does: an
# issue `PATCH` replaces its labels and its body. No request reaches a project board.

GITHUB_MILESTONES = [
    {"number": 25, "title": DONE, "state": "closed", "closed_at": "2026-10-03T12:00:00Z"},
    {"number": 26, "title": PLANNED, "state": "open", "due_on": "2026-11-05T07:00:00Z"},
    {"number": 27, "title": LATER, "state": "open"},
]


FINISHED = ("type/feature", "status/ready", "priority/p3-low", "value/low", "effort/low")


def on_github(items: int = 0) -> tuple[GitHubFake, GitHubRoadmapStore]:
    """A repository that holds `items` finished items, and the store over it."""
    github = GitHubFake(
        REPO,
        milestones=GITHUB_MILESTONES,
        files={".github/labels.yml": LABELS_YML},
        commits=("abc1234",),
    )
    for number in range(1, items + 1):
        github.seed_issue(number, f"feat: finished item {number}", labels=FINISHED)
    return github, GitHubRoadmapStore(REPO, runner=github, session=RunnerSession(github))


def intake_on_github(
    store: GitHubRoadmapStore, model: FakeModel, **options: Any
) -> tuple[IntakePlan, Any]:
    plan = plan_intake(store, repo=REPO, model=model, **options)
    return plan, lambda: apply_intake(store, plan, repo=REPO)
