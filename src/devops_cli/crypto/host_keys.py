"""SSH host key parsing, fingerprinting, and verification against pinned values.

`ssh-keyscan` reports whatever key the network hands back. It performs no verification --
that is the caller's job, and it was not being done: a scanned key was appended to
`known_hosts` unconditionally, so anyone able to intercept the first connection to a host
had their key pinned permanently and silently.

This module supplies the missing half. It computes the SHA256 fingerprint OpenSSH displays
and compares it against fingerprints published by the host's operator over a channel that
is already authenticated, so trust is established by TLS PKI rather than by assuming the
first answer received is honest.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from dataclasses import dataclass

from devops_cli.config.constants import (
    CONST_GITHUB_HOST,
    CONST_GITHUB_HOST_KEY_FINGERPRINTS,
    CONST_SSH_FINGERPRINT_PREFIX,
    CONST_SSH_HOST_KEY_TYPES,
)

logger = logging.getLogger(__name__)


class HostKeyVerificationError(ValueError):
    """Raised when a host key cannot be verified against its published fingerprints."""


@dataclass(frozen=True)
class HostKey:
    """One SSH host key as advertised by a server."""

    hostname: str
    key_type: str
    key_data: str
    comment: str = ""

    @property
    def fingerprint(self) -> str:
        """The SHA256 fingerprint in the form OpenSSH prints.

        OpenSSH renders it as unpadded standard base64 of the SHA256 digest of the raw key
        blob. Padding or hex would not compare equal to what a user reads from the
        publisher's documentation, which is the entire point of showing it.
        """
        digest = hashlib.sha256(base64.b64decode(self.key_data, validate=True)).digest()
        encoded = base64.b64encode(digest).decode("ascii").rstrip("=")
        return f"{CONST_SSH_FINGERPRINT_PREFIX}{encoded}"

    def to_known_hosts_line(self) -> str:
        """Render this key as a `known_hosts` entry."""
        line = f"{self.hostname} {self.key_type} {self.key_data}"
        return f"{line} {self.comment}".rstrip()


def parse_host_key_line(line: str) -> HostKey | None:
    """Parse one line of `ssh-keyscan` output, returning ``None`` if unusable.

    The key material is base64-decoded during parsing rather than trusted as a string: a
    line that is not decodable is not a key, and accepting it would write an unusable entry
    into `known_hosts` that silently breaks every later connection to that host.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    fields = stripped.split()
    if len(fields) < 3:
        return None

    hostname, key_type, key_data = fields[0], fields[1], fields[2]
    if key_type not in CONST_SSH_HOST_KEY_TYPES:
        logger.debug("Ignoring unsupported host key type '%s'.", key_type)
        return None

    try:
        base64.b64decode(key_data, validate=True)
    except ValueError:
        logger.debug("Ignoring host key with undecodable key material.")
        return None

    return HostKey(
        hostname=hostname,
        key_type=key_type,
        key_data=key_data,
        comment=" ".join(fields[3:]),
    )


def parse_host_keys(output: str) -> list[HostKey]:
    """Parse the full output of `ssh-keyscan` into host keys."""
    parsed = (parse_host_key_line(line) for line in output.splitlines())
    return [key for key in parsed if key is not None]


def published_fingerprints(hostname: str) -> frozenset[str]:
    """Return the fingerprints published for a host, empty if none are pinned."""
    return CONST_GITHUB_HOST_KEY_FINGERPRINTS if hostname == CONST_GITHUB_HOST else frozenset()


def is_pinned_host(hostname: str) -> bool:
    """Report whether this host's keys can be verified against published fingerprints."""
    return bool(published_fingerprints(hostname))


def verify_fingerprint(key: HostKey, expected: frozenset[str]) -> bool:
    """Report whether a key's fingerprint is among the expected set.

    Compared with a constant-time primitive. The comparison is not secret, but the habit of
    short-circuiting on the first differing character is one worth not forming in a
    verification path.
    """
    actual = key.fingerprint
    return any(hmac.compare_digest(actual, candidate) for candidate in expected)


def select_verified_key(keys: list[HostKey], hostname: str) -> HostKey:
    """Return the first scanned key whose fingerprint matches what the host publishes.

    Raises when no key matches. Failing closed is the point: the alternative is the previous
    behaviour, where an unverifiable key was pinned anyway and the check may as well not
    have existed. A legitimate key rotation surfaces here as a refusal the operator can
    resolve deliberately, rather than as a silent acceptance they never see.
    """
    expected = published_fingerprints(hostname)
    if not expected:
        raise HostKeyVerificationError(
            f"No published fingerprints are pinned for '{hostname}', so its host key "
            f"cannot be verified automatically."
        )
    if not keys:
        raise HostKeyVerificationError(f"No usable host key was returned for '{hostname}'.")

    for key in keys:
        if verify_fingerprint(key, expected):
            return key

    offered = ", ".join(sorted({key.fingerprint for key in keys})) or "none"
    raise HostKeyVerificationError(
        f"Host key for '{hostname}' does not match any published fingerprint. "
        f"Offered: {offered}. This is expected after a legitimate key rotation, and is "
        f"also what an interception attempt looks like: verify against the operator's "
        f"published fingerprints before trusting it."
    )


__all__ = [
    "HostKey",
    "HostKeyVerificationError",
    "is_pinned_host",
    "parse_host_key_line",
    "parse_host_keys",
    "published_fingerprints",
    "select_verified_key",
    "verify_fingerprint",
]
