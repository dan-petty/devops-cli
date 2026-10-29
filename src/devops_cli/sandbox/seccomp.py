"""A seccomp profile that a container sandbox runs under, in place of the engine's default (#1822).

The profile is a file in the format that Docker and Podman read (`--security-opt seccomp=<file>`).
It is loaded and checked once, when the command reads its option, and travels on `SandboxPolicy`.
The Engine API takes it in `HostConfig.SecurityOpt` in one of two forms: the profile's JSON (as the
docker CLI sends it), or the path of the file, which Podman's compat API reads before 6.2.0.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict

from devops_cli.exceptions.sandbox import SandboxValidationError

# The default actions that let every system call through: a profile with one of these confines
# nothing that it does not name, so it is no sandbox profile.
_ALLOW_ALL_ACTIONS: Final[frozenset[str]] = frozenset({"SCMP_ACT_ALLOW", "SCMP_ACT_LOG"})


class SeccompProfile(BaseModel):
    """A checked seccomp profile: the file it came from and its compact JSON."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    document: str

    def security_opt(self, *, inline: bool) -> str:
        """The `security_opt` entry for an engine that takes the JSON inline, or the path."""
        return f"seccomp={self.document if inline else self.path}"


def load_seccomp_profile(path: Path) -> SeccompProfile:
    """Read and check the profile at `path`.

    The file must be a JSON object whose `defaultAction` refuses the calls that the profile does
    not name. Each refusal is a `SandboxValidationError` that names the file.
    """
    resolved = path.expanduser().resolve()
    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise SandboxValidationError(
            f"Cannot read seccomp profile {resolved}: {exc.strerror or type(exc).__name__}.",
            path=str(resolved),
        ) from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SandboxValidationError(
            f"Seccomp profile {resolved} is not JSON (line {exc.lineno}, column {exc.colno}).",
            path=str(resolved),
        ) from exc
    if not isinstance(data, dict):
        raise SandboxValidationError(
            f"Seccomp profile {resolved} is not a JSON object.", path=str(resolved)
        )
    action = data.get("defaultAction")
    if not isinstance(action, str) or not action:
        raise SandboxValidationError(
            f"Seccomp profile {resolved} names no defaultAction.", path=str(resolved)
        )
    if action in _ALLOW_ALL_ACTIONS:
        raise SandboxValidationError(
            f"Seccomp profile {resolved} allows every system call by default "
            f"(defaultAction {action}). Use a profile whose defaultAction refuses the calls that "
            "it does not name, such as SCMP_ACT_ERRNO.",
            path=str(resolved),
        )
    return SeccompProfile(path=resolved, document=json.dumps(data, separators=(",", ":")))
