"""A shared git repository fixture with a recorded commit and no real git process (ADR 0007)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall

GIT_REPO_COMMIT = "0123456789abcdef0123456789abcdef01234567"


def _answer_git_repo(repo: Path, call: ProcessCall) -> ProcessAnswer:
    argv = list(call.argv)
    if "rev-parse" in argv and "HEAD" in argv:
        return ProcessAnswer(stdout=f"{GIT_REPO_COMMIT}\n")
    if "status" in argv:
        return ProcessAnswer(stdout="")
    return ProcessAnswer()


@pytest.fixture
def git_repo(tmp_path: Path, git_fake: GitFake) -> Path:
    """A git repository fixture that creates .git and answers rev-parse HEAD with a recorded commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    git_fake.answer(
        lambda call: bool(
            call.argv and (call.argv[0] == "git" or Path(call.argv[0]).name == "git")
        ),
        lambda call: _answer_git_repo(repo, call),
    )
    return repo
