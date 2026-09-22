"""Test suite for in-memory evaluation of git ignore rules."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from devops_cli.core.gitignore import GitignoreIndex, get_index, reset_indexes


@pytest.fixture(autouse=True)
def clear_indexes() -> None:
    """Evaluators are cached per repository root; tests must not share them."""
    reset_indexes()


def make_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a real git repository with the given files."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


def git_says_ignored(repo: Path, relative: str) -> bool:
    """Ask git itself whether a path is ignored."""
    result = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "-q", "--", relative],
        capture_output=True,
    )
    return result.returncode == 0


def assert_matches_git(repo: Path, relative: str, is_dir: bool | None = None) -> None:
    """Assert the in-memory verdict equals git's own."""
    index = GitignoreIndex(repo_root=repo)
    ours = index.is_ignored(repo / relative, is_dir=is_dir)
    theirs = git_says_ignored(repo, relative)
    assert ours == theirs, f"{relative}: ours={ours} git={theirs}"


# =============================================================================
# Agreement With Git
# =============================================================================


def test_a_root_pattern_is_honoured(tmp_path: Path) -> None:
    """The case the previous implementation already handled."""
    repo = make_repo(tmp_path, {".gitignore": "*.log\n", "app.log": "", "app.py": ""})
    assert_matches_git(repo, "app.log", is_dir=False)
    assert_matches_git(repo, "app.py", is_dir=False)


def test_a_nested_gitignore_is_honoured(tmp_path: Path) -> None:
    """Git consults a .gitignore in every directory between the root and the file.

    Reading only the root file meant a nested rule was invisible to the in-memory path and
    could be resolved only by spawning git.
    """
    repo = make_repo(
        tmp_path,
        {
            ".gitignore": "",
            "pkg/.gitignore": "secret.txt\n",
            "pkg/secret.txt": "",
            "pkg/ok.txt": "",
        },
    )
    assert_matches_git(repo, "pkg/secret.txt", is_dir=False)
    assert_matches_git(repo, "pkg/ok.txt", is_dir=False)


def test_a_deeper_gitignore_overrides_a_shallower_one(tmp_path: Path) -> None:
    """Precedence runs root-downwards; the deepest matching rule decides."""
    repo = make_repo(
        tmp_path,
        {
            ".gitignore": "*.txt\n",
            "pkg/.gitignore": "!keep.txt\n",
            "pkg/keep.txt": "",
            "pkg/drop.txt": "",
        },
    )
    assert_matches_git(repo, "pkg/keep.txt", is_dir=False)
    assert_matches_git(repo, "pkg/drop.txt", is_dir=False)


def test_negation_re_includes_a_file(tmp_path: Path) -> None:
    """A later `!` pattern overrides an earlier exclusion."""
    repo = make_repo(
        tmp_path, {".gitignore": "*.log\n!keep.log\n", "keep.log": "", "other.log": ""}
    )
    assert_matches_git(repo, "keep.log", is_dir=False)
    assert_matches_git(repo, "other.log", is_dir=False)


def test_a_directory_only_pattern_does_not_match_a_file(tmp_path: Path) -> None:
    """`build/` names a directory; a file called `build` is not ignored."""
    repo = make_repo(tmp_path, {".gitignore": "build/\n", "build": ""})
    assert_matches_git(repo, "build", is_dir=False)


def test_a_directory_only_pattern_matches_a_directory(tmp_path: Path) -> None:
    """The same pattern does match when the path is a directory."""
    repo = make_repo(tmp_path, {".gitignore": "build/\n", "build/out.txt": ""})
    assert_matches_git(repo, "build", is_dir=True)


def test_a_file_inside_an_ignored_directory_is_ignored(tmp_path: Path) -> None:
    """Everything under an excluded directory is excluded."""
    repo = make_repo(tmp_path, {".gitignore": "build/\n", "build/out.txt": ""})
    assert_matches_git(repo, "build/out.txt", is_dir=False)


def test_a_negation_inside_an_ignored_directory_cannot_re_include(tmp_path: Path) -> None:
    """Git does not descend into an excluded directory, so the rule never takes effect.

    Evaluating the file's own rules without checking its ancestors would wrongly report it
    as tracked.
    """
    repo = make_repo(
        tmp_path,
        {".gitignore": "build/\n", "build/.gitignore": "!keep.txt\n", "build/keep.txt": ""},
    )
    assert_matches_git(repo, "build/keep.txt", is_dir=False)


def test_an_anchored_pattern_matches_only_at_its_own_level(tmp_path: Path) -> None:
    """A leading slash anchors a pattern to the directory of its .gitignore."""
    repo = make_repo(tmp_path, {".gitignore": "/root.txt\n", "root.txt": "", "pkg/root.txt": ""})
    assert_matches_git(repo, "root.txt", is_dir=False)
    assert_matches_git(repo, "pkg/root.txt", is_dir=False)


def test_an_unanchored_pattern_matches_at_any_depth(tmp_path: Path) -> None:
    """A bare name matches in any directory beneath the ignore file."""
    repo = make_repo(tmp_path, {".gitignore": "notes.txt\n", "notes.txt": "", "a/b/notes.txt": ""})
    assert_matches_git(repo, "notes.txt", is_dir=False)
    assert_matches_git(repo, "a/b/notes.txt", is_dir=False)


def test_a_double_star_pattern_spans_directories(tmp_path: Path) -> None:
    """`**` crosses separators where `*` does not."""
    repo = make_repo(tmp_path, {".gitignore": "a/**/target.txt\n", "a/b/c/target.txt": ""})
    assert_matches_git(repo, "a/b/c/target.txt", is_dir=False)


def test_the_repository_local_exclude_file_is_honoured(tmp_path: Path) -> None:
    """`.git/info/exclude` ignores paths without committing a rule."""
    repo = make_repo(tmp_path, {"scratch.tmp": ""})
    exclude = repo / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text("*.tmp\n", encoding="utf-8")
    assert_matches_git(repo, "scratch.tmp", is_dir=False)


def test_a_committed_rule_can_override_the_local_exclude(tmp_path: Path) -> None:
    """`.gitignore` is applied after `.git/info/exclude`, so it wins."""
    repo = make_repo(tmp_path, {".gitignore": "!scratch.tmp\n", "scratch.tmp": ""})
    exclude = repo / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text("*.tmp\n", encoding="utf-8")
    assert_matches_git(repo, "scratch.tmp", is_dir=False)


# =============================================================================
# Boundaries
# =============================================================================


def test_a_path_outside_the_repository_is_not_ignored(tmp_path: Path) -> None:
    """Ignore rules describe a repository; nothing outside it is in scope."""
    repo = make_repo(tmp_path / "repo", {".gitignore": "*.log\n"})
    outside = tmp_path / "elsewhere.log"
    outside.write_text("", encoding="utf-8")
    assert GitignoreIndex(repo_root=repo).is_ignored(outside, is_dir=False) is False


def test_the_repository_root_itself_is_not_ignored(tmp_path: Path) -> None:
    """A root that ignored itself would exclude the entire tree."""
    repo = make_repo(tmp_path, {".gitignore": "*\n"})
    assert GitignoreIndex(repo_root=repo).is_ignored(repo, is_dir=True) is False


def test_a_repository_with_no_ignore_files_ignores_nothing(tmp_path: Path) -> None:
    """The absence of rules is not an error."""
    repo = make_repo(tmp_path, {"app.py": ""})
    assert GitignoreIndex(repo_root=repo).is_ignored(repo / "app.py", is_dir=False) is False


def test_a_malformed_ignore_file_does_not_break_evaluation(tmp_path: Path) -> None:
    """One bad pattern must not make a whole directory unevaluable."""
    repo = make_repo(tmp_path, {".gitignore": "[unclosed\n*.log\n", "a.log": "", "a.py": ""})
    index = GitignoreIndex(repo_root=repo)
    assert index.is_ignored(repo / "a.py", is_dir=False) is False


def test_a_relative_path_is_resolved_against_the_repository_root(tmp_path: Path) -> None:
    """Callers pass both absolute and repository-relative paths."""
    repo = make_repo(tmp_path, {".gitignore": "*.log\n", "a.log": ""})
    assert GitignoreIndex(repo_root=repo).is_ignored(Path("a.log"), is_dir=False) is True


# =============================================================================
# Caching
# =============================================================================


def test_an_edited_ignore_file_takes_effect(tmp_path: Path) -> None:
    """A compiled spec is revalidated, so an edit is picked up.

    A cache that never expired would leave a long-running process applying the rules that
    were in force when it started.
    """
    repo = make_repo(tmp_path, {".gitignore": "*.log\n", "a.log": "", "a.tmp": ""})
    index = GitignoreIndex(repo_root=repo, revalidate_after=0.0)
    assert index.is_ignored(repo / "a.tmp", is_dir=False) is False

    (repo / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
    assert index.is_ignored(repo / "a.tmp", is_dir=False) is True


def test_invalidating_forces_a_reload(tmp_path: Path) -> None:
    """An explicit reset is available for callers that know the rules changed."""
    repo = make_repo(tmp_path, {".gitignore": "*.log\n", "a.tmp": ""})
    index = GitignoreIndex(repo_root=repo, revalidate_after=3600.0)
    assert index.is_ignored(repo / "a.tmp", is_dir=False) is False

    (repo / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
    index.invalidate()
    assert index.is_ignored(repo / "a.tmp", is_dir=False) is True


def test_the_index_is_reused_per_repository_root(tmp_path: Path) -> None:
    """Recompiling per call is what made the previous implementation slow."""
    repo = make_repo(tmp_path, {".gitignore": "*.log\n"})
    assert get_index(repo) is get_index(repo)


def test_evaluation_does_not_spawn_git(tmp_path: Path) -> None:
    """The whole point: a miss used to cost a process spawn, and a miss is the common case.

    Most files in a repository are not ignored, so the slow path ran per file.
    """
    from unittest.mock import patch

    repo = make_repo(tmp_path, {".gitignore": "*.log\n", "app.py": ""})
    index = GitignoreIndex(repo_root=repo)
    with patch("subprocess.run") as spawn:
        index.is_ignored(repo / "app.py", is_dir=False)
    spawn.assert_not_called()
