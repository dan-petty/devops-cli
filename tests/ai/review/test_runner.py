"""What the review runner reads: the target's analysis metadata (#1100), the review.toml
suppressions a branch or PR change touches, and what a model's reply may not set (#1150)."""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.analyze.symbols import BaseRevision
from devops_cli.ai.personas import Persona
from devops_cli.ai.review.flags import resolve_stage_flags
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review.protocol import ReviewLLMClient
from devops_cli.ai.review.runner import (
    ReviewClients,
    _check_and_warn_perimeter_changes,
    _execute_review_workflow,
    _record_review_metrics,
    _run_orchestrator_review,
    format_pr_review_comment,
)
from devops_cli.ai.review_schema import (
    FileReviewPayload,
    SavedFinding,
    derive_recommendation,
)
from devops_cli.config.constants import CONST_REVIEW_CONFIG_FILE
from devops_cli.review.anchors import ToolAnchor
from devops_cli.review.finding import Finding as AdmittedFinding
from devops_cli.review.state import FindingState

_RUNNER = """import textwrap


def run_snippet(source, namespace):
    code = compile(textwrap.dedent(source), "doc", "exec")
    exec(code, {"__name__": "count"})
    return namespace
"""

_REVIEW_TOML = """\
[[suppressions]]
rule = "B602"
path = "src/a.py"
reason = "The argv is a constant list"
expiry = "2099-12-31"

[[suppressions]]
rule = "B603"
path = "src/b.py"
reason = "Expired reason"
expiry = "2020-01-01"
"""


def _base_revision() -> BaseRevision:
    """A base revision whose review.toml holds the two suppressions; the checkout holds none,
    so a warning can only come from the base revision."""
    return BaseRevision(
        changes=(),
        read=lambda path: _REVIEW_TOML if path == CONST_REVIEW_CONFIG_FILE else None,
    )


@pytest.mark.parametrize("target_type", ["branch", "pr"])
def test_a_change_review_names_the_unexpired_suppressions_it_touches(
    target_type: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Changing src/a.py and src/b.py names the unexpired suppression on src/a.py, read at the
    base revision, and not the expired one on src/b.py."""
    (tmp_path / ".git").mkdir()

    _check_and_warn_perimeter_changes(
        target_type,
        ["src/a.py", "src/b.py"],
        base_revision=_base_revision(),
        target_dir=tmp_path,
    )

    output = " ".join(capsys.readouterr().out.split())
    assert (
        output.count("1 review.toml suppression"),
        "B602" in output,
        "src/a.py" in output,
        "The argv is a constant list" in output,
        "Expired reason" in output,
    ) == (1, True, True, True, False)


def test_a_path_review_lists_no_suppressions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A path review has no change to compare, so it prints nothing."""
    (tmp_path / ".git").mkdir()

    _check_and_warn_perimeter_changes(
        "path", ["src/a.py"], base_revision=_base_revision(), target_dir=tmp_path
    )

    assert capsys.readouterr().out == ""


def _checkout(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'target'\n", encoding="utf-8")
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return root


def test_no_review_layer_falls_back_to_the_working_directory_for_its_target() -> None:
    """Verify every layer that carries a review's target down to the personas requires it
    (#1100). A default of the working directory let a new caller that left the target out
    type-check and review the working directory's files, one layer above the fix."""
    layers = {
        "_execute_review_workflow": _execute_review_workflow,
        "ReviewPipelineOrchestrator": ReviewPipelineOrchestrator.__init__,
    }
    targets = {name: inspect.signature(fn).parameters["target_dir"] for name, fn in layers.items()}
    refresh = inspect.signature(ReviewPipelineOrchestrator.run_pre_analysis_refresh)

    assert {
        name: (p.kind, p.default is inspect.Parameter.empty) for name, p in targets.items()
    } == dict.fromkeys(layers, (inspect.Parameter.KEYWORD_ONLY, True))
    assert refresh.parameters["target_dir"].default is inspect.Parameter.empty


def test_a_review_outside_the_working_directory_reads_its_targets_analysis_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a review whose target is not the working directory loads analysis metadata from
    the target's repository in the summary (#1100)."""
    here = _checkout(tmp_path / "here", {"runner.py": _RUNNER})
    target = _checkout(tmp_path / "target", {"runner.py": _RUNNER})
    monkeypatch.chdir(here)
    roots: list[object] = []

    def metas(_files: object, repo_root: object = None) -> dict[str, object]:
        roots.append(repo_root)
        return {}

    with (
        patch("devops_cli.ai.review.runner._load_file_analysis_metas", side_effect=metas),
        patch("devops_cli.ai.review.runner._print_analysis_metadata"),
    ):
        _execute_review_workflow(
            [f"### File: runner.py\n{_RUNNER}"],
            "Path review",
            False,
            Persona.DEVSECOPS,
            True,
            ReviewClients(analysis=MagicMock(spec=ReviewLLMClient)),
            target_type="path",
            target_ref=str(target),
            target_dir=target,
        )

    assert (len(roots) > 0, set(roots)) == (True, {target.resolve()})


def test_summary_only_exits_before_orchestrator_construction(tmp_path: Path) -> None:
    """Verify --summary prints metadata and returns before ReviewPipelineOrchestrator construction,
    making zero model calls and creating no session directory (#995)."""
    target = _checkout(tmp_path / "target", {"app.py": "def foo(): pass\n"})
    mock_client = MagicMock(spec=ReviewLLMClient)

    with (
        patch("devops_cli.ai.review.pipeline.ReviewPipelineOrchestrator") as mock_orchestrator,
        patch("devops_cli.ai.review.runner._print_analysis_metadata"),
    ):
        result = _execute_review_workflow(
            ["### File: app.py\ndef foo(): pass\n"],
            "Path review",
            False,
            Persona.DEVSECOPS,
            True,
            ReviewClients(analysis=mock_client),
            target_type="path",
            target_ref=str(target),
            target_dir=target,
        )

    assert (
        result,
        mock_orchestrator.called,
        mock_client.chat.called,
        mock_client.chat_messages.called,
        (target / ".data" / "reviews").exists(),
    ) == ([], False, False, False, False)


@pytest.mark.usefixtures("scanner_fake")
def test_routed_files_only_branch_diff_makes_no_model_calls(tmp_path: Path) -> None:
    """Verify a review of routed files only (such as uv.lock) invokes _review_routed_files_only
    with zero model calls and succeeds (#948, #995)."""
    target = _checkout(tmp_path / "target", {"uv.lock": "version = 1\n"})
    mock_client = MagicMock(spec=ReviewLLMClient)
    mock_client.backend_info = "mock-llm"

    result = _execute_review_workflow(
        [],
        "Branch `feature` vs `main`",
        False,
        Persona.DEVSECOPS,
        False,
        ReviewClients(analysis=mock_client),
        target_type="branch",
        target_ref="feature",
        target_dir=target,
        routed_files=["uv.lock"],
    )

    assert (
        len(result) == 1,
        mock_client.chat.called,
        mock_client.chat_messages.called,
    ) == (True, False, False)


def test_unverified_high_findings_stay_in_report_with_request_changes(tmp_path: Path) -> None:
    """Verify #789 constraint: unverified HIGH findings remain in the report and findings.json
    with REQUEST CHANGES recommendation; only INVALIDATED findings leave the report."""
    mock_client = MagicMock(spec=ReviewLLMClient)
    mock_client.backend_info = "mock-llm"
    orchestrator = ReviewPipelineOrchestrator(
        session_id="test-789",
        session_dir=tmp_path / "session",
        llm_client=mock_client,
        target_dir=tmp_path,
    )
    unverified_high = SavedFinding(
        title="Unverified SQL Injection",
        severity="HIGH",
        status="UNVERIFIED",
        reportable=True,
        location="app.py:10",
        description="Possible injection",
        fix="Use parameters",
    )
    invalidated_high = SavedFinding(
        title="False Positive Overflow",
        severity="HIGH",
        status="INVALIDATED",
        reportable=False,
        location="app.py:20",
        description="Not reachable",
        fix="None",
    )
    payload = FileReviewPayload(
        file_path="app.py",
        findings=[unverified_high, invalidated_high],
    )
    data, _ = orchestrator.generate_consolidated_report([payload])

    findings_in_report = data.get("findings", [])
    assert (
        len(findings_in_report),
        findings_in_report[0]["title"],
        findings_in_report[0]["status"],
        derive_recommendation([unverified_high]),
        derive_recommendation([invalidated_high]),
    ) == (1, "Unverified SQL Injection", "UNVERIFIED", "REQUEST CHANGES", "APPROVE")


def test_orchestrator_review_feeds_comment_and_metrics_with_and_without_reporting(
    tmp_path: Path,
) -> None:
    """Verify #791: real _run_orchestrator_review output feeds PR comment and metrics
    with and without --no-reporting, preserving persona labels."""
    repo = _checkout(tmp_path / "repo", {"app.py": "import os\nprint('hello')\n"})
    mock_client = MagicMock(spec=ReviewLLMClient)
    mock_client.backend_info = "mock-llm"
    orchestrator = ReviewPipelineOrchestrator(
        session_id="test-791-rep",
        session_dir=tmp_path / "session",
        llm_client=mock_client,
        target_dir=repo,
    )
    qa_finding = SavedFinding(
        title="Unverified Test Coverage Gap",
        severity="MEDIUM",
        status="VERIFIED",
        verified=True,
        verified_by="llm",
        reportable=True,
        location="app.py:2",
        description="Missing unit tests",
        fix="Add test cases",
        persona="qa",
        persona_title="QA Engineer",
    )
    admitted = AdmittedFinding(
        anchor=ToolAnchor(run_id="bandit", result_index=0, rule_id="B602"),
        tool="bandit",
        rule_id="B602",
        path="app.py",
        line=1,
        message="subprocess shell=True",
        severity="HIGH",
        severity_derivation="rule",
        state=FindingState.OPEN,
        fingerprint_v2="fp791",
    )
    orchestrator.admitted_scanner_findings = [admitted]

    flags_no_rep = resolve_stage_flags(
        no_reporting=True, no_persona_review=True, no_static_scan=True
    )
    with patch.object(orchestrator, "_collect_and_deduplicate_findings", return_value=[qa_finding]):
        results_no_rep = _run_orchestrator_review(
            orchestrator,
            ["app.py"],
            {},
            repo,
            ["app.py"],
            ["qa"],
            Persona.DEVSECOPS,
            stage_flags=flags_no_rep,
        )

    comment_no_rep = format_pr_review_comment(results_no_rep, files=["app.py"])
    with patch("devops_cli.telemetry.instruments.emit") as mock_emit:
        _record_review_metrics(results_no_rep, 12.0, "pr")
        metrics_no_rep = [
            (call.args[1], call.args[2])
            for call in mock_emit.call_args_list
            if call.args[0].name == "devops_cli_findings_total"
        ]

    flags_rep = resolve_stage_flags(no_reporting=False, no_persona_review=True, no_static_scan=True)
    with patch.object(orchestrator, "_collect_and_deduplicate_findings", return_value=[qa_finding]):
        results_rep = _run_orchestrator_review(
            orchestrator,
            ["app.py"],
            {},
            repo,
            ["app.py"],
            ["qa"],
            Persona.DEVSECOPS,
            stage_flags=flags_rep,
        )

    comment_rep = format_pr_review_comment(results_rep, files=["app.py"])
    with patch("devops_cli.telemetry.instruments.emit") as mock_emit:
        _record_review_metrics(results_rep, 15.0, "pr")
        metrics_rep = [
            (call.args[1], call.args[2])
            for call in mock_emit.call_args_list
            if call.args[0].name == "devops_cli_findings_total"
        ]

    assert (
        "Zero findings identified." in comment_no_rep,
        "Unverified Test Coverage Gap" in comment_no_rep,
        "[bandit] B602" in comment_no_rep,
        metrics_no_rep,
        "Zero findings identified." in comment_rep,
        "Unverified Test Coverage Gap" in comment_rep,
        metrics_rep,
    ) == (
        False,
        True,
        True,
        [
            (1, {"persona": "qa", "severity": "MEDIUM", "status": "VERIFIED"}),
            (1, {"persona": "devsecops", "severity": "HIGH", "status": "VERIFIED"}),
        ],
        False,
        True,
        [(1, {"persona": "qa", "severity": "MEDIUM", "status": "VERIFIED"})],
    )


def test_orchestrator_review_no_static_scan_reports_analyzers_none_when_empty(
    tmp_path: Path,
) -> None:
    """Verify #657 constraint via real _run_orchestrator_review: --no-static-scan with zero
    findings emits Analyzers: None."""
    repo = _checkout(tmp_path / "repo", {"app.py": "x = 1\n"})
    mock_client = MagicMock(spec=ReviewLLMClient)
    mock_client.backend_info = "mock-llm"
    orchestrator = ReviewPipelineOrchestrator(
        session_id="test-791-scanners",
        session_dir=tmp_path / "session",
        llm_client=mock_client,
        target_dir=repo,
    )
    flags = resolve_stage_flags(no_static_scan=True, no_persona_review=True, no_reporting=True)
    results = _run_orchestrator_review(
        orchestrator,
        ["app.py"],
        {},
        repo,
        ["app.py"],
        ["devsecops"],
        None,
        stage_flags=flags,
    )
    comment = format_pr_review_comment(results, files=["app.py"])

    assert (
        "Zero findings identified." in comment,
        "- **Analyzers:** None" in comment,
    ) == (True, True)
