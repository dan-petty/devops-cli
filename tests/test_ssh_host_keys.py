"""Test suite for known_hosts parsing and SSH host key verification."""

from __future__ import annotations

import base64
import hashlib
import hmac
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.config.constants import CONST_GITHUB_HOST_KEY_FINGERPRINTS
from devops_cli.crypto.host_keys import (
    HostKey,
    HostKeyVerificationError,
    is_pinned_host,
    parse_host_key_line,
    parse_host_keys,
    published_fingerprints,
    select_verified_key,
    verify_fingerprint,
)
from devops_cli.crypto.known_hosts import (
    append_entry,
    find_host_entries,
    format_entry,
    has_trusted_host_key,
    is_key_revoked,
    parse_known_hosts,
    parse_line,
)
from devops_cli.exceptions import GitOperationError
from devops_cli.git.operations import _ensure_known_host, _is_host_in_known_hosts

# GitHub's published host keys, as served by https://api.github.com/meta over TLS.
GITHUB_ED25519 = "AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl"
GITHUB_ED25519_FINGERPRINT = "SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU"
GITHUB_ECDSA = (
    "AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBEmKSENjQEezOmxkZMy7opKgwFB9"
    "nkt5YRrYMjNuG5N87uRgg6CLrbo5wAdT/y6v0mKV0U2w0WZ2YB/++Tpockg="
)
# A syntactically valid key that is not GitHub's: what an interception would look like.
HOSTILE_ED25519 = "AAAAC3NzaC1lZDI1NTE5AAAAIBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"


def hashed_host(hostname: str, salt: bytes = b"0123456789abcdef0123") -> str:
    """Build the hashed host field OpenSSH writes with `HashKnownHosts yes`."""
    digest = hmac.new(salt, hostname.encode(), hashlib.sha1).digest()
    return f"|1|{base64.b64encode(salt).decode()}|{base64.b64encode(digest).decode()}"


def write_known_hosts(path: Path, *lines: str) -> Path:
    """Write a known_hosts file from the given lines."""
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# =============================================================================
# known_hosts Parsing
# =============================================================================


def test_a_plain_entry_is_parsed_into_its_fields() -> None:
    """The ordinary case: one host, one key type, one key."""
    entry = parse_line(f"github.com ssh-ed25519 {GITHUB_ED25519} comment here")
    assert entry is not None
    assert (entry.patterns, entry.key_type, entry.key_data, entry.comment) == (
        ("github.com",),
        "ssh-ed25519",
        GITHUB_ED25519,
        "comment here",
    )


@pytest.mark.parametrize(
    ("description", "line"),
    [
        ("blank", ""),
        ("whitespace", "   "),
        ("comment", "# a comment"),
        ("too few fields", "github.com ssh-ed25519"),
        ("host only", "github.com"),
        ("malformed hash", "|1|onlysalt ssh-ed25519 AAAA"),
    ],
)
def test_unusable_lines_are_skipped(description: str, line: str) -> None:
    """A line that is not an entry yields nothing rather than a half-built one."""
    assert parse_line(line) is None, description


def test_a_comma_separated_alias_list_matches_every_alias() -> None:
    """OpenSSH records a host and its addresses on one line."""
    entry = parse_line(f"github.com,140.82.121.4 ssh-ed25519 {GITHUB_ED25519}")
    assert entry is not None
    assert (entry.matches("github.com"), entry.matches("140.82.121.4")) == (True, True)


def test_a_wildcard_pattern_matches_subdomains() -> None:
    """Wildcards are why a substring search is not equivalent to ssh-keygen -F."""
    entry = parse_line(f"*.example.com ssh-ed25519 {GITHUB_ED25519}")
    assert entry is not None
    assert (entry.matches("git.example.com"), entry.matches("example.com")) == (True, False)


def test_a_negated_pattern_excludes_a_host_from_a_wildcard() -> None:
    """A negation anywhere in the list excludes the host outright."""
    entry = parse_line(f"*.example.com,!secret.example.com ssh-ed25519 {GITHUB_ED25519}")
    assert entry is not None
    assert (entry.matches("git.example.com"), entry.matches("secret.example.com")) == (
        True,
        False,
    )


def test_host_matching_is_case_insensitive() -> None:
    """Hostnames are case-insensitive; treating them otherwise splits one host in two."""
    entry = parse_line(f"GitHub.com ssh-ed25519 {GITHUB_ED25519}")
    assert entry is not None
    assert entry.matches("github.com") is True


def test_a_non_default_port_is_matched_in_its_bracketed_form() -> None:
    """OpenSSH records a non-default port as [host]:port."""
    entry = parse_line(f"[git.example.com]:2222 ssh-ed25519 {GITHUB_ED25519}")
    assert entry is not None
    assert (entry.matches("git.example.com", 2222), entry.matches("git.example.com")) == (
        True,
        False,
    )


def test_the_default_port_is_matched_bare() -> None:
    """Port 22 is written without brackets, so both spellings must resolve."""
    entry = parse_line(f"git.example.com ssh-ed25519 {GITHUB_ED25519}")
    assert entry is not None
    assert entry.matches("git.example.com", 22) is True


def test_a_hashed_hostname_is_matched_by_recomputing_its_digest() -> None:
    """With HashKnownHosts enabled the hostname is not present in the file at all.

    A substring search finds nothing, so the host is scanned and re-added on every
    operation -- and never verified against what is already recorded.
    """
    entry = parse_line(f"{hashed_host('github.com')} ssh-ed25519 {GITHUB_ED25519}")
    assert entry is not None
    assert (entry.is_hashed, entry.matches("github.com"), entry.matches("gitlab.com")) == (
        True,
        True,
        False,
    )


def test_a_hashed_entry_with_undecodable_material_matches_nothing() -> None:
    """A corrupt hash must not raise on every lookup."""
    entry = parse_line(f"|1|!!!notbase64!!!|alsobad ssh-ed25519 {GITHUB_ED25519}")
    assert entry is not None
    assert entry.matches("github.com") is False


def test_a_revoked_marker_is_recognised() -> None:
    """A revocation withdraws trust rather than granting it."""
    entry = parse_line(f"@revoked github.com ssh-ed25519 {HOSTILE_ED25519}")
    assert entry is not None
    assert (entry.is_revoked, entry.is_cert_authority) == (True, False)


def test_a_cert_authority_marker_is_recognised() -> None:
    """A CA line delegates trust and is not itself a host key."""
    entry = parse_line(f"@cert-authority *.example.com ssh-ed25519 {GITHUB_ED25519}")
    assert entry is not None
    assert entry.is_cert_authority is True


def test_a_file_is_parsed_line_by_line_with_numbers(tmp_path: Path) -> None:
    """Line numbers make a malformed entry findable."""
    path = write_known_hosts(
        tmp_path / "known_hosts",
        "# comment",
        f"github.com ssh-ed25519 {GITHUB_ED25519}",
        "",
        f"gitlab.com ssh-ed25519 {GITHUB_ECDSA}",
    )
    entries = parse_known_hosts(path)
    assert [(entry.patterns[0], entry.line_number) for entry in entries] == [
        ("github.com", 2),
        ("gitlab.com", 4),
    ]


def test_one_malformed_line_does_not_discard_the_file(tmp_path: Path) -> None:
    """Losing the rest of the file would drop a @revoked marker recorded further down."""
    path = write_known_hosts(
        tmp_path / "known_hosts",
        "garbage",
        f"github.com ssh-ed25519 {GITHUB_ED25519}",
    )
    assert len(parse_known_hosts(path)) == 1


def test_an_unreadable_file_yields_no_entries(tmp_path: Path) -> None:
    """A missing or unreadable file is not an error at this layer."""
    assert parse_known_hosts(tmp_path / "absent") == []


# =============================================================================
# Membership
# =============================================================================


def test_a_recorded_host_is_found(tmp_path: Path) -> None:
    """The pure-Python replacement for `ssh-keygen -F`."""
    path = write_known_hosts(tmp_path / "kh", f"github.com ssh-ed25519 {GITHUB_ED25519}")
    assert has_trusted_host_key(path, "github.com") is True


def test_an_unrecorded_host_is_not_found(tmp_path: Path) -> None:
    """A host with no entry is not trusted."""
    path = write_known_hosts(tmp_path / "kh", f"github.com ssh-ed25519 {GITHUB_ED25519}")
    assert has_trusted_host_key(path, "gitlab.com") is False


def test_a_missing_file_means_no_host_is_trusted(tmp_path: Path) -> None:
    """A fresh machine has no known_hosts at all."""
    assert has_trusted_host_key(tmp_path / "absent", "github.com") is False


def test_a_host_with_only_a_revoked_key_is_not_trusted(tmp_path: Path) -> None:
    """Treating a revocation as trust would skip verification and keep the withdrawn key.

    This is the case `ssh-keygen -F` gets right and a substring search gets exactly
    backwards: the host *is* mentioned in the file, but not as trusted.
    """
    path = write_known_hosts(tmp_path / "kh", f"@revoked github.com ssh-ed25519 {HOSTILE_ED25519}")
    assert has_trusted_host_key(path, "github.com") is False


def test_a_host_with_a_revoked_and_a_valid_key_is_trusted(tmp_path: Path) -> None:
    """One withdrawn key does not invalidate a good one recorded alongside it."""
    path = write_known_hosts(
        tmp_path / "kh",
        f"@revoked github.com ssh-ed25519 {HOSTILE_ED25519}",
        f"github.com ssh-ed25519 {GITHUB_ED25519}",
    )
    assert has_trusted_host_key(path, "github.com") is True


def test_a_specific_revoked_key_is_identifiable(tmp_path: Path) -> None:
    """Revocation applies to a key, not to the host."""
    path = write_known_hosts(tmp_path / "kh", f"@revoked github.com ssh-ed25519 {HOSTILE_ED25519}")
    assert (
        is_key_revoked(path, "github.com", HOSTILE_ED25519),
        is_key_revoked(path, "github.com", GITHUB_ED25519),
    ) == (True, False)


def test_every_entry_for_a_host_is_returned(tmp_path: Path) -> None:
    """A host commonly has several key types on file."""
    path = write_known_hosts(
        tmp_path / "kh",
        f"github.com ssh-ed25519 {GITHUB_ED25519}",
        f"github.com ecdsa-sha2-nistp256 {GITHUB_ECDSA}",
    )
    assert len(find_host_entries(path, "github.com")) == 2


# =============================================================================
# Writing Entries
# =============================================================================


def test_an_entry_is_appended_with_restrictive_permissions(tmp_path: Path) -> None:
    """known_hosts is written into the user's ssh directory."""
    path = tmp_path / "kh"
    append_entry(path, format_entry("github.com", "ssh-ed25519", GITHUB_ED25519))
    assert (GITHUB_ED25519 in path.read_text(), oct(path.stat().st_mode & 0o777)) == (
        True,
        "0o600",
    )


def test_appending_to_a_file_without_a_trailing_newline_does_not_corrupt_it(
    tmp_path: Path,
) -> None:
    """Concatenating onto the previous entry would break both lines."""
    path = tmp_path / "kh"
    path.write_text("gitlab.com ssh-ed25519 AAAA", encoding="utf-8")
    append_entry(path, "github.com ssh-ed25519 BBBB")
    assert path.read_text() == "gitlab.com ssh-ed25519 AAAA\ngithub.com ssh-ed25519 BBBB\n"


def test_appending_does_not_introduce_blank_lines(tmp_path: Path) -> None:
    """A file already ending in a newline needs no extra one."""
    path = tmp_path / "kh"
    path.write_text("gitlab.com ssh-ed25519 AAAA\n", encoding="utf-8")
    append_entry(path, "github.com ssh-ed25519 BBBB")
    assert "\n\n" not in path.read_text()


def test_appending_an_empty_entry_is_a_no_op(tmp_path: Path) -> None:
    """A blank line carries no key and must not be written."""
    path = tmp_path / "kh"
    path.write_text("existing\n", encoding="utf-8")
    append_entry(path, "   ")
    assert path.read_text() == "existing\n"


def test_appending_creates_the_ssh_directory(tmp_path: Path) -> None:
    """A fresh machine has no ~/.ssh yet."""
    path = tmp_path / "nested" / "kh"
    append_entry(path, "github.com ssh-ed25519 AAAA")
    assert path.exists()


# =============================================================================
# Fingerprints
# =============================================================================


def test_a_fingerprint_matches_what_the_host_operator_publishes() -> None:
    """Computed independently from the raw key and compared with GitHub's own value.

    If this implementation disagreed with OpenSSH's, every comparison against a published
    fingerprint would fail and verification would be useless.
    """
    key = HostKey("github.com", "ssh-ed25519", GITHUB_ED25519)
    assert key.fingerprint == GITHUB_ED25519_FINGERPRINT


def test_a_fingerprint_is_unpadded_base64_as_openssh_prints_it() -> None:
    """Padding or hex would not compare equal to what a user reads from documentation."""
    fingerprint = HostKey("h", "ssh-ed25519", GITHUB_ED25519).fingerprint
    assert (fingerprint.startswith("SHA256:"), fingerprint.endswith("=")) == (True, False)


def test_every_published_github_key_verifies_against_the_pinned_set() -> None:
    """The pinned fingerprints must actually match the keys GitHub serves."""
    keys = [
        HostKey("github.com", "ssh-ed25519", GITHUB_ED25519),
        HostKey("github.com", "ecdsa-sha2-nistp256", GITHUB_ECDSA),
    ]
    assert all(verify_fingerprint(key, CONST_GITHUB_HOST_KEY_FINGERPRINTS) for key in keys)


def test_a_key_that_is_not_githubs_does_not_verify() -> None:
    """The check has to actually reject something."""
    hostile = HostKey("github.com", "ssh-ed25519", HOSTILE_ED25519)
    assert verify_fingerprint(hostile, CONST_GITHUB_HOST_KEY_FINGERPRINTS) is False


def test_github_is_a_pinned_host_and_an_arbitrary_host_is_not() -> None:
    """Only hosts publishing fingerprints can be verified automatically."""
    assert (is_pinned_host("github.com"), is_pinned_host("git.example.com")) == (True, False)


def test_an_unpinned_host_has_no_published_fingerprints() -> None:
    """An empty set is what makes verification fail closed for unknown hosts."""
    assert published_fingerprints("git.example.com") == frozenset()


# =============================================================================
# Host Key Parsing
# =============================================================================


def test_a_keyscan_line_is_parsed() -> None:
    """The ordinary output of ssh-keyscan."""
    key = parse_host_key_line(f"github.com ssh-ed25519 {GITHUB_ED25519}")
    assert key is not None
    assert (key.hostname, key.key_type, key.key_data) == (
        "github.com",
        "ssh-ed25519",
        GITHUB_ED25519,
    )


@pytest.mark.parametrize(
    ("description", "line"),
    [
        ("blank", ""),
        ("comment banner", "# github.com:22 SSH-2.0-babeld"),
        ("too few fields", "github.com ssh-ed25519"),
        ("unsupported key type", "github.com ssh-dss AAAAB3NzaC1kc3M="),
        ("undecodable key material", "github.com ssh-ed25519 !!!not-base64!!!"),
    ],
)
def test_unusable_keyscan_lines_are_rejected(description: str, line: str) -> None:
    """An entry that is not a usable key must not reach known_hosts.

    Writing one silently breaks every later connection to that host, which presents as an
    unrelated failure long after the cause.
    """
    assert parse_host_key_line(line) is None, description


def test_keyscan_output_with_banners_yields_only_the_keys() -> None:
    """ssh-keyscan interleaves informational comments with the keys."""
    output = (
        "# github.com:22 SSH-2.0-babeld\n"
        f"github.com ssh-ed25519 {GITHUB_ED25519}\n"
        "# github.com:22 SSH-2.0-babeld\n"
        f"github.com ecdsa-sha2-nistp256 {GITHUB_ECDSA}\n"
    )
    assert [key.key_type for key in parse_host_keys(output)] == [
        "ssh-ed25519",
        "ecdsa-sha2-nistp256",
    ]


def test_a_host_key_renders_as_a_known_hosts_line() -> None:
    """What is verified is what gets written."""
    key = HostKey("github.com", "ssh-ed25519", GITHUB_ED25519)
    assert key.to_known_hosts_line() == f"github.com ssh-ed25519 {GITHUB_ED25519}"


# =============================================================================
# Verification
# =============================================================================


def test_the_genuine_key_is_selected_from_a_scan() -> None:
    """Verification picks the key that matches a published fingerprint."""
    keys = parse_host_keys(
        f"github.com ssh-ed25519 {HOSTILE_ED25519}\ngithub.com ssh-ed25519 {GITHUB_ED25519}\n"
    )
    assert select_verified_key(keys, "github.com").key_data == GITHUB_ED25519


def test_a_scan_returning_only_an_unrecognised_key_is_refused() -> None:
    """Failing closed is the point; accepting anyway is the defect this replaces."""
    keys = parse_host_keys(f"github.com ssh-ed25519 {HOSTILE_ED25519}")
    with pytest.raises(HostKeyVerificationError, match="does not match any published"):
        select_verified_key(keys, "github.com")


def test_the_refusal_names_the_fingerprint_that_was_offered() -> None:
    """An operator resolving a legitimate rotation needs to see what was presented."""
    keys = parse_host_keys(f"github.com ssh-ed25519 {HOSTILE_ED25519}")
    with pytest.raises(HostKeyVerificationError, match="SHA256:"):
        select_verified_key(keys, "github.com")


def test_a_host_with_no_published_fingerprints_cannot_be_verified() -> None:
    """Silently succeeding would make the check meaningless for unknown hosts."""
    keys = parse_host_keys(f"git.example.com ssh-ed25519 {GITHUB_ED25519}")
    with pytest.raises(HostKeyVerificationError, match="No published fingerprints"):
        select_verified_key(keys, "git.example.com")


def test_an_empty_scan_is_refused() -> None:
    """No key is not a verified key."""
    with pytest.raises(HostKeyVerificationError, match="No usable host key"):
        select_verified_key([], "github.com")


# =============================================================================
# Integration: _ensure_known_host
# =============================================================================


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ~/.ssh into a temporary directory."""
    home = tmp_path / "home"
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    return home


def _scan_returning(output: str) -> Any:
    """Patch the subprocess runner so ssh-keyscan returns the given output."""
    return patch(
        "devops_cli.git.operations.run_subprocess",
        return_value=MagicMock(returncode=0, stdout=output),
    )


def test_a_genuine_github_key_is_recorded(fake_home: Path) -> None:
    """The ordinary path still works."""
    with _scan_returning(f"github.com ssh-ed25519 {GITHUB_ED25519}\n"):
        _ensure_known_host("github.com")
    assert GITHUB_ED25519 in (fake_home / ".ssh" / "known_hosts").read_text()


def test_an_intercepted_key_is_refused_and_nothing_is_written(fake_home: Path) -> None:
    """The defect this task fixes.

    Previously the scanned key was appended unconditionally, so anyone able to intercept
    the first connection had their key pinned permanently and silently, for every clone
    afterwards.
    """
    known_hosts = fake_home / ".ssh" / "known_hosts"
    with _scan_returning(f"github.com ssh-ed25519 {HOSTILE_ED25519}\n"):
        with pytest.raises(GitOperationError, match="does not match any published"):
            _ensure_known_host("github.com")
    assert known_hosts.exists() is False or known_hosts.read_text().strip() == ""


def test_an_already_trusted_host_is_not_rescanned(fake_home: Path) -> None:
    """A host on file needs no network round trip at all."""
    known_hosts = fake_home / ".ssh" / "known_hosts"
    known_hosts.parent.mkdir(parents=True, exist_ok=True)
    write_known_hosts(known_hosts, f"github.com ssh-ed25519 {GITHUB_ED25519}")
    with patch("devops_cli.git.operations.run_subprocess") as mock_run:
        _ensure_known_host("github.com")
        mock_run.assert_not_called()


def test_a_revoked_key_on_file_triggers_reverification(fake_home: Path) -> None:
    """A withdrawn key must not be mistaken for a trusted one."""
    known_hosts = fake_home / ".ssh" / "known_hosts"
    known_hosts.parent.mkdir(parents=True, exist_ok=True)
    write_known_hosts(known_hosts, f"@revoked github.com ssh-ed25519 {HOSTILE_ED25519}")
    with _scan_returning(f"github.com ssh-ed25519 {GITHUB_ED25519}\n"):
        _ensure_known_host("github.com")
    assert GITHUB_ED25519 in known_hosts.read_text()


def test_a_failed_scan_writes_nothing(fake_home: Path) -> None:
    """An unreachable host is not a verification failure."""
    with patch(
        "devops_cli.git.operations.run_subprocess",
        return_value=MagicMock(returncode=1, stdout=""),
    ):
        _ensure_known_host("github.com")
    assert (fake_home / ".ssh" / "known_hosts").exists() is False


def test_an_unpinned_host_is_refused_by_default(fake_home: Path) -> None:
    """Trust-on-first-use is no longer the silent default."""
    with _scan_returning(f"git.example.com ssh-ed25519 {GITHUB_ED25519}\n"):
        with pytest.raises(GitOperationError, match="No published fingerprints"):
            _ensure_known_host("git.example.com")


def test_an_unpinned_host_can_be_trusted_on_request(fake_home: Path) -> None:
    """Trust-on-first-use remains available, but the caller has to ask for it."""
    with _scan_returning(f"git.example.com ssh-ed25519 {GITHUB_ED25519}\n"):
        _ensure_known_host("git.example.com", allow_unverified=True)
    assert "git.example.com" in (fake_home / ".ssh" / "known_hosts").read_text()


def test_opting_into_unverified_trust_does_not_weaken_a_pinned_host(fake_home: Path) -> None:
    """For a host that publishes fingerprints, an unverifiable key is a signal, not a gap.

    Letting the flag override verification would reintroduce the defect behind an option.
    """
    with _scan_returning(f"github.com ssh-ed25519 {HOSTILE_ED25519}\n"):
        with pytest.raises(GitOperationError):
            _ensure_known_host("github.com", allow_unverified=True)
    known_hosts = fake_home / ".ssh" / "known_hosts"
    assert known_hosts.exists() is False or known_hosts.read_text().strip() == ""


def test_the_entry_is_written_under_the_requested_hostname(fake_home: Path) -> None:
    """The recorded name comes from the request, not from whatever the scan line said.

    ssh-keyscan reports the host and addresses it resolved; pinning the key under those
    names would trust the key for hosts that were never asked about.
    """
    with _scan_returning(f"github.com,140.82.121.4 ssh-ed25519 {GITHUB_ED25519}\n"):
        _ensure_known_host("github.com")
    content = (fake_home / ".ssh" / "known_hosts").read_text().strip()
    assert content == f"github.com ssh-ed25519 {GITHUB_ED25519}"


def test_a_scan_naming_a_different_host_is_rejected(fake_home: Path) -> None:
    """A response that does not mention the host asked about is not an answer about it."""
    with _scan_returning(f"evil.example.com ssh-ed25519 {GITHUB_ED25519}\n"):
        _ensure_known_host("github.com")
    assert (fake_home / ".ssh" / "known_hosts").exists() is False


def test_an_unusable_scan_for_an_unpinned_host_writes_nothing(fake_home: Path) -> None:
    """Banner-only output contains no key to trust."""
    with _scan_returning("# git.example.com:22 SSH-2.0-OpenSSH\n"):
        _ensure_known_host("git.example.com", allow_unverified=True)
    assert (fake_home / ".ssh" / "known_hosts").exists() is False


def test_membership_is_checked_without_spawning_a_process(tmp_path: Path) -> None:
    """The check no longer requires the OpenSSH client to be installed."""
    path = write_known_hosts(tmp_path / "kh", f"github.com ssh-ed25519 {GITHUB_ED25519}")
    with patch("devops_cli.git.operations.run_subprocess") as mock_run:
        found = _is_host_in_known_hosts("github.com", path)
        mock_run.assert_not_called()
    assert found is True


def test_a_hashed_known_hosts_file_is_matched_without_rescanning(fake_home: Path) -> None:
    """With HashKnownHosts enabled the host is absent from the file as plain text.

    A substring check finds nothing and rescans on every clone; recomputing the HMAC finds
    the entry that is genuinely there.
    """
    known_hosts = fake_home / ".ssh" / "known_hosts"
    known_hosts.parent.mkdir(parents=True, exist_ok=True)
    write_known_hosts(known_hosts, f"{hashed_host('github.com')} ssh-ed25519 {GITHUB_ED25519}")
    with patch("devops_cli.git.operations.run_subprocess") as mock_run:
        _ensure_known_host("github.com")
        mock_run.assert_not_called()


def test_an_unwritable_known_hosts_does_not_crash_the_clone(tmp_path: Path) -> None:
    """A read-only home directory should degrade, not abort the operation.

    The clone will fail its own host key check afterwards, which is the correct and visible
    outcome; raising here would obscure it with an unrelated filesystem error.
    """
    path = tmp_path / "kh"
    with patch("pathlib.Path.open", side_effect=OSError("read-only file system")):
        append_entry(path, "github.com ssh-ed25519 AAAA")
    assert path.exists() is False
