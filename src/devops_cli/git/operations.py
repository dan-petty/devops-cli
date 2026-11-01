"""Git repository operations through the process runner and the git CLI.

Functionality:
- URL normalization: forces HTTPS for web URLs while leaving SSH URLs intact.
- SSH known_hosts management: ensures GitHub host key presence in `~/.ssh/known_hosts` (mode 0600).
- Branch management: listing, tracking branch pull, and merged branch deletion.
- Revisions: a file's text at a revision, the merge base of two refs, and the files a diff changed.
"""

from __future__ import annotations

import functools
import logging
import os
import subprocess
from collections.abc import Generator
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from devops_cli.config.constants import (
    CONST_GIT_DIR_NAME,
    CONST_GIT_MAIN_BRANCH,
    CONST_GIT_NAME_STATUS_CHANGE_TYPES,
    CONST_GIT_NAME_STATUS_TWO_PATH_LETTERS,
    CONST_GIT_SYMLINK_MODE,
    CONST_GITHUB_HOST,
    CONST_GITHUB_HTTP_PREFIX,
    CONST_GITHUB_HTTPS_PREFIX,
    CONST_GITHUB_KNOWN_HOSTS_LINES,
    CONST_GITHUB_REPO_SUFFIX,
    CONST_GITHUB_SSH_PREFIX,
    CONST_GITHUB_SSH_URL_PREFIX,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_PERM_DIR,
    CONST_PERM_PRIVATE_KEY,
    CONST_SAFE_GIT_REF_PATTERN,
    CONST_URL_SCHEME_HTTP,
    CONST_URL_SCHEME_HTTPS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import (
    BranchAlreadyExistsError,
    GitOperationError,
    InvalidBranchNameError,
)
from devops_cli.models.git import BranchListing, ChangedFile

logger = logging.getLogger(__name__)

_HEADS_PREFIX = "refs/heads/"
_REMOTES_PREFIX = "refs/remotes/"
_CONFIG_KEY_UNSET = 1
"""The exit status of `git config --get` for a key that is not set (git-config(1)). Any other
status above 0 is a failure, such as a configuration file that cannot be read."""


def _normalize_clone_url(url: str) -> str:
    if url.startswith((CONST_GITHUB_SSH_PREFIX, CONST_GITHUB_SSH_URL_PREFIX)):
        return url
    if url.startswith(f"{CONST_GITHUB_HOST}/"):
        return f"{CONST_URL_SCHEME_HTTPS}{url}"
    if url.startswith(CONST_GITHUB_HTTP_PREFIX):
        return f"{CONST_URL_SCHEME_HTTPS}{url.removeprefix(CONST_URL_SCHEME_HTTP)}"
    if url.startswith(CONST_GITHUB_HTTPS_PREFIX):
        return url
    return url


def iter_workspace_repos(root: Path) -> Generator[Path]:
    """Yield all valid Git repository directories under *root* across 2 directory levels."""
    if not root.exists():
        return
    resolved_root = root.resolve()
    for group_dir in sorted(root.iterdir()):
        if not group_dir.is_dir():
            continue
        for repo_dir in sorted(group_dir.iterdir()):
            if (repo_dir / CONST_GIT_DIR_NAME).exists() and repo_dir.resolve().is_relative_to(
                resolved_root
            ):
                yield repo_dir


def _read_existing_lines(path: Path) -> tuple[set[str], bool]:
    """Read existing lines and check whether trailing newline is missing."""
    if not path.is_file():
        return set(), False
    content = path.read_text(encoding="utf-8", errors="replace")
    needs_newline = bool(content and not content.endswith("\n"))
    return set(content.splitlines()), needs_newline


@functools.cache
def _ensure_known_host(known_hosts: Path | None = None) -> None:
    """Ensure GitHub's published host keys are present in known_hosts.

    Compares lines verbatim with pathlib/os only, appending any missing keys.
    Runs once per process via caching. An unwritable directory logs a warning
    and allows execution to continue.
    """
    path = known_hosts or (Path.home() / ".ssh" / "known_hosts")
    try:
        path.parent.mkdir(mode=CONST_PERM_DIR, parents=True, exist_ok=True)
        try:
            path.parent.chmod(CONST_PERM_DIR)
        except OSError:
            pass

        existing_lines, needs_newline = _read_existing_lines(path)
        missing = [line for line in CONST_GITHUB_KNOWN_HOSTS_LINES if line not in existing_lines]
        if not missing:
            return

        with path.open("a", encoding="utf-8") as handle:
            if needs_newline:
                handle.write("\n")
            for line in missing:
                handle.write(f"{line}\n")
        path.chmod(CONST_PERM_PRIVATE_KEY)
    except OSError as exc:
        logger.warning("Could not update known_hosts '%s': %s", path, exc)


def reset_known_host_cache() -> None:
    """Clear the cached known_hosts check."""
    _ensure_known_host.cache_clear()


def _extract_url_path(url: str) -> tuple[str, bool]:
    """Extract raw path from URL and return whether it is a file:// scheme."""
    clean = url.strip()
    parsed = urlsplit(clean)
    if parsed.scheme:
        return parsed.path, parsed.scheme == "file"
    if ":" in clean:
        _, _, path = clean.rpartition(":")
        return path, False
    return clean, False


def parse_clone_destination(url: str) -> tuple[str, str]:
    """Extract organization/group and repository name from a Git clone URL.

    Returns (org_name, repo_name). Falls back to ("_standalone", repo_name)
    when no organization or owner can be determined from the URL.
    """
    from devops_cli.core.paths import validate_no_path_traversal

    path, is_file_scheme = _extract_url_path(url)
    validate_no_path_traversal(path, label="URL path")
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        return "_standalone", "repo"

    repo_name = Path(parts[-1].removesuffix(CONST_GITHUB_REPO_SUFFIX)).name
    if is_file_scheme:
        return "_standalone", repo_name

    if len(parts) >= 2 and ("." in parts[0] or ":" in parts[0]):
        parts = parts[1:]

    org_name = Path(parts[-2]).name if len(parts) >= 2 else "_standalone"
    return org_name, repo_name


def _validate_clone_dest(dest: Path) -> None:
    """Validate that repository destination path does not attempt path traversal."""
    from devops_cli.core.paths import is_forbidden_system_path, validate_no_path_traversal
    from devops_cli.exceptions import SecurityError

    try:
        validate_no_path_traversal(dest, label="Clone destination")
    except SecurityError as exc:
        raise GitOperationError(str(exc)) from exc

    resolved = dest.resolve()
    if is_forbidden_system_path(resolved):
        raise GitOperationError(f"Clone destination resolves to forbidden system path: {resolved}")
    if dest.is_symlink():
        raise GitOperationError(f"Clone destination must not be a symlink: {dest}")


def _prepare_clone_url(url: str) -> str:
    """Normalize clone url and ensure GitHub host keys are known."""
    _ensure_known_host()
    return _normalize_clone_url(url)


def _reason(proc: subprocess.CompletedProcess[str]) -> str:
    """Why git failed, from its standard error, with credentials masked."""
    from devops_cli.security.sanitizer import mask_secrets

    return mask_secrets(proc.stderr.strip() or f"git exited with status {proc.returncode}")


def _git(
    repo_dir: Path,
    *args: str,
    read: bool = False,
    input: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run `git -C <repo_dir> <args>` through the process runner. A read runs in a dry run."""
    return run_subprocess(
        git_argv(repo_dir, *args), quiet=True, local_read=read, input=input, env=env
    )


def git_argv(repo_dir: Path, *args: str) -> list[str]:
    """The command `git -C <repo_dir> <args>`, as `_git` runs it and a dry run lists it."""
    return ["git", "-C", str(repo_dir), *args]


def _checked(
    repo_dir: Path,
    *args: str,
    operation: str,
    read: bool = False,
    input: str | None = None,
    env: dict[str, str] | None = None,
) -> str:
    """The standard output of `git -C <repo_dir> <args>`; git's reason in a `GitOperationError`
    when it exits with a status other than 0."""
    proc = _git(repo_dir, *args, read=read, input=input, env=env)
    if proc.returncode != 0:
        raise GitOperationError(_reason(proc), operation=operation)
    return proc.stdout.strip()


def _remote_error(
    verb: str, operation: str, repo_dir: Path, remote: str, reason: str
) -> GitOperationError:
    """The error of a fetch or pull that failed on `remote`, with the repository and remote."""
    return GitOperationError(
        f"Failed to {verb} remote '{remote}' in '{repo_dir}': {reason}",
        operation=operation,
        details={
            "repository": str(repo_dir)[:CONST_MAX_ERROR_DETAIL_LENGTH],
            "remote": remote[:CONST_MAX_ERROR_DETAIL_LENGTH],
        },
    )


def clone_argv(url: str, dest: Path) -> list[str]:
    """The command that clones `url`, normalized, to `dest`, as `clone_repo` runs it."""
    return ["git", "clone", "--", _normalize_clone_url(url), str(dest)]


def clone_repo(url: str, dest: Path) -> None:
    """Clone a repository to *dest*."""
    _validate_clone_dest(dest)
    normalized_url = _prepare_clone_url(url)
    proc = run_subprocess(clone_argv(normalized_url, dest), quiet=True)
    if proc.returncode != 0:
        raise GitOperationError(_reason(proc))


def _remotes(repo_dir: Path, operation: str) -> list[str]:
    """The names of the remotes of a repository."""
    return _checked(repo_dir, "remote", operation=operation, read=True).splitlines()


def fetch_commands(repo_dir: Path) -> list[tuple[str, list[str]]]:
    """The remote and the git arguments of each fetch that `fetch_all` runs, in order. It reads
    the remotes of the local repository, which a dry run also does."""
    return [(remote, ["fetch", "--prune", remote]) for remote in _remotes(repo_dir, "fetch")]


def fetch_all(repo_dir: Path) -> None:
    """Fetch all remotes with pruning."""
    for remote, args in fetch_commands(repo_dir):
        proc = _git(repo_dir, *args)
        if proc.returncode != 0:
            raise _remote_error("fetch", "fetch", repo_dir, remote, _reason(proc))


def current_branch(repo_dir: Path) -> str:
    """The name of the checked-out branch; empty when HEAD is detached."""
    return _checked(repo_dir, "branch", "--show-current", operation="branch_current", read=True)


def _tracking_remote(repo_dir: Path, branch: str) -> str:
    """The remote that `branch` tracks, from its `branch.<name>.remote` setting; empty when it
    tracks none, or only a local branch (`.`)."""
    proc = _git(repo_dir, "config", "--get", f"branch.{branch}.remote", read=True)
    if proc.returncode == _CONFIG_KEY_UNSET:
        return ""
    if proc.returncode != 0:
        raise GitOperationError(_reason(proc), operation="pull")
    remote = proc.stdout.strip()
    return "" if remote == "." else remote


def pull_command(repo_dir: Path) -> tuple[str, list[str]] | None:
    """The remote and the git arguments of the pull that `pull_tracking` runs; `None` when the
    current branch tracks no remote. It reads only the local repository, which a dry run also
    does, and it refuses a tracking remote that does not exist, as the run does."""
    branch = current_branch(repo_dir)
    remote = _tracking_remote(repo_dir, branch) if branch else ""
    if not remote:
        return None
    if remote not in _remotes(repo_dir, "pull"):
        raise GitOperationError(
            f"Remote '{remote}' configured for tracking in '{repo_dir}' not found",
            operation="pull",
            details={
                "repository": str(repo_dir)[:CONST_MAX_ERROR_DETAIL_LENGTH],
                "remote": remote[:CONST_MAX_ERROR_DETAIL_LENGTH],
            },
        )
    return remote, ["pull", remote, branch]


def pull_tracking(repo_dir: Path) -> None:
    """Pull the current tracking branch if one is configured."""
    command = pull_command(repo_dir)
    if command is None:
        return
    remote, args = command
    proc = _git(repo_dir, *args)
    if proc.returncode != 0:
        raise _remote_error("pull", "pull", repo_dir, remote, _reason(proc))


def create_branch(repo_dir: Path, branch_name: str) -> None:
    """Create and checkout a new branch from the current HEAD.

    When git refuses the branch, :class:`GitOperationError` carries git's reason. `-b` takes
    the next argument as the name, and the hyphen guard stops it being read as an option, so
    no `--` is used.
    """
    if branch_name.startswith("-"):
        raise InvalidBranchNameError(branch_name, reason="cannot start with a hyphen")
    taken = _git(
        repo_dir, "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}", read=True
    )
    if taken.returncode == 0:
        raise BranchAlreadyExistsError(branch_name)
    proc = _git(repo_dir, "checkout", "-b", branch_name)
    if proc.returncode != 0:
        raise GitOperationError(
            _reason(proc),
            operation="branch_create",
            details={"branch_name": branch_name[:CONST_MAX_ERROR_DETAIL_LENGTH]},
        )


def commit_snapshot(
    repo_dir: Path,
    paths: list[str],
    message: str,
    *,
    author: str,
    email: str,
    date: datetime,
) -> str:
    """Make `repo_dir` a new repository whose one commit holds `paths`, and return its id.

    The author, committer and both dates are the ones given, no hook runs and nothing is signed,
    so the same files always give the same commit, whatever the configuration of git on the host.
    The commit is made with plumbing. `add` takes each path as one file name (`--literal-pathspecs`)
    and the files as they are: no line-ending conversion, and no attributes file of the user or the
    system. `commit-tree` reads the message from standard input as it is.
    """
    operation = "commit_snapshot"
    when = date.isoformat()
    identity = {
        "GIT_AUTHOR_NAME": author,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_AUTHOR_DATE": when,
        "GIT_COMMITTER_NAME": author,
        "GIT_COMMITTER_EMAIL": email,
        "GIT_COMMITTER_DATE": when,
    }
    init = run_subprocess(
        ["git", "init", "--quiet", f"--initial-branch={CONST_GIT_MAIN_BRANCH}", str(repo_dir)],
        quiet=True,
    )
    if init.returncode != 0:
        raise GitOperationError(_reason(init), operation=operation)
    as_they_are = [
        "--literal-pathspecs",
        *("-c", "core.autocrlf=false"),
        *("-c", "core.safecrlf=false"),
        *("-c", f"core.attributesFile={os.devnull}"),
    ]
    _checked(repo_dir, *as_they_are, "add", "--force", "--", *sorted(paths), operation=operation)
    tree = _checked(repo_dir, "write-tree", operation=operation)
    commit = _checked(
        repo_dir,
        "commit-tree",
        "--no-gpg-sign",
        tree,
        input=message,
        env=identity,
        operation=operation,
    )
    _checked(repo_dir, "update-ref", "HEAD", commit, operation=operation)
    return commit


def _branch_refs(repo_dir: Path) -> tuple[list[str], list[str]]:
    """The names of the local branches and of the remote-tracking branches, each sorted."""
    refs = _checked(
        repo_dir,
        "for-each-ref",
        "--format=%(refname)",
        "refs/heads",
        "refs/remotes",
        operation="branch_list",
        read=True,
    ).splitlines()
    local = sorted(ref.removeprefix(_HEADS_PREFIX) for ref in refs if ref.startswith(_HEADS_PREFIX))
    remote = sorted(
        ref.removeprefix(_REMOTES_PREFIX) for ref in refs if ref.startswith(_REMOTES_PREFIX)
    )
    return local, remote


def list_branches(
    repo_dir: Path,
    all_branches: bool = False,
) -> BranchListing:
    """Return a BranchListing with branch names and the current branch name."""
    current = current_branch(repo_dir) or "HEAD"
    local, remote = _branch_refs(repo_dir)
    if not all_branches:
        return BranchListing(branches=local, current=current)
    remote_names = [name for name in remote if not name.endswith("/HEAD")]
    return BranchListing(branches=sorted(set(local) | set(remote_names)), current=current)


def delete_merged_branches(repo_dir: Path, dry_run: bool = False) -> list[str]:
    """Delete local branches that have been merged into the default branch."""
    local, _ = _branch_refs(repo_dir)
    default = next((name for name in local if name in ("main", "master")), None)
    default = default or (local[0] if local else None)
    if not default:
        return []

    merged_output = _checked(
        repo_dir,
        "branch",
        "--merged",
        default,
        "--format=%(refname:lstrip=2)",
        operation="branch_delete",
        read=True,
    )
    merged = set(merged_output.splitlines())
    protected = {default, "main", "master"}
    to_delete = [name for name in local if name in merged - protected]
    for name in to_delete:
        if not dry_run:
            _checked(repo_dir, "branch", "--delete", "--", name, operation="branch_delete")
    return to_delete


def is_git_clean(repo_dir: Path) -> bool:
    """Check whether git working directory has uncommitted changes."""
    try:
        proc = run_subprocess(
            ["git", "status", "--porcelain"], cwd=repo_dir, quiet=True, local_read=True
        )
        return proc.returncode == 0 and not bool(proc.stdout.strip())
    except Exception:
        return False


def get_latest_git_tag(repo_dir: Path) -> str | None:
    """Retrieve latest git tag for the repository if available."""
    try:
        proc = run_subprocess(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=repo_dir,
            quiet=True,
            local_read=True,
        )
        if proc.returncode == 0 and proc.stdout:
            return str(proc.stdout).strip()
    except Exception:
        pass
    return None


def _is_safe_revision(revision: str) -> bool:
    """Whether a revision can be passed to git as one: no option prefix, ref characters only."""
    return (
        not revision.startswith("-") and CONST_SAFE_GIT_REF_PATTERN.fullmatch(revision) is not None
    )


def _is_safe_relpath(rel_path: str) -> bool:
    """Whether a path is relative to the repository, stays inside it, and reads as no option.

    It reaches git as one argument, a literal pathspec after `--`, so any other character, such
    as a space or one outside ASCII, is harmless.
    """
    path = PurePosixPath(rel_path)
    return (
        bool(rel_path)
        and not rel_path.startswith("-")
        and not path.is_absolute()
        and ".." not in path.parts
    )


def _regular_file_object(repo_dir: Path, revision: str, rel_path: str) -> str | None:
    """The object id of the regular file at `rel_path` in `revision`, or None.

    A link's blob is the path it points to, not its text, and a directory or a submodule is no
    file. `--full-tree` reads the path from the repository root, as `<rev>:<path>` does, and
    the entry must name the path itself, since `dir/` lists the files in `dir`.
    """
    proc = run_subprocess(
        ["git", "--literal-pathspecs", "ls-tree", "-z", "--full-tree", revision, "--", rel_path],
        cwd=repo_dir,
        quiet=True,
        local_read=True,
    )
    if proc.returncode != 0:
        return None
    for entry in proc.stdout.split("\0"):
        meta, _, path = entry.partition("\t")
        match meta.split():
            case [mode, "blob", object_id] if path == rel_path and mode != CONST_GIT_SYMLINK_MODE:
                return object_id
    return None


def read_file_at_revision(repo_dir: Path, revision: str, rel_path: str) -> str | None:
    """A regular file's text at a revision; None when there is none at the path or either
    argument is refused.

    The revision comes before `--`, so it is validated rather than set off: `git show --
    <rev>:<path>` read its argument as a pathspec and printed the head commit's header (#787).
    The path is looked up with `ls-tree`, whose mode tells a regular file from a link, a
    directory or a submodule, and the blob is read by its object id.
    """
    if not (_is_safe_revision(revision) and _is_safe_relpath(rel_path)):
        return None
    try:
        if (object_id := _regular_file_object(repo_dir, revision, rel_path)) is None:
            return None
        proc = run_subprocess(
            ["git", "cat-file", "blob", object_id], cwd=repo_dir, quiet=True, local_read=True
        )
    except Exception as exc:
        logger.debug("Could not read %s at %s: %s", rel_path, revision, exc)
        return None
    return proc.stdout if proc.returncode == 0 else None


def resolve_merge_base(repo_dir: Path, base: str, head: str = "HEAD") -> str | None:
    """The merge base of `base` and `head`; `base` itself when git finds none, None if refused."""
    if not (_is_safe_revision(base) and _is_safe_revision(head)):
        return None
    try:
        proc = run_subprocess(
            ["git", "merge-base", "--", base, head], cwd=repo_dir, quiet=True, local_read=True
        )
    except Exception as exc:
        logger.debug("Could not resolve the merge base of %s and %s: %s", base, head, exc)
        return base
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else base


def list_changed_files(repo_dir: Path, base: str, head: str | None = None) -> list[ChangedFile]:
    """The files `git diff <base> [<head>]` changes, renames detected; without `head`, the
    working tree's changes. A refused revision or a failed diff lists nothing.

    `-z` leaves paths unquoted and gives a rename's old and new path as separate fields. The
    plain format prints `R088<TAB>old.py<TAB>new.py`, which split once reads as one path.
    """
    if head is not None and not (_is_safe_revision(base) and _is_safe_revision(head)):
        return []
    if head is None and not _is_safe_revision(base):
        return []
    ref_arg = [f"{base}...{head}"] if head is not None else [base]
    cmd = ["git", "diff", "--name-status", "-z", "--find-renames", *ref_arg, "--"]
    try:
        proc = run_subprocess(cmd, cwd=repo_dir, quiet=True, local_read=True)
        if proc.returncode != 0 and head is not None:
            fallback_cmd = [
                "git",
                "diff",
                "--name-status",
                "-z",
                "--find-renames",
                base,
                head,
                "--",
            ]
            proc = run_subprocess(fallback_cmd, cwd=repo_dir, quiet=True, local_read=True)
    except Exception as exc:
        logger.debug("Could not list the files changed since %s: %s", base, exc)
        return []
    return _parse_name_status(proc.stdout) if proc.returncode == 0 else []


def _parse_name_status(output: str) -> list[ChangedFile]:
    """Read `--name-status -z` output: a status, then one path, or the old and new for a copy or
    rename, every field ending in NUL."""
    fields = iter(output.split("\0"))
    changes: list[ChangedFile] = []
    for status in filter(None, fields):
        letter = status[0]
        old_path = next(fields, "") if letter in CONST_GIT_NAME_STATUS_TWO_PATH_LETTERS else None
        change_type = CONST_GIT_NAME_STATUS_CHANGE_TYPES.get(letter, "unknown")
        changes.append(
            ChangedFile(change_type=change_type, path=next(fields, ""), old_path=old_path)
        )
    return changes


def git_show_toplevel(path: Path) -> Path | None:
    """The repository root enclosing `path`, via `git rev-parse --show-toplevel`, or None."""
    target = path if path.is_dir() else path.parent
    try:
        proc = run_subprocess(
            ["git", "-C", str(target), "rev-parse", "--show-toplevel"],
            quiet=True,
            local_read=True,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return Path(proc.stdout.strip()).resolve()
    except Exception:
        pass
    return None
