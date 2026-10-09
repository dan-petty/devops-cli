"""`.github/roadmap.toml` parsing and reading through the roadmap store, with no network (#739, #1153)."""

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
        config.open_issue_limit,
        config.throttle_start_fraction,
        config.overage_step_fraction,
        config.release_credit_base,
        config.release_credit_per_delivered_item,
        config.release_item_target,
    ) == (2, 12, 24, 2, 14, 200, 0.8, 0.25, 10, 1, 50)


def test_a_missing_board_fails_and_names_the_key() -> None:
    with pytest.raises(ConfigurationError, match="board") as raised:
        parse_roadmap_config("release_cap = 10\n")
    assert raised.value.details["key"] == "board"


def test_an_unknown_key_fails_and_names_it() -> None:
    with pytest.raises(ConfigurationError, match="release_kap") as raised:
        parse_roadmap_config("board = 2\nrelease_kap = 10\n")
    assert raised.value.details["key"] == "release_kap"


def test_an_unknown_quota_key_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="quota_bogus") as raised:
        parse_roadmap_config("board = 2\nquota_bogus = 123\n")
    assert raised.value.details["key"] == "quota_bogus"


def test_text_that_is_not_toml_fails() -> None:
    with pytest.raises(ConfigurationError, match="not valid TOML"):
        parse_roadmap_config("board = = 2\n")


@pytest.mark.parametrize(
    ("key", "val"),
    [
        ("throttle_start_fraction", "0.0"),
        ("throttle_start_fraction", "1.0"),
        ("overage_step_fraction", "0.0"),
        ("overage_step_fraction", "1.0"),
    ],
)
def test_fraction_boundary_zero_or_one_rejected_with_key_named(key: str, val: str) -> None:
    with pytest.raises(ConfigurationError, match=key) as raised:
        parse_roadmap_config(f"board = 2\n{key} = {val}\n")
    assert raised.value.details["key"] == key


def test_every_key_can_be_set() -> None:
    text = (
        "board = 3\nrelease_cap = 8\ndiscovery_threshold = 10\nplanning_horizon = 1\n"
        "stall_days = 7\nopen_issue_limit = 150\nthrottle_start_fraction = 0.75\n"
        "overage_step_fraction = 0.2\nrelease_credit_base = 5\n"
        "release_credit_per_delivered_item = 2\nrelease_item_target = 40\n"
    )
    assert parse_roadmap_config(text) == RoadmapConfig(
        board=3,
        release_cap=8,
        discovery_threshold=10,
        planning_horizon=1,
        stall_days=7,
        open_issue_limit=150,
        throttle_start_fraction=0.75,
        overage_step_fraction=0.2,
        release_credit_base=5,
        release_credit_per_delivered_item=2,
        release_item_target=40,
    )


def test_this_repositorys_file_names_board_2_and_declares_quota_keys() -> None:
    text = (Path(__file__).parents[1] / ".github" / "roadmap.toml").read_text(encoding="utf-8")
    assert parse_roadmap_config(text) == RoadmapConfig(
        board=2,
        planning_horizon=3,
        release_cap=16,  # temporary bridge until the Service runs #1514's slots
        open_issue_limit=200,
        throttle_start_fraction=0.8,
        overage_step_fraction=0.25,
        release_credit_base=10,
        release_credit_per_delivered_item=1,
        release_item_target=50,
    )


def test_the_file_is_read_at_the_ref_and_a_failed_read_stops() -> None:
    store = InMemoryRoadmapStore()
    store.seed_file(".github/roadmap.toml", "board = 2\nplanning_horizon = 3\n", ref="release/x")
    found = read_roadmap_config(store, ref="release/x")
    with pytest.raises(GitHubOperationError, match=r"roadmap\.toml"):
        read_roadmap_config(store, ref=None)
    assert (found.board, found.planning_horizon) == (2, 3)
