"""Pure-Python parsing and matching of OpenSSH `known_hosts` files.

Membership was previously tested by shelling out to `ssh-keygen -F`, which requires the
OpenSSH client to be installed and costs a process spawn per check. Replacing it with a
naive substring search is not equivalent: OpenSSH supports hashed hostnames, bracketed
`[host]:port` forms, comma-separated alias lists, wildcard patterns, negations, and
`@revoked` markers. A check that missed any of those would either fail to find a host that
is present, and re-add it, or — in the case of `@revoked` — report a key as trusted that
has been explicitly withdrawn.

Reference: sshd(8), "SSH_KNOWN_HOSTS FILE FORMAT".
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from devops_cli.config.constants import (
    CONST_KNOWN_HOSTS_HASH_PREFIX,
    CONST_KNOWN_HOSTS_MARKER_CERT_AUTHORITY,
    CONST_KNOWN_HOSTS_MARKER_REVOKED,
    CONST_PERM_PRIVATE_KEY,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KnownHostEntry:
    """One parsed line of a `known_hosts` file."""

    patterns: tuple[str, ...]
    key_type: str
    key_data: str
    marker: str | None = None
    comment: str = ""
    hashed_salt: str = ""
    hashed_digest: str = ""
    line_number: int = 0

    @property
    def is_revoked(self) -> bool:
        """Whether this line withdraws trust from the key rather than granting it."""
        return self.marker == CONST_KNOWN_HOSTS_MARKER_REVOKED

    @property
    def is_cert_authority(self) -> bool:
        """Whether this line delegates trust to a certificate authority key."""
        return self.marker == CONST_KNOWN_HOSTS_MARKER_CERT_AUTHORITY

    @property
    def is_hashed(self) -> bool:
        """Whether the hostname is stored hashed rather than in the clear."""
        return bool(self.hashed_salt and self.hashed_digest)

    def matches(self, hostname: str, port: int | None = None) -> bool:
        """Report whether this entry applies to a host.

        A negated pattern anywhere in the list excludes the host outright, which is how
        OpenSSH lets a wildcard entry carve out exceptions.
        """
        if self.is_hashed:
            return self._matches_hashed(hostname, port)

        candidates = _candidate_names(hostname, port)
        matched = False
        for pattern in self.patterns:
            if pattern.startswith("!"):
                if _pattern_matches(pattern[1:], candidates):
                    return False
            elif _pattern_matches(pattern, candidates):
                matched = True
        return matched

    def _matches_hashed(self, hostname: str, port: int | None) -> bool:
        """Compare a hashed entry against the candidate spellings of a host.

        OpenSSH hashes the host with HMAC-SHA1 keyed by a per-entry random salt, so the
        only way to test membership is to recompute the digest for each spelling the host
        could have been stored under.
        """
        try:
            salt = base64.b64decode(self.hashed_salt, validate=True)
            expected = base64.b64decode(self.hashed_digest, validate=True)
        except ValueError:  # binascii.Error subclasses ValueError
            logger.debug("Malformed hashed known_hosts entry on line %d.", self.line_number)
            return False

        for candidate in _candidate_names(hostname, port):
            digest = hmac.new(salt, candidate.encode("utf-8"), hashlib.sha1).digest()
            if hmac.compare_digest(digest, expected):
                return True
        return False


def _candidate_names(hostname: str, port: int | None) -> tuple[str, ...]:
    """Return the spellings a host may be recorded under.

    OpenSSH writes a non-default port as `[host]:port` and the default port bare, so both
    have to be considered or a host recorded one way is missed when looked up the other.
    """
    host = hostname.strip()
    if port is None or port == 22:
        return (host,)
    return (f"[{host}]:{port}", host)


@lru_cache(maxsize=512)
def _compile_pattern(pattern: str) -> re.Pattern[str]:
    """Compile an OpenSSH host pattern, which supports only `*` and `?`.

    `fnmatch` cannot be used here: it also honours `[...]` as a character class, and OpenSSH
    writes a non-default port as the literal `[host]:port`. Under `fnmatch` that bracket is
    a one-character class, so an entry recorded for a non-default port never matches itself
    and the host is rescanned and re-added on every connection.
    """
    translated = "".join(
        ".*" if char == "*" else "." if char == "?" else re.escape(char) for char in pattern
    )
    return re.compile(f"{translated}\\Z", re.IGNORECASE)


def _pattern_matches(pattern: str, candidates: tuple[str, ...]) -> bool:
    """Match a single `known_hosts` pattern against candidate host spellings.

    Matching is case-insensitive because hostnames are; treating `GitHub.com` and
    `github.com` as different hosts would split one host across two entries.
    """
    compiled = _compile_pattern(pattern)
    return any(compiled.match(candidate) is not None for candidate in candidates)


def parse_line(line: str, line_number: int = 0) -> KnownHostEntry | None:
    """Parse one `known_hosts` line, returning ``None`` for blanks and comments."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    fields = stripped.split()
    marker: str | None = None
    if fields and fields[0].startswith("@"):
        marker = fields[0]
        fields = fields[1:]

    # A usable line needs at least a host field, a key type and the key itself.
    if len(fields) < 3:
        logger.debug("Skipping malformed known_hosts line %d.", line_number)
        return None

    host_field, key_type, key_data = fields[0], fields[1], fields[2]
    comment = " ".join(fields[3:])

    salt, digest = "", ""
    patterns: tuple[str, ...] = ()
    if host_field.startswith(CONST_KNOWN_HOSTS_HASH_PREFIX):
        parts = host_field.split("|")
        # Format is |1|<salt>|<digest>, which splits into ['', '1', salt, digest].
        if len(parts) != 4:
            logger.debug("Skipping malformed hashed host on line %d.", line_number)
            return None
        salt, digest = parts[2], parts[3]
    else:
        patterns = tuple(part for part in host_field.split(",") if part)

    return KnownHostEntry(
        patterns=patterns,
        key_type=key_type,
        key_data=key_data,
        marker=marker,
        comment=comment,
        hashed_salt=salt,
        hashed_digest=digest,
        line_number=line_number,
    )


def parse_known_hosts(path: Path) -> list[KnownHostEntry]:
    """Parse a `known_hosts` file, skipping lines that cannot be read.

    A single malformed line must not discard the rest of the file: the consequence would be
    re-adding hosts that are already trusted, or worse, ignoring a `@revoked` marker
    recorded further down.
    """
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.debug("Cannot read known_hosts '%s': %s", path, exc)
        return []

    entries: list[KnownHostEntry] = []
    for number, line in enumerate(raw.splitlines(), start=1):
        entry = parse_line(line, number)
        if entry is not None:
            entries.append(entry)
    return entries


def find_host_entries(path: Path, hostname: str, port: int | None = None) -> list[KnownHostEntry]:
    """Return every entry applying to a host, the pure-Python `ssh-keygen -F`."""
    if not path.exists():
        return []
    return [entry for entry in parse_known_hosts(path) if entry.matches(hostname, port)]


def has_trusted_host_key(path: Path, hostname: str, port: int | None = None) -> bool:
    """Report whether a host already has a usable, non-revoked key on file.

    A host whose only entries are `@revoked` is deliberately *not* trusted. Treating a
    revocation as evidence of trust would skip the verification that follows and leave the
    withdrawn key in place.
    """
    entries = find_host_entries(path, hostname, port)
    return any(not entry.is_revoked for entry in entries)


def is_key_revoked(path: Path, hostname: str, key_data: str) -> bool:
    """Report whether a specific key has been revoked for a host."""
    return any(
        entry.is_revoked and entry.key_data == key_data
        for entry in find_host_entries(path, hostname)
    )


def format_entry(hostname: str, key_type: str, key_data: str, comment: str = "") -> str:
    """Render a `known_hosts` line."""
    line = f"{hostname} {key_type} {key_data}"
    return f"{line} {comment}".rstrip()


def append_entry(path: Path, entry_line: str) -> None:
    """Append a line to `known_hosts`, preserving line integrity and file permissions.

    A file not ending in a newline would otherwise have the new entry concatenated onto the
    last one, corrupting both.
    """
    cleaned = entry_line.strip()
    if not cleaned:
        return
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        needs_newline = False
        if path.is_file() and path.stat().st_size > 0:
            with path.open("rb") as handle:
                handle.seek(-1, os.SEEK_END)
                needs_newline = handle.read(1) != b"\n"
        with path.open("a", encoding="utf-8") as handle:
            if needs_newline:
                handle.write("\n")
            handle.write(f"{cleaned}\n")
        path.chmod(CONST_PERM_PRIVATE_KEY)
    except OSError as exc:
        logger.debug("Failed updating known_hosts '%s': %s", path, exc)


__all__ = [
    "KnownHostEntry",
    "append_entry",
    "find_host_entries",
    "format_entry",
    "has_trusted_host_key",
    "is_key_revoked",
    "parse_known_hosts",
    "parse_line",
]
