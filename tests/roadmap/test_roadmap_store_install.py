"""The install hook of the roadmap store: `get_roadmap_store` opens what a test installs, and the
GitHub store otherwise (#3746)."""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.roadmap.github_store import GitHubRoadmapStore
from devops_cli.roadmap.store import (
    get_roadmap_store,
    install_roadmap_store,
    reset_roadmap_store,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

REPO = "example/project"


def test_an_installed_factory_answers_for_every_repository() -> None:
    """`get_roadmap_store` returns what the installed factory returns, with the repository."""
    roadmap = InMemoryRoadmapStore()
    opened: list[str] = []

    def factory(repo: str, **_: Any) -> InMemoryRoadmapStore:
        opened.append(repo)
        return roadmap

    install_roadmap_store(factory)

    assert (get_roadmap_store(REPO), get_roadmap_store("example/other"), opened) == (
        roadmap,
        roadmap,
        [REPO, "example/other"],
    )


def test_an_installed_factory_receives_the_runner() -> None:
    """The runner a caller gives reaches the factory, so a factory can build the GitHub store
    over it."""
    received: list[Any] = []

    def runner(*_: Any, **__: Any) -> None:
        raise AssertionError("the factory runs no gh")

    def factory(repo: str, *, runner: Any = None) -> InMemoryRoadmapStore:
        received.append(runner)
        return InMemoryRoadmapStore()

    install_roadmap_store(factory)
    get_roadmap_store(REPO, runner=runner)

    assert received == [runner]


def test_a_reset_opens_the_github_store_again() -> None:
    """After `reset_roadmap_store`, the store is the GitHub adapter, which a factory no longer
    replaces. Opening it reads nothing."""
    install_roadmap_store(lambda repo, **_: InMemoryRoadmapStore())
    reset_roadmap_store()

    assert type(get_roadmap_store(REPO)) is GitHubRoadmapStore


def test_a_reset_with_no_factory_installed_changes_nothing() -> None:
    reset_roadmap_store()

    assert type(get_roadmap_store(REPO)) is GitHubRoadmapStore


def test_the_floor_fails_a_test_that_opens_the_github_store_and_runs_gh(
    unexpected_loopback_connects: list[str],
) -> None:
    """A test that does not install a store reaches the GitHub store, which starts `gh` as the
    developer's own login. The floor refuses it, and the error names `gh`."""
    try:
        with pytest.raises(pytest.fail.Exception, match="real gh"):
            get_roadmap_store(REPO).repository_is_private()
    finally:
        unexpected_loopback_connects.clear()
