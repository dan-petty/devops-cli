"""Test suite for the content-addressed CI cache fingerprint."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from devops_cli.ci.cache import (
    _worktree_divergent_paths,
    compute_workspace_fingerprint,
)
from devops_cli.core.gitignore import get_index, reset_indexes
from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall


def _git_blob_sha(content: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(content)).encode() + b"\0" + content,
        usedforsecurity=False,
    ).hexdigest()


class _FingerprintGitRepo:
    def __init__(self, root: Path, git_fake: GitFake) -> None:
        self.root = root
        self.git_fake = git_fake
        self.head_sha = "1111111111111111111111111111111111111111"
        self.index: dict[str, str] = {}
        self.staged_replaces: dict[str, str] = {}
        self._setup_answers()

    def _setup_answers(self) -> None:
        self.git_fake.answer(
            lambda call: bool(
                call.argv and call.argv[0:2] == ("git", "rev-parse") and "HEAD" in call.argv
            ),
            lambda _call: ProcessAnswer(returncode=0, stdout=f"{self.head_sha}\n"),
        )
        self.git_fake.answer(
            lambda call: bool(call.argv and "ls-files" in call.argv and "-s" in call.argv),
            self._ls_files_answer,
        )
        self.git_fake.answer(
            lambda call: bool(
                call.argv and "status" in call.argv and "--porcelain=v1" in call.argv
            ),
            self._status_answer,
        )
        self.git_fake.answer(
            lambda call: bool(call.argv and "hash-object" in call.argv),
            self._hash_object_answer,
        )

    def _ls_files_answer(self, _call: ProcessCall) -> ProcessAnswer:
        lines = [f"100644 {sha} 0\t{path}" for path, sha in sorted(self.index.items())]
        return ProcessAnswer(returncode=0, stdout="\n".join(lines) + ("\n" if lines else ""))

    def _tracked_status(self) -> list[str]:
        lines: list[str] = [f"R  {old} -> {new}" for old, new in self.staged_replaces.items()]
        for path in sorted(self.index):
            if path in self.staged_replaces:
                continue
            target = self.root / path
            if not target.exists():
                lines.append(f" D {path}")
            elif _git_blob_sha(target.read_bytes()) != self.index[path]:
                lines.append(f" M {path}")
        return lines

    def _untracked_status(self) -> list[str]:
        lines: list[str] = []
        for p in sorted(self.root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(self.root).as_posix()
            if rel.startswith(".git") or rel in self.index or rel in self.staged_replaces.values():
                continue
            if not get_index(self.root).is_ignored(p):
                lines.append(f"?? {rel}")
        return lines

    def _status_answer(self, _call: ProcessCall) -> ProcessAnswer:
        lines = self._tracked_status() + self._untracked_status()
        return ProcessAnswer(returncode=0, stdout="\n".join(lines) + ("\n" if lines else ""))

    def _hash_object_answer(self, call: ProcessCall) -> ProcessAnswer:
        hashes: list[str] = []
        if call.stdin and isinstance(call.stdin, str):
            for path_str in call.stdin.splitlines():
                if path_str:
                    target = self.root / path_str
                    if target.is_file():
                        hashes.append(_git_blob_sha(target.read_bytes()))
                    else:
                        hashes.append("0000000000000000000000000000000000000000")
        return ProcessAnswer(returncode=0, stdout="\n".join(hashes) + ("\n" if hashes else ""))

    def git_add(self, *args: str) -> None:
        reset_indexes()
        for old, new in list(self.staged_replaces.items()):
            sha = self.index.pop(old, None)
            if (self.root / new).is_file():
                self.index[new] = _git_blob_sha((self.root / new).read_bytes())
            elif sha:
                self.index[new] = sha
        self.staged_replaces.clear()

        for p in sorted(self.root.rglob("*")):
            if p.is_file():
                rel = p.relative_to(self.root).as_posix()
                if rel.startswith(".git"):
                    continue
                if not get_index(self.root).is_ignored(p):
                    self.index[rel] = _git_blob_sha(p.read_bytes())
        for rel in list(self.index):
            if not (self.root / rel).is_file():
                del self.index[rel]

    def git_commit(self, *args: str) -> None:
        if any("-a" in arg for arg in args):
            self.git_add()
        self.staged_replaces.clear()
        self.head_sha = hashlib.sha1(
            (self.head_sha + "commit").encode(), usedforsecurity=False
        ).hexdigest()

    def git_mv(self, src: str, dst: str) -> None:
        source = self.root / src
        target = self.root / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file():
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            source.unlink()
        sha = self.index.pop(src, None)
        if target.is_file():
            self.index[dst] = _git_blob_sha(target.read_bytes())
        elif sha:
            self.index[dst] = sha
        self.staged_replaces[src] = dst


_REPOS: dict[Path, _FingerprintGitRepo] = {}


@pytest.fixture
def repo(tmp_path: Path, git_fake: GitFake) -> Path:
    """Create a git repository fixture with one committed file."""
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("value = 1\n", encoding="utf-8")

    sim = _FingerprintGitRepo(tmp_path, git_fake)
    sim.git_add()
    _REPOS[tmp_path.resolve()] = sim
    return tmp_path


def fingerprint(repo: Path) -> str:
    """Compute the workspace fingerprint, failing loudly if it cannot be produced."""
    result = compute_workspace_fingerprint(root=repo)
    assert result is not None
    return result[0]


def git(repo: Path, *args: str) -> None:
    """Run simulated git commands for repository manipulation."""
    sim = _REPOS.get(repo.resolve())
    if not sim or not args:
        return
    cmd = args[0]
    if cmd == "add":
        sim.git_add(*args[1:])
    elif cmd == "commit":
        sim.git_commit(*args[1:])
    elif cmd == "mv":
        sim.git_mv(args[1], args[2])


# =============================================================================
# Invariance
# =============================================================================


def test_staging_a_change_does_not_change_the_fingerprint(repo: Path) -> None:
    """`git add` moves content between the worktree and the index without altering it.

    The fingerprint previously hashed the staged and unstaged diffs separately, so staging
    invalidated a verified run even though nothing the checks read had changed.
    """
    (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
    before = fingerprint(repo)
    git(repo, "add", "-A")
    assert fingerprint(repo) == before


def test_committing_does_not_change_the_fingerprint(repo: Path) -> None:
    """This is the defect that made the cache useless in practice.

    A commit often comes between two runs of `devops ci`, and the fingerprint included
    HEAD -- so the second run could never hit the cache and ran the entire suite again
    (#375).
    """
    (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    before = fingerprint(repo)
    git(repo, "commit", "-qm", "change")
    assert fingerprint(repo) == before


def test_a_verified_tree_survives_the_whole_commit_and_push_sequence(repo: Path) -> None:
    """The sequence a developer actually performs, end to end."""
    (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
    after_ci = fingerprint(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "change")
    assert fingerprint(repo) == after_ci


def test_an_amended_commit_preserves_the_fingerprint(repo: Path) -> None:
    """Amending rewrites history without changing what the checks read."""
    (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "change")
    before = fingerprint(repo)
    git(repo, "commit", "-q", "--amend", "-m", "reworded")
    assert fingerprint(repo) == before


# =============================================================================
# Sensitivity
# =============================================================================


def test_editing_a_tracked_file_changes_the_fingerprint(repo: Path) -> None:
    """Invariance is only safe if real changes still invalidate."""
    before = fingerprint(repo)
    (repo / "app.py").write_text("value = 99\n", encoding="utf-8")
    assert fingerprint(repo) != before


def test_an_untracked_file_changes_the_fingerprint(repo: Path) -> None:
    """A new file is code the checks will read."""
    before = fingerprint(repo)
    (repo / "extra.py").write_text("value = 1\n", encoding="utf-8")
    assert fingerprint(repo) != before


def test_deleting_a_file_changes_the_fingerprint(repo: Path) -> None:
    """Removal changes what the checks read just as much as addition."""
    before = fingerprint(repo)
    (repo / "app.py").unlink()
    assert fingerprint(repo) != before


def test_reverting_a_change_restores_the_fingerprint(repo: Path) -> None:
    """Content addressing means the fingerprint follows content, not history.

    Undoing an edit returns the tree to a state that was already verified.
    """
    before = fingerprint(repo)
    (repo / "scratch.py").write_text("value = 1\n", encoding="utf-8")
    assert fingerprint(repo) != before
    (repo / "scratch.py").unlink()
    assert fingerprint(repo) == before


def test_options_are_part_of_the_fingerprint(repo: Path) -> None:
    """A run with different options verified something different."""
    first = compute_workspace_fingerprint(root=repo, options={"fast": True})
    second = compute_workspace_fingerprint(root=repo, options={"fast": False})
    assert first is not None
    assert second is not None
    assert first[0] != second[0]


def test_an_ignored_file_does_not_change_the_fingerprint(repo: Path) -> None:
    """Build output and caches are not inputs to any check.

    Counting them would invalidate a verified tree every time a tool wrote a log.
    """
    (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "ignore logs")
    before = fingerprint(repo)
    (repo / "run.log").write_text("noise\n", encoding="utf-8")
    assert fingerprint(repo) == before


# =============================================================================
# Status Parsing
# =============================================================================


def test_a_worktree_modification_is_detected(repo: Path) -> None:
    """Porcelain reports an unmodified index as a leading space.

    Stripping that space shifts every column by one, so a file modified in the working tree
    reads as one modified in the index -- inverting the distinction entirely.
    """
    (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
    changed, deleted = _worktree_divergent_paths(repo)
    assert ("app.py" in changed, deleted) == (True, [])


def test_an_untracked_file_is_detected(repo: Path) -> None:
    """Untracked files are inputs too."""
    (repo / "new.py").write_text("value = 1\n", encoding="utf-8")
    changed, _ = _worktree_divergent_paths(repo)
    assert "new.py" in changed


def test_a_deleted_file_is_detected(repo: Path) -> None:
    """A removal must drop the path rather than hash a file that is gone."""
    (repo / "app.py").unlink()
    _, deleted = _worktree_divergent_paths(repo)
    assert "app.py" in deleted


def test_a_rename_changes_the_fingerprint(repo: Path) -> None:
    """A rename changes which paths the checks read, even though no content differs.

    `git mv` stages the move, so the index already carries the new path and nothing needs
    re-hashing -- the fingerprint changes because it is computed over paths and contents
    together.
    """
    before = fingerprint(repo)
    git(repo, "mv", "app.py", "renamed.py")
    assert fingerprint(repo) != before


def test_an_unstaged_rename_reports_the_new_path(repo: Path) -> None:
    """Moving a file without staging leaves a deletion and an untracked path."""
    (repo / "renamed.py").write_text(
        (repo / "app.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (repo / "app.py").unlink()
    changed, deleted = _worktree_divergent_paths(repo)
    assert ("renamed.py" in changed, "app.py" in deleted) == (True, True)


def test_a_clean_repository_reports_nothing_divergent(repo: Path) -> None:
    """A freshly committed tree has no divergence to hash."""
    assert _worktree_divergent_paths(repo) == ([], [])
