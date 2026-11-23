"""What a dependency audit's exit status and output say: clean, vulnerable, or not run.

Each audit tool tells a finding from an audit that could not run by its own signal, so each
command is read by its kind:

- `uv audit` exits 1 for a finding and 2 when it could not run, such as with no network.
- `osv-scanner` exits 1 for a finding and any other non-zero status when it could not run.

`osv-scanner` reads `osv-scanner.toml` directly for time-limited `[[IgnoredVulns]]` entries,
so the project keeps no custom ignore loader or filter.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from enum import StrEnum
from typing import Final

from devops_cli.config.commands import BIN_OSV_SCANNER, BIN_UV
from devops_cli.config.constants import (
    CONST_EXIT_FAILURE,
    CONST_EXIT_SUCCESS,
    CONST_UV_EXIT_FAILURE,
)


class AuditVerdict(StrEnum):
    """What one audit command's run says about the dependencies it audits."""

    CLEAN = "clean"
    VULNERABLE = "vulnerable"
    NOT_RUN = "not_run"


def _read_uv_failure(returncode: int, _stdout: str, _ignored: Collection[str]) -> AuditVerdict:
    """uv's own split: 1 is a finding, any other failure an audit that could not run."""
    return AuditVerdict.VULNERABLE if returncode == CONST_UV_EXIT_FAILURE else AuditVerdict.NOT_RUN


def _read_osv_failure(returncode: int, _stdout: str, _ignored: Collection[str]) -> AuditVerdict:
    """osv-scanner's own split: 1 is a finding, any other failure an audit that could not run."""
    return AuditVerdict.VULNERABLE if returncode == CONST_EXIT_FAILURE else AuditVerdict.NOT_RUN


_FAILURE_READERS: Final[Mapping[str, Callable[[int, str, Collection[str]], AuditVerdict]]] = {
    BIN_UV: _read_uv_failure,
    BIN_OSV_SCANNER: _read_osv_failure,
}


def audit_verdict(
    cmd: Sequence[str], returncode: int, stdout: str, *, ignored: Collection[str] = frozenset()
) -> AuditVerdict:
    """The verdict of one audit command that exited `returncode` and printed `stdout`, read by the
    kind of command it is, the program it starts. Every audit exits 0 when it is clean. `ignored`
    holds the advisory IDs that an entry of the ignore file covers for this command."""
    if returncode == CONST_EXIT_SUCCESS:
        return AuditVerdict.CLEAN
    return _FAILURE_READERS[cmd[0]](returncode, stdout, ignored)
