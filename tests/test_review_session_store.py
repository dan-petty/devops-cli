"""The review session store: the one place that says where review sessions live (#771)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_ERROR_CODE_SECURITY, CONST_EXIT_FAILURE
from devops_cli.exceptions import SecurityError
from devops_cli.review.session import ReviewSessionStore
from devops_cli.ui.data_providers import fetch_review_status, list_review_sessions


def test_sessions_live_in_the_reviews_directory_of_the_data_directory_variable(
    isolate_data_dir: Path,
) -> None:
    """Verify `DEVOPS_CLI_DATA_DIR` names the data directory whose `reviews` holds the sessions."""
    assert ReviewSessionStore.root() == isolate_data_dir / "reviews"


def test_a_relative_data_directory_variable_is_under_the_review_data_root(
    monkeypatch: pytest.MonkeyPatch, isolate_user_data_root: Path
) -> None:
    """Verify a relative `DEVOPS_CLI_DATA_DIR` resolves where a review resolves its data (#972),
    so a command run from another directory finds the sessions a review wrote."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", "kept")

    assert ReviewSessionStore.root() == isolate_user_data_root / "kept" / "reviews"


@pytest.mark.parametrize("set_by", ["environment", "config file"])
def test_sessions_live_where_the_reviews_directory_setting_points(
    set_by: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    config: Callable[..., Path],
) -> None:
    """Verify without `DEVOPS_CLI_DATA_DIR`, `data.reviews_dir` says where the sessions are,
    whether `DEVOPS_CLI_DATA_REVIEWS_DIR` or the config file sets it."""
    elsewhere = tmp_path / "elsewhere"
    monkeypatch.delenv("DEVOPS_CLI_DATA_DIR")
    if set_by == "environment":
        monkeypatch.setenv("DEVOPS_CLI_DATA_REVIEWS_DIR", str(elsewhere))
        config(data={"dir": str(tmp_path / "data")})
    else:
        config(data={"dir": str(tmp_path / "data"), "reviews_dir": str(elsewhere)})

    assert ReviewSessionStore.root() == elsewhere


def test_the_store_root_is_created_by_writing_a_session_not_by_asking_for_it(
    isolate_data_dir: Path,
) -> None:
    """Verify naming the root creates no directory, so a command that only reads sessions
    leaves a data directory without reviews as it found it."""
    root = ReviewSessionStore.root()

    assert (root.exists(), list(isolate_data_dir.iterdir())) == (False, [])


REFUSED_DATA_DIRECTORIES = [
    pytest.param("../../../outside", id="traversal"),
    pytest.param("/etc", id="system-directory"),
]


@pytest.mark.parametrize("data_dir", REFUSED_DATA_DIRECTORIES)
def test_the_store_root_refuses_a_directory_a_session_may_not_be_kept_in(
    data_dir: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a traversal sequence or a host system directory in the data directory is refused
    with a security error, whichever command resolved the root."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", data_dir)

    with pytest.raises(SecurityError) as refused:
        ReviewSessionStore.root()

    assert (refused.value.exit_code, refused.value.error_code) == (
        CONST_EXIT_FAILURE,
        CONST_ERROR_CODE_SECURITY,
    )


@pytest.mark.parametrize("data_dir", REFUSED_DATA_DIRECTORIES)
def test_the_dashboard_lists_no_review_when_the_store_root_is_refused(
    data_dir: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the dashboard shows an empty review panel for a refused directory, not a crash."""
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", data_dir)

    assert (list_review_sessions(), fetch_review_status().has_session) == ([], False)


def test_the_dashboard_lists_the_sessions_of_the_review_store(
    review_store: type[ReviewSessionStore],
) -> None:
    """Verify a session written under the store root is the one the dashboard lists."""
    session_dir = review_store.root() / "20261001-120000"
    session_dir.mkdir()
    (session_dir / "findings.json").write_text('{"findings": [{}]}', encoding="utf-8")

    assert [(info.name, info.completed) for info in list_review_sessions()] == [
        ("20261001-120000", True)
    ]
