"""Tests for Git operation helpers."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import git as gitlib
import pytest

from devops_cli.exceptions import (
    BranchAlreadyExistsError,
    GitOperationError,
    InvalidBranchNameError,
)
from devops_cli.git.operations import (
    _ensure_known_host,
    _normalize_clone_url,
    clone_repo,
    commit_snapshot,
    create_branch,
    delete_merged_branches,
    fetch_all,
    iter_workspace_repos,
    list_branches,
    list_changed_files,
    pull_tracking,
    read_file_at_revision,
    resolve_merge_base,
)
from devops_cli.models.git import ChangedFile


def test_normalize_clone_url() -> None:
    """Verify clone URL normalization logic."""
    assert _normalize_clone_url("git@github.com:org/repo.git") == "git@github.com:org/repo.git"
    assert (
        _normalize_clone_url("ssh://git@github.com/org/repo.git")
        == "ssh://git@github.com/org/repo.git"
    )
    assert _normalize_clone_url("github.com/org/repo.git") == "https://github.com/org/repo.git"
    assert (
        _normalize_clone_url("http://github.com/org/repo.git") == "https://github.com/org/repo.git"
    )
    assert (
        _normalize_clone_url("https://github.com/org/repo.git") == "https://github.com/org/repo.git"
    )
    assert (
        _normalize_clone_url("https://gitlab.com/org/repo.git") == "https://gitlab.com/org/repo.git"
    )


def test_iter_workspace_repos(tmp_path: Path) -> None:
    """Verify iter_workspace_repos traverses two directory levels and discovers .git repos."""
    # Non-existent root
    assert list(iter_workspace_repos(tmp_path / "nonexistent")) == []

    # Valid root with group and repo directories
    group_a = tmp_path / "group_a"
    group_a.mkdir()
    repo_1 = group_a / "repo_1"
    repo_1.mkdir()
    (repo_1 / ".git").mkdir()

    repo_2 = group_a / "repo_2"
    repo_2.mkdir()  # No .git

    # Plain file in root should be skipped
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")

    discovered = list(iter_workspace_repos(tmp_path))
    assert discovered == [repo_1]


def test_ensure_known_host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _ensure_known_host writes GitHub's pinned lines and sets permissions."""
    from devops_cli.config.constants import CONST_GITHUB_KNOWN_HOSTS_LINES

    _ensure_known_host.cache_clear()
    fake_home = tmp_path / "home"
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

    known_hosts = fake_home / ".ssh" / "known_hosts"
    _ensure_known_host()

    content = known_hosts.read_text(encoding="utf-8")
    for line in CONST_GITHUB_KNOWN_HOSTS_LINES:
        assert line in content
    assert (
        oct(known_hosts.stat().st_mode & 0o777),
        oct(known_hosts.parent.stat().st_mode & 0o777),
    ) == ("0o600", "0o700")

    # A second run adds nothing
    _ensure_known_host.cache_clear()
    _ensure_known_host()
    assert known_hosts.read_text(encoding="utf-8") == content


def test_clone_repo_ensures_github_known_host_for_all_urls(tmp_path: Path) -> None:
    """Verify clone_repo ensures host keys are known for all clone URLs."""
    with (
        patch("devops_cli.git.operations._ensure_known_host") as mock_known_host,
        patch("devops_cli.git.operations.gitlib.Repo.clone_from") as mock_clone_from,
    ):
        clone_repo("git@github.com:example/repo.git", tmp_path / "repo")
        clone_repo("https://github.com/example/repo2.git", tmp_path / "repo2")

    assert (mock_known_host.call_count, mock_clone_from.call_count) == (2, 2)


def test_fetch_all(tmp_path: Path) -> None:
    """Verify fetch_all calls remote.fetch on all remotes."""
    with patch("devops_cli.git.operations.gitlib.Repo") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_remote = MagicMock()
        mock_repo.remotes = [mock_remote]
        mock_repo_cls.return_value = mock_repo

        fetch_all(tmp_path)
        mock_remote.fetch.assert_called_once_with(prune=True)

        # Exception handling
        mock_remote.fetch.side_effect = gitlib.GitCommandError("fetch", "network error")
        fetch_all(tmp_path)


def test_pull_tracking(tmp_path: Path) -> None:
    """Verify pull_tracking pulls tracking branch when configured."""
    with patch("devops_cli.git.operations.gitlib.Repo") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.head.is_detached = False
        mock_tracking = MagicMock(remote_name="origin")
        mock_branch = MagicMock()
        mock_branch.name = "main"
        mock_branch.tracking_branch.return_value = mock_tracking
        mock_repo.active_branch = mock_branch
        mock_remote = MagicMock()
        mock_repo.remotes = {"origin": mock_remote}
        mock_repo_cls.return_value = mock_repo

        pull_tracking(tmp_path)
        mock_remote.pull.assert_called_once_with("main")


def _init_repo(git: Callable[..., None], repo: Path) -> None:
    git(repo, "init", "--quiet", "-b", "main")
    git(repo, "commit", "--quiet", "--allow-empty", "-m", "init")


def _current_branch(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_create_branch(tmp_path: Path, git: Callable[..., None]) -> None:
    """create_branch creates the branch from HEAD and checks it out; bad or taken names raise."""
    # The hyphen guard runs before the repository is opened.
    with pytest.raises(InvalidBranchNameError, match="cannot start with a hyphen"):
        create_branch(tmp_path, "-invalid")

    _init_repo(git, tmp_path)
    with pytest.raises(BranchAlreadyExistsError, match="already exists"):
        create_branch(tmp_path, "main")

    create_branch(tmp_path, "feat/test")
    assert _current_branch(tmp_path) == "feat/test"


def test_create_branch_raises_gits_reason_when_git_refuses(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """A branch git refuses raises GitOperationError with git's own reason."""
    _init_repo(git, tmp_path)
    git(tmp_path, "branch", "feature")

    with pytest.raises(GitOperationError, match="'refs/heads/feature' exists") as raised:
        create_branch(tmp_path, "feature/x")

    assert (raised.value.details["operation"], raised.value.details["branch_name"]) == (
        "branch_create",
        "feature/x",
    )


def test_list_branches(tmp_path: Path) -> None:
    """Verify list_branches returns local and remote branch listings."""
    with patch("devops_cli.git.operations.gitlib.Repo") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.head.is_detached = False
        mock_repo.active_branch.name = "main"
        mock_b1 = MagicMock()
        mock_b1.name = "main"
        mock_b2 = MagicMock()
        mock_b2.name = "feat/xyz"
        mock_repo.branches = [mock_b1, mock_b2]

        mock_remote = MagicMock()
        mock_ref1 = MagicMock()
        mock_ref1.name = "origin/feat/remote"
        mock_ref_head = MagicMock()
        mock_ref_head.name = "origin/HEAD"
        mock_remote.refs = [mock_ref1, mock_ref_head]
        mock_repo.remotes = [mock_remote]
        mock_repo_cls.return_value = mock_repo

        # Local only
        listing_local = list_branches(tmp_path, all_branches=False)
        assert listing_local.current == "main"
        assert listing_local.branches == ["feat/xyz", "main"]

        # All branches
        listing_all = list_branches(tmp_path, all_branches=True)
        assert "origin/feat/remote" in listing_all.branches
        assert "origin/HEAD" not in listing_all.branches


def test_delete_merged_branches(tmp_path: Path) -> None:
    """Verify delete_merged_branches identifies and removes non-protected merged branches."""
    with patch("devops_cli.git.operations.gitlib.Repo") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_main = MagicMock()
        mock_main.name = "main"
        mock_feat = MagicMock()
        mock_feat.name = "feat/merged"
        mock_repo.branches = [mock_main, mock_feat]
        mock_repo.git.branch.return_value = "  main\n* feat/merged\n"
        mock_repo_cls.return_value = mock_repo

        # Dry run
        deleted_dry = delete_merged_branches(tmp_path, dry_run=True)
        assert deleted_dry == ["feat/merged"]
        mock_repo.delete_head.assert_not_called()

        # Actual run
        deleted_act = delete_merged_branches(tmp_path, dry_run=False)
        assert deleted_act == ["feat/merged"]
        mock_repo.delete_head.assert_called_once_with(mock_feat, force=False)


def test_is_git_clean_and_get_latest_tag(tmp_path: Path) -> None:
    """Verify is_git_clean and get_latest_git_tag."""
    from devops_cli.git.operations import get_latest_git_tag, is_git_clean

    mock_clean = MagicMock(returncode=0, stdout="")
    with patch("devops_cli.git.operations.run_subprocess", return_value=mock_clean):
        assert is_git_clean(tmp_path) is True

    mock_dirty = MagicMock(returncode=0, stdout=" M file.py\n")
    with patch("devops_cli.git.operations.run_subprocess", return_value=mock_dirty):
        assert is_git_clean(tmp_path) is False

    # Exception in is_git_clean
    with patch("devops_cli.git.operations.run_subprocess", side_effect=Exception("git error")):
        assert is_git_clean(tmp_path) is False

    mock_tag = MagicMock(returncode=0, stdout="v0.2.1\n")
    with patch("devops_cli.git.operations.run_subprocess", return_value=mock_tag):
        assert get_latest_git_tag(tmp_path) == "v0.2.1"

    mock_no_tag = MagicMock(returncode=128, stdout="")
    with patch("devops_cli.git.operations.run_subprocess", return_value=mock_no_tag):
        assert get_latest_git_tag(tmp_path) is None

    # Exception in get_latest_git_tag
    with patch("devops_cli.git.operations.run_subprocess", side_effect=Exception("git error")):
        assert get_latest_git_tag(tmp_path) is None


def test_git_operations_edge_cases(tmp_path: Path) -> None:
    """Verify pull_tracking error handling, delete_merged_branches empty branches, and keyscan failure."""
    # 1. pull_tracking handles GitCommandError and IndexError
    with patch("devops_cli.git.operations.gitlib.Repo") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.head.is_detached = False
        mock_branch = MagicMock()
        mock_tracking = MagicMock()
        mock_tracking.remote_name = "origin"
        mock_branch.tracking_branch.return_value = mock_tracking
        mock_branch.name = "main"
        mock_repo.active_branch = mock_branch
        mock_remote = MagicMock()
        mock_remote.pull.side_effect = gitlib.GitCommandError("pull", "network down")
        mock_repo.remotes = {"origin": mock_remote}
        mock_repo_cls.return_value = mock_repo

        pull_tracking(tmp_path)

    # 2. delete_merged_branches with no default branch
    with patch("devops_cli.git.operations.gitlib.Repo") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.branches = []
        mock_repo_cls.return_value = mock_repo
        assert delete_merged_branches(tmp_path) == []


def test_validate_clone_dest_and_prepare_clone_url(tmp_path: Path) -> None:
    """Verify _validate_clone_dest traversal checks and _prepare_clone_url host key seeding."""
    from devops_cli.exceptions import GitOperationError
    from devops_cli.git.operations import _prepare_clone_url, _validate_clone_dest

    # Path traversal rejection
    with pytest.raises(GitOperationError, match="Path traversal detected"):
        _validate_clone_dest(Path("../unsafe_path"))

    with pytest.raises(GitOperationError, match="Path traversal detected"):
        _validate_clone_dest(Path("foo/../bar"))

    # Safe destination passes
    _validate_clone_dest(tmp_path / "safe_dest")
    _validate_clone_dest(tmp_path / "safe_dest_2")

    # Symlink rejection
    real_dest = tmp_path / "real_dir"
    real_dest.mkdir()
    symlink_dest = tmp_path / "symlink_dir"
    symlink_dest.symlink_to(real_dest)
    with pytest.raises(GitOperationError, match="must not be a symlink"):
        _validate_clone_dest(symlink_dest)

    # Forbidden system path
    with pytest.raises(GitOperationError, match="forbidden system path"):
        _validate_clone_dest(Path("/etc/git-dest"))

    # _prepare_clone_url calls _ensure_known_host for both SSH and HTTPS
    with patch("devops_cli.git.operations._ensure_known_host") as mock_ensure:
        url_ssh = _prepare_clone_url("git@github.com:org/repo.git")
        assert (url_ssh, mock_ensure.call_count) == ("git@github.com:org/repo.git", 1)

    with patch("devops_cli.git.operations._ensure_known_host") as mock_ensure:
        url_https = _prepare_clone_url("https://github.com/org/repo.git")
        assert (url_https, mock_ensure.call_count) == ("https://github.com/org/repo.git", 1)


def test_read_file_at_revision_reads_the_base_revision(symbol_removal_repo: Path) -> None:
    """The file is read at the base revision, not taken for a pathspec (#787)."""
    content = read_file_at_revision(symbol_removal_repo, "main", "mod.py")

    assert content == "def kept(): pass\ndef gone(): pass\n"


def test_read_file_at_revision_reads_no_directory(tmp_path: Path, git: Callable[..., None]) -> None:
    """A directory at the revision is not a file. `git show` printed its listing, which a
    branch review reading its conventions at the merge base took for `.cursor/rules` (#946)."""
    git(tmp_path, "init", "--quiet", "-b", "main")
    (tmp_path / ".cursor" / "rules").mkdir(parents=True)
    (tmp_path / ".cursor" / "rules" / "style.mdc").write_text("Rule.\n", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "--quiet", "-m", "rules")

    assert (
        read_file_at_revision(tmp_path, "main", ".cursor/rules"),
        read_file_at_revision(tmp_path, "main", ".cursor/rules/style.mdc"),
    ) == (None, "Rule.\n")


def test_read_file_at_revision_reads_no_link(tmp_path: Path, git: Callable[..., None]) -> None:
    """A committed link is no file at the revision. Its blob is the path it points to, which a
    branch review took for the `.devops/review.md` a project linked to its rules (#946)."""
    git(tmp_path, "init", "--quiet", "-b", "main")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "rules.md").write_text("Rules.\n", encoding="utf-8")
    (tmp_path / ".devops").mkdir()
    (tmp_path / ".devops" / "review.md").symlink_to("../docs/rules.md")
    (tmp_path / "linked").symlink_to("docs", target_is_directory=True)
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "--quiet", "-m", "links")

    assert (
        read_file_at_revision(tmp_path, "main", ".devops/review.md"),
        read_file_at_revision(tmp_path, "main", "linked/rules.md"),
        read_file_at_revision(tmp_path, "main", "docs/rules.md"),
    ) == (None, None, "Rules.\n")


def test_read_file_at_revision_reads_any_path_inside_the_repository(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """A path is refused only when it could leave the repository or read as an option (#946).

    It reaches git inside one argument, after the validated revision, so a space or a character
    outside ASCII is harmless. Both were refused, and a subproject named with one lost its
    conventions in a branch review.
    """
    git(tmp_path, "init", "--quiet", "-b", "main")
    (tmp_path / "my project").mkdir()
    (tmp_path / "my project" / "AGENTS.md").write_text("Spaced.\n", encoding="utf-8")
    (tmp_path / "café").mkdir()
    (tmp_path / "café" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "--quiet", "-m", "names")

    assert (
        read_file_at_revision(tmp_path, "main", "my project/AGENTS.md"),
        read_file_at_revision(tmp_path, "main", "café/mod.py"),
    ) == ("Spaced.\n", "x = 1\n")


def test_list_changed_files_gives_a_rename_its_old_and_new_path(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """A rename is one entry with both paths, so its base can be read at the old one (#593).

    The plain `--name-status` parser kept `old.py<TAB>new.py` as one path, which does not exist,
    and handled the renamed file as deleted.
    """
    outline = "".join(f"def step_{n}():\n    return {n}\n\n\n" for n in range(8))
    git(tmp_path, "init", "--quiet", "-b", "main")
    (tmp_path / "old_name.py").write_text(outline, encoding="utf-8")
    (tmp_path / "gone.py").write_text("x = 1\n", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "--quiet", "-m", "base")
    git(tmp_path, "switch", "--quiet", "-c", "feature")
    (tmp_path / "old_name.py").unlink()
    (tmp_path / "new_name.py").write_text(
        outline + "def step_9():\n    return 9\n", encoding="utf-8"
    )
    (tmp_path / "gone.py").unlink()
    (tmp_path / "fresh.py").write_text("y = 2\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "rename")
    main_sha = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "main"], capture_output=True, text=True
    ).stdout.strip()

    changes = list_changed_files(tmp_path, "main", "feature")

    assert (
        sorted(changes, key=lambda c: c.path),
        resolve_merge_base(tmp_path, "main", "feature"),
    ) == (
        [
            ChangedFile(change_type="added", path="fresh.py"),
            ChangedFile(change_type="deleted", path="gone.py"),
            ChangedFile(change_type="renamed", path="new_name.py", old_path="old_name.py"),
        ],
        main_sha,
    )


def test_revision_helpers_refuse_option_like_arguments(tmp_path: Path) -> None:
    """A revision or path that git could read as an option is refused before git runs."""
    with patch("devops_cli.git.operations.run_subprocess") as run:
        refused = (
            read_file_at_revision(tmp_path, "--output=x", "mod.py"),
            read_file_at_revision(tmp_path, "main", "../escape.py"),
            read_file_at_revision(tmp_path, "main", "src/../../escape.py"),
            read_file_at_revision(tmp_path, "main", "-p"),
            read_file_at_revision(tmp_path, "main", "/etc/hostname"),
            read_file_at_revision(tmp_path, "main", ""),
            resolve_merge_base(tmp_path, "-x"),
            list_changed_files(tmp_path, "main", "--no-index"),
        )

    assert (refused, run.call_count) == ((None, None, None, None, None, None, None, []), 0)


def test_revision_helpers_report_a_failed_git_call(tmp_path: Path) -> None:
    """A failed `git show` or `git diff` reads nothing, and a failed merge base falls back to the
    base, where the review's two-dot diff starts."""
    failed = MagicMock(returncode=128, stdout="")
    with patch("devops_cli.git.operations.run_subprocess", return_value=failed):
        results = (
            read_file_at_revision(tmp_path, "main", "mod.py"),
            resolve_merge_base(tmp_path, "main", "feature"),
            list_changed_files(tmp_path, "main"),
        )

    assert results == (None, "main", [])


def test_commit_snapshot_makes_the_same_one_commit_of_the_same_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The id is the one `git commit` gives these files with that identity, date and message."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    when = datetime(2026, 10, 3, tzinfo=UTC)
    commits = []
    for name in ("one", "two"):
        (tmp_path / name / "app").mkdir(parents=True)
        (tmp_path / name / "app" / "db.py").write_text("query = f'{x}'\n")
        (tmp_path / name / "a.py").write_text("x = 1\n")
        commits.append(
            commit_snapshot(
                tmp_path / name,
                ["app/db.py", "a.py"],
                "The golden review set's files, for a path review\n",
                author="devops-cli golden",
                email="",
                date=when,
            )
        )
    repo = gitlib.Repo(tmp_path / "one")

    assert (commits, repo.active_branch.name, len(list(repo.iter_commits()))) == (
        ["63b6e3c00959a24f7f5badfa9508a96cca4504ae"] * 2,
        "main",
        1,
    )
