"""Tests for what a review prints to the terminal: the findings that matter in full, and one
line each for LOW findings, dependencies and network references, pointing at review.md (#987).
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from devops_cli.ai.review import ReviewPipelineOrchestrator
from devops_cli.ai.review.runner import ReviewClients, _execute_review_workflow
from devops_cli.ai.review_schema import FileReviewPayload, SavedFinding
from devops_cli.models.vulnerability import (
    DependencySpec,
    NetworkReference,
    NetworkReputationRecord,
)

_SESSION = "20261002-180320"
# Wide enough that nothing wraps, so one printed line is one recorded line.
_WIDTH = 400
# Review tables are borderless and Rich pads every cell, so cells are two or more spaces apart.
_CELL_GAP = re.compile(r"\s{2,}")


@pytest.fixture
def terminal(monkeypatch: pytest.MonkeyPatch) -> Console:
    """The shared console, recording everything the review prints."""
    import devops_cli.output.console as console_module

    recording = Console(record=True, width=_WIDTH, color_system=None, file=io.StringIO())
    monkeypatch.setattr(console_module, "_CONSOLE", recording)
    return recording


def _orchestrator(tmp_path: Path, name: str, **options: Any) -> ReviewPipelineOrchestrator:
    return ReviewPipelineOrchestrator(
        session_id=_SESSION,
        session_dir=tmp_path / name / _SESSION,
        llm_client=MagicMock(),
        target_dir=tmp_path,
        **options,
    )


def _printed(
    terminal: Console, orchestrator: ReviewPipelineOrchestrator, payload: Any
) -> list[str]:
    orchestrator.generate_consolidated_report([payload])
    return terminal.export_text().splitlines()


def _findings() -> list[SavedFinding]:
    """1 CRITICAL, 1 HIGH, 2 MEDIUM and 10 LOW findings, six of the LOW ones verified."""
    severities = ["CRITICAL", "HIGH", "MEDIUM", "MEDIUM", *["LOW"] * 10]
    verified = {"status": "VERIFIED", "verified": True, "verified_by": "criteria"}
    return [
        SavedFinding(
            severity=severity,
            location=f"src/module_{number}.py:10",
            title=f"{severity} defect in module {number}",
            description=f"Description of defect {number}.",
            persona="devsecops",
            **(verified if number <= 10 else {}),
        )
        for number, severity in enumerate(severities, 1)
    ]


def _clean_dependencies() -> list[DependencySpec]:
    return [
        DependencySpec(
            name=f"package-{number:02d}",
            version_range=">=1.0",
            source_file="pyproject.toml",
            line_number=number,
            severity="CLEAN",
            security_status="✓ Clean",
            queried=True,
        )
        for number in range(58)
    ]


def _unflagged_references() -> list[NetworkReference]:
    """531 references, 252 of them local. example.com is dropped as a documentation target,
    so the external references name a domain that is not reserved."""
    local = [
        NetworkReference(
            target=f"http://localhost:{1000 + number}",
            reference_type="url",
            source_file="src/app.py",
            line_number=number + 1,
            is_local=True,
            scope="local",
            security_status="✓ Safe / Low Risk",
        )
        for number in range(252)
    ]
    external = [
        NetworkReference(
            target=f"https://example-corp.com/v{number}",
            reference_type="url",
            source_file="src/app.py",
            line_number=number + 1,
            security_status="✓ Safe / Low Risk",
        )
        for number in range(279)
    ]
    return local + external


def _everything() -> FileReviewPayload:
    """The findings and dependencies above, and 60 of the references, local and external: a
    531-row table alone takes Rich most of a second to lay out."""
    return FileReviewPayload(
        file_path="src/app.py",
        findings=_findings(),
        external_dependencies=_clean_dependencies(),
        network_references=_unflagged_references()[226:286],
    )


def _cells(line: str) -> list[str]:
    return _CELL_GAP.split(line.strip())


def _finding_rows(lines: list[str]) -> list[list[str]]:
    """The findings table's rows, each starting with the finding's number."""
    return [cells for cells in map(_cells, lines) if cells[0].isdigit() and len(cells) > 2]


def _panel_titles(lines: list[str]) -> list[str]:
    return [line for line in lines if line.startswith("╭") and "Finding #" in line]


def test_terminal_tables_medium_and_up_details_high_and_up_and_counts_low_on_one_line(
    tmp_path: Path, terminal: Console
) -> None:
    """With 1 CRITICAL, 1 HIGH, 2 MEDIUM and 10 LOW findings the terminal shows 4 table rows,
    2 detail panels and one line counting the LOW ones by status, with review.md and the
    command that lists them."""
    orchestrator = _orchestrator(tmp_path, "compact")
    lines = _printed(
        terminal, orchestrator, FileReviewPayload(file_path="src/app.py", findings=_findings())
    )
    command = f"devops review findings {_SESSION} --severity LOW --details"
    summary = [line for line in lines if line.startswith("Not shown:")]

    assert (
        [row[1] for row in _finding_rows(lines)],
        [title.split("[")[1].split("]")[0] for title in _panel_titles(lines)],
        len(summary),
        "10 LOW finding(s) (6 VERIFIED, 4 UNVERIFIED)" in "".join(summary),
        str(orchestrator.session_dir / "review.md") in "".join(summary),
        [line.strip() for line in lines if command in line],
        any("LOW defect" in line for line in lines),
    ) == (
        ["CRITICAL", "HIGH", "MEDIUM", "MEDIUM"],
        ["CRITICAL", "HIGH"],
        1,
        True,
        True,
        [command],
        False,
    )


def test_the_command_that_lists_low_findings_prints_whole_on_a_narrow_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """At 60 columns the command is still one unbroken line, so it can be copied as is."""
    import devops_cli.output.console as console_module

    narrow = Console(record=True, width=60, color_system=None, file=io.StringIO())
    monkeypatch.setattr(console_module, "_CONSOLE", narrow)
    lines = _printed(
        narrow,
        _orchestrator(tmp_path, "narrow"),
        FileReviewPayload(file_path="src/app.py", findings=_findings()),
    )
    command = f"devops review findings {_SESSION} --severity LOW --details"

    assert (len(command) > 60, [line.strip() for line in lines if "review findings" in line]) == (
        True,
        [command],
    )


def test_low_and_info_findings_share_the_line_and_the_command_names_both(
    tmp_path: Path, terminal: Console
) -> None:
    """INFO findings are counted with the LOW ones, and the command lists both."""
    findings = [
        SavedFinding(severity=severity, location=f"src/{name}.py:3", title=f"{name} note")
        for name, severity in (("first", "LOW"), ("second", "INFO"), ("third", "INFO"))
    ]
    lines = _printed(
        terminal,
        _orchestrator(tmp_path, "info"),
        FileReviewPayload(file_path="src/app.py", findings=findings),
    )
    command = f"devops review findings {_SESSION} --severity LOW --severity INFO --details"

    assert (
        [line for line in lines if command in line] != [],
        "3 LOW and INFO finding(s) (3 UNVERIFIED)" in "\n".join(lines),
        _finding_rows(lines),
        _panel_titles(lines),
    ) == (True, True, [], [])


def test_clean_dependencies_print_one_summary_line_and_no_rows(
    tmp_path: Path, terminal: Console
) -> None:
    """58 clean dependencies give one summary line pointing at review.md, and no table."""
    payload = FileReviewPayload(
        file_path="pyproject.toml", external_dependencies=_clean_dependencies()
    )
    lines = _printed(terminal, _orchestrator(tmp_path, "clean"), payload)
    summary = [line for line in lines if line.startswith("Dependencies:")]

    assert (
        len(summary),
        "58 scanned, 0 vulnerable" in "".join(summary),
        '"External Dependencies" in review.md' in "".join(summary),
        [line for line in lines if "package-" in line],
    ) == (1, True, True, [])


def test_vulnerable_dependencies_are_counted_by_severity_and_listed_alone(
    tmp_path: Path, terminal: Console
) -> None:
    """Only the vulnerable packages are listed, their names printed as written."""
    vulnerable = [
        DependencySpec(
            name=name,
            version_range="1.0",
            source_file="requirements.txt",
            severity=severity,
            security_status=f"⚠️ 1 Known Vuln(s) [{severity}]",
            queried=True,
        )
        for name, severity in (("uvicorn[standard]", "CRITICAL"), ("vulnerable-pkg", "HIGH"))
    ]
    unchecked = DependencySpec(name="unlooked-pkg", source_file="requirements.txt")
    payload = FileReviewPayload(
        file_path="requirements.txt",
        external_dependencies=[*_clean_dependencies()[:3], *vulnerable, unchecked],
    )
    lines = _printed(terminal, _orchestrator(tmp_path, "vulnerable"), payload)
    summary = [line for line in lines if line.startswith("Dependencies:")]

    assert (
        "6 scanned, 2 vulnerable (1 CRITICAL, 1 HIGH), 1 not checked" in "".join(summary),
        [_cells(line)[1] for line in lines if "1 Known Vuln" in line],
        [line for line in lines if "package-" in line or "unlooked-pkg" in line],
    ) == (True, ["uvicorn[standard]", "vulnerable-pkg"], [])


def test_unflagged_network_references_print_one_summary_line(
    tmp_path: Path, terminal: Console
) -> None:
    """531 references with none flagged give one summary line pointing at review.md."""
    payload = FileReviewPayload(file_path="src/app.py", network_references=_unflagged_references())
    lines = _printed(terminal, _orchestrator(tmp_path, "network"), payload)
    summary = [line for line in lines if line.startswith("Network references:")]

    assert (
        len(summary),
        "531 found (252 local, 279 external), 0 flagged by reputation" in "".join(summary),
        '"Network References & Endpoints" in review.md' in "".join(summary),
        [line for line in lines if "example-corp.com" in line or "localhost:" in line],
    ) == (1, True, True, [])


def test_flagged_network_references_are_listed_alone(tmp_path: Path, terminal: Console) -> None:
    """Only the endpoints flagged by reputation are listed."""
    flagged = NetworkReference(
        target="https://example-corp.com/[/{payload}]",
        reference_type="url",
        source_file="src/app.py",
        line_number=7,
        reputation=NetworkReputationRecord(
            target="example-corp.com", is_malicious=True, reputation_summary="Malware"
        ),
        security_status="⚠️ Flagged (Malware)",
    )
    payload = FileReviewPayload(
        file_path="src/app.py", network_references=[*_unflagged_references()[250:254], flagged]
    )
    lines = _printed(terminal, _orchestrator(tmp_path, "flagged"), payload)

    assert (
        "5 found (2 local, 3 external), 1 flagged by reputation" in "\n".join(lines),
        [_cells(line)[0] for line in lines if "example-corp.com" in line],
    ) == (True, ["https://example-corp.com/[/{payload}]"])


def test_closing_line_names_the_session_directory_and_review_md(
    tmp_path: Path, terminal: Console
) -> None:
    """The last line says where the session and its full report are."""
    orchestrator = _orchestrator(tmp_path, "closing")
    lines = _printed(terminal, orchestrator, FileReviewPayload(file_path="src/app.py"))

    assert (
        lines[-1].startswith("✓ Consolidated review completed"),
        str(orchestrator.session_dir) in lines[-1],
        str(orchestrator.session_dir / "review.md") in lines[-1],
    ) == (True, True, True)


def _saved_report(orchestrator: ReviewPipelineOrchestrator) -> tuple[dict[str, Any], list[str]]:
    findings = json.loads((orchestrator.session_dir / "findings.json").read_text(encoding="utf-8"))
    findings.pop("generated_at")
    review_md = (orchestrator.session_dir / "review.md").read_text(encoding="utf-8")
    return findings, [line for line in review_md.splitlines() if "Generated at" not in line]


def test_full_output_prints_every_finding_dependency_and_reference(
    tmp_path: Path, terminal: Console
) -> None:
    """`full_output` prints every finding with its detail panel, every dependency and every
    network reference."""
    lines = _printed(terminal, _orchestrator(tmp_path, "full", full_output=True), _everything())

    assert (
        len(_finding_rows(lines)),
        len(_panel_titles(lines)),
        len([line for line in lines if "package-" in line]),
        len([line for line in lines if "example-corp.com" in line or "localhost:" in line]),
    ) == (14, 14, 58, 60)


def test_review_md_and_findings_json_are_the_same_with_or_without_full_output(
    tmp_path: Path, terminal: Console
) -> None:
    """Only the terminal output changes: review.md and findings.json hold everything either way."""
    saved = []
    for name, options in (("compact", {}), ("full", {"full_output": True})):
        orchestrator = _orchestrator(tmp_path, name, **options)
        orchestrator.generate_consolidated_report(
            [
                FileReviewPayload(
                    file_path="src/app.py",
                    findings=_findings()[1:6],
                    external_dependencies=_clean_dependencies()[:3],
                    network_references=_unflagged_references()[250:254],
                )
            ]
        )
        saved.append(_saved_report(orchestrator))

    assert (saved[0] == saved[1], len(saved[0][0]["findings"])) == (True, 5)


def test_review_workflow_hands_full_output_to_the_orchestrator(tmp_path: Path) -> None:
    """`--full` reaches the orchestrator that prints the report; without it, the summary."""
    built: list[ReviewPipelineOrchestrator] = []

    def build(**kwargs: Any) -> ReviewPipelineOrchestrator:
        built.append(ReviewPipelineOrchestrator(**kwargs))
        return built[-1]

    clients = ReviewClients(analysis=MagicMock(), compose=MagicMock())
    with (
        patch("devops_cli.ai.review.pipeline.ReviewPipelineOrchestrator", side_effect=build),
        patch("devops_cli.ai.review.runner._run_persona_loop", return_value=[]),
    ):
        for full_output in (True, False):
            _execute_review_workflow(
                [],
                "Path Review",
                MagicMock(),
                "",
                False,
                None,
                False,
                clients,
                target_dir=tmp_path,
                full_output=full_output,
            )

    assert [orchestrator.full_output for orchestrator in built] == [True, False]
