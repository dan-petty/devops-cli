"""`.github/roadmap.toml` parsing and reading through the roadmap store, with no network (#739)."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.config import RoadmapConfig, parse_roadmap_config, read_roadmap_config
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore


def test_omitted_keys_take_their_defaults() -> None:
    config = parse_roadmap_config("board = 2\n")
    assert (
        config.board,
        config.release_cap,
        config.discovery_threshold,
        config.planning_horizon,
        config.stall_days,
    ) == (2, 12, 24, 2, 14)


def test_a_missing_board_fails_and_names_the_key() -> None:
    with pytest.raises(ConfigurationError, match="board") as raised:
        parse_roadmap_config("release_cap = 10\n")
    assert raised.value.details["key"] == "board"


def test_an_unknown_key_fails_and_names_it() -> None:
    with pytest.raises(ConfigurationError, match="release_kap") as raised:
        parse_roadmap_config("board = 2\nrelease_kap = 10\n")
    assert raised.value.details["key"] == "release_kap"


def test_text_that_is_not_toml_fails() -> None:
    with pytest.raises(ConfigurationError, match="not valid TOML"):
        parse_roadmap_config("board = = 2\n")


def test_every_key_can_be_set() -> None:
    text = (
        "board = 3\nrelease_cap = 8\ndiscovery_threshold = 10\nplanning_horizon = 1\n"
        "stall_days = 7\n"
    )
    assert parse_roadmap_config(text) == RoadmapConfig(
        board=3, release_cap=8, discovery_threshold=10, planning_horizon=1, stall_days=7
    )


def test_this_repositorys_file_names_board_2_and_keeps_three_planned_releases() -> None:
    text = (Path(__file__).parents[1] / ".github" / "roadmap.toml").read_text(encoding="utf-8")
    assert parse_roadmap_config(text) == RoadmapConfig(board=2, planning_horizon=3)


def test_the_file_is_read_at_the_ref_and_a_failed_read_stops() -> None:
    store = InMemoryRoadmapStore()
    store.seed_file(".github/roadmap.toml", "board = 2\nplanning_horizon = 3\n", ref="release/x")
    found = read_roadmap_config(store, ref="release/x")
    with pytest.raises(GitHubOperationError, match=r"roadmap\.toml"):
        read_roadmap_config(store, ref=None)
    assert (found.board, found.planning_horizon) == (2, 3)
