"""Contract suite of the provider seam of the reference step (#4672): each case runs over the
fake provider and over the GitHub code search provider on the in-memory roadmap store.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest

from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.references.providers import (
    GitHubCodeSearch,
    Hit,
    HitKind,
    ReferenceProvider,
    SearchKind,
)
from devops_cli.roadmap.stores.store import CodeSearchHit
from tests.support.fakes.reference_provider import FakeReferenceProvider
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

QUERY = "pydantic_ai"
ERROR = GitHubOperationError("HTTP 502", operation="roadmap.read")


@dataclass
class World:
    """A provider, with what makes it find one file for `QUERY` and what makes it fail."""

    provider: ReferenceProvider
    seed: Callable[[], None]
    fail: Callable[[], None]


def _fake() -> World:
    provider = FakeReferenceProvider("github-code", SearchKind.CODE)
    hit = Hit("github-code", HitKind.CODE, QUERY, repository="example/agent", path="src/agent.py")
    return World(provider, lambda: provider.answer(QUERY, hit), lambda: provider.fail(ERROR))


def _github() -> World:
    store = InMemoryRoadmapStore(repo="example/roadmap")
    found = CodeSearchHit(repository="example/agent", path="src/agent.py")
    return World(
        GitHubCodeSearch(store),
        lambda: store.seed_code_search(QUERY, found),
        lambda: store.fail_read("search_code", ERROR),
    )


@pytest.fixture(params=[_fake, _github], ids=["fake", "github-code"])
def world(request: pytest.FixtureRequest) -> World:
    return request.param()


def test_a_search_gives_the_code_hits_of_its_query_under_the_name_of_the_provider(
    world: World,
) -> None:
    world.seed()

    assert (world.provider.search(QUERY), world.provider.search("another query")) == (
        [Hit("github-code", HitKind.CODE, QUERY, repository="example/agent", path="src/agent.py")],
        [],
    )


def test_a_provider_names_itself_and_the_bound_that_a_search_spends(world: World) -> None:
    assert (world.provider.name, world.provider.kind) == ("github-code", SearchKind.CODE)


def test_a_search_that_cannot_complete_raises_a_typed_error(world: World) -> None:
    world.fail()

    with pytest.raises(DevOpsCLIError, match="HTTP 502"):
        world.provider.search(QUERY)
