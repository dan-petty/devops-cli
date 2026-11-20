"""The mapping file and the research fixtures hold no private name, address or device path (#3932).

A watch entry and a pin entry name a host, an address or a repository that a later research step
queries, and the research fixtures stand for the answers of those steps. A private value in either
sends a query into the network of this project or of a workstation, so the scan fails on it, and
SECURITY.md rule 10 keeps it out of the repository.

The same file also holds the OSV identity of the three Go release binaries and the two pins that
live outside the repository, which `devops research inventory` reads at run time.
"""

from __future__ import annotations

import ipaddress
import re

from devops_cli.research.mapping import mapped_inventory
from devops_cli.research.models import ComponentKind, Ecosystem
from devops_cli.research.watch import WATCH_FILE
from tests.support.paths import FIXTURES, REPO_ROOT

# The file of the mapping, at the path that the inventory reads it from.
_MAPPING_FILE = REPO_ROOT / WATCH_FILE
# The fixtures of the research package: the recorded answers of OSV, GitHub and the scanners.
_RESEARCH_FIXTURES = FIXTURES / "research"
# RFC 1918's three blocks. `ipaddress.is_private` also holds the documentation blocks of RFC 5737,
# which a fixture may name.
_RFC1918 = tuple(
    ipaddress.ip_network(block) for block in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
# The suffixes of a host name of a private network, and the name of the loopback host.
_PRIVATE_SUFFIXES = (".local", ".internal", ".svc")
_LOOPBACK_NAME = "localhost"
# The characters of a host name, of an address with its optional prefix, and of a device path.
_HOST_RUN = re.compile(r"[A-Za-z0-9_.-]+")
_ADDRESS_RUN = re.compile(r"[0-9A-Fa-f:.]{3,}(?:/\d{1,3})?")
_DEVICE_PATH = re.compile(r"/dev/[A-Za-z0-9_.-]+")


def _is_private_host(run: str) -> bool:
    """`run` names the loopback host or a host of a private network."""
    host = run.strip(".").lower()
    return host == _LOOPBACK_NAME or host.endswith(_PRIVATE_SUFFIXES)


def _is_private_address(run: str) -> bool:
    """`run` names one loopback address or one RFC 1918 address.

    A run with a port after the address keeps the address, and a range with a prefix shorter than
    the width of the address names no machine, so neither is a private host.
    """
    text = run.strip(".")
    address, _, prefix = text.partition("/")
    if address.count(":") == 1:
        address = address.partition(":")[0]
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False
    if prefix.isdigit() and int(prefix) < parsed.max_prefixlen:
        return False
    return parsed.is_loopback or (
        parsed.version == 4 and any(parsed in block for block in _RFC1918)
    )


def _private_values(line: str) -> list[str]:
    """Each private host name, address and device path of one line, as `<kind> <value>`."""
    return [
        *(f"private host {run}" for run in _HOST_RUN.findall(line) if _is_private_host(run)),
        *(
            f"private address {run}"
            for run in _ADDRESS_RUN.findall(line)
            if _is_private_address(run)
        ),
        *(f"device path {run}" for run in _DEVICE_PATH.findall(line)),
    ]


def _violations(text: str) -> list[str]:
    """Each private host name, address and device path of some text, as `<line>: <kind> <value>`."""
    return [
        f"{number}: {value}"
        for number, line in enumerate(text.splitlines(), start=1)
        for value in _private_values(line)
    ]


def test_the_mapping_file_and_the_research_fixtures_hold_no_private_value() -> None:
    """The mapping file and every file of the research fixtures hold no private host name, no RFC
    1918 or loopback address and no device path."""
    fixtures = sorted(path for path in _RESEARCH_FIXTURES.rglob("*") if path.is_file())
    scanned = [_MAPPING_FILE, *fixtures]

    found = [
        f"{path.relative_to(REPO_ROOT)}:{violation}"
        for path in scanned
        for violation in _violations(path.read_text(encoding="utf-8"))
    ]

    assert (len(scanned) > 1, found) == (True, [])


def test_the_repository_lists_the_pins_outside_it() -> None:
    """The inventory of the repository lists the two pins that no file holds, at the file
    `external` and line 0. The watch list names no release binary: the devtools image audits the
    tools that it installs (#4363)."""
    inventory = mapped_inventory(REPO_ROOT)
    external = [component for component in inventory.components if component.file == "external"]

    assert [
        (
            component.name,
            component.line,
            component.kind,
            component.ecosystem,
            component.osv_ecosystem,
            component.osv_name,
        )
        for component in external
    ] == [
        ("nvidia-driver", 0, ComponentKind.TOOL, Ecosystem.UNKNOWN, "", ""),
        ("ubuntu", 0, ComponentKind.TOOL, Ecosystem.UNKNOWN, "Ubuntu", "linux"),
    ]
