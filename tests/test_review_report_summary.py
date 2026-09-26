"""Tests for AI code review report Executive Summary generation with key good and bad patterns."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review_schema import SavedFinding


def _make_dummy_pipeline(tmp_path: Path) -> ReviewPipelineOrchestrator:
    pipeline = ReviewPipelineOrchestrator(
        target_dir=tmp_path,
        session_id="20260906-test-exec-summary",
    )
    return pipeline


def test_consolidated_markdown_report_clean_executive_summary(tmp_path: Path) -> None:
    pipeline = _make_dummy_pipeline(tmp_path)
    report_md = pipeline._build_consolidated_markdown_report(
        session_id="test-clean-session",
        generated_at="2026-09-06T12:00:00Z",
        reportable_findings=[],
        all_deps=[],
        all_nets=[],
    )

    assert (
        "# Code Review Report (Session `test-clean-session`)" in report_md,
        "## Executive Summary" in report_md,
        "### Key Good Patterns Observed" not in report_md,
        "The codebase demonstrates exceptional engineering quality" not in report_md,
        "0 reportable defects" in report_md,
        "No critical anti-patterns or recurring defect patterns identified" in report_md,
        "✅ **No critical issues found during review.**" in report_md,
    ) == (True, True, True, True, True, True, True)


def test_consolidated_markdown_report_with_findings_patterns(tmp_path: Path) -> None:
    pipeline = _make_dummy_pipeline(tmp_path)

    findings = [
        SavedFinding(
            id=1,
            severity="CRITICAL",
            location="src/devops_cli/core/repo.py:168-174",
            title="list_repo_files can expose files outside repository via symlink traversal",
            description="Symlink traversal allows path traversal outside repo root.",
            status="VERIFIED",
            verified=True,
            reportable=True,
            persona_title="Principal DevSecOps Engineer",
        ),
        SavedFinding(
            id=2,
            severity="HIGH",
            location="k8s/argocd/apps/infra-apps.yaml:13",
            title="Insecure git:// protocol used for ArgoCD repoURL",
            description="Cleartext git protocol permits network tampering.",
            status="VERIFIED",
            verified=True,
            reportable=True,
            persona_title="Principal DevSecOps Engineer",
        ),
        SavedFinding(
            id=3,
            severity="HIGH",
            location="src/devops_cli/ai/agents/tools.py:45-46",
            title="Missing argument validation for tools with no defined parameters",
            description="Unbounded parameters skip path traversal checking.",
            status="VERIFIED",
            verified=True,
            reportable=True,
            persona_title="Principal DevSecOps Engineer",
        ),
    ]

    report_md = pipeline._build_consolidated_markdown_report(
        session_id="test-findings-session",
        generated_at="2026-09-06T12:00:00Z",
        reportable_findings=findings,
        all_deps=[],
        all_nets=[],
    )

    lower_report = report_md.lower()
    assert (
        "## Executive Summary" in report_md,
        "### Key Good Patterns Observed" not in report_md,
        any(
            header in report_md
            for header in ("### Key Bad Patterns Observed", "### Key Anti-Patterns Observed")
        ),
        any(kw in lower_report for kw in ("path traversal", "filesystem")),
        any(kw in lower_report for kw in ("protocol", "network", "insecure")),
        any(kw in lower_report for kw in ("validation", "parameter", "input")),
    ) == (True, True, True, True, True, True)


def test_executive_summary_single_low_finding_described_by_own_theme_only(
    tmp_path: Path,
) -> None:
    """A review with a single low finding describes only that finding's theme without generic security text."""
    pipeline = _make_dummy_pipeline(tmp_path)
    finding = SavedFinding(
        id=1,
        severity="LOW",
        location="src/utils.py:10",
        title="Missing docstring in helper function",
        description="Public helper function should include a docstring.",
        status="VERIFIED",
        verified=True,
        reportable=True,
        persona_title="Senior QA Engineer",
    )
    report_md = pipeline._build_consolidated_markdown_report(
        session_id="test-low-session",
        generated_at="2026-09-06T12:00:00Z",
        reportable_findings=[finding],
        all_deps=[],
        all_nets=[],
    )
    assert (
        "Missing docstring in helper function" in report_md,
        "path traversal defenses" not in report_md,
        "transport protocol safeguards" not in report_md,
        "security risks" not in report_md,
    ) == (True, True, True, True)


def test_unqueried_dependencies_not_marked_clean(tmp_path: Path) -> None:
    """Unqueried dependencies default to NOT_QUERIED / Not Queried and emit no false good patterns."""
    from devops_cli.models.vulnerability import DependencySpec

    pipeline = _make_dummy_pipeline(tmp_path)
    dep_unqueried = DependencySpec(
        name="some-pkg",
        version_range=">=1.0.0",
        ecosystem="PyPI",
    )
    assert (dep_unqueried.severity, dep_unqueried.security_status, dep_unqueried.queried) == (
        "NOT_QUERIED",
        "Not Queried",
        False,
    )
    report_md = pipeline._build_consolidated_markdown_report(
        session_id="test-dep-session",
        generated_at="2026-09-06T12:00:00Z",
        reportable_findings=[],
        all_deps=[dep_unqueried],
        all_nets=[],
    )
    assert (
        "### Key Good Patterns Observed" not in report_md,
        "Not Queried" in report_md,
    ) == (True, True)


def test_queried_dependencies_clean_yields_good_pattern(tmp_path: Path) -> None:
    """Queried clean dependencies emit Supply Chain & Lockfile Integrity pattern with counts."""
    from devops_cli.models.vulnerability import DependencySpec

    pipeline = _make_dummy_pipeline(tmp_path)
    dep_clean = DependencySpec(
        name="pydantic",
        version_range="2.11.0",
        ecosystem="PyPI",
        severity="CLEAN",
        security_status="✓ Clean",
        queried=True,
    )
    report_md = pipeline._build_consolidated_markdown_report(
        session_id="test-dep-clean-session",
        generated_at="2026-09-06T12:00:00Z",
        reportable_findings=[],
        all_deps=[dep_clean],
        all_nets=[],
    )
    assert (
        "### Key Good Patterns Observed" in report_md,
        "Supply Chain & Lockfile Integrity" in report_md,
        "1 external dependencies queried against vulnerability databases with zero critical/high CVEs"
        in report_md,
    ) == (True, True, True)


def test_static_analyzers_ran_yields_good_pattern(tmp_path: Path) -> None:
    """When static analyzers ran with zero critical findings, an executive summary pattern records it."""
    pipeline = _make_dummy_pipeline(tmp_path)
    pipeline.static_analyzers = {"Bandit": "ran", "Semgrep": "ran"}
    report_md = pipeline._build_consolidated_markdown_report(
        session_id="test-analyzers-session",
        generated_at="2026-09-06T12:00:00Z",
        reportable_findings=[],
        all_deps=[],
        all_nets=[],
    )
    assert (
        "### Key Good Patterns Observed" in report_md,
        "Static Security Analysis" in report_md,
        "2 static analyzer(s) executed (Bandit, Semgrep) with 0 critical findings." in report_md,
    ) == (True, True, True)


def test_network_references_states_counts(tmp_path: Path) -> None:
    """Network references in review scope state local and external counts."""
    from devops_cli.models.vulnerability import NetworkReference

    pipeline = _make_dummy_pipeline(tmp_path)
    nets = [
        NetworkReference(target="127.0.0.1", reference_type="ipv4", is_local=True),
        NetworkReference(target="example.com", reference_type="domain", is_local=False),
    ]
    report_md = pipeline._build_consolidated_markdown_report(
        session_id="test-nets-session",
        generated_at="2026-09-06T12:00:00Z",
        reportable_findings=[],
        all_deps=[],
        all_nets=nets,
    )
    assert (
        "### Key Good Patterns Observed" in report_md,
        "Network Reference Review" in report_md,
        "2 network reference(s) identified (1 local, 1 external)" in report_md,
    ) == (True, True, True)


def test_consolidated_markdown_report_with_errored_files(tmp_path: Path) -> None:
    """Ensure that reviews encountering provider or analysis errors do not report a false-clean executive summary."""
    pipeline = _make_dummy_pipeline(tmp_path)
    pipeline.errored_files["src/devops_cli/commands/ai.py"] = "Review: Cannot connect to Ollama"

    report_md = pipeline._build_consolidated_markdown_report(
        session_id="test-errored-session",
        generated_at="2026-09-11T02:00:00Z",
        reportable_findings=[],
        all_deps=[],
        all_nets=[],
    )

    assert "## Executive Summary" in report_md
    assert "The automated review encountered errors on **1 file(s)**" in report_md
    assert "The codebase demonstrates exceptional engineering quality" not in report_md
    assert "## Skipped / Errored Files" in report_md
    assert "`src/devops_cli/commands/ai.py`" in report_md
    assert "Cannot connect to Ollama" in report_md


def test_format_error_detail_sanitizes_and_bounds() -> None:
    """Verify _format_error_detail masks secrets and bounds error strings to <= 256 chars."""
    from devops_cli.ai.review.pipeline import _format_error_detail

    # 1. Credential masking
    secret_exc = ValueError(
        "Failed with token ghp_1234567890abcdef1234 and pass password='secret_pwd_1234!'"
    )
    cleaned = _format_error_detail("Review", secret_exc)
    assert "ghp_1234567890abcdef1234" not in cleaned
    assert "<masked-github-token>" in cleaned
    assert "secret_pwd_1234!" not in cleaned

    # 2. Length bounding to <= 256 chars
    huge_exc = RuntimeError("Server returned huge body: " + "A" * 500)
    bounded = _format_error_detail("Initialization", huge_exc, max_len=256)
    assert len(bounded) <= 256
    assert bounded.endswith("...")


def test_format_markdown_fix_balances_and_escapes() -> None:
    """Ensure fix recommendations are cleanly formatted into Markdown with balanced code fences."""
    from devops_cli.ai.review.pipeline import format_markdown_fix

    # 1. Plain code with backticks inside: requires outer 4 backticks
    fix_with_ticks = 'return f"`{var}`"'
    res1 = format_markdown_fix(fix_with_ticks)

    # 2. Text already containing a complete code fence block
    fix_with_fence = "Use CSP:\n```\nheader { ... }\n```\nDone."
    res2 = format_markdown_fix(fix_with_fence)

    # 3. Truncated/unclosed code fence from LLM output: auto-balanced
    unclosed_fix = "Apply patch:\n```python\ndef foo(): pass"
    res3 = format_markdown_fix(unclosed_fix)

    # 4. Empty / whitespace-only fix
    res4 = format_markdown_fix("   ")

    # 5. Fix with literal backticks inside inline string (e.g. print("```")): wrapped in 4 backticks, not malformed
    fix_inline_ticks = 'print("```")'
    res5 = format_markdown_fix(fix_inline_ticks)

    assert (
        res1.startswith("- **Fix Recommendation**:\n```\n"),
        res2.count("```") % 2,
        res3.endswith("\n```"),
        res4,
        res5.startswith('- **Fix Recommendation**:\n````\nprint("```")\n````'),
    ) == (True, 0, True, "", True)


def test_escape_markdown_title_and_heading_asterisks() -> None:
    """Ensure asterisks in finding titles are escaped to prevent Markdown heading and table collisions."""
    from devops_cli.ai.review.sanitization import escape_markdown_title

    heading_title = escape_markdown_title("Unused **kwargs in resolve_stage_flags", is_table=False)
    table_title = escape_markdown_title("Handle *ptr | and **kwargs", is_table=True)
    backticked_title = escape_markdown_title("Unused `**kwargs` and `*args`", is_table=False)
    unclosed_backtick = escape_markdown_title("Unclosed `backtick title", is_table=False)

    assert (
        heading_title,
        table_title,
        backticked_title,
        unclosed_backtick,
    ) == (
        r"Unused \*\*kwargs in resolve_stage_flags",
        r"Handle \*ptr \| and \*\*kwargs",
        "Unused `**kwargs` and `*args`",
        "Unclosed `backtick title`",
    )


def test_derive_finding_theme_strips_scanner_prefixes_and_avoids_word_hyphens() -> None:
    """Ensure finding themes strip bracketed scanner tags and do not split internal hyphens/backticks."""
    from devops_cli.ai.review.stages.reporting import _derive_finding_theme

    f_dry = SavedFinding(
        id=1,
        severity="HIGH",
        location="a.py:1",
        title="[DRY-RUN] Simulated Pluto Deprecated K8s API Detection",
    )
    f_gitleaks = SavedFinding(
        id=2,
        severity="CRITICAL",
        location="b.py:1",
        title="[GITLEAKS:simulated-secret] [DRY-RUN] Simulated Secret Detection",
    )
    f_flag = SavedFinding(
        id=3,
        severity="HIGH",
        location="c.py:1",
        title="Potential bypass of PR merge readiness check due to `--allow-blocked-state` flag",
    )
    f_kwargs = SavedFinding(
        id=4,
        severity="LOW",
        location="d.py:1",
        title="Unused **kwargs in resolve_stage_flags",
    )
    f_proto = SavedFinding(
        id=5,
        severity="HIGH",
        location="e.py:1",
        title="Insecure git:// protocol used for ArgoCD repoURL",
    )

    t_dry = _derive_finding_theme(f_dry)
    t_gitleaks = _derive_finding_theme(f_gitleaks)
    t_flag = _derive_finding_theme(f_flag)
    t_kwargs = _derive_finding_theme(f_kwargs)
    t_proto = _derive_finding_theme(f_proto)

    assert (
        t_dry,
        t_gitleaks,
        t_flag.count("`") % 2,
        "**" in t_kwargs,
        t_proto,
    ) == (
        "Simulated Pluto Deprecated K8s API Detection",
        "Simulated Secret Detection",
        0,
        False,
        "Insecure git:// protocol used for ArgoCD repoURL",
    )


def _find_table_column_mismatches(markdown_lines: list[str]) -> list[str]:
    """Inspect Markdown lines and identify table rows with column counts differing from the header."""
    import re

    mismatches: list[str] = []
    in_table = False
    expected_cols = 0
    for line in markdown_lines:
        if not (line.startswith("|") and line.endswith("|")):
            in_table = False
            continue
        parts = [c for c in re.split(r"(?<!\\)\|", line)[1:-1]]
        if not in_table:
            in_table = True
            expected_cols = len(parts)
        elif not re.match(r"^\|(\s*:?-+:?\s*\|)+$", line) and len(parts) != expected_cols:
            mismatches.append(line)
    return mismatches


def test_consolidated_markdown_report_markdown_invariants(tmp_path: Path) -> None:
    """Ensure generated review report strictly adheres to Markdown syntax invariants."""
    pipeline = _make_dummy_pipeline(tmp_path)

    findings = [
        SavedFinding(
            id=1,
            severity="CRITICAL",
            location="src/auth.py:10",
            title="[GITLEAKS:token] Simulated Secret Leak",
            description="** Description from LLM **:\nFound secret `ghp_token`.\n```\ntoken = 123",
            fix="```python\ndef fix():\n    return 1\n```",
            status="VERIFIED",
            verified=True,
            reportable=True,
            persona_title="Principal DevSecOps Engineer",
        ),
        SavedFinding(
            id=2,
            severity="HIGH",
            location="src/util.py:20",
            title="Flag `--allow-blocked-state` bypasses verification",
            description="Multiline description line 1.\nLine 2 with `inline_code`.",
            fix="Run with `devops --check`",
            status="VERIFIED",
            verified=True,
            reportable=True,
            persona_title="Senior QA Engineer",
        ),
    ]

    report_md = pipeline._build_consolidated_markdown_report(
        session_id="invariant-test-session",
        generated_at="2026-09-18T12:00:00Z",
        reportable_findings=findings,
        all_deps=[],
        all_nets=[],
    )

    # 1. Even number of total code fences (zero unclosed blocks)
    fences_count = report_md.count("```")
    # 2. Executive summary bad pattern lines have balanced brackets and no broken bold
    bad_pattern_lines = [
        line
        for line in report_md.splitlines()
        if line.startswith("- **") and "finding(s) identified" in line
    ]
    unclosed_bold = [line for line in bad_pattern_lines if line.count("**") < 2 or "**[" in line]
    # 3. Table consistency: every table row has matching pipe count
    table_mismatches = _find_table_column_mismatches(report_md.splitlines())

    assert (
        fences_count % 2,
        len(unclosed_bold),
        len(table_mismatches),
    ) == (0, 0, 0)


def test_consolidated_markdown_report_none_severity(tmp_path: Path) -> None:
    """Verify that findings with severity=None default safely to INFORMATIONAL without error."""
    pipeline = _make_dummy_pipeline(tmp_path)
    finding = SavedFinding(
        id=1,
        location="src/test.py:10",
        title="Finding with None severity",
        description="Detailed explanation",
        status="VERIFIED",
        verified=True,
        reportable=True,
        persona_title="Senior QA Engineer",
    )
    object.__setattr__(finding, "severity", None)
    report_md = pipeline._build_consolidated_markdown_report(
        session_id="none-severity-session",
        generated_at="2026-09-18T12:00:00Z",
        reportable_findings=[finding],
        all_deps=[],
        all_nets=[],
    )
    assert "| **INFORMATIONAL** |" in report_md
    assert "### 1. [INFORMATIONAL] Finding with None severity" in report_md
