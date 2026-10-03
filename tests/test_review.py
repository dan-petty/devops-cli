"""Unit tests covering the devops review CLI subcommands and workflows."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, sentinel

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review.history import review_subject
from devops_cli.ai.review_schema import ReviewSessionPayload, SavedFinding
from devops_cli.commands.review import app as review_app

runner = CliRunner()


def test_review_explain() -> None:
    """Verify review subcommands with --explain flag."""
    res = runner.invoke(review_app, ["path", "--explain"])
    assert res.exit_code == 0

    res_pr = runner.invoke(review_app, ["pr", "123", "--explain"])
    assert res_pr.exit_code == 0

    res_br = runner.invoke(review_app, ["branch", "feat/test", "--explain"])
    assert res_br.exit_code == 0


def test_review_path_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify devops review path workflow execution."""
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )
    py_file = tmp_path / "app.py"
    py_file.write_text("def run():\n    pass\n", encoding="utf-8")

    mock_wf = [(MagicMock(title="Architect", name="architect"), "Review comments")]
    with (
        patch(
            "devops_cli.commands.review._prepare_path_content",
            return_value=(["code page"], "Path Review", "AGENTS.md", []),
        ),
        patch("devops_cli.commands.review._execute_review_workflow", return_value=mock_wf),
        patch("devops_cli.commands.review.load_settings"),
    ):
        res = runner.invoke(review_app, ["path", str(py_file), "--persona", "architect"])
        assert res.exit_code == 0


def test_review_branch_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify devops review branch workflow execution, handed the base revision its diff
    starts from (#593)."""
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )

    mock_wf = [(MagicMock(title="DevSecOps", name="devsecops"), "Security comments")]
    prepared = (
        ["diff content"],
        "Branch Review",
        "AGENTS.md",
        "feat/my-feature",
        sentinel.base_revision,
    )
    with (
        patch("devops_cli.commands.review._prepare_branch_content", return_value=prepared),
        patch(
            "devops_cli.commands.review._execute_review_workflow", return_value=mock_wf
        ) as workflow,
        patch("devops_cli.commands.review.load_settings"),
    ):
        res = runner.invoke(review_app, ["branch", "feat/my-feature", "--persona", "devsecops"])

    assert (res.exit_code, workflow.call_args.kwargs["base_revision"]) == (
        0,
        sentinel.base_revision,
    )


def test_review_pr_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify devops review pr workflow execution, handed the base revision its diff starts
    from (#593)."""
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )
    mock_pull = MagicMock()
    mock_wf = [(MagicMock(title="QA", name="qa"), "QA feedback")]
    prepared = (["pr diff"], "PR 10", "AGENTS.md", mock_pull, "org/repo", sentinel.base_revision)

    with (
        patch("devops_cli.config.settings.get_github_token", return_value="ghp_test"),
        patch("devops_cli.commands.review._prepare_pr_content", return_value=prepared),
        patch(
            "devops_cli.commands.review._execute_review_workflow", return_value=mock_wf
        ) as workflow,
        patch("devops_cli.commands.review.load_settings"),
    ):
        res = runner.invoke(review_app, ["pr", "10", "--persona", "qa"])

    assert (res.exit_code, workflow.call_args.kwargs["base_revision"]) == (
        0,
        sentinel.base_revision,
    )


def test_review_findings_stats_export_feedback(tmp_path: Path) -> None:
    """Verify review findings, stats, and export-feedback subcommands."""
    session_dir = tmp_path / "session_1"
    session_dir.mkdir()
    findings_file = session_dir / "findings.json"
    session_payload = ReviewSessionPayload(
        subject=review_subject("path", str(tmp_path), []),
        findings=[],
        generated_at=datetime.now(UTC).isoformat(),
    )
    findings_file.write_text(session_payload.model_dump_json(), encoding="utf-8")

    with (
        patch("devops_cli.commands.review._find_session_dir", return_value=session_dir),
        patch(
            "devops_cli.commands.review.export_invalidated_feedback",
            return_value=(1, tmp_path / "fb.jsonl"),
        ),
    ):
        res_find = runner.invoke(review_app, ["findings"])
        assert res_find.exit_code == 0

        res_stats = runner.invoke(review_app, ["stats"])
        assert res_stats.exit_code == 0

        res_fb = runner.invoke(
            review_app,
            [
                "export-feedback",
                "--reviews-dir",
                str(tmp_path),
                "--output",
                str(tmp_path / "fb.jsonl"),
            ],
        )
        assert res_fb.exit_code == 0


def test_review_verify_command(tmp_path: Path) -> None:
    """Verify devops review verify updating finding status."""
    from devops_cli.ai.review_schema import SavedFinding

    session_dir = tmp_path / "session_verify"
    session_dir.mkdir()
    findings_file = session_dir / "findings.json"

    f1 = SavedFinding(
        title="SQL Injection",
        location="src/db.py:10",
        description="Raw SQL concatenation",
        fix="Use parameters",
        status="UNVERIFIED",
    )
    f2 = SavedFinding(
        title="Weak Cryptography",
        location="src/crypto.py:20",
        description="MD5 usage",
        fix="Use SHA256",
        status="UNVERIFIED",
    )
    session_payload = ReviewSessionPayload(
        subject=review_subject("path", str(tmp_path), []),
        findings=[f1, f2],
        generated_at=datetime.now(UTC).isoformat(),
    )
    findings_file.write_text(session_payload.model_dump_json(), encoding="utf-8")

    with patch("devops_cli.commands.review._find_session_dir", return_value=session_dir):
        # Update by index
        res_idx = runner.invoke(
            review_app, ["verify", "session_verify", "--index", "1", "--status", "VERIFIED"]
        )
        assert res_idx.exit_code == 0
        assert "VERIFIED" in res_idx.output

        # Update by title pattern
        res_title = runner.invoke(
            review_app,
            [
                "verify",
                "session_verify",
                "--title",
                "Weak Crypto",
                "--status",
                "INVALIDATED",
                "--reason",
                "False positive",
            ],
        )
        assert res_title.exit_code == 0
        assert "INVALIDATED" in res_title.output

        # Index out of bounds
        res_oob = runner.invoke(
            review_app, ["verify", "session_verify", "--index", "99", "--status", "VERIFIED"]
        )
        assert res_oob.exit_code == 1

        # Invalid status choice
        res_bad_st = runner.invoke(
            review_app, ["verify", "session_verify", "--index", "1", "--status", "INVALID_CHOICE"]
        )
        assert res_bad_st.exit_code == 1

        # Neither index nor title provided
        res_no_spec = runner.invoke(
            review_app, ["verify", "session_verify", "--status", "VERIFIED"]
        )
        assert res_no_spec.exit_code == 1

        # Findings command filtering
        res_unver = runner.invoke(
            review_app, ["findings", "--session", "session_verify", "--unverified"]
        )
        assert res_unver.exit_code == 0

        res_ver = runner.invoke(
            review_app, ["findings", "--session", "session_verify", "--verified"]
        )
        assert res_ver.exit_code == 0

        res_inval = runner.invoke(
            review_app, ["findings", "--session", "session_verify", "--invalidated"]
        )
        assert res_inval.exit_code == 0


def test_review_stats_and_export_empty(tmp_path: Path) -> None:
    """Verify review stats and export-feedback empty behavior."""
    # Stats with non-existent directory
    res_no_dir = runner.invoke(
        review_app, ["stats", "--reviews-dir", str(tmp_path / "nonexistent")]
    )
    assert res_no_dir.exit_code == 0

    # Stats with empty directory
    empty_dir = tmp_path / "empty_reviews"
    empty_dir.mkdir()
    res_empty = runner.invoke(review_app, ["stats", "--reviews-dir", str(empty_dir)])
    assert res_empty.exit_code == 0

    # Export feedback when count is 0
    with patch(
        "devops_cli.commands.review.export_invalidated_feedback",
        return_value=(0, tmp_path / "empty.jsonl"),
    ):
        res_exp_0 = runner.invoke(review_app, ["export-feedback", "--reviews-dir", str(empty_dir)])
        assert res_exp_0.exit_code == 0


def test_review_error_branches_and_patch_failure(tmp_path: Path) -> None:
    """Verify error branches for missing session dirs, missing findings.json, and apply-patch failure."""
    # 1. verify with non-existent session
    res_no_sess = runner.invoke(
        review_app, ["verify", "nonexistent_sess_123", "--index", "1", "--status", "VERIFIED"]
    )
    assert res_no_sess.exit_code == 1

    # 2. verify with missing findings.json
    empty_sess = tmp_path / "empty_sess"
    empty_sess.mkdir()
    with patch("devops_cli.commands.review._find_session_dir", return_value=empty_sess):
        res_no_find = runner.invoke(
            review_app, ["verify", "empty_sess", "--index", "1", "--status", "VERIFIED"]
        )
        assert res_no_find.exit_code == 1

        # findings with missing findings.json
        res_find_none = runner.invoke(review_app, ["findings", "--session", "empty_sess"])
        assert res_find_none.exit_code == 0


def test_review_multiple_targets_and_findings_options(tmp_path: Path) -> None:
    """Verify review path with multiple file targets, patterns, and findings formatting."""
    f1 = tmp_path / "app1.py"
    f2 = tmp_path / "app2.py"
    f1.write_text("def a(): pass\n", encoding="utf-8")
    f2.write_text("def b(): pass\n", encoding="utf-8")

    with (
        patch("devops_cli.commands.review._execute_review_workflow") as mock_exec,
        patch("devops_cli.ai.review.runner._is_allowed_review_boundary", return_value=True),
    ):
        res_multi = runner.invoke(
            review_app, ["path", str(f1), str(f2), "--pattern", "*.py", "--persona", "architect"]
        )
        assert res_multi.exit_code == 0
        mock_exec.assert_called_once()


def _create_sample_review_session(target_dir: Path) -> Path:
    """Helper to initialize a test review session fixture."""
    from devops_cli.ai.review_schema import ReviewSessionPayload, SavedFinding

    sess_dir = target_dir / "rev_sess_1"
    sess_dir.mkdir(exist_ok=True)
    f1 = SavedFinding(
        id="f-001",
        persona="devsecops",
        severity="HIGH",
        title="Hardcoded API Key",
        location="src/app.py:10",
        description="Found sensitive secret in source",
        status="UNVERIFIED",
    )
    f2 = SavedFinding(
        id="f-002",
        persona="architect",
        severity="MEDIUM",
        title="Cyclic Dependency",
        location="src/mod.py:20",
        description="Circular import between modules",
        status="UNVERIFIED",
    )
    payload = ReviewSessionPayload(
        generated_at="2026-08-26T12:00:00Z",
        subject=review_subject("path", "src/", []),
        findings=[f1, f2],
    )
    (sess_dir / "findings.json").write_text(payload.model_dump_json(indent=2), encoding="utf-8")
    return sess_dir


def test_review_verify_with_title_pattern_and_status(tmp_path: Path) -> None:
    """Verify review verify with title pattern, invalid status, and out of bounds indices."""
    sess_dir = _create_sample_review_session(tmp_path)

    with patch("devops_cli.commands.review._find_session_dir", return_value=sess_dir):
        res_ver_title = runner.invoke(
            review_app,
            [
                "verify",
                "rev_sess_1",
                "--title",
                "Hardcoded",
                "--status",
                "INVALIDATED",
                "--reason",
                "False positive test token",
            ],
        )
        assert res_ver_title.exit_code == 0
        assert "status → INVALIDATED" in res_ver_title.output

        res_ver_bad_st = runner.invoke(
            review_app, ["verify", "rev_sess_1", "--index", "2", "--status", "UNKNOWN_STATUS"]
        )
        assert res_ver_bad_st.exit_code == 1

        res_ver_oob = runner.invoke(
            review_app, ["verify", "rev_sess_1", "--index", "99", "--status", "VERIFIED"]
        )
        assert res_ver_oob.exit_code == 1

        res_ver_mit = runner.invoke(
            review_app, ["verify", "rev_sess_1", "--index", "2", "--status", "MITIGATED"]
        )
        assert res_ver_mit.exit_code == 0


def test_review_stats_command(tmp_path: Path) -> None:
    """Verify review stats command execution across saved sessions."""
    _create_sample_review_session(tmp_path)
    res_stats = runner.invoke(review_app, ["stats", "--reviews-dir", str(tmp_path)])
    assert (
        res_stats.exit_code,
        "Finding Status Breakdown" in res_stats.output,
        "Persona False Positive Rate" in res_stats.output,
        "Category False Positive Rate (Invalidated)" in res_stats.output,
    ) == (0, True, True, True)


def test_review_findings_details_pretty_printing(tmp_path: Path) -> None:
    """Verify review findings command with --details formatting."""
    sess_dir = _create_sample_review_session(tmp_path)
    with patch("devops_cli.commands.review._find_session_dir", return_value=sess_dir):
        res_details = runner.invoke(
            review_app, ["findings", "--session", "rev_sess_1", "--details"]
        )
        assert res_details.exit_code == 0
        assert "Finding #1" in res_details.output
        assert "Hardcoded API Key" in res_details.output
        assert "Found sensitive secret in source" in res_details.output


def test_format_clean_text_field_and_finding_unwrapping() -> None:
    """Verify that format_clean_text_field unwraps raw lists, tuples, and stringified Python lists."""
    from devops_cli.ai.review_schema import Finding, format_clean_text_field

    # Test raw list of strings
    raw_list = ["Step 1: Validate input", "Step 2: Apply boundary check"]
    assert (
        format_clean_text_field(raw_list) == "Step 1: Validate input\nStep 2: Apply boundary check"
    )

    # Test stringified Python list
    stringified_list = "['Validate module path prefix', 'Reject untrusted modules']"
    cleaned = format_clean_text_field(stringified_list)
    assert cleaned == "Validate module path prefix\nReject untrusted modules"
    assert "['" not in cleaned

    # Test Finding initialization with list fix and description
    finding_dict = {
        "title": ["Insecure", "Deserialization"],
        "location": "src/loader.py:10",
        "description": ["Avoid pickle.loads", "Use json.loads instead"],
        "fix": ["Replace pickle with json", "Add schema validation"],
        "references": "['https://cwe.mitre.org/995', 'https://owasp.org']",
    }
    f = Finding(**finding_dict)
    assert f.title == "Insecure Deserialization"
    assert f.description == "Avoid pickle.loads\nUse json.loads instead"
    assert f.fix == "Replace pickle with json\nAdd schema validation"
    assert f.references == ["https://cwe.mitre.org/995", "https://owasp.org"]


def test_review_path_watch_mode(tmp_path: Path) -> None:
    """Verify devops review path --watch executes DebouncedFileWatcher."""
    py_file = tmp_path / "app.py"
    py_file.write_text("def run(): pass\n", encoding="utf-8")

    with (
        patch("devops_cli.commands.review._make_review_clients"),
        patch("devops_cli.commands.review.load_settings"),
        patch("devops_cli.watchers.file_watcher.DebouncedFileWatcher.watch") as mock_watcher_watch,
    ):
        res = runner.invoke(review_app, ["path", str(py_file), "--watch", "--debounce-ms", "300"])
        assert res.exit_code == 0
        assert mock_watcher_watch.called


def test_finding_location_and_title_sanitizes_criteria_leakage() -> None:
    """Verify that criteria leakage or prompt instructions in location and title are stripped."""
    from devops_cli.ai.review_schema import Finding

    raw_finding = {
        "title": "Syntax error in foo: line where defined. Provide verification criteria: None.",
        "location": "src/devops_cli/commands/install_tools.py: line where _current_version defined. Provide fix: change to except. Provide verification criteria: Running CLI should not crash. Invalidation criteria: CLI runs cleanly.",
        "description": "Defect details",
    }
    f = Finding(**raw_finding)
    assert f.location == "src/devops_cli/commands/install_tools.py:1"
    assert "Provide verification criteria" not in f.title
    assert "Invalidation criteria" not in f.location


def test_tally_findings_splits_comma_joined_personas() -> None:
    """Verify that _tally_findings splits comma-joined persona strings."""
    from devops_cli.ai.review.history import HistoryFinding
    from devops_cli.commands.review import _tally_findings

    findings = [
        HistoryFinding(title="SQL Injection", status="INVALIDATED", persona="devsecops, architect"),
        HistoryFinding(
            title="Unbounded Concurrency", status="VERIFIED", persona="architect, performance"
        ),
        HistoryFinding(title="Missing Test", status="UNVERIFIED", persona=""),
    ]

    expected_status = {"VERIFIED": 1, "UNVERIFIED": 1, "INVALIDATED": 1, "MITIGATED": 0}
    expected_total = {"devsecops": 1, "architect": 2, "performance": 1, "unknown": 1}
    expected_invalidated = {"devsecops": 1, "architect": 1}
    assert _tally_findings(findings) == (expected_status, expected_total, expected_invalidated)


_PREPARED_REVIEWS = {
    "path": ("_prepare_path_content", ["path", "app.py"], (["page"], "Path Review", "", [])),
    "branch": (
        "_prepare_branch_content",
        ["branch", "feat/x"],
        (["diff"], "Branch Review", "", "feat/x", sentinel.base_revision),
    ),
    "pr": (
        "_prepare_pr_content",
        ["pr", "10"],
        (["diff"], "PR 10", "", MagicMock(), "org/repo", sentinel.base_revision),
    ),
}


@pytest.mark.parametrize("target", sorted(_PREPARED_REVIEWS))
@pytest.mark.parametrize(("flags", "full_output"), [(["--full"], True), ([], False)])
def test_review_full_flag_reaches_the_review_workflow(
    target: str, flags: list[str], full_output: bool
) -> None:
    """`--full` asks the review to print its whole report to the terminal (#987)."""
    prepare, command, prepared = _PREPARED_REVIEWS[target]
    with (
        patch("devops_cli.config.settings.get_github_token", return_value="ghp_test"),
        patch(f"devops_cli.commands.review.{prepare}", return_value=prepared),
        patch("devops_cli.commands.review._make_review_clients"),
        patch("devops_cli.commands.review._init_logfire_if_enabled"),
        patch("devops_cli.commands.review._execute_review_workflow", return_value=[]) as workflow,
        patch("devops_cli.commands.review.load_settings"),
    ):
        result = runner.invoke(review_app, [*command, *flags])

    assert (result.exit_code, workflow.call_args.kwargs["full_output"]) == (0, full_output)


def _listed_numbers(output: str, titles: tuple[str, ...]) -> tuple[str, ...]:
    """The number in the first column of the table row naming each title; "" when not listed."""
    rows = output.splitlines()
    return tuple(next((row.split()[0] for row in rows if title in row), "") for title in titles)


def _saved_finding(title: str, severity: str, status: str = "UNVERIFIED") -> SavedFinding:
    return SavedFinding(
        severity=severity, location="src/app.py:4", title=title, persona="qa", status=status
    )


def test_review_findings_filters_by_severity_and_keeps_each_number_in_findings_json(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """`--severity` is repeatable and takes any spelling of a severity, which is how a review
    names its LOW and INFO findings. Each finding keeps its number in findings.json, the one
    `review verify --index` takes, and titles print as written, brackets included (#987)."""
    titles = (
        "Hardcoded token",
        "Closing tag [/{status_color}] in format string",
        "Second hardcoded token",
        "Pin uvicorn[standard]",
    )
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261002-180320",
        generated_at="2026-10-02T18:03:20+00:00",
        findings=[
            _saved_finding(title, severity)
            for title, severity in zip(titles, ("HIGH", "LOW", "HIGH", "INFO"), strict=True)
        ],
    )

    result = runner.invoke(
        review_app,
        ["findings", session.name, "--severity", "low", "--severity", "informational"],
        env={"COLUMNS": "200"},
    )

    assert (result.exit_code, _listed_numbers(result.output, titles)) == (0, ("", "2", "", "4"))


def test_review_findings_severity_lists_candidates_by_their_numbers_in_candidates_json(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """`--severity` combines with `--candidates` and a status filter: candidates.json's LOW
    candidates that verification invalidated, under their numbers there (#987, #949)."""
    titles = ("Dropped nit", "Dropped traversal", "Open nit", "Another dropped nit")
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261002-180320",
        generated_at="2026-10-02T18:03:20+00:00",
        findings=[_saved_finding("Open nit", "LOW")],
        candidates=[
            _saved_finding(title, severity, status)
            for title, severity, status in zip(
                titles,
                ("LOW", "HIGH", "LOW", "LOW"),
                ("INVALIDATED", "INVALIDATED", "UNVERIFIED", "INVALIDATED"),
                strict=True,
            )
        ],
    )

    result = runner.invoke(
        review_app,
        ["findings", session.name, "--candidates", "--invalidated", "--severity", "LOW"],
        env={"COLUMNS": "200"},
    )

    assert (
        result.exit_code,
        f"Candidates: {session.name}" in result.output,
        _listed_numbers(result.output, titles),
    ) == (0, True, ("1", "", "", "4"))


def test_review_findings_prints_untrusted_text_as_written(
    isolate_data_dir: Path, write_review_session: Callable[..., Path]
) -> None:
    """A finding's title, location, persona and verdict reason come from a model or the code
    under review, so `devops review findings` prints them as written: a closing tag no longer
    stops the command with a MarkupError, and a lowercase bracket no longer vanishes (#987)."""
    finding = SavedFinding(
        severity="MEDIUM",
        location="src/[bold]app.py:4",
        title="Closing tag [/{status_color}] in format string",
        persona="qa[ops]",
        status="INVALIDATED",
        reportable=False,
        verified_by="human",
        invalidation_reason="Pinned as uvicorn[standard] already",
    )
    session = write_review_session(
        isolate_data_dir / "reviews" / "20261002-180320",
        generated_at="2026-10-02T18:03:20+00:00",
        findings=[finding],
    )

    result = runner.invoke(review_app, ["findings", session.name], env={"COLUMNS": "200"})

    assert (
        result.exit_code,
        "Closing tag [/{status_color}] in format string" in result.output,
        "src/[bold]app.py:4" in result.output,
        "qa[ops]" in result.output,
        "human: Pinned as uvicorn[standard] already" in result.output,
    ) == (0, True, True, True, True)
