"""A review states each file that one of its stages could not read as a coverage gap (#2160).

The pre-analysis, the admission of a scanner finding and the threat-intelligence stage each read
the reviewed files. A file that a stage cannot read changes what the review checks: the file has
no metadata, its scanner findings cannot be checked against its lines, or its network references
are not looked up. The report names the file, the stage and the reason in its table of skipped
and errored files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from devops_cli.ai.review.flags import ReviewStageFlags
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from tests.support.fakes.tool_executor import ToolAnswer

if TYPE_CHECKING:
    from tests.support.fakes.scanners import ScannerFake

_GAPS_HEADING = "## Skipped / Errored Files"


def _project(root: Path, modules: dict[str, str]) -> Path:
    """A project outside git with the Python modules `modules` under `src/`."""
    (root / "src").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'app'\n", encoding="utf-8")
    for name, text in modules.items():
        (root / "src" / name).write_text(text, encoding="utf-8")
    return root


def _unreadable(path: Path) -> None:
    """Take every permission off `path`."""
    path.chmod(0)


def _gap_rows(report: str) -> list[str]:
    """The rows of the report's table of skipped and errored files; none without the table."""
    lines = report.splitlines()
    if _GAPS_HEADING not in lines:
        return []
    rows = lines[lines.index(_GAPS_HEADING) + 3 :]
    return rows[: rows.index("")] if "" in rows else rows


def test_a_file_that_pre_analysis_cannot_read_is_a_coverage_gap_of_the_review(
    tmp_path: Path,
) -> None:
    """Verify pre-analysis gives metadata for the file that it reads, and the report names the
    file that it cannot read with the stage and the reason."""
    root = _project(
        tmp_path / "app",
        {"app.py": "def app() -> int:\n    return 1\n", "locked.py": "def locked() -> int:\n"},
    )
    _unreadable(root / "src" / "locked.py")
    orchestrator = ReviewPipelineOrchestrator(
        session_id="gap-pre-analysis", target_dir=root, session_dir=tmp_path / "session"
    )

    metadata = orchestrator.run_pre_analysis_refresh(
        files=["src/app.py", "src/locked.py"], target_type="pr", target_ref="7"
    )
    _, report = orchestrator.generate_consolidated_report([])

    assert (sorted(metadata), _gap_rows(report)) == (
        ["src/app.py"],
        ["| `src/locked.py` | Pre-analysis: Permission denied |"],
    )


def test_a_python_file_too_deep_for_the_ast_module_gets_metadata_and_no_coverage_gap(
    tmp_path: Path,
) -> None:
    """Verify pre-analysis gives metadata for a Python file whose expression is too deep for the
    `ast` module, as it does for a file with a syntax error: the symbols come from the text of
    the file, and the report has no coverage gap."""
    deep = "def deep() -> int:\n    return 1\n\n\nTOTAL = a" + " + a" * 200_000 + "\n"
    root = _project(tmp_path / "app", {"deep.py": deep})
    orchestrator = ReviewPipelineOrchestrator(
        session_id="deep-pre-analysis", target_dir=root, session_dir=tmp_path / "session"
    )

    metadata = orchestrator.run_pre_analysis_refresh(
        files=["src/deep.py"], target_type="pr", target_ref="7"
    )
    _, report = orchestrator.generate_consolidated_report([])

    assert (
        {path: meta.key_symbols for path, meta in metadata.items()},
        _gap_rows(report),
    ) == ({"src/deep.py": ["deep"]}, [])


def test_a_scanner_finding_in_a_file_that_admission_cannot_read_is_a_coverage_gap(
    tmp_path: Path, scanner_fake: ScannerFake
) -> None:
    """Verify a Bandit finding in a file that admission cannot read is not reported, since its
    line cannot be checked, and the report names the file with the stage and the reason."""
    root = _project(tmp_path / "app", {"main.py": "import subprocess\n" * 15})
    bandit = {
        "errors": [],
        "results": [
            {
                "filename": str(root / "src" / "main.py"),
                "issue_severity": "HIGH",
                "issue_text": "subprocess call with shell=True identified, security issue.",
                "line_number": 10,
                "test_id": "B602",
                "test_name": "subprocess_popen_with_shell_equals_true",
            }
        ],
    }
    scanner_fake.script("bandit", ToolAnswer(exit_code=1, stdout=json.dumps(bandit)))
    _unreadable(root / "src" / "main.py")
    orchestrator = ReviewPipelineOrchestrator(
        session_id="gap-admission",
        target_dir=root,
        session_dir=tmp_path / "session",
        tool_executor=scanner_fake,
    )

    payloads = orchestrator.init_per_file_payloads(file_paths=["src/main.py"], metadata_by_path={})
    _, report = orchestrator.generate_consolidated_report(payloads)

    assert ({p.file_path: p.findings for p in payloads}, _gap_rows(report)) == (
        {"src/main.py": []},
        ["| `src/main.py` | Admission: Permission denied |"],
    )


def test_a_file_that_threat_intelligence_cannot_read_is_a_coverage_gap(tmp_path: Path) -> None:
    """Verify a review with threat intelligence names the file whose network references it
    cannot read, with the stage and the reason."""
    root = _project(tmp_path / "app", {"hosts.py": "URL = 'https://example.com/'\n"})
    _unreadable(root / "src" / "hosts.py")
    orchestrator = ReviewPipelineOrchestrator(
        session_id="gap-threat-intel",
        target_dir=root,
        session_dir=tmp_path / "session",
        threat_intel=True,
    )

    payloads = orchestrator.init_per_file_payloads(
        file_paths=["src/hosts.py"],
        metadata_by_path={},
        stage_flags=ReviewStageFlags(static_scan=False),
    )
    _, report = orchestrator.generate_consolidated_report(payloads)

    assert _gap_rows(report) == ["| `src/hosts.py` | Threat intelligence: Permission denied |"]
