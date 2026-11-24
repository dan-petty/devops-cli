"""The toolchain presets of the implement job (#4635).

A preset holds the checks and the commands of one toolchain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from devops_cli.config.commands import BIN_DEVOPS, BIN_OPENSPEC, BIN_PYTEST, BIN_UV
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_SCOPED_ROWS
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.verification_command import VERIFICATION_FIRST_WORDS


@dataclass(frozen=True)
class ToolchainPreset:
    """The check and command settings for one toolchain preset (#4635)."""

    name: str
    static_check: tuple[str, ...] | None
    test_command: tuple[str, ...] | None
    test_selection: bool
    verify_prefixes: tuple[str, ...]
    docs_step: bool
    docs_verification: tuple[str, ...] | None
    # The command that writes the snapshots of the test files `{tests}` again (#6116).
    snapshot_update: tuple[str, ...] | None
    archive_argv: tuple[str, ...] | None
    step_gates: str | None
    review_bullet: str | None
    self_hosting: bool


DEVOPS_CLI_PRESET: Final[ToolchainPreset] = ToolchainPreset(
    name="devops-cli",
    static_check=(
        BIN_UV,
        "run",
        BIN_DEVOPS,
        "ci",
        "--check",
        "--only",
        ",".join(CONST_ROADMAP_IMPLEMENT_SCOPED_ROWS),
    ),
    test_command=(BIN_UV, "run", BIN_DEVOPS, "ci", "test", "{tests}"),
    test_selection=True,
    verify_prefixes=VERIFICATION_FIRST_WORDS,
    docs_step=True,
    docs_verification=(BIN_UV, "run", BIN_DEVOPS, "ci", "docs"),
    # Serial, so syrupy writes a shared snapshot file from one process (syrupy issue 1237).
    snapshot_update=(BIN_UV, "run", BIN_PYTEST, "-n", "0", "--snapshot-update", "{tests}"),
    archive_argv=(BIN_UV, "run", BIN_DEVOPS, "openspec", "archive", "<change>"),
    step_gates="ruff-mypy",
    review_bullet=MESSAGES.roadmap.stage_pending_review,
    self_hosting=True,
)

NEUTRAL_PRESET: Final[ToolchainPreset] = ToolchainPreset(
    name="neutral",
    static_check=None,
    test_command=None,
    test_selection=False,
    verify_prefixes=(),
    docs_step=False,
    docs_verification=None,
    snapshot_update=None,
    archive_argv=(BIN_OPENSPEC, "archive", "<change>", "--yes"),
    step_gates=None,
    review_bullet=None,
    self_hosting=False,
)

PRESETS: Final[dict[str, ToolchainPreset]] = {
    "devops-cli": DEVOPS_CLI_PRESET,
    "neutral": NEUTRAL_PRESET,
}

__all__ = [
    "DEVOPS_CLI_PRESET",
    "NEUTRAL_PRESET",
    "PRESETS",
    "ToolchainPreset",
]
