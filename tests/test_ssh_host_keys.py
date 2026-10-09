"""Test suite for GitHub SSH known_hosts pinning, OpenSSH trust, and clone error wrapping."""

from __future__ import annotations

import base64
import stat
from pathlib import Path
from unittest.mock import patch

import git as gitlib
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from typer.testing import CliRunner

from devops_cli.commands.repos import app as repos_app
from devops_cli.config.constants import CONST_GITHUB_KNOWN_HOSTS_LINES
from devops_cli.exceptions import GitOperationError
from devops_cli.git.operations import _ensure_known_host, clone_repo

runner = CliRunner()

# Published fingerprints from https://api.github.com/meta (.ssh_key_fingerprints)
# and https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints
_PUBLISHED_FINGERPRINTS: dict[str, str] = {
    "ssh-ed25519": "+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU",
    "ecdsa-sha2-nistp256": "p2QAMXNIC1TJYWeIOttrVc98/R1BUFWu3/LiyKgUfQM",
    "ssh-rsa": "uNiVztksCsDhcc0u9e8BujQXVUpKZIDTMczCvj3tD2s",
}


# =============================================================================
# 1. Structure & Fingerprint Tests
# =============================================================================


def test_github_known_hosts_lines_structure() -> None:
    """Each pinned line has host github.com and round-trips through cryptography."""
    assert len(CONST_GITHUB_KNOWN_HOSTS_LINES) == 3
    for line in CONST_GITHUB_KNOWN_HOSTS_LINES:
        host, sep, rest = line.partition(" ")
        assert (host, sep) == ("github.com", " ")
        key = serialization.load_ssh_public_key(rest.encode("ascii"))
        reencoded = key.public_bytes(
            serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
        ).decode("ascii")
        assert reencoded == rest


def test_github_known_hosts_lines_fingerprints() -> None:
    """Each pinned key reproduces GitHub's published SHA256 fingerprint."""
    for line in CONST_GITHUB_KNOWN_HOSTS_LINES:
        _, _, rest = line.partition(" ")
        key_type = rest.split()[0]
        key = serialization.load_ssh_public_key(rest.encode("ascii"))
        raw_fp = serialization.ssh_key_fingerprint(key, hashes.SHA256())
        b64_fp = base64.b64encode(raw_fp).decode("ascii").rstrip("=")
        assert (key_type, b64_fp) == (key_type, _PUBLISHED_FINGERPRINTS[key_type])


# =============================================================================
# 2. Writing Pinned Lines to known_hosts
# =============================================================================


def test_ensure_known_host_writes_file_and_dir_modes(tmp_path: Path) -> None:
    """Verify lines are written with file mode 0600 and directory mode 0700."""
    _ensure_known_host.cache_clear()
    known_hosts = tmp_path / ".ssh" / "known_hosts"

    with patch("subprocess.run") as mock_subproc, patch("subprocess.Popen") as mock_popen:
        _ensure_known_host(known_hosts)
        assert (mock_subproc.called, mock_popen.called) == (False, False)

    content = known_hosts.read_text(encoding="utf-8")
    for line in CONST_GITHUB_KNOWN_HOSTS_LINES:
        assert line in content

    file_mode = oct(stat.S_IMODE(known_hosts.stat().st_mode))
    dir_mode = oct(stat.S_IMODE(known_hosts.parent.stat().st_mode))
    assert (file_mode, dir_mode) == ("0o600", "0o700")

    # A second run adds nothing
    _ensure_known_host.cache_clear()
    _ensure_known_host(known_hosts)
    assert known_hosts.read_text(encoding="utf-8") == content


def test_ensure_known_host_preserves_file_without_trailing_newline(tmp_path: Path) -> None:
    """A file missing a trailing newline is not corrupted by appending."""
    _ensure_known_host.cache_clear()
    known_hosts = tmp_path / ".ssh" / "known_hosts"
    known_hosts.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    known_hosts.write_text("example.com ssh-ed25519 AAAApreexisting", encoding="utf-8")

    _ensure_known_host(known_hosts)
    content = known_hosts.read_text(encoding="utf-8")
    assert content.startswith("example.com ssh-ed25519 AAAApreexisting\n")
    for line in CONST_GITHUB_KNOWN_HOSTS_LINES:
        assert line in content


def test_ensure_known_host_unwritable_directory_logs_warning(tmp_path: Path) -> None:
    """An unwritable directory logs one warning and allows clone to continue."""
    _ensure_known_host.cache_clear()
    unwritable = tmp_path / "read_only_ssh" / "known_hosts"

    with patch("pathlib.Path.mkdir", side_effect=PermissionError("Read-only filesystem")):
        with patch("devops_cli.git.operations.logger.warning") as mock_warn:
            _ensure_known_host(unwritable)
            # Second call in same process is cached and logs no additional warning
            _ensure_known_host(unwritable)
            assert mock_warn.call_count == 1


# =============================================================================
# 3. Regression: Fail-Open Junk Lines Do Not Prevent Pinning
# =============================================================================


@pytest.mark.parametrize(
    "junk_line",
    [
        "@cert-authority github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICA",
        "@cert-authority * ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICA",
        "@foo github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICA",
        "github.com ssh-ed25519 AAAA",
        "github.com ssh-ed25519 not_valid_base64!!!",
        "github.com ssh-dss AAAAB3NzaC1kc3MAAACBA",
        "@revoked github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOldRevoked",
        "|1|0123456789abcdef0123|abcdefghijklmnopqrstuvwx= ssh-ed25519 AAAAC3NzaC1",
    ],
)
def test_junk_known_hosts_lines_do_not_skip_pinning(junk_line: str, tmp_path: Path) -> None:
    """Existing junk, marker, or revoked lines are preserved verbatim and pinned lines appended."""
    _ensure_known_host.cache_clear()
    known_hosts = tmp_path / ".ssh" / "known_hosts"
    known_hosts.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    known_hosts.write_text(f"{junk_line}\n", encoding="utf-8")

    _ensure_known_host(known_hosts)

    content = known_hosts.read_text(encoding="utf-8")
    assert content.startswith(f"{junk_line}\n")
    for line in CONST_GITHUB_KNOWN_HOSTS_LINES:
        assert line in content


# =============================================================================
# 4. Every URL Spelling Triggers Pinning
# =============================================================================


@pytest.mark.parametrize(
    "url",
    [
        "git@GitHub.com:org/repo.git",
        "ssh://git@github.com:22/org/repo.git",
        "ssh://GIT@GITHUB.COM/org/repo.git",
        "ssh://github.com/org/repo.git",
        "git+ssh://git@github.com/org/repo.git",
        "github.com:org/repo",
        "org-123@github.com:org/repo.git",
        "gh-work:org/repo.git",
        "https://github.com/org/repo.git",
    ],
)
def test_clone_repo_pins_known_hosts_for_all_spellings(url: str, tmp_path: Path) -> None:
    """The write runs for every URL passed to clone_repo with no URL filtering."""
    with (
        patch("devops_cli.git.operations._ensure_known_host") as mock_ensure,
        patch("devops_cli.git.operations.gitlib.Repo.clone_from"),
    ):
        clone_repo(url, tmp_path / "dest")
        assert mock_ensure.call_count == 1


# =============================================================================
# 5. Clone Error Wrapping & Credential Masking
# =============================================================================


def test_clone_repo_wraps_git_command_error_with_masked_stderr(tmp_path: Path) -> None:
    """GitCommandError is wrapped in GitOperationError carrying masked stderr."""
    ssh_err = (
        "Host key for github.com has changed and you have requested strict checking.\n"
        "Host key verification failed.\n"
        "fatal: Could not read from remote repository 'https://user:secret@example.com/o/r.git'."
    )
    fake_cmd_err = gitlib.GitCommandError("clone", 128, stderr=ssh_err)

    with (
        patch("devops_cli.git.operations._ensure_known_host"),
        patch("devops_cli.git.operations.gitlib.Repo.clone_from", side_effect=fake_cmd_err),
    ):
        with pytest.raises(GitOperationError) as exc_info:
            clone_repo("git@github.com:org/repo.git", tmp_path / "dest")

    msg = str(exc_info.value)
    assert (
        "Host key for github.com has changed and you have requested strict checking." in msg,
        "Host key verification failed." in msg,
        "user:secret" not in msg,
    ) == (True, True, True)


def test_devops_repos_clone_cli_exits_nonzero_with_no_traceback(tmp_path: Path) -> None:
    """CLI devops repos clone exits non-zero with clean error and no traceback on failure."""
    fake_cmd_err = gitlib.GitCommandError(
        "clone", 128, stderr="Host key verification failed for github.com"
    )

    with (
        patch("devops_cli.git.operations._ensure_known_host"),
        patch("devops_cli.git.operations.gitlib.Repo.clone_from", side_effect=fake_cmd_err),
        patch("devops_cli.commands.repos.load_settings"),
    ):
        dest = tmp_path / "clone_target"
        res = runner.invoke(repos_app, ["clone", "git@github.com:org/repo.git", str(dest)])
        assert (res.exit_code != 0, "Traceback" not in res.output) == (True, True)
