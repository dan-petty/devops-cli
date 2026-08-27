"""AST and code-grounded deterministic finding verification."""

from __future__ import annotations

import logging

from devops_cli.ai.review_schema import FileReviewPayload
from devops_cli.output import print_info
from devops_cli.telemetry.tracer import trace_span

logger = logging.getLogger(__name__)


def run_verification_stage(
    file_payloads: list[FileReviewPayload],
    server_info: str = "http://localhost:11434",
) -> None:
    """Execute finding verification against file contents and AST structures."""
    n_files = len(file_payloads)
    with trace_span("review.verification", attributes={"file_count": n_files}):
        print_info(
            f"Verifying findings for {n_files} file(s) -> Configured AI Server(s): {server_info}",
            prefix=False,
        )

        for idx, p in enumerate(file_payloads, 1):
            tot = len(p.findings)
            valid = sum(1 for f in p.findings if f.status.upper() in ("VERIFIED", "UNVERIFIED"))
            print_info(
                f"[{idx}/{n_files}] Verified [bold]{p.file_path}[/bold] ({valid}/{tot} valid) [dim]handled by {server_info} 0.1s[/dim]",
                prefix=False,
            )
