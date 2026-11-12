"""The lines that name the commit that a `devops infra` command read, and where the checkout is
(#5162). The read itself runs through the onboarding (`tests/infra/test_onboard.py`)."""

from __future__ import annotations

import pytest

from devops_cli.infra.repo_tree import render_read
from devops_cli.models.infra import ReadCommit
from tests.support.infra import DEFAULT_BRANCH, OLD_COMMIT, ORIGIN_COMMIT

_READ = f"Reads {DEFAULT_BRANCH} at {ORIGIN_COMMIT}, not the working tree of the checkout."


@pytest.mark.parametrize(
    ("branch", "commit", "lines"),
    [
        pytest.param("main", ORIGIN_COMMIT, [_READ], id="at-the-commit"),
        pytest.param(
            "main",
            OLD_COMMIT,
            [_READ, f"The checkout is on the branch main at {OLD_COMMIT}, not on origin/main."],
            id="behind-origin",
        ),
        pytest.param(
            None,
            OLD_COMMIT,
            [_READ, f"The checkout is on a detached HEAD at {OLD_COMMIT}, not on origin/main."],
            id="detached",
        ),
        pytest.param(
            None,
            None,
            [_READ, "The checkout has no commit."],
            id="no-commit",
        ),
    ],
)
def test_the_read_names_the_commit_and_a_checkout_at_another_commit(
    branch: str | None, commit: str | None, lines: list[str]
) -> None:
    read = ReadCommit(
        ref=DEFAULT_BRANCH, commit=ORIGIN_COMMIT, checkout_branch=branch, checkout_commit=commit
    )

    assert render_read(read) == lines
