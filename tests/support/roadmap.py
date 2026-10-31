"""Roadmap store fixtures for testing roadmap commands and sync."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any, NoReturn
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
    from devops_cli.roadmap.store import RoadmapStore


@pytest.fixture(autouse=True, scope="session")
def github_roadmap_factory() -> Iterator[Callable[..., RoadmapStore]]:
    """Keep every test off the GitHub roadmap store, and hand its real factory to its own test.

    The GitHub store runs `gh`, which in a test acts as the developer's own login: `run_gh` passes
    its child no `GH_CONFIG_DIR`, so `isolate_gh_config` does not reach it. For the whole run the
    factory refuses instead, and a test that drives a roadmap command requests `roadmap_store`.
    """
    from devops_cli.roadmap import store as roadmap_module

    factory = roadmap_module.get_roadmap_store

    def refuse(repo: str, **_: Any) -> NoReturn:
        raise AssertionError(
            f"A test opened the GitHub roadmap store for {repo}, which runs the developer's own "
            "gh login. Request the roadmap_store fixture instead."
        )

    with patch.object(roadmap_module, "get_roadmap_store", refuse):
        yield factory


@pytest.fixture
def roadmap_store_repos() -> list[str]:
    """The repository each roadmap store a command opened during the test was opened for."""
    return []


@pytest.fixture
def roadmap_store(
    monkeypatch: pytest.MonkeyPatch, roadmap_store_repos: list[str]
) -> InMemoryRoadmapStore:
    """The in-memory roadmap that every store a command opens during the test reads and writes.

    Each store a command opens adds its repository to `roadmap_store_repos`, so a test can pin
    which repository a command reads and writes.
    """
    from devops_cli.roadmap import store as roadmap_module
    from devops_cli.roadmap.memory_store import InMemoryRoadmapStore

    roadmap = InMemoryRoadmapStore()

    def open_store(repo: str, **_: Any) -> InMemoryRoadmapStore:
        roadmap_store_repos.append(repo)
        return roadmap

    monkeypatch.setattr(roadmap_module, "get_roadmap_store", open_store)
    return roadmap


@pytest.fixture
def unreadable_github_roadmap(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Open the GitHub store over a `gh` that exits 1, as when GitHub can't be read, and a
    session whose listings that `gh` answers.

    Returns the argv of every `gh` command the store ran and every listing it read.
    """
    from devops_cli.roadmap import store as roadmap_module
    from devops_cli.roadmap.github_store import GitHubRoadmapStore
    from tests.support.fakes.github import RunnerSession

    calls: list[list[str]] = []

    def gh_exits_1(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 1, "", "HTTP 503: Service Unavailable")

    monkeypatch.setattr(
        roadmap_module,
        "get_roadmap_store",
        lambda repo, runner=None, **kwargs: GitHubRoadmapStore(
            repo, runner=gh_exits_1, **kwargs, session=RunnerSession(gh_exits_1)
        ),
    )
    return calls
