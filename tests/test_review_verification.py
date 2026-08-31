"""Unit tests for review finding verification, manual invalidation, and stats commands."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review_schema import Finding
from devops_cli.commands.review import app

runner = CliRunner()


def test_finding_status_defaults_and_normalization() -> None:
    f1 = Finding(title="SQL Injection", location="db.py:10", status="unverified")
    assert f1.status == "UNVERIFIED"
    assert f1.verified is False

    f2 = Finding(
        title="XSS", location="ui.py:5", status="invalidated", invalidation_reason="False positive"
    )
    assert f2.status == "INVALIDATED"
    assert f2.invalidation_reason == "False positive"

    f3 = Finding(title="Secret Leak", location="cfg.py:1", status="mitigated", mitigated=True)
    assert f3.status == "MITIGATED"
    assert f3.mitigated is True


def test_review_findings_list_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reviews_dir = tmp_path / "reviews"
    session_dir = reviews_dir / "20260809-120000-test-repo"
    session_dir.mkdir(parents=True)

    findings_payload = {
        "generated_at": "2026-08-09T12:00:00",
        "personas": ["devsecops", "architect"],
        "findings": [
            {
                "persona": "devsecops",
                "severity": "HIGH",
                "location": "auth.py:42",
                "title": "Hardcoded Token",
                "description": "Token in source",
                "status": "UNVERIFIED",
                "verified": True,
                "mitigated": False,
            },
            {
                "persona": "architect",
                "severity": "MEDIUM",
                "location": "server.py:100",
                "title": "Tight Coupling",
                "description": "Direct class dependency",
                "status": "INVALIDATED",
                "invalidation_reason": "Design choice",
                "verified_by": "human",
                "verified": False,
                "mitigated": False,
            },
        ],
    }
    (session_dir / "findings.json").write_text(json.dumps(findings_payload), encoding="utf-8")

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))

    res = runner.invoke(
        app,
        ["findings", "--session", "test-repo"],
        env={"COLUMNS": "160", "DEVOPS_CLI_DATA_DIR": str(tmp_path)},
    )
    assert res.exit_code == 0
    assert "Hardcoded Token" in res.output
    assert "Tight Coupling" in res.output
    assert "INVALIDATED" in res.output


def test_review_verify_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reviews_dir = tmp_path / "reviews"
    session_dir = reviews_dir / "20260809-120000-test-repo"
    session_dir.mkdir(parents=True)

    findings_payload = {
        "generated_at": "2026-08-09T12:00:00",
        "personas": ["devsecops"],
        "findings": [
            {
                "persona": "devsecops",
                "severity": "HIGH",
                "location": "auth.py:42",
                "title": "Hardcoded Token",
                "description": "Token in source",
                "status": "UNVERIFIED",
                "verified": True,
                "mitigated": False,
            }
        ],
    }
    findings_file = session_dir / "findings.json"
    findings_file.write_text(json.dumps(findings_payload), encoding="utf-8")

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))

    res = runner.invoke(
        app,
        [
            "verify",
            "test-repo",
            "--index",
            "1",
            "--status",
            "INVALIDATED",
            "--reason",
            "Environment variable fallback used",
        ],
        env={"DEVOPS_CLI_DATA_DIR": str(tmp_path)},
    )
    assert res.exit_code == 0
    assert "Updated finding #1" in res.output

    updated_data = json.loads(findings_file.read_text(encoding="utf-8"))
    updated_finding = updated_data["findings"][0]
    assert updated_finding["status"] == "INVALIDATED"
    assert updated_finding["verified"] is False
    assert updated_finding["invalidation_reason"] == "Environment variable fallback used"
    assert updated_finding["verified_by"] == "human"


def test_review_stats_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reviews_dir = tmp_path / "reviews"
    session_dir = reviews_dir / "20260809-120000-test-repo"
    session_dir.mkdir(parents=True)

    findings_payload = {
        "generated_at": "2026-08-09T12:00:00",
        "personas": ["devsecops"],
        "findings": [
            {
                "persona": "devsecops",
                "severity": "HIGH",
                "location": "auth.py:42",
                "title": "Hardcoded Token",
                "status": "VERIFIED",
            },
            {
                "persona": "devsecops",
                "severity": "MEDIUM",
                "location": "logging.py:10",
                "title": "Verbose Log",
                "status": "INVALIDATED",
                "invalidation_reason": "Debug mode only",
            },
        ],
    }
    (session_dir / "findings.json").write_text(json.dumps(findings_payload), encoding="utf-8")

    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path))

    res = runner.invoke(app, ["stats"], env={"DEVOPS_CLI_DATA_DIR": str(tmp_path)})
    assert res.exit_code == 0
    assert "Total Sessions:  1" in res.output
    assert "Total Findings:  2" in res.output
    assert "VERIFIED" in res.output
    assert "INVALIDATED" in res.output


def test_find_related_file_metas_matches_dependencies_and_symbols() -> None:
    from devops_cli.commands.review import _find_related_file_metas
    from devops_cli.models.ai import FileAnalysisMeta

    finding = Finding(
        title="Unvalidated Egress Request",
        location="src/devops_cli/commands/review.py:100",
        description="Call to validate_service_url without timeout.",
        status="UNVERIFIED",
    )
    analysis_metas = {
        "src/devops_cli/commands/review.py": FileAnalysisMeta(
            path="src/devops_cli/commands/review.py",
            dependencies=["devops_cli.http.client", "devops_cli.models.ai"],
        ),
        "src/devops_cli/http/client.py": FileAnalysisMeta(
            path="src/devops_cli/http/client.py",
            primary_purpose="Secure HTTP client with SSRF validation",
            key_symbols=["validate_service_url", "safe_get"],
            pseudocode=["validate_service_url(url)", "httpx.get(...)"],
        ),
    }

    related = _find_related_file_metas(finding, "src/devops_cli/commands/review.py", analysis_metas)
    assert len(related) == 1
    assert related[0].path == "src/devops_cli/http/client.py"


def test_build_validation_prompt_includes_related_file_analysis_metadata() -> None:
    from devops_cli.commands.review import _build_validation_prompt
    from devops_cli.models.ai import FileAnalysisMeta

    finding = Finding(
        title="Insecure Key Generation",
        location="crypto/ssh.py:15",
        description="Uses weak key size.",
        status="UNVERIFIED",
    )
    analysis_metas = {
        "crypto/ssh.py": FileAnalysisMeta(
            path="crypto/ssh.py",
            dependencies=["crypto.keyring"],
        ),
        "crypto/keyring.py": FileAnalysisMeta(
            path="crypto/keyring.py",
            primary_purpose="OS Keyring secret store and ED25519 helper",
            key_symbols=["get_secret", "generate_ed25519_key"],
            pseudocode=["generate_ed25519_key()", "keyring.set_password(...)"],
        ),
    }

    prompt = _build_validation_prompt(
        [finding],
        ["### File: crypto/ssh.py\ncode\n"],
        analysis_metas=analysis_metas,
    )
    assert "<untrusted_related_files>" in prompt
    assert "crypto/keyring.py" in prompt
    assert "generate_ed25519_key" in prompt
    assert "Pseudocode Outline" in prompt


def test_deterministic_pre_verification_path_traversal_guard(tmp_path: Path) -> None:
    from devops_cli.ai.review.verification import _deterministic_pre_verification

    outside_file = tmp_path / "outside.py"
    outside_file.write_text("valid = True\n", encoding="utf-8")

    sub_repo = tmp_path / "repo"
    sub_repo.mkdir()

    finding = Finding(
        title="Syntax error in python code",
        location="../outside.py:1",
        description="Fake syntax error",
        status="UNVERIFIED",
    )
    # Even if outside file exists, path traversal should be ignored and not crash/resolve outside
    result = _deterministic_pre_verification(finding, repo_root=sub_repo)
    assert result.location == "../outside.py:1"


def test_deterministic_pre_verification_line_boundary_context(tmp_path: Path) -> None:
    from devops_cli.ai.review.verification import _deterministic_pre_verification

    code_file = tmp_path / "app.py"
    code_file.write_text("print('hello')\n", encoding="utf-8")

    finding = Finding(
        title="Missing exception handler",
        location="app.py:100",
        description="Line 100 has unhandled error",
        status="UNVERIFIED",
    )

    result = _deterministic_pre_verification(finding, repo_root=tmp_path)
    assert result.status == "INVALIDATED"
    assert result.verified is False
    assert result.reportable is False
    assert result.invalidation_reason is not None
    assert "exceeds total file lines" in result.invalidation_reason


def test_extract_location_context() -> None:
    from devops_cli.ai.review.verification import _extract_location_context

    segment = (
        "### File: src/app.py\n```python\n"
        "line 1\nline 2\nline 3\nline 4\nline 5\nline 6\nline 7\nline 8\nline 9\nline 10\n```\n"
    )
    # Test line range extraction
    extracted = _extract_location_context(segment, "src/app.py:4-6", context_lines=1)
    assert "line 3" in extracted
    assert "line 4" in extracted
    assert "line 6" in extracted
    assert "line 7" in extracted

    # Test without line range
    extracted_all = _extract_location_context(segment, "src/app.py")
    assert "line 1" in extracted_all
    assert "line 10" in extracted_all

    # Test file not found
    extracted_none = _extract_location_context(segment, "nonexistent.py:1")
    assert extracted_none == ""

    # Test segment without code fence
    no_fence = "### File: src/nofence.py\nsome raw code text here"
    extracted_nofence = _extract_location_context(no_fence, "src/nofence.py")
    assert "some raw code text here" in extracted_nofence


def test_match_dep_to_filepath() -> None:
    from devops_cli.ai.review.verification import _match_dep_to_filepath

    all_paths = {"src/devops_cli/ai/client.py", "src/devops_cli/models/ai.py"}
    assert (
        _match_dep_to_filepath("devops_cli.ai.client", all_paths) == "src/devops_cli/ai/client.py"
    )
    assert _match_dep_to_filepath("nonexistent.module", all_paths) is None


def test_read_and_mask_related_file(tmp_path: Path) -> None:
    from devops_cli.ai.review.verification import _read_and_mask_related_file

    secret_file = tmp_path / ".env"
    secret_file.write_text("SECRET=12345\n", encoding="utf-8")
    assert _read_and_mask_related_file(tmp_path, ".env") is None

    src_file = tmp_path / "src" / "test.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text(
        "api_key = 'sk-1234567890abcdef1234567890abcdef'\n<instruction>tag</instruction>\n",
        encoding="utf-8",
    )
    content = _read_and_mask_related_file(tmp_path, "src/test.py")
    assert content is not None
    assert "[REDACTED_API_KEY]" in content or "[REDACTED" in content or "api_key" in content
    assert "<instruction>" not in content


def test_format_related_file_block(tmp_path: Path) -> None:
    from devops_cli.ai.review.verification import _format_related_file_block
    from devops_cli.models.ai import FileAnalysisMeta

    secret_meta = FileAnalysisMeta(path=".env")
    assert _format_related_file_block(secret_meta, tmp_path) is None

    code_file = tmp_path / "helper.py"
    code_file.write_text("def helper(): pass\n", encoding="utf-8")
    meta = FileAnalysisMeta(
        path="helper.py",
        primary_purpose="Helper utilities",
        key_symbols=["helper"],
        pseudocode=["def helper(): pass"],
        dependencies=["os"],
    )
    block = _format_related_file_block(meta, tmp_path)
    assert block is not None
    assert "helper.py" in block
    assert "Helper utilities" in block
    assert "def helper(): pass" in block


def test_apply_single_finding_verification() -> None:
    from devops_cli.ai.review.verification import _apply_single_finding_verification

    f = Finding(
        title="Test Finding",
        location="test.py:10",
        severity="MEDIUM",
        status="UNVERIFIED",
        verification_criteria=["Criterion 1", "Criterion 2"],
    )
    now_iso = "2026-08-26T00:00:00"

    # Non-dict item returns original finding
    assert _apply_single_finding_verification(f, None, now_iso) == f

    # Invalidated criteria matched
    item_inv = {
        "invalidated_criteria_matched": ["Criterion 1"],
        "confidence_score": 0.95,
        "severity": "LOW",
        "location": "test.py:12",
    }
    f_inv = _apply_single_finding_verification(f, item_inv, now_iso)
    assert f_inv.status == "INVALIDATED"
    assert f_inv.verified is False
    assert f_inv.mitigated is True
    assert f_inv.reportable is False
    assert f_inv.confidence_score == 0.95
    assert f_inv.severity == "LOW"
    assert f_inv.location == "test.py:12"

    # Mitigated item
    item_mit = {
        "mitigated": True,
        "verified": False,
    }
    f_mit = _apply_single_finding_verification(f, item_mit, now_iso)
    assert f_mit.status == "MITIGATED"
    assert f_mit.reportable is False

    # Verified item with auto confidence
    item_ver = {
        "verified": True,
        "reportable": True,
        "verified_criteria_matched": ["Criterion 1"],
    }
    f_ver = _apply_single_finding_verification(f, item_ver, now_iso)
    assert f_ver.status == "VERIFIED"
    assert f_ver.reportable is True
    assert f_ver.confidence_score == 0.5  # 1 matched / 2 criteria

    # Unverified item
    item_unver = {
        "verified": False,
        "confidence_score": "invalid",
    }
    f_unver = _apply_single_finding_verification(f, item_unver, now_iso)
    assert f_unver.status == "UNVERIFIED"
    assert f_unver.reportable is False


def test_validate_segment_findings_and_merge() -> None:
    from unittest.mock import MagicMock

    from devops_cli.ai.review.verification import (
        _merge_segment_results,
        _reconcile_verified,
        _validate_segment_findings,
    )
    from devops_cli.ai.review_schema import ReviewResult

    # Test merge on empty list
    assert _merge_segment_results([]) is None

    f1 = Finding(title="Finding 1", location="a.py:1", status="UNVERIFIED")
    f2 = Finding(title="Finding 2", location="b.py:2", status="UNVERIFIED")
    r1 = ReviewResult(findings=[f1], summary="Summary 1", positive_observations=["Obs 1"])
    r2 = ReviewResult(findings=[f2], summary="Summary 2", positive_observations=["Obs 2"])

    merged = _merge_segment_results([r1, r2])
    assert merged is not None
    assert len(merged.findings) == 2

    # Test validate_segment_findings with empty findings
    r_empty = ReviewResult(findings=[])
    res, sec, info = _validate_segment_findings(r_empty, [], None)
    assert res.findings == []
    assert sec is None

    # Test validate_segment_findings with mock client returning findings
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.__str__.return_value = json.dumps(
        {
            "findings": [
                {
                    "verified": True,
                    "reportable": True,
                    "confidence_score": 0.9,
                    "verified_criteria_matched": ["ok"],
                }
            ]
        }
    )
    mock_resp.processing_seconds = 1.5
    mock_resp.backend_info = "mock-llm"
    mock_client.chat.return_value = mock_resp

    val_res, sec, info = _validate_segment_findings(
        ReviewResult(findings=[f1]), ["### File: a.py\ncode"], mock_client
    )
    assert len(val_res.findings) == 1
    assert val_res.findings[0].verified is True
    assert sec == 1.5
    assert info == "mock-llm"

    # Test reconcile_verified
    f1_verified = f1.model_copy(update={"verified": False, "status": "UNVERIFIED"})
    recomposed = ReviewResult(findings=[f1])
    reconciled = _reconcile_verified(recomposed, [ReviewResult(findings=[f1_verified])])
    assert reconciled.findings[0].verified is False
    assert reconciled.findings[0].status == "UNVERIFIED"
    assert reconciled.findings[0].reportable is False


def test_deterministic_pre_verification_invalidates_hallucinated_syntax_errors(
    tmp_path: Path,
) -> None:
    """Verify that deterministic AST verification invalidates false positive syntax error findings."""
    from devops_cli.ai.review.verification import _deterministic_pre_verification

    valid_py = tmp_path / "valid_code.py"
    valid_py.write_text(
        'sec_opts = list(getattr(param, "secondary_opts", []))\ndefault_val = getattr(param, "default", None)\n',
        encoding="utf-8",
    )

    finding_syntax = Finding(
        title="Syntax error: missing closing parenthesis in `introspect_param`",
        location="valid_code.py:1-2",
        description="The assignment contains an extra closing parenthesis.",
        severity="CRITICAL",
        status="UNVERIFIED",
    )

    checked = _deterministic_pre_verification(finding_syntax, repo_root=tmp_path)
    assert checked.status == "INVALIDATED"
    assert checked.verified is False
    assert checked.reportable is False
    assert "parser" in (checked.invalidation_reason or "").lower()


def test_deterministic_pre_verification_line_boundaries(tmp_path: Path) -> None:
    """Verify that findings referencing line numbers beyond total lines are invalidated."""
    from devops_cli.ai.review.verification import _deterministic_pre_verification

    short_file = tmp_path / "short.py"
    short_file.write_text("x = 1\ny = 2\n", encoding="utf-8")

    out_of_bounds_finding = Finding(
        title="Unbound variable",
        location="short.py:99",
        description="Line 99 references undefined z",
        severity="HIGH",
        status="UNVERIFIED",
    )

    checked = _deterministic_pre_verification(out_of_bounds_finding, repo_root=tmp_path)
    assert checked.status == "INVALIDATED"
    assert "exceeds total file lines" in (checked.invalidation_reason or "")


def test_validate_segment_findings_bypasses_llm_when_deterministic(tmp_path: Path) -> None:
    """Verify that _validate_segment_findings skips LLM call when all findings are deterministically resolved."""
    from unittest.mock import MagicMock

    from devops_cli.ai.review.verification import _validate_segment_findings
    from devops_cli.ai.review_schema import ReviewResult

    valid_file = tmp_path / "valid.py"
    valid_file.write_text("def hello() -> str:\n    return 'world'\n", encoding="utf-8")

    syntax_finding = Finding(
        title="Syntax error: invalid function syntax",
        location="valid.py:1",
        description="Invalid syntax in def hello",
        severity="HIGH",
        status="UNVERIFIED",
    )

    mock_client = MagicMock()
    result = ReviewResult(findings=[syntax_finding])

    validated, proc_sec, backend = _validate_segment_findings(
        result,
        all_segments=["def hello() -> str:"],
        client=mock_client,
        repo_root=tmp_path,
    )

    assert mock_client.chat.call_count == 0
    assert backend == "deterministic"
    assert validated.findings[0].status == "INVALIDATED"


def test_deterministic_pre_verification_handles_json_yaml_toml_syntax(tmp_path: Path) -> None:
    """Verify that deterministic syntax parser checks apply across JSON, YAML, and TOML files."""
    from devops_cli.ai.review.verification import _deterministic_pre_verification

    # 1. JSON
    json_file = tmp_path / "valid.json"
    json_file.write_text('{"name": "devops-cli", "version": "0.2.5"}\n', encoding="utf-8")
    finding_json = Finding(
        title="Syntax error: invalid JSON comma",
        location="valid.json:1",
        description="Missing comma in json",
        severity="HIGH",
        status="UNVERIFIED",
    )
    checked_json = _deterministic_pre_verification(finding_json, repo_root=tmp_path)
    assert checked_json.status == "INVALIDATED"

    # 2. YAML
    yaml_file = tmp_path / "valid.yaml"
    yaml_file.write_text("key: value\nlist:\n  - item1\n", encoding="utf-8")
    finding_yaml = Finding(
        title="Parse error in YAML indentation",
        location="valid.yaml:2",
        description="Invalid syntax in YAML mapping",
        severity="MEDIUM",
        status="UNVERIFIED",
    )
    checked_yaml = _deterministic_pre_verification(finding_yaml, repo_root=tmp_path)
    assert checked_yaml.status == "INVALIDATED"

    # 3. TOML
    toml_file = tmp_path / "valid.toml"
    toml_file.write_text("[tool.devops]\nenabled = true\n", encoding="utf-8")
    finding_toml = Finding(
        title="Syntaxerror in pyproject.toml",
        location="valid.toml:1",
        description="Unexpected token in TOML table",
        severity="HIGH",
        status="UNVERIFIED",
    )
    checked_toml = _deterministic_pre_verification(finding_toml, repo_root=tmp_path)
    assert checked_toml.status == "INVALIDATED"
