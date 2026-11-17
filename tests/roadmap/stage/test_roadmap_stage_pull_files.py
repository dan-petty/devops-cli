"""The files of the pull requests that an issue or a plan names (#3447)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_ROADMAP_STAGE_VERIFY_MAX_FILES
from devops_cli.exceptions.git import GitHubNotFoundError
from devops_cli.github.client import CommitRef, PullRequest
from devops_cli.roadmap.stage.stage_pull_files import (
    PullRequestFiles,
    named_pull_requests,
    pull_request_files,
)


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def _configure(root: Path) -> None:
    for key, value in (("user.email", "ci@example.com"), ("user.name", "CI")):
        _git(root, "config", key, value)
    _git(root, "config", "commit.gpgsign", "false")


class _Reads:
    """A GitHub client whose one pull request read answers `pull` or raises `error`."""

    def __init__(self, pull: PullRequest | None = None, error: Exception | None = None) -> None:
        self._pull = pull
        self._error = error

    def get_pull(self, repo: str, number: int) -> PullRequest:
        if self._error is not None:
            raise self._error
        assert self._pull is not None
        return self._pull


def _reads(pull: PullRequest | None = None, error: Exception | None = None) -> object:
    return lambda: _Reads(pull, error)


def _pull(sha: str, *, merged: bool = True) -> PullRequest:
    return PullRequest(
        title="the pull request",
        head=CommitRef(sha=sha, ref="main"),
        base=CommitRef(sha="", ref="main"),
        merged=merged,
        merge_commit_sha=sha,
    )


@pytest.fixture
def pr_repo(tmp_path: Path) -> tuple[Path, str]:
    """A clone that lacks the merge commit, and the merge commit on `origin/main` of another
    clone: the read fetches the commit, as the stage job does."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "-q", "-b", "main", str(origin))
    reader = tmp_path / "reader"
    _git(tmp_path, "clone", "-q", str(origin), str(reader))
    _configure(reader)
    (reader / "src").mkdir()
    (reader / "src" / "a.py").write_text("one\n", encoding="utf-8")
    _git(reader, "add", "-A")
    _git(reader, "commit", "-q", "-m", "one")
    _git(reader, "push", "-q", "origin", "main")
    writer = tmp_path / "writer"
    _git(tmp_path, "clone", "-q", str(origin), str(writer))
    _configure(writer)
    (writer / "src" / "a.py").write_text("one\ntwo\n", encoding="utf-8")
    (writer / "src" / "b.py").write_text("b\n", encoding="utf-8")
    _git(writer, "add", "-A")
    _git(writer, "commit", "-q", "-m", "the merge of the pull request")
    _git(writer, "push", "-q", "origin", "main")
    return reader, _git(writer, "rev-parse", "HEAD")


def test_only_the_phrase_pull_request_names_a_pull_request() -> None:
    texts = [
        "The plan of #3372 in pull request #3378 chose a literal.",
        "See PR #3410 and #3435 and issue #1.",
        "pr #9 names the same pull request.",
        "pull request #3378 again",
    ]

    assert named_pull_requests(texts) == [3378, 3410, 9]
    assert named_pull_requests(["a bare #3378 and no phrase"]) == []


def test_the_changed_files_of_a_named_pull_request_are_read_at_its_merge_commit(
    pr_repo: tuple[Path, str],
) -> None:
    reader, sha = pr_repo

    found = pull_request_files(reader, "o/r", [7], _reads(_pull(sha)), operation="test")

    assert found == {7: PullRequestFiles(7, sha, {"src/a.py": "one\ntwo", "src/b.py": "b"})}


def test_an_unmerged_pull_request_gives_no_entry(pr_repo: tuple[Path, str]) -> None:
    reader, sha = pr_repo

    found = pull_request_files(
        reader, "o/r", [7], _reads(_pull(sha, merged=False)), operation="test"
    )

    assert found == {}


def test_a_pull_request_that_cannot_be_read_gives_no_entry(pr_repo: tuple[Path, str]) -> None:
    reader, _ = pr_repo

    found = pull_request_files(
        reader, "o/r", [7], _reads(error=GitHubNotFoundError("no")), operation="test"
    )

    assert found == {}


def test_a_pull_request_that_the_clone_cannot_fetch_gives_no_entry(tmp_path: Path) -> None:
    root = tmp_path / "alone"
    _git(tmp_path, "init", "-q", "-b", "main", str(root))
    _configure(root)

    found = pull_request_files(root, "o/r", [7], _reads(_pull("0" * 40)), operation="test")

    assert found == {}


def test_a_named_pull_request_reads_at_most_the_maximum_number_of_files(
    tmp_path: Path,
) -> None:
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "-q", "-b", "main", str(origin))
    writer = tmp_path / "writer"
    _git(tmp_path, "clone", "-q", str(origin), str(writer))
    _configure(writer)
    (writer / "README.md").write_text("start\n", encoding="utf-8")
    _git(writer, "add", "-A")
    _git(writer, "commit", "-q", "-m", "start")
    names = [f"src/f{index}.py" for index in range(CONST_ROADMAP_STAGE_VERIFY_MAX_FILES + 5)]
    (writer / "src").mkdir()
    for name in names:
        (writer / name).write_text("x = 1\n", encoding="utf-8")
    (writer / "openspec" / "changes").mkdir(parents=True)
    (writer / "openspec" / "changes" / "plan.md").write_text("the plan\n", encoding="utf-8")
    _git(writer, "add", "-A")
    _git(writer, "commit", "-q", "-m", "many files")
    _git(writer, "push", "-q", "origin", "main")
    sha = _git(writer, "rev-parse", "HEAD")

    found = pull_request_files(writer, "o/r", [7], _reads(_pull(sha)), operation="test")

    kept = found[7].files
    assert len(kept) == CONST_ROADMAP_STAGE_VERIFY_MAX_FILES
    assert next(iter(kept)) == "openspec/changes/plan.md"
