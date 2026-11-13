"""HTTP domain exception definitions for devops-cli."""

from __future__ import annotations

from devops_cli.exceptions.base import DevOpsCLIError


class ServiceRequestError(DevOpsCLIError):
    """Raised when a request to a cluster service fails after the attempts of its retry policy.

    `devops_cli.http.retry.service_error` makes it from the last httpx2 error (#5532). The message
    is one line: the service, the HTTP status or the network error, the attempts, the time and a
    hint. `status_code` is the HTTP status of the last reply, or None for a network error.
    """

    error_code = "SERVICE_REQUEST_ERROR"

    def __init__(
        self,
        message: str,
        *,
        service: str,
        status_code: int | None,
        attempts: int,
        seconds: float,
    ) -> None:
        super().__init__(
            message,
            details={
                "service": service,
                "status_code": status_code,
                "attempts": attempts,
                "seconds": seconds,
            },
        )
        self.service = service
        self.status_code = status_code
        self.attempts = attempts
        self.seconds = seconds
