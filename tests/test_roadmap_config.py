"""`.github/roadmap.toml` parsing and reading through the roadmap store, with no network (#739, #1153)."""

from __future__ import annotations

import pytest

from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.config import RoadmapConfig, parse_roadmap_config, read_roadmap_config
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from tests.support.paths import REPO_ROOT


def test_omitted_keys_take_their_defaults() -> None:
    config = parse_roadmap_config("board = 2\n")
    assert (
        config.board,
        config.refine_ready_target,
        config.open_issue_limit,
        config.throttle_start_fraction,
        config.overage_step_fraction,
        config.quota_window_days,
        config.quota_credit_base,
        config.quota_credit_per_delivered_item,
        config.quota_credit_cap,
    ) == (2, 12, 200, 0.8, 0.25, 7, 10, 1, 50)


def test_a_missing_board_fails_and_names_the_key() -> None:
    with pytest.raises(ConfigurationError, match="board") as raised:
        parse_roadmap_config("quota_window_days = 10\n")
    assert raised.value.details["key"] == "board"


def test_an_unknown_key_fails_and_names_it() -> None:
    with pytest.raises(ConfigurationError, match="refine_ready_targit") as raised:
        parse_roadmap_config("board = 2\nrefine_ready_targit = 10\n")
    assert raised.value.details["key"] == "refine_ready_targit"


def test_an_unknown_quota_key_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="quota_bogus") as raised:
        parse_roadmap_config("board = 2\nquota_bogus = 123\n")
    assert raised.value.details["key"] == "quota_bogus"


@pytest.mark.parametrize(
    ("line", "key"),
    [
        pytest.param("quota_window_days = 0", "quota_window_days", id="window-below-one"),
        pytest.param("refine_ready_target = 0", "refine_ready_target", id="target-below-one"),
        pytest.param("quota_credit_cap = 0", "quota_credit_cap", id="cap-below-one"),
    ],
)
def test_a_count_below_one_fails_and_names_the_key(line: str, key: str) -> None:
    with pytest.raises(ConfigurationError, match=key) as raised:
        parse_roadmap_config(f"board = 2\n{line}\n")
    assert raised.value.details["key"] == key


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
        "board = 3\nrefine_ready_target = 8\nopen_issue_limit = 150\n"
        "throttle_start_fraction = 0.75\noverage_step_fraction = 0.2\nquota_window_days = 14\n"
        "quota_credit_base = 5\nquota_credit_per_delivered_item = 2\nquota_credit_cap = 40\n"
    )
    assert parse_roadmap_config(text) == RoadmapConfig(
        board=3,
        refine_ready_target=8,
        open_issue_limit=150,
        throttle_start_fraction=0.75,
        overage_step_fraction=0.2,
        quota_window_days=14,
        quota_credit_base=5,
        quota_credit_per_delivered_item=2,
        quota_credit_cap=40,
    )


def test_this_repositorys_file_names_board_2_and_declares_quota_keys() -> None:
    text = (REPO_ROOT / ".github" / "roadmap.toml").read_text(encoding="utf-8")
    assert parse_roadmap_config(text) == RoadmapConfig(
        board=2,
        open_issue_limit=200,
        throttle_start_fraction=0.8,
        overage_step_fraction=0.25,
        quota_window_days=7,
        quota_credit_base=10,
        quota_credit_per_delivered_item=1,
        quota_credit_cap=50,
    )


def test_the_file_is_read_at_the_ref_and_a_failed_read_stops() -> None:
    store = InMemoryRoadmapStore()
    store.seed_file(".github/roadmap.toml", "board = 2\nquota_window_days = 3\n", ref="topic/x")
    found = read_roadmap_config(store, ref="topic/x")
    with pytest.raises(GitHubOperationError, match=r"roadmap\.toml"):
        read_roadmap_config(store, ref=None)
    assert (found.board, found.quota_window_days) == (2, 3)
