"""`.github/roadmap.toml` parsing and reading through the roadmap store, with no network (#739)."""

from __future__ import annotations

import pytest

from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.config import RoadmapConfig, parse_roadmap_config, read_roadmap_config
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.paths import REPO_ROOT


def test_omitted_keys_take_their_defaults() -> None:
    config = parse_roadmap_config("board = 2\n")
    assert (config.board, config.refine_ready_target) == (2, 12)


def test_a_missing_board_fails_and_names_the_key() -> None:
    with pytest.raises(ConfigurationError, match="board") as raised:
        parse_roadmap_config("refine_ready_target = 10\n")
    assert raised.value.details["key"] == "board"


def test_an_unknown_key_fails_and_names_it() -> None:
    with pytest.raises(ConfigurationError, match="refine_ready_targit") as raised:
        parse_roadmap_config("board = 2\nrefine_ready_targit = 10\n")
    assert raised.value.details["key"] == "refine_ready_targit"


def test_a_ready_target_below_one_fails_and_names_the_key() -> None:
    with pytest.raises(ConfigurationError, match="refine_ready_target") as raised:
        parse_roadmap_config("board = 2\nrefine_ready_target = 0\n")
    assert raised.value.details["key"] == "refine_ready_target"


def test_text_that_is_not_toml_fails() -> None:
    with pytest.raises(ConfigurationError, match="not valid TOML"):
        parse_roadmap_config("board = = 2\n")


def test_every_key_can_be_set() -> None:
    text = "board = 3\nrefine_ready_target = 8\n"
    assert parse_roadmap_config(text) == RoadmapConfig(board=3, refine_ready_target=8)


def test_this_repositorys_file_names_board_2() -> None:
    text = (REPO_ROOT / ".github" / "roadmap.toml").read_text(encoding="utf-8")
    assert parse_roadmap_config(text) == RoadmapConfig(board=2)


def test_the_file_is_read_at_the_ref_and_a_failed_read_stops() -> None:
    store = InMemoryRoadmapStore()
    store.seed_file(".github/roadmap.toml", "board = 2\nrefine_ready_target = 3\n", ref="topic/x")
    found = read_roadmap_config(store, ref="topic/x")
    with pytest.raises(GitHubOperationError, match=r"roadmap\.toml"):
        read_roadmap_config(store, ref=None)
    assert (found.board, found.refine_ready_target) == (2, 3)
