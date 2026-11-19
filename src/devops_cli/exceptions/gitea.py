"""Gitea forge domain exception definitions for devops-cli (#1090)."""

from __future__ import annotations

from devops_cli.exceptions.base import DevOpsCLIError


class GiteaError(DevOpsCLIError):
    """Base exception for Gitea forge operations."""

    error_code = "GITEA_ERROR"
    exit_code = 1

    def __init__(self, message: str, *, token: str | None = None) -> None:
        if token and token in message:
            message = message.replace(token, "[REDACTED]")
        super().__init__(message)


class GiteaAccessBlocked(GiteaError):
    """Raised when Cloudflare Access blocks a Gitea request with a redirect or challenge."""

    error_code = "GITEA_ACCESS_BLOCKED"
    exit_code = 1

    def __init__(
        self, reason: str = "Cloudflare Access redirect or challenge", *, token: str | None = None
    ) -> None:
        msg = (
            f"Gitea access blocked ({reason}). "
            "The workstation public IP address is not in the Cloudflare Access bypass policy. "
            "See the guide in k8s/README.md ('Cloudflare' section) to update the bypass policy: "
            "devops cloudflare access sync --domain '*.<domain>'"
        )
        if token and token in msg:
            msg = msg.replace(token, "[REDACTED]")
        super().__init__(msg)


__all__ = [
    "GiteaAccessBlocked",
    "GiteaError",
]
