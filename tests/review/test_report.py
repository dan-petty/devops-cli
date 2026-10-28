"""The review report: review.md and the terminal view, rendered from one session (#1008)."""

from __future__ import annotations

import io
import re
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from rich.console import Console
from syrupy.assertion import SnapshotAssertion

from devops_cli.ai.kb import DriftManual
from devops_cli.ai.review import ReviewPipelineOrchestrator
from devops_cli.ai.review.flags import ReviewStageFlags
from devops_cli.ai.review_schema import FileReviewPayload, SavedFinding
from devops_cli.models.ai import FileAnalysisMeta
from devops_cli.models.vulnerability import (
    DependencySpec,
    NetworkReference,
    NetworkReputationRecord,
)
from devops_cli.review.admission import ToolAnchor, admit
from devops_cli.review.analysis import AnalysisReport, RatioRecord, SamplingRecord

_SESSION = "20261028-120000"
# A fixed width, wide enough that no line wraps, so the recorded view is the same on any host.
_WIDTH = 240
_GENERATED_AT = re.compile(r"\*Generated at: [^*]+\*")
# Rich pads each cell to its column, and a column is as wide as the session's temporary path.
_CELL_PADDING = re.compile(r" {2,}")
# The group analysis does not run here: a canned report keeps the knowledge base out of the text.
_ANALYSIS = AnalysisReport(
    groups=[],
    sampling=SamplingRecord(temperature=0.1, top_p=0.95),
    reference_coverage=RatioRecord(numerator=1, denominator=2),
    rejections={"G10-anchor": 1},
    dispatched=1,
    drift_manuals=[DriftManual(path="it_domains/tools/example.md", reason="tool:example drifted")],
)


@pytest.fixture
def terminal(monkeypatch: pytest.MonkeyPatch) -> Console:
    """The shared console, recording everything the review prints."""
    import devops_cli.output.console as console_module

    recording = Console(record=True, width=_WIDTH, color_system=None, file=io.StringIO())
    monkeypatch.setattr(console_module, "_CONSOLE", recording)
    return recording


def _findings() -> list[SavedFinding]:
    """A finding of each severity and status, with the text a report must escape."""
    verified = {"status": "VERIFIED", "verified": True, "verified_by": "criteria"}
    return [
        SavedFinding(
            severity="CRITICAL",
            location="src/app.py:12",
            title="Command | injection via ```shell``` call",
            description="The `cmd` reaches [bold]subprocess[/bold].\nSecond paragraph.",
            fix="```python\nsubprocess.run(args)\n```",
            references=["CWE-78", "https://example.com/cwe-78"],
            producer="semgrep",
            confidence_score=0.9,
            category="injection",
            **verified,
        ),
        SavedFinding(
            severity="HIGH",
            location="src/app.py:30",
            title="Second injection of the same class",
            description="Another command reaches the shell.",
            producer="bandit",
            category="injection",
            **verified,
        ),
        SavedFinding(
            severity="MEDIUM",
            location="src/util.py:4",
            title="Weak hash",
            description="md5 is used for an identity.",
            fix="Use `sha256`.",
            producer="bandit",
            introduced=False,
        ),
        SavedFinding(
            severity="LOW",
            location="src/util.py:9",
            title="Broad exception",
            description="An exception handler catches everything.",
            status="MITIGATED",
            invalidation_reason="The handler logs and re-raises.",
            producer="ruff",
        ),
        SavedFinding(
            severity="INFO",
            location="src/util.py:20",
            title="TODO left in code",
            description="A TODO marker.",
            producer="ruff",
        ),
        SavedFinding(
            severity="HIGH",
            location="src/app.py:50",
            title="Rejected finding",
            description="The verifier rejected it.",
            status="INVALIDATED",
            reportable=False,
            invalidation_reason="The value is a constant.",
            producer="semgrep",
        ),
    ]


def _payload() -> FileReviewPayload:
    return FileReviewPayload(
        file_path="src/app.py",
        metadata=FileAnalysisMeta(
            path="src/app.py",
            symbols_added=["run", "parse"],
            symbols_removed=["legacy"],
            symbols_retained=["main"],
        ),
        findings=_findings(),
        external_dependencies=[
            DependencySpec(
                name="requests",
                version_range="==2.0.0",
                severity="HIGH",
                security_status="2 vulnerabilities",
                queried=True,
                source_file="requirements.txt",
            ),
            DependencySpec(
                name="rich",
                version_range=">=13",
                severity="CLEAN",
                security_status="No known vulnerabilities",
                queried=True,
            ),
            DependencySpec(name="left-pad", version_range="*", ecosystem="npm"),
        ],
        network_references=[
            NetworkReference(target="https://example-corp.com/v1", security_status="✓ Safe"),
            NetworkReference(
                target="https://malware.example-corp.com/x",
                security_status="⚠️ Malicious",
                reputation=NetworkReputationRecord(
                    target="malware.example-corp.com", is_malicious=True
                ),
            ),
            NetworkReference(target="http://localhost:8080", is_local=True, scope="local"),
        ],
    )


def _admitted() -> list[Any]:
    """An admitted scanner finding of the change, and one its inline marker suppresses."""
    anchor = ToolAnchor(run_id="run-1", result_index=0, rule_id="B101")
    shared = {
        "anchor": anchor,
        "tool": "bandit",
        "rule_id": "B101",
        "path": "src/app.py",
        "line": 1,
        "commit_files": {"src/app.py"},
    }
    open_finding = admit(
        message="assert used", file_content_getter=lambda _: "assert x\n", **shared
    )
    suppressed = admit(
        message="assert used",
        file_content_getter=lambda _: "assert x  # nosec B101\n",
        added_diff_lines={("src/app.py", 1)},
        **shared,
    )
    return [open_finding, suppressed]


def _orchestrator(tmp_path: Path, *, full_output: bool) -> ReviewPipelineOrchestrator:
    orchestrator = ReviewPipelineOrchestrator(
        session_id=_SESSION,
        session_dir=tmp_path / "reviews" / _SESSION,
        llm_client=MagicMock(),
        target_dir=tmp_path,
        partial_context=True,
        full_output=full_output,
    )
    orchestrator.static_analyzers = {"Bandit": "ran", "Semgrep": "failed", "Trivy": "not installed"}
    orchestrator.static_analyzer_reasons = {"Semgrep": 'exited with code 1 | output "a | b"'}
    orchestrator.static_analyzer_unscanned = {"Bandit": {"src/big.py": "too large"}}
    orchestrator.static_severities = Counter({"CRITICAL": 1, "HIGH": 1})
    orchestrator.errored_files = {"src/broken.py": "pre_analysis: invalid | syntax"}
    orchestrator.coverage = {"bandit": {"src/app.py": "scanned", "src/big.py": "skipped"}}
    orchestrator.complexity_deltas = [
        {"file": "src/app.py", "function": "run", "before": 4, "after": 9},
        {"file": "src/app.py", "function": "parse", "before": None, "after": 3},
    ]
    orchestrator.admitted_scanner_findings = _admitted()
    orchestrator.analysis_report = _ANALYSIS
    return orchestrator


def _rendered(
    tmp_path: Path, terminal: Console, *, full_output: bool
) -> tuple[list[str], list[str]]:
    """review.md and the terminal view of one session, with its time and paths made fixed."""
    orchestrator = _orchestrator(tmp_path, full_output=full_output)
    _, report = orchestrator.generate_consolidated_report(
        [_payload()], stage_flags=ReviewStageFlags(group_analysis=False)
    )
    markdown = _GENERATED_AT.sub("*Generated at: <time>*", report).replace(str(tmp_path), "<tmp>")
    view = terminal.export_text().replace(str(tmp_path), "<tmp>")
    return (
        markdown.splitlines(),
        [_CELL_PADDING.sub("  ", line).rstrip() for line in view.splitlines()],
    )


def test_the_report_and_the_summary_view_of_a_session(
    tmp_path: Path, terminal: Console, snapshot: SnapshotAssertion
) -> None:
    """Verify review.md and the terminal summary view of one session keep their exact text."""
    assert _rendered(tmp_path, terminal, full_output=False) == snapshot


def test_the_full_terminal_view_of_a_session(
    tmp_path: Path, terminal: Console, snapshot: SnapshotAssertion
) -> None:
    """Verify the --full-output terminal view of one session keeps its exact text."""
    assert _rendered(tmp_path, terminal, full_output=True)[1] == snapshot
