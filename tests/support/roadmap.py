"""Roadmap store fixtures for testing roadmap commands and sync."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore


@pytest.fixture
def roadmap_store_repos() -> list[str]:
    """The repository each roadmap store a command opened during the test was opened for."""
    return []


@pytest.fixture
def roadmap_store(roadmap_store_repos: list[str]) -> InMemoryRoadmapStore:
    """The in-memory roadmap that every store a command opens during the test reads and writes.

    The fake is installed through `install_roadmap_store`, and the floor removes it after the
    test. Each store a command opens adds its repository to `roadmap_store_repos`, so a test can
    pin which repository a command reads and writes.
    """
    from devops_cli.roadmap.store import install_roadmap_store
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

    roadmap = InMemoryRoadmapStore()

    def open_store(repo: str, **_: Any) -> InMemoryRoadmapStore:
        roadmap_store_repos.append(repo)
        return roadmap

    install_roadmap_store(open_store)
    return roadmap


@pytest.fixture
def unreadable_github_roadmap() -> list[list[str]]:
    """Open the GitHub store over a `gh` that exits 1, as when GitHub can't be read, and a
    session whose listings that `gh` answers.

    Returns the argv of every `gh` command the store ran and every listing it read.
    """
    from devops_cli.roadmap.github_store import GitHubRoadmapStore
    from devops_cli.roadmap.store import install_roadmap_store
    from tests.support.fakes.github import RunnerSession

    calls: list[list[str]] = []

    def gh_exits_1(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 1, "", "HTTP 503: Service Unavailable")

    install_roadmap_store(
        lambda repo, runner=None, **kwargs: GitHubRoadmapStore(
            repo, runner=gh_exits_1, **kwargs, session=RunnerSession(gh_exits_1)
        )
    )
    return calls
