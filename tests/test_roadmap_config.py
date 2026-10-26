"""`.github/roadmap.toml` parsing and reading through the roadmap store, with no network (#739)."""

from __future__ import annotations

import pytest

from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.config import RoadmapConfig, parse_roadmap_config, read_roadmap_config
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.paths import REPO_ROOT


def test_a_missing_board_fails_and_names_the_key() -> None:
    with pytest.raises(ConfigurationError, match="board") as raised:
        parse_roadmap_config("# No board.\n")
    assert raised.value.details["key"] == "board"


def test_an_unknown_key_fails_and_names_it() -> None:
    """A key the model does not hold, such as the ready target that #2004 removed, is refused."""
    with pytest.raises(ConfigurationError, match="refine_ready_target") as raised:
        parse_roadmap_config("board = 2\nrefine_ready_target = 12\n")
    assert raised.value.details["key"] == "refine_ready_target"


def test_a_board_below_one_fails_and_names_the_key() -> None:
    with pytest.raises(ConfigurationError, match="board") as raised:
        parse_roadmap_config("board = 0\n")
    assert raised.value.details["key"] == "board"


def test_text_that_is_not_toml_fails() -> None:
    with pytest.raises(ConfigurationError, match="not valid TOML"):
        parse_roadmap_config("board = = 2\n")


def test_every_key_can_be_set() -> None:
    assert parse_roadmap_config("board = 3\n") == RoadmapConfig(board=3)


def test_this_repositorys_file_names_board_12() -> None:
    text = (REPO_ROOT / ".github" / "roadmap.toml").read_text(encoding="utf-8")
    assert parse_roadmap_config(text) == RoadmapConfig(board=12)


def test_the_file_is_read_at_the_ref_and_a_failed_read_stops() -> None:
    store = InMemoryRoadmapStore()
    store.seed_file(".github/roadmap.toml", "board = 3\n", ref="topic/x")
    found = read_roadmap_config(store, ref="topic/x")
    with pytest.raises(GitHubOperationError, match=r"roadmap\.toml"):
        read_roadmap_config(store, ref=None)
    assert found.board == 3
