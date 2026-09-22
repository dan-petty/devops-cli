"""Git repository operations using GitPython and git CLI subprocesses.

Functionality:
- URL normalization: forces HTTPS for web URLs while leaving SSH URLs intact.
- SSH known_hosts management: ensures GitHub host key presence in `~/.ssh/known_hosts` (mode 0600).
- Branch management: listing, tracking branch pull, and merged branch deletion.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path

import git as gitlib

from devops_cli.config.constants import (
    CONST_GIT_DIR_NAME,
    CONST_GITHUB_HOST,
    CONST_GITHUB_HTTP_PREFIX,
    CONST_GITHUB_HTTPS_PREFIX,
    CONST_GITHUB_SSH_PREFIX,
    CONST_GITHUB_SSH_URL_PREFIX,
    CONST_PERM_DIR,
    CONST_URL_SCHEME_HTTP,
    CONST_URL_SCHEME_HTTPS,
)
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.crypto.host_keys import (
    HostKey,
    HostKeyVerificationError,
    is_pinned_host,
    parse_host_keys,
    select_verified_key,
)
from devops_cli.crypto.known_hosts import append_entry, format_entry, has_trusted_host_key
from devops_cli.exceptions import (
    BranchAlreadyExistsError,
    GitOperationError,
    InvalidBranchNameError,
)
from devops_cli.models.git import BranchListing

logger = logging.getLogger(__name__)


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


def _is_host_in_known_hosts(hostname: str, known_hosts: Path) -> bool:
    """Check whether *hostname* already has a trusted key on file.

    Parsed in-process rather than through `ssh-keygen -F`: that required the OpenSSH client
    to be installed and cost a process spawn per check. A key carrying an `@revoked` marker
    does not count as trusted, so a withdrawn key is re-verified rather than relied upon.
    """
    return has_trusted_host_key(known_hosts, hostname)


def _scan_host_key(hostname: str) -> str | None:
    """Scan the ed25519 host key for *hostname* via ssh-keyscan."""
    result = run_subprocess(
        ["ssh-keyscan", "-t", "ed25519", hostname],
        capture_output=True,
        text=True,
        check=False,
        quiet=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    if result.returncode != 0 or not result.stdout.strip() or hostname not in result.stdout:
        logger.debug(
            "Failed scanning SSH host key for %s (exit code %s)", hostname, result.returncode
        )
        return None
    return result.stdout


def _append_known_host_entry(known_hosts: Path, entry: str) -> None:
    """Safely append a host key entry to known_hosts with secure file permissions."""
    append_entry(known_hosts, entry)


def _verified_host_key(hostname: str, scan_output: str) -> HostKey:
    """Select the scanned key whose fingerprint matches what the host's operator publishes.

    Raises :class:`GitOperationError` when none does. `ssh-keyscan` reports whatever the
    network returns and verifies nothing, so without this step an intercepted first
    connection pins the interceptor's key permanently and silently.
    """
    try:
        return select_verified_key(parse_host_keys(scan_output), hostname)
    except HostKeyVerificationError as exc:
        raise GitOperationError(str(exc)) from exc


def _ensure_known_host(
    hostname: str = CONST_GITHUB_HOST, *, allow_unverified: bool = False
) -> None:
    """Add *hostname* to ~/.ssh/known_hosts, verifying the key before trusting it.

    Verification fails closed. A key that cannot be checked against published fingerprints
    is not written, because accepting it anyway is indistinguishable from having no check:
    that was the previous behaviour, and it meant anyone able to intercept the first
    connection had their key trusted for every clone afterwards.

    `allow_unverified` restores trust-on-first-use for hosts that publish no fingerprints,
    and is refused for hosts that do -- there, an unverifiable key is a signal, not a gap.
    """
    ssh_dir = Path.home() / ".ssh"
    known_hosts = ssh_dir / "known_hosts"
    ssh_dir.mkdir(mode=CONST_PERM_DIR, parents=True, exist_ok=True)
    if _is_host_in_known_hosts(hostname, known_hosts):
        return

    scan_output = _scan_host_key(hostname)
    if not scan_output:
        return

    if allow_unverified and not is_pinned_host(hostname):
        keys = parse_host_keys(scan_output)
        if not keys:
            return
        logger.warning(
            "Trusting unverified host key for '%s' (%s); no published fingerprints are "
            "pinned for this host.",
            hostname,
            keys[0].fingerprint,
        )
        _append_known_host_entry(
            known_hosts, format_entry(hostname, keys[0].key_type, keys[0].key_data)
        )
        return

    key = _verified_host_key(hostname, scan_output)
    # Written under the hostname that was requested, not the one the scan claimed, so a
    # response naming a different host cannot pin a key under that name.
    _append_known_host_entry(known_hosts, format_entry(hostname, key.key_type, key.key_data))


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
    """Normalize clone url and ensure host key is known for SSH clones."""
    normalized_url = _normalize_clone_url(url)
    if normalized_url.startswith((CONST_GITHUB_SSH_PREFIX, CONST_GITHUB_SSH_URL_PREFIX)):
        _ensure_known_host()
    return normalized_url


def clone_repo(url: str, dest: Path) -> None:
    """Clone a repository to *dest*."""
    _validate_clone_dest(dest)
    normalized_url = _prepare_clone_url(url)
    gitlib.Repo.clone_from(normalized_url, str(dest))


def fetch_all(repo_dir: Path) -> None:
    """Fetch all remotes with pruning."""
    repo = gitlib.Repo(str(repo_dir))
    for remote in repo.remotes:
        try:
            remote.fetch(prune=True)
        except gitlib.GitCommandError:
            pass


def pull_tracking(repo_dir: Path) -> None:
    """Pull the current tracking branch if one is configured."""
    repo = gitlib.Repo(str(repo_dir))
    try:
        if not repo.head.is_detached:
            tracking = repo.active_branch.tracking_branch()
            if tracking:
                repo.remotes[tracking.remote_name].pull(repo.active_branch.name)
    except gitlib.GitCommandError, IndexError:
        pass


def create_branch(repo_dir: Path, branch_name: str) -> None:
    """Create and checkout a new branch from the current HEAD."""
    if branch_name.startswith("-"):
        raise InvalidBranchNameError(branch_name, reason="cannot start with a hyphen")
    repo = gitlib.Repo(str(repo_dir))
    if branch_name in [b.name for b in repo.branches]:
        raise BranchAlreadyExistsError(branch_name)
    repo.git.checkout("-b", "--", branch_name)


def list_branches(
    repo_dir: Path,
    all_branches: bool = False,
) -> BranchListing:
    """Return a BranchListing with branch names and the current branch name."""
    repo = gitlib.Repo(str(repo_dir))
    current = "HEAD" if repo.head.is_detached else repo.active_branch.name
    local = sorted(b.name for b in repo.branches)
    if not all_branches:
        return BranchListing(branches=local, current=current)
    remote_names = [
        ref.name for remote in repo.remotes for ref in remote.refs if not ref.name.endswith("/HEAD")
    ]
    return BranchListing(branches=sorted(set(local) | set(remote_names)), current=current)


def delete_merged_branches(repo_dir: Path, dry_run: bool = False) -> list[str]:
    """Delete local branches that have been merged into the default branch."""
    repo = gitlib.Repo(str(repo_dir))
    default = next(
        (b.name for b in repo.branches if b.name in ("main", "master")),
        repo.branches[0].name if repo.branches else None,
    )
    if not default:
        return []

    merged_output = repo.git.branch("--merged", default)
    merged = {b.strip().lstrip("* ") for b in merged_output.splitlines()}
    protected = {default, "main", "master"}
    to_delete = [b for b in repo.branches if b.name in merged - protected]

    deleted: list[str] = []
    for branch in to_delete:
        if not dry_run:
            repo.delete_head(branch, force=False)
        deleted.append(branch.name)
    return deleted


def is_git_clean(repo_dir: Path) -> bool:
    """Check whether git working directory has uncommitted changes."""
    try:
        proc = run_subprocess(["git", "status", "--porcelain"], cwd=repo_dir, quiet=True)
        return proc.returncode == 0 and not bool(proc.stdout.strip())
    except Exception:
        return False


def get_latest_git_tag(repo_dir: Path) -> str | None:
    """Retrieve latest git tag for the repository if available."""
    try:
        proc = run_subprocess(["git", "describe", "--tags", "--abbrev=0"], cwd=repo_dir, quiet=True)
        if proc.returncode == 0 and proc.stdout:
            return str(proc.stdout).strip()
    except Exception:
        pass
    return None
