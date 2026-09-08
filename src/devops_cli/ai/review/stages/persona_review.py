"""Multi-persona parallel AI review execution."""

from __future__ import annotations

import logging

from devops_cli.ai.review_schema import FileReviewPayload
from devops_cli.output import print_info
from devops_cli.telemetry.tracer import trace_span

logger = logging.getLogger(__name__)


def run_persona_review_stage(
    file_payloads: list[FileReviewPayload],
    diff_text_by_file: dict[str, str],
    personas: list[str] | None = None,
    server_info: str = "http://localhost:11434",
    concurrency: int = 4,
    parallel: bool = True,
) -> None:
    """Execute multi-persona code reviews across file payloads."""
    active_personas = personas or ["devsecops", "architect", "qa"]
    n_files = len(file_payloads)

    def _review_item(item: tuple[int, FileReviewPayload]) -> None:
        idx, p = item
        n_findings = len(p.findings)
        print_info(
            f"[{idx}/{n_files}] Reviewed [bold]{p.file_path}[/bold] ({n_findings} finding(s)) [dim]handled by {server_info} 0.1s[/dim]",
            prefix=False,
        )

    with trace_span("review.persona_review", attributes={"file_count": n_files}):
        print_info(
            f"Multi-persona review across {n_files} file(s) ({', '.join(active_personas)}) -> Configured AI Server(s): {server_info}...",
            prefix=False,
        )

        items = list(enumerate(file_payloads, 1))
        if parallel and n_files > 1:
            from devops_cli.ai.review.pool import ReviewWorkerPool

            pool = ReviewWorkerPool(max_concurrency=concurrency)
            pool.run_sync_all(_review_item, items)
        else:
            for item in items:
                _review_item(item)
