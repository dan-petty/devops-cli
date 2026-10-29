"""No committed file holds a private address or an internal `.lan` host (SECURITY.md rule 8, #1977).

The check reads the files that git tracks. It splits each line into the runs of characters an
address or a host name can hold, and parses each run with `ipaddress`, so no pattern matches an
octet.
"""

from __future__ import annotations

import ipaddress
import subprocess
from pathlib import PurePosixPath

import pytest

from tests.support.paths import REPO_ROOT

# RFC 1918's three blocks. `ipaddress.is_private` also holds loopback and the RFC 5737
# documentation blocks, which SECURITY.md allows, so the check tests membership of these blocks.
_RFC1918_BLOCKS = tuple(
    ipaddress.ip_network(block) for block in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
# Addresses that an upstream project documents as its own default or example. None of them names
# a machine of this project's networks.
_UPSTREAM_ADDRESSES = {
    # minikube's node address with the docker driver (`minikube ip`).
    ipaddress.ip_address("192.168.49.2"): "minikube docker driver node",
    # AKS's default `dns_service_ip`, inside its default service CIDR 10.0.0.0/16.
    ipaddress.ip_address("10.0.0.10"): "AKS default DNS service",
    # The OpenTelemetry semantic conventions' example of `server.address`.
    ipaddress.ip_address("10.1.2.80"): "OpenTelemetry server.address example",
}
_ADDRESS_BYTES = b"0123456789./"
_HOST_BYTES = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-"
_LAN_SUFFIX = ".lan"
_BINARY_PROBE_BYTES = 8192
_GIT_TIMEOUT_SECONDS = 30


def _run_table(kept: bytes) -> bytes:
    """A `bytes.translate` table that keeps the bytes in `kept` and turns every other byte into a
    space, so `split()` gives the runs of kept bytes."""
    return bytes(byte if byte in kept else ord(" ") for byte in range(256))


_ADDRESS_RUNS = _run_table(_ADDRESS_BYTES)
_HOST_RUNS = _run_table(_HOST_BYTES)


def _in_scope(path: str) -> bool:
    """Whether the rule applies to a tracked file.

    It does not apply to test code, which must hold private addresses and `.lan` hosts to test
    the egress and reference classifiers; to the archived OpenSpec changes, which record merged
    work and do not change; or to CHANGELOG.md, which release-please writes.
    """
    parts = PurePosixPath(path).parts
    if parts[0] == "tests" and path.endswith(".py"):
        return False
    if parts[:2] == (".ast-grep", "rule-tests"):
        return False
    if parts[:3] == ("openspec", "changes", "archive"):
        return False
    return path != "CHANGELOG.md"


def _private_address(run: bytes) -> str | None:
    """The kind of private address a run names, or None.

    A range in CIDR form with a prefix shorter than 32 names no machine, so it is allowed. So are
    the upstream defaults and examples in `_UPSTREAM_ADDRESSES`.
    """
    text = run.strip(b"./").decode("ascii")
    if text.count(".") != 3:
        return None
    try:
        interface = ipaddress.ip_interface(text)
    except ValueError:
        return None
    if not any(interface.ip in block for block in _RFC1918_BLOCKS):
        return None
    if "/" in text and interface.network.prefixlen < 32:
        return None
    if interface.ip in _UPSTREAM_ADDRESSES:
        return None
    return f"RFC 1918 address {text}"


def _lan_host(run: bytes) -> str | None:
    """The `.lan` host a run names, or None. A bare `.lan` or `*.lan` names no host."""
    text = run.rstrip(b".-").decode("ascii").lower()
    label = text.removesuffix(_LAN_SUFFIX)
    if label == text or not label or label[-1] in ".-":
        return None
    return f".lan host {text}"


def _kinds(data: bytes) -> list[str]:
    """Each private address and `.lan` host in some text, in order."""
    found = [
        kind for run in data.translate(_ADDRESS_RUNS).split() if (kind := _private_address(run))
    ]
    if _LAN_SUFFIX.encode() in data.lower():
        found += [kind for run in data.translate(_HOST_RUNS).split() if (kind := _lan_host(run))]
    return found


def violations(path: str, data: bytes) -> list[str]:
    """Each private address and `.lan` host in one file, as `<path>:<line>: <kind> <value>`.

    The whole file is read in one pass. Only a file that holds a violation is read again line by
    line, to name each line.
    """
    if b"\0" in data[:_BINARY_PROBE_BYTES] or not _kinds(data):
        return []
    return [
        f"{path}:{number}: {kind}"
        for number, line in enumerate(data.splitlines(), start=1)
        for kind in _kinds(line)
    ]


def _tracked_files() -> list[str]:
    """The files git tracks in the checkout; a git failure ends the test with git's reason."""
    done = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
        capture_output=True,
        check=False,
        timeout=_GIT_TIMEOUT_SECONDS,
    )
    if done.returncode:
        pytest.fail(f"git ls-files failed: {done.stderr.decode()[:256]}", pytrace=False)
    return [name for name in done.stdout.decode().split("\0") if name]


def test_no_committed_file_holds_a_private_address_or_a_lan_host() -> None:
    """Every tracked file in scope holds no RFC 1918 address and no `.lan` host."""
    tracked = _tracked_files()
    found = [
        line
        for path in tracked
        if _in_scope(path) and (REPO_ROOT / path).is_file()
        for line in violations(path, (REPO_ROOT / path).read_bytes())
    ]
    assert (len(tracked) > 0, found) == (True, [])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("url: http://10.0.0.1:8080/", ["f:1: RFC 1918 address 10.0.0.1"]),
        ("host 192.168.1.5/32 only", ["f:1: RFC 1918 address 192.168.1.5/32"]),
        ("dns: 172.16.0.2.", ["f:1: RFC 1918 address 172.16.0.2"]),
        ("ollama at myhost.lan:11434", ["f:1: .lan host myhost.lan"]),
        ("a\nGPU.LAN", ["f:2: .lan host gpu.lan"]),
        ("docs use 192.0.2.1, 198.51.100.7 and 203.0.113.5", []),
        ("example.com, localhost, 127.0.0.1 and ::1", []),
        ("except: [10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16]", []),
        ("vpc_cidr = 10.0.0.0/16, subnet 10.0.1.0/24", []),
        ("minikube at 192.168.49.2", []),
        ("never `*.lan` or `<host>.lan` or .lan", []),
        ("version 1.2.3.4 and 010.000.000.001", []),
        ("language.lane plan.landing", []),
    ],
)
def test_the_scan_names_each_private_address_and_lan_host(text: str, expected: list[str]) -> None:
    """The scan finds RFC 1918 addresses and `.lan` hosts, and passes documentation addresses,
    example names, loopback, ranges, upstream defaults and non-addresses."""
    assert violations("f", text.encode()) == expected


def test_a_binary_file_is_not_read() -> None:
    """A file with a NUL byte in its first block is binary, and the scan reads nothing in it."""
    assert violations("f", b"\0" + b"10.0.0.1") == []


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tests/test_http_egress.py", False),
        ("tests/security/test_reference_extraction.py", False),
        (".ast-grep/rule-tests/net-address-list-test.yml", False),
        ("openspec/changes/archive/2026-10-28-2424-x/proposal.md", False),
        ("CHANGELOG.md", False),
        ("tests/fixtures/metrics/otel-collector.yaml", True),
        ("tests/__snapshots__/test_x.ambr", True),
        ("openspec/specs/configured-service-urls/spec.md", True),
        ("src/devops_cli/config/defaults.py", True),
        ("k8s/devops/networkpolicy.yaml", True),
        ("docs/CHANGELOG.md", True),
    ],
)
def test_the_rule_applies_outside_test_code_archives_and_the_changelog(
    path: str, expected: bool
) -> None:
    """Test code, archived OpenSpec changes and release-please's CHANGELOG.md are out of scope;
    fixtures, snapshots, specs, source, manifests and documents are in it."""
    assert _in_scope(path) is expected
