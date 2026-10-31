"""Tests for Git operation helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_GITHUB_KNOWN_HOSTS_LINES
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
    parse_clone_destination,
    pull_tracking,
    read_file_at_revision,
    reset_known_host_cache,
    resolve_merge_base,
)
from devops_cli.models.git import ChangedFile
from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessAnswer
from tests.support.git_recording import load_transcript


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


def test_is_git_clean_and_get_latest_tag(git_fake: GitFake, tmp_path: Path) -> None:
    """is_git_clean is true for a tree with no change, and get_latest_git_tag gives the newest
    tag, or None when the repository has none."""
    from devops_cli.git.operations import get_latest_git_tag, is_git_clean

    git_fake.replay("working_tree_state")
    repo = tmp_path / "repo"

    assert (
        (is_git_clean(repo), get_latest_git_tag(repo)),
        get_latest_git_tag(repo),
        is_git_clean(repo),
    ) == ((True, None), "v0.2.1", False)


def test_is_git_clean_and_get_latest_tag_report_a_git_that_cannot_run(
    git_fake: GitFake, tmp_path: Path
) -> None:
    """A git that fails to start leaves the tree not clean and the repository with no tag."""
    from devops_cli.git.operations import get_latest_git_tag, is_git_clean

    git_fake.answer(["git"], ProcessAnswer(side_effect=OSError("git error")))

    assert (is_git_clean(tmp_path), get_latest_git_tag(tmp_path)) == (False, None)


def test_validate_clone_dest_and_prepare_clone_url(tmp_path: Path, known_hosts: Path) -> None:
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

    # _prepare_clone_url pins the GitHub host keys, and keeps both spellings of the URL
    url_ssh = _prepare_clone_url("git@github.com:org/repo.git")
    url_https = _prepare_clone_url("https://github.com/org/repo.git")
    assert (url_ssh, url_https, known_hosts.read_text().splitlines()) == (
        "git@github.com:org/repo.git",
        "https://github.com/org/repo.git",
        list(CONST_GITHUB_KNOWN_HOSTS_LINES),
    )


def test_read_file_at_revision_reads_the_base_revision(git_fake: GitFake, tmp_path: Path) -> None:
    """The file is read at the base revision, not taken for a pathspec (#787)."""
    git_fake.replay("revision_reads")

    assert (
        read_file_at_revision(tmp_path / "repo", "main", "mod.py")
        == "def kept(): pass\ndef gone(): pass\n"
    )


def test_read_file_at_revision_reads_no_directory(git_fake: GitFake, tmp_path: Path) -> None:
    """A directory at the revision is not a file. `git show` printed its listing, which a
    branch review reading its conventions at the merge base took for `.cursor/rules` (#946)."""
    git_fake.replay("revision_reads")
    repo = tmp_path / "repo"

    assert (
        read_file_at_revision(repo, "main", ".cursor/rules"),
        read_file_at_revision(repo, "main", ".cursor/rules/style.mdc"),
    ) == (None, "Rule.\n")


def test_read_file_at_revision_reads_no_link(git_fake: GitFake, tmp_path: Path) -> None:
    """A committed link is no file at the revision. Its blob is the path it points to, which a
    branch review took for the `AGENTS.md` a project linked to its rules (#946)."""
    git_fake.replay("revision_reads")
    repo = tmp_path / "repo"

    assert (
        read_file_at_revision(repo, "main", "AGENTS.md"),
        read_file_at_revision(repo, "main", "linked/rules.md"),
        read_file_at_revision(repo, "main", "docs/rules.md"),
    ) == (None, None, "Rules.\n")


def test_read_file_at_revision_reads_any_path_inside_the_repository(
    git_fake: GitFake, tmp_path: Path
) -> None:
    """A path is refused only when it could leave the repository or read as an option (#946).

    It reaches git inside one argument, after the validated revision, so a space or a character
    outside ASCII is harmless. Both were refused, and a subproject named with one lost its
    conventions in a branch review.
    """
    git_fake.replay("revision_reads")
    repo = tmp_path / "repo"

    assert (
        read_file_at_revision(repo, "main", "my project/AGENTS.md"),
        read_file_at_revision(repo, "main", "café/mod.py"),
    ) == ("Spaced.\n", "x = 1\n")


def test_list_changed_files_gives_a_rename_its_old_and_new_path(
    git_fake: GitFake, tmp_path: Path
) -> None:
    """A rename is one entry with both paths, so its base can be read at the old one (#593).

    The plain `--name-status` parser kept `old.py<TAB>new.py` as one path, which does not exist,
    and handled the renamed file as deleted.
    """
    git_fake.replay("renamed_files")
    repo = tmp_path / "repo"

    changes = list_changed_files(repo, "main", "feature")

    assert (
        sorted(changes, key=lambda c: c.path),
        resolve_merge_base(repo, "main", "feature"),
    ) == (
        [
            ChangedFile(change_type="added", path="fresh.py"),
            ChangedFile(change_type="deleted", path="gone.py"),
            ChangedFile(change_type="renamed", path="new_name.py", old_path="old_name.py"),
        ],
        load_transcript("renamed_files")["result"]["merge_base"],
    )


def test_revision_helpers_refuse_option_like_arguments(git_fake: GitFake, tmp_path: Path) -> None:
    """A revision or path that git could read as an option is refused before git runs."""
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

    assert (refused, git_fake.call_count) == ((None, None, None, None, None, None, None, []), 0)


def test_revision_helpers_report_a_failed_git_call(git_fake: GitFake, tmp_path: Path) -> None:
    """A failed `git ls-tree` or `git diff` reads nothing, and a failed merge base falls back to
    the base, where the review's two-dot diff starts."""
    git_fake.replay("revision_failures")
    repo = tmp_path / "repo"

    results = (
        read_file_at_revision(repo, "nosuch", "mod.py"),
        resolve_merge_base(repo, "nosuch", "main"),
        list_changed_files(repo, "nosuch"),
    )

    assert results == (None, "nosuch", [])


def _git_words(fake: GitFake, repo: Path) -> list[list[str]]:
    """The arguments each git call had after `git -C <repo>`."""
    return [list(call.argv[3:]) for call in fake.calls if call.argv[2:3] == (str(repo),)]


def test_clone_repo_ensures_github_known_host_for_all_urls(
    git_fake: GitFake, tmp_path: Path, known_hosts: Path
) -> None:
    """Verify clone_repo ensures host keys are known for all clone URLs, and clones the URL
    that it normalized."""
    git_fake.answer(["git", "clone"], ProcessAnswer())
    clone_repo("git@github.com:example/repo.git", tmp_path / "repo")
    clone_repo("github.com/example/repo2.git", tmp_path / "repo2")

    assert (known_hosts.read_text().splitlines(), [list(call.argv) for call in git_fake.calls]) == (
        list(CONST_GITHUB_KNOWN_HOSTS_LINES),
        [
            ["git", "clone", "--", "git@github.com:example/repo.git", str(tmp_path / "repo")],
            ["git", "clone", "--", "https://github.com/example/repo2.git", str(tmp_path / "repo2")],
        ],
    )


def test_clone_repo_clones_a_repository_and_gives_gits_reason_for_a_missing_one(
    git_fake: GitFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repository is cloned; one that does not exist raises GitOperationError with git's text."""
    git_fake.replay("clone")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    reset_known_host_cache()

    clone_repo(str(tmp_path / "remote.git"), tmp_path / "first")
    with pytest.raises(GitOperationError) as raised:
        clone_repo(str(tmp_path / "missing.git"), tmp_path / "second")

    reset_known_host_cache()

    assert str(raised.value) == f"fatal: repository '{tmp_path / 'missing.git'}' does not exist"


def test_fetch_all_fetches_each_remote_with_pruning(git_fake: GitFake, tmp_path: Path) -> None:
    """fetch_all lists the remotes and fetches each one with `--prune`."""
    git_fake.replay("fetch_and_pull_updates")
    clone = tmp_path / "clone2"

    fetch_all(clone)

    assert _git_words(git_fake, clone) == [["remote"], ["fetch", "--prune", "origin"]]


def test_fetch_all_refused_by_the_remote_raises_git_operation_error(
    git_fake: GitFake, tmp_path: Path
) -> None:
    """A remote that git cannot fetch raises GitOperationError with repository, remote, and reason."""
    git_fake.replay("fetch_refused")
    repo = tmp_path / "repo"

    with pytest.raises(GitOperationError) as raised:
        fetch_all(repo)

    msg = str(raised.value)
    assert (
        str(tmp_path / "missing.git") in msg,
        raised.value.details["operation"],
        raised.value.details["repository"],
        raised.value.details["remote"],
    ) == (True, "fetch", str(repo), "origin")


def test_pull_tracking_pulls_the_tracked_branch_from_its_remote(
    git_fake: GitFake, tmp_path: Path
) -> None:
    """pull_tracking reads the branch and the remote it tracks, and pulls that branch."""
    git_fake.replay("fetch_and_pull_updates")
    clone = tmp_path / "clone2"

    pull_tracking(clone)

    assert _git_words(git_fake, clone) == [
        ["branch", "--show-current"],
        ["config", "--get", "branch.main.remote"],
        ["remote"],
        ["pull", "origin", "main"],
    ]


def test_pull_tracking_divergent_branch_raises_git_operation_error(
    git_fake: GitFake, tmp_path: Path
) -> None:
    """A divergent tracking branch that cannot fast-forward raises GitOperationError."""
    git_fake.replay("pull_divergent")
    repo = tmp_path / "diverged"

    with pytest.raises(GitOperationError) as raised:
        pull_tracking(repo)

    msg = str(raised.value)
    assert (
        str(repo) in msg,
        "divergent branches" in msg,
        raised.value.details["operation"],
        raised.value.details["repository"],
        raised.value.details["remote"],
    ) == (True, True, "pull", str(repo), "origin")


def test_pull_tracking_raises_gits_reason_when_the_configuration_cannot_be_read(
    git_fake: GitFake, tmp_path: Path
) -> None:
    """Only exit status 1 of `git config --get` means that the branch tracks no remote. Any other
    status is a failure of git, and it is not read as "nothing to pull"."""
    git_fake.replay("fetch_and_pull_updates")
    git_fake.answer(
        lambda call: call.argv[3:5] == ("config", "--get"),
        ProcessAnswer(returncode=128, stderr="fatal: bad config line 3 in file .git/config"),
    )

    with pytest.raises(GitOperationError, match="bad config line 3") as raised:
        pull_tracking(tmp_path / "clone2")

    assert (
        raised.value.details["operation"],
        [call for call in _git_words(git_fake, tmp_path / "clone2") if call[0] == "pull"],
    ) == ("pull", [])


def test_pull_tracking_does_nothing_without_a_remote_branch_and_names_a_missing_remote(
    git_fake: GitFake, tmp_path: Path
) -> None:
    """A branch with no upstream and a detached HEAD pull nothing; a branch that tracks a remote
    that does not exist raises GitOperationError."""
    git_fake.replay("pull_without_a_remote_branch")

    pull_tracking(tmp_path / "untracked")
    pull_tracking(tmp_path / "detached")
    with pytest.raises(GitOperationError, match="Remote 'gone' configured for tracking") as raised:
        pull_tracking(tmp_path / "orphaned")

    assert (
        [call for call in _git_words(git_fake, tmp_path / "untracked") if call[0] == "pull"],
        raised.value.details["remote"],
    ) == ([], "gone")


def test_create_branch(git_fake: GitFake, tmp_path: Path) -> None:
    """create_branch creates the branch from HEAD and checks it out; bad or taken names raise."""
    git_fake.replay("branch_creation")
    repo = tmp_path / "repo"

    # The hyphen guard runs before git.
    with pytest.raises(InvalidBranchNameError, match="cannot start with a hyphen"):
        create_branch(repo, "-invalid")
    with pytest.raises(BranchAlreadyExistsError, match="already exists"):
        create_branch(repo, "main")
    create_branch(repo, "feat/test")

    assert _git_words(git_fake, repo) == [
        ["show-ref", "--verify", "--quiet", "refs/heads/main"],
        ["show-ref", "--verify", "--quiet", "refs/heads/feat/test"],
        ["checkout", "-b", "feat/test"],
    ]


def test_create_branch_raises_gits_reason_when_git_refuses(
    git_fake: GitFake, tmp_path: Path
) -> None:
    """A branch git refuses raises GitOperationError with git's own reason."""
    git_fake.replay("branch_creation")

    with pytest.raises(GitOperationError, match="'refs/heads/feature' exists") as raised:
        create_branch(tmp_path / "repo", "feature/x")

    assert (raised.value.details["operation"], raised.value.details["branch_name"]) == (
        "branch_create",
        "feature/x",
    )


def test_list_branches(git_fake: GitFake, tmp_path: Path) -> None:
    """list_branches gives the local branches, the remote ones on request without `origin/HEAD`,
    and `HEAD` as the current branch when it is detached."""
    git_fake.replay("branch_listing")
    clone = tmp_path / "clone"

    local = list_branches(clone, all_branches=False)
    everything = list_branches(clone, all_branches=True)
    detached = list_branches(clone)

    assert (local.model_dump(), everything.branches, detached.current) == (
        {"branches": ["feat/xyz", "main"], "current": "main"},
        ["feat/xyz", "main", "origin/feat/remote", "origin/main"],
        "HEAD",
    )


def test_delete_merged_branches(git_fake: GitFake, tmp_path: Path) -> None:
    """delete_merged_branches removes the merged branches that are not protected, and only names
    them on a dry run; a repository with no branch has nothing to delete."""
    git_fake.replay("merged_branches")
    work = tmp_path / "work"

    dry = delete_merged_branches(work, dry_run=True)
    deleted = delete_merged_branches(work, dry_run=False)
    empty = delete_merged_branches(tmp_path / "empty")

    assert (dry, deleted, empty) == (["feat/merged"], ["feat/merged"], [])
    assert [w for w in _git_words(git_fake, work) if w[0] == "branch" and "--delete" in w] == [
        ["branch", "--delete", "--", "feat/merged"]
    ]


def test_commit_snapshot_makes_the_same_one_commit_of_the_same_files(
    git_fake: GitFake, tmp_path: Path
) -> None:
    """The id is the one `git commit-tree` gives these files with that identity, date and message
    (the golden review set pins it); the commit is made with the author and date in the
    environment and the message on standard input, and no hook or signature."""
    git_fake.replay("commit_snapshots")
    when = datetime(2026, 10, 3, tzinfo=UTC)
    message = "The golden review set's files, for a path review\n"
    commits = [
        commit_snapshot(
            tmp_path / name,
            ["app/db.py", "a.py"],
            message,
            author="devops-cli golden",
            email="",
            date=when,
        )
        for name in ("one", "two")
    ]
    commit_call = next(call for call in git_fake.calls if "commit-tree" in call.argv)

    assert (commits, commit_call.stdin, commit_call.env) == (
        ["63b6e3c00959a24f7f5badfa9508a96cca4504ae"] * 2,
        message,
        {
            "GIT_AUTHOR_NAME": "devops-cli golden",
            "GIT_AUTHOR_EMAIL": "",
            "GIT_AUTHOR_DATE": "2026-10-03T00:00:00+00:00",
            "GIT_COMMITTER_NAME": "devops-cli golden",
            "GIT_COMMITTER_EMAIL": "",
            "GIT_COMMITTER_DATE": "2026-10-03T00:00:00+00:00",
        },
    )


def test_parse_clone_destination_extracts_org_and_repo() -> None:
    """`parse_clone_destination` resolves organization and repo name from HTTPS and SSH URLs."""
    assert parse_clone_destination("https://github.com/my-org/my-repo.git") == (
        "my-org",
        "my-repo",
    )
    assert parse_clone_destination("git@github.com:my-org/my-repo.git") == (
        "my-org",
        "my-repo",
    )
    assert parse_clone_destination("file:///tmp/repo.git") == (
        "_standalone",
        "repo",
    )
    assert parse_clone_destination("just-a-repo") == ("_standalone", "just-a-repo")
