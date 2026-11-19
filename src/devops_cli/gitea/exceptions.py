"""Exceptions for Gitea client operations (#1090)."""

from __future__ import annotations

from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.security.sanitizer import mask_secrets


class GiteaError(DevOpsCLIError):
    """An error returned by Gitea API."""

    def __init__(self, message: str, *, token: str | None = None) -> None:
        if token and token in message:
            message = message.replace(token, "[REDACTED]")
        super().__init__(mask_secrets(message))


class GiteaAccessBlocked(DevOpsCLIError):
    """Cloudflare Access blocked the Gitea request (redirect or challenge)."""

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
        super().__init__(mask_secrets(msg))
