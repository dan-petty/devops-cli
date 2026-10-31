"""The claim of a roadmap Item (#2910): the `owner/*` label family, the rule of a claim, and the
commands `devops roadmap claim` and `devops roadmap release`.

The rule and the family run against both adapters of the store: the in-memory one, and the
GitHub one over `GitHubFake`, the `gh` process edge.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

import pytest

from devops_cli.exceptions import DevOpsCLIError
from devops_cli.exceptions.roadmap import RoadmapClaimError, RoadmapItemChangedError
from devops_cli.roadmap.claim import (
    Claimant,
    apply_claim,
    claimed_by,
    plan_claim,
    render_claim_plan,
)
from devops_cli.roadmap.github_store import GitHubRoadmapStore
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import GitHubState, Item, ItemField, RoadmapStore
from tests.roadmap_github_fake import GitHubFake
from tests.support.fakes.github import RunnerSession

REPO = "example/roadmap"
ITEM = ("priority/p2-medium",)


class World(Protocol):
    """One repository, the job's store on it, and what a person does on GitHub."""

    store: RoadmapStore

    def seed(self, *labels: str) -> int: ...

    def person_adds(self, number: int, label: str) -> None: ...

    def labels(self, number: int) -> list[str]: ...

    def writes(self) -> int: ...


class MemoryWorld:
    def __init__(self) -> None:
        self._roadmap = InMemoryRoadmapStore(repo=REPO)
        self.store: RoadmapStore = self._roadmap

    def seed(self, *labels: str) -> int:
        return self._roadmap.seed_issue("work", labels=labels)

    def person_adds(self, number: int, label: str) -> None:
        self._roadmap.as_actor("alice").add_label(number, label)

    def labels(self, number: int) -> list[str]:
        return next(list(i.labels) for i in self._roadmap.issues() if i.number == number)

    def writes(self) -> int:
        return len(self._roadmap.job_writes())


class GitHubWorld:
    def __init__(self) -> None:
        self.github = GitHubFake(REPO)
        self.store: RoadmapStore = GitHubRoadmapStore(
            REPO, runner=self.github, session=RunnerSession(self.github)
        )

    def seed(self, *labels: str) -> int:
        number = len(self.github.issues) + 1
        self.github.seed_issue(number, "work", labels=labels)
        return number

    def person_adds(self, number: int, label: str) -> None:
        self.github.issues[number]["labels"].append({"name": label})

    def labels(self, number: int) -> list[str]:
        return self.github.labels(number)

    def writes(self) -> int:
        return len(self.github.writes())


@pytest.fixture(params=["memory", "github"])
def world(request: pytest.FixtureRequest) -> Iterator[World]:
    yield MemoryWorld() if request.param == "memory" else GitHubWorld()


def read(world: World, number: int) -> Item:
    found = world.store.item(number)
    assert found is not None
    return found


def claim(world: World, number: int, claimant: Claimant | None) -> bool:
    """Plan and apply a claim of `number`, or a release when `claimant` is None."""
    return apply_claim(world.store, plan_claim(world.store, number, claimant, REPO))


def owner_labels(world: World, number: int) -> list[str]:
    return [label for label in world.labels(number) if label.startswith("owner/")]


# ── The owner label family ────────────────────────────────────────────────────


def test_the_owner_is_read_from_its_label_family(world: World) -> None:
    held = world.seed(*ITEM, "owner/agent")
    free = world.seed(*ITEM)
    assert (read(world, held).owner, read(world, free).owner) == ("Agent", None)


def test_a_label_a_person_adds_beside_the_services_is_the_owner(world: World) -> None:
    number = world.seed(*ITEM)
    world.store.set_field(read(world, number), ItemField.OWNER, "Service")
    world.person_adds(number, "owner/human")
    assert (read(world, number).owner, owner_labels(world, number)) == (
        "Human",
        ["owner/service", "owner/human"],
    )


def test_a_job_write_of_the_owner_raises_after_a_persons_change(world: World) -> None:
    number = world.seed(*ITEM)
    seen = read(world, number)
    world.person_adds(number, "owner/human")
    with pytest.raises(RoadmapItemChangedError, match="Owner is Human"):
        world.store.set_field(seen, ItemField.OWNER, "Service")
    assert owner_labels(world, number) == ["owner/human"]


# ── The rule of a claim ───────────────────────────────────────────────────────


def test_a_claim_of_a_free_item_sets_one_owner_label(world: World) -> None:
    number = world.seed(*ITEM, "type/bug")
    assert claim(world, number, Claimant.AGENT) is True
    assert (world.labels(number), read(world, number).owner) == (
        ["priority/p2-medium", "type/bug", "owner/agent"],
        "Agent",
    )


def test_a_person_takes_an_item_from_the_service(world: World) -> None:
    number = world.seed(*ITEM, "owner/service")
    assert claim(world, number, Claimant.HUMAN) is True
    assert owner_labels(world, number) == ["owner/human"]


@pytest.mark.parametrize(
    ("held", "claimant"),
    [
        ("owner/human", Claimant.AGENT),
        ("owner/agent", Claimant.HUMAN),
        ("owner/service", Claimant.AGENT),
    ],
)
def test_a_second_owner_is_refused_with_the_owner_named(
    world: World, held: str, claimant: Claimant
) -> None:
    number = world.seed(*ITEM, held)
    before = world.writes()
    with pytest.raises(RoadmapClaimError, match=held.removeprefix("owner/")):
        plan_claim(world.store, number, claimant, REPO)
    assert (owner_labels(world, number), world.writes()) == ([held], before)


def test_a_claim_by_the_owner_that_holds_the_item_sends_no_write(world: World) -> None:
    number = world.seed(*ITEM, "owner/agent")
    before = world.writes()
    assert claim(world, number, Claimant.AGENT) is False
    assert world.writes() == before


def test_a_claim_made_after_the_plan_is_refused_and_never_reverted(world: World) -> None:
    number = world.seed(*ITEM)
    plan = plan_claim(world.store, number, Claimant.AGENT, REPO)
    world.person_adds(number, "owner/human")
    with pytest.raises(RoadmapClaimError, match="human"):
        apply_claim(world.store, plan)
    assert owner_labels(world, number) == ["owner/human"]


def test_an_issue_with_no_priority_is_no_item_to_claim(world: World) -> None:
    number = world.seed("type/bug")
    with pytest.raises(DevOpsCLIError, match=f"#{number} is not an item of the roadmap"):
        plan_claim(world.store, number, Claimant.AGENT, REPO)


def test_a_closed_issue_cannot_be_claimed_but_its_stray_owner_can_be_released() -> None:
    roadmap = InMemoryRoadmapStore(repo=REPO)
    closed = roadmap.seed_issue("done", state=GitHubState.CLOSED, labels=ITEM)
    stray = roadmap.seed_issue("done", state=GitHubState.CLOSED, labels=(*ITEM, "owner/human"))

    with pytest.raises(RoadmapClaimError, match=f"#{closed} is closed"):
        plan_claim(roadmap, closed, Claimant.HUMAN, REPO)
    assert apply_claim(roadmap, plan_claim(roadmap, stray, None, REPO)) is True


def test_a_release_clears_the_owner_and_keeps_the_other_labels(world: World) -> None:
    number = world.seed(*ITEM, "owner/agent", "type/bug")
    assert claim(world, number, None) is True
    assert world.labels(number) == ["priority/p2-medium", "type/bug"]


def test_a_release_of_a_free_item_sends_no_write(world: World) -> None:
    number = world.seed(*ITEM)
    before = world.writes()
    assert claim(world, number, None) is False
    assert world.writes() == before


@pytest.mark.parametrize(
    ("label", "held_by"),
    [("owner/service", None), ("owner/agent", "agent"), ("owner/human", "human"), ("", None)],
)
def test_only_an_agent_and_a_person_hold_an_item_against_the_jobs(
    world: World, label: str, held_by: str | None
) -> None:
    assert claimed_by(read(world, world.seed(*ITEM, *filter(None, [label])))) == held_by


def test_the_plan_names_the_item_and_the_change() -> None:
    store = InMemoryRoadmapStore(repo=REPO)
    number = store.seed_issue("Fix it", labels=("priority/p2-medium", "owner/service"))
    plan = plan_claim(store, number, Claimant.HUMAN, REPO)
    assert render_claim_plan(plan) == f"Item #{number}: Fix it\nOwner: Service -> Human"
