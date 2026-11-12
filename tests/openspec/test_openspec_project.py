"""`repository_uses_openspec` reads the switch of OpenSpec of a repository that has no clone
(#3767): `openspec/config.yaml` on a branch, through the contents API. Only a missing file turns
the switch off."""

from __future__ import annotations

import pytest

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.openspec.project import repository_uses_openspec
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore


def test_a_branch_with_the_config_file_uses_openspec(roadmap_store: InMemoryRoadmapStore) -> None:
    roadmap_store.seed_file("openspec/config.yaml", "schema: spec-driven\n", ref="main")
    assert (
        repository_uses_openspec(roadmap_store, ref="main"),
        repository_uses_openspec(roadmap_store, ref=None),
    ) == (True, False)


def test_a_read_that_fails_is_no_repository_without_openspec(
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    roadmap_store.fail_read("repository_file", GitHubOperationError("HTTP 502: Bad Gateway"))
    with pytest.raises(GitHubOperationError, match="502"):
        repository_uses_openspec(roadmap_store, ref=None)
