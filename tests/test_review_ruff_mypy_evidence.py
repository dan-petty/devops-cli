"""Unit tests for Ruff, mypy, and C901 complexity review evidence integration (#873)."""

from __future__ import annotations

import json
from pathlib import Path

from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review_schema import Finding, ReviewSessionPayload
from devops_cli.config.constants import (
    CONST_COMPLEXITY_SOURCE,
)
from devops_cli.core.code_metrics import FunctionComplexity
from devops_cli.security.complexity import (
    _evaluate_single_function_delta,
    compute_complexity_deltas,
)
from devops_cli.security.mypy import (
    parse_mypy_output,
    run_mypy_scan,
    verify_uv_lock_match,
)
from devops_cli.security.ruff import (
    RuffScanner,
    filter_or_group_advisories,
    parse_ruff_sarif,
)

# ── Acceptance Criterion 1 & 2: C901 Complexity Deltas ───────────────────────


def test_complexity_delta_hardcoded_function_going_from_3_to_12_and_unchanged() -> None:
    """Verify C901 delta records function going from 3 to 12 and omits unchanged one (#873)."""
    # Function going from 3 to 12
    fn_changing_base = FunctionComplexity(
        name="calculate_metrics",
        cyclomatic_complexity=3,
        max_nesting_depth=1,
        line_number=10,
        end_line_number=20,
    )
    fn_changing_head = FunctionComplexity(
        name="calculate_metrics",
        cyclomatic_complexity=12,
        max_nesting_depth=3,
        line_number=10,
        end_line_number=35,
    )

    delta_changed, finding_changed = _evaluate_single_function_delta(
        rel_path="src/metrics.py",
        name="calculate_metrics",
        base_fn=fn_changing_base,
        head_fn=fn_changing_head,
        cap=10,
        max_increase=None,
    )

    # Unchanged function (5 to 5)
    fn_unchanged_base = FunctionComplexity(
        name="helper_func",
        cyclomatic_complexity=5,
        max_nesting_depth=2,
        line_number=40,
        end_line_number=50,
    )
    fn_unchanged_head = FunctionComplexity(
        name="helper_func",
        cyclomatic_complexity=5,
        max_nesting_depth=2,
        line_number=40,
        end_line_number=50,
    )

    delta_unchanged, finding_unchanged = _evaluate_single_function_delta(
        rel_path="src/metrics.py",
        name="helper_func",
        base_fn=fn_unchanged_base,
        head_fn=fn_unchanged_head,
        cap=10,
        max_increase=None,
    )

    expected_delta = {
        "file": "src/metrics.py",
        "function": "calculate_metrics",
        "before": 3,
        "after": 12,
        "source": CONST_COMPLEXITY_SOURCE,
    }

    assert (delta_changed, delta_unchanged, finding_unchanged) == (
        expected_delta,
        None,
        None,
    )
    assert finding_changed is not None
    assert (
        finding_changed.location,
        finding_changed.title,
        finding_changed.severity,
    ) == (
        "src/metrics.py:10",
        "High Cyclomatic Complexity in `calculate_metrics` (12 > 10)",
        "MEDIUM",
    )


def test_complexity_deltas_added_and_removed_functions() -> None:
    """Verify added function has before: None and removed has after: None."""
    base_src = """
def kept_func():
    return 1

def old_func():
    a = 1
    if a:
        return 2
    return 3
"""
    head_src = """
def kept_func():
    return 1

def new_func():
    x = 10
    if x > 5:
        return 1
    return 0
"""
    deltas, _findings = compute_complexity_deltas(
        {"app.py": base_src},
        {"app.py": head_src},
        cap=10,
    )

    delta_funcs = {d["function"]: (d["before"], d["after"], d["source"]) for d in deltas}

    assert (
        "kept_func" in delta_funcs,
        delta_funcs.get("new_func"),
        delta_funcs.get("old_func"),
    ) == (
        False,
        (None, 2, CONST_COMPLEXITY_SOURCE),
        (2, None, CONST_COMPLEXITY_SOURCE),
    )


def test_complexity_table_rendering_in_markdown(tmp_path: Path) -> None:
    """Verify review.md gets a before/after Complexity table (#873)."""
    orchestrator = ReviewPipelineOrchestrator(session_id="test-c901", target_dir=tmp_path)
    orchestrator.complexity_deltas = [
        {
            "file": "src/app.py",
            "function": "complex_worker",
            "before": 3,
            "after": 12,
            "source": CONST_COMPLEXITY_SOURCE,
        },
        {
            "file": "src/app.py",
            "function": "new_helper",
            "before": None,
            "after": 4,
            "source": CONST_COMPLEXITY_SOURCE,
        },
        {
            "file": "src/old.py",
            "function": "deleted_func",
            "before": 7,
            "after": None,
            "source": CONST_COMPLEXITY_SOURCE,
        },
    ]

    report = orchestrator._build_consolidated_markdown_report("test-c901", "now", [], [], [])

    assert "## Complexity" in report
    complexity_section = report.split("## Complexity\n", 1)[1].split("\n\n", 1)[0]
    expected_rows = [
        "| File | Function | Before | After |",
        "|---|---|---|---|",
        "| `src/app.py` | `complex_worker` | 3 | 12 |",
        "| `src/app.py` | `new_helper` | — | 4 |",
        "| `src/old.py` | `deleted_func` | 7 | — |",
    ]
    assert complexity_section.splitlines() == expected_rows


# ── Acceptance Criterion 3: Ruff SARIF Parsing ───────────────────────────────


def test_ruff_sarif_parsing_and_command_building(tmp_path: Path) -> None:
    """Verify RuffScanner parses SARIF output and constructs correct command list."""
    sample_file = tmp_path / "pricing.py"
    sample_file.write_text("x = 1\n", encoding="utf-8")
    sample_sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ruff",
                        "rules": [
                            {
                                "id": "BLE001",
                                "name": "blind-except",
                                "helpUri": "https://docs.astral.sh/ruff/rules/blind-except/",
                            }
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": "BLE001",
                        "level": "warning",
                        "message": {"text": "Do not catch blind exception: `Exception`"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "src/pricing.py"},
                                    "region": {"startLine": 55, "endLine": 55},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }

    findings = parse_ruff_sarif(sample_sarif)
    assert len(findings) == 1
    f = findings[0]
    assert (
        f.location,
        f.severity,
        f.title,
        "https://docs.astral.sh/ruff/rules/blind-except/" in f.fix,
    ) == (
        "src/pricing.py:55",
        "MEDIUM",
        "[BLE001] Do not catch blind exception: `Exception`",
        True,
    )

    scanner = RuffScanner()
    cmd = scanner.build_command(
        sample_file, advisory_rules=["BLE001"], config_path="pyproject.toml"
    )
    assert any("--extend-select=BLE001" in arg for arg in cmd)
    assert any("--output-format=sarif" in arg for arg in cmd)


# ── Acceptance Criterion 4: Advisory Rules Filtering ─────────────────────────


def test_advisory_rules_filtered_to_diff_hunks_on_pr_or_branch() -> None:
    """Verify advisory findings report only inside diff hunks for branch and PR reviews."""
    findings = [
        Finding(
            severity="MEDIUM",
            location="src/pricing.py:55",
            title="[BLE001] Do not catch blind exception",
            description="desc",
            fix="fix",
        ),
        Finding(
            severity="MEDIUM",
            location="src/pricing.py:120",
            title="[BLE001] Do not catch blind exception outside hunk",
            description="desc",
            fix="fix",
        ),
        Finding(
            severity="HIGH",
            location="src/pricing.py:200",
            title="[E999] SyntaxError outside hunk",
            description="desc",
            fix="fix",
        ),
    ]

    diff_hunks = {"src/pricing.py": [(50, 60)]}

    filtered = filter_or_group_advisories(
        findings,
        advisory_rules=["BLE001"],
        diff_hunks=diff_hunks,
        is_branch_or_pr=True,
    )

    # BLE001 at line 55 is kept; BLE001 at line 120 is filtered out; non-advisory E999 is kept
    locations = [f.location for f in filtered]
    assert locations == ["src/pricing.py:200", "src/pricing.py:55"]


def test_advisory_rules_grouped_per_rule_and_file_on_path_review() -> None:
    """Verify advisory findings are grouped one per (rule, file) on path reviews."""
    findings = [
        Finding(
            severity="MEDIUM",
            location="src/pricing.py:55",
            title="[BLE001] Do not catch blind exception at 55",
            description="desc1",
            fix="fix",
        ),
        Finding(
            severity="MEDIUM",
            location="src/pricing.py:67",
            title="[BLE001] Do not catch blind exception at 67",
            description="desc2",
            fix="fix",
        ),
    ]

    grouped = filter_or_group_advisories(
        findings,
        advisory_rules=["BLE001"],
        is_branch_or_pr=False,
    )

    assert len(grouped) == 1
    g = grouped[0]
    assert (
        g.location,
        g.severity,
        g.title,
        "line(s): 55, 67" in g.description,
    ) == (
        "src/pricing.py:55",
        "LOW",
        "[BLE001] 2 advisory finding(s) in src/pricing.py",
        True,
    )


# ── Acceptance Criterion 5: mypy uv.lock & Environment Isolation ─────────────


def test_mypy_lock_matching_and_coverage_gap(tmp_path: Path) -> None:
    """Verify mypy flags coverage gap when worktree uv.lock differs from checkout."""
    wt_dir = tmp_path / "worktree"
    co_dir = tmp_path / "checkout"
    wt_dir.mkdir()
    co_dir.mkdir()

    # Case 1: Mismatched uv.lock
    (wt_dir / "uv.lock").write_text("lock-version-worktree", encoding="utf-8")
    (co_dir / "uv.lock").write_text("lock-version-checkout", encoding="utf-8")

    assert verify_uv_lock_match(wt_dir, co_dir) is False

    outcome_mismatch = run_mypy_scan(
        target=[wt_dir / "app.py"],
        tree=wt_dir,
        checkout_root=co_dir,
    )
    assert (outcome_mismatch.status, outcome_mismatch.reason) == (
        "coverage_gap",
        "worktree uv.lock hash does not match checkout; uv sync never runs on a reviewed tree",
    )

    # Case 2: Matching uv.lock
    (wt_dir / "uv.lock").write_text("identical-lock-content", encoding="utf-8")
    (co_dir / "uv.lock").write_text("identical-lock-content", encoding="utf-8")

    assert verify_uv_lock_match(wt_dir, co_dir) is True


def test_mypy_output_parsing() -> None:
    """Verify parsing of standard console mypy output into Finding models."""
    raw_mypy = """
src/service.py:42: error: Incompatible types in assignment (expression has type "int", variable has type "str")  [assignment]
src/service.py:88: note: See https://mypy.readthedocs.io for details
src/models.py:15: error: Function is missing a return type annotation  [no-untyped-def]
"""
    findings = parse_mypy_output(raw_mypy)
    assert len(findings) == 2

    assert (
        findings[0].location,
        findings[0].severity,
        findings[0].title,
        findings[1].location,
        findings[1].title,
    ) == (
        "src/service.py:42",
        "HIGH",
        '[assignment] Incompatible types in assignment (expression has type "int", variable has type "str")',
        "src/models.py:15",
        "[no-untyped-def] Function is missing a return type annotation",
    )


# ── Acceptance Criterion 6: Session JSON keeps complexity_delta ──────────────


def test_session_json_payload_keeps_complexity_delta() -> None:
    """Verify ReviewSessionPayload serializes complexity_delta field correctly."""
    deltas = [
        {
            "file": "src/main.py",
            "function": "run_job",
            "before": 3,
            "after": 12,
            "source": CONST_COMPLEXITY_SOURCE,
        }
    ]

    payload = ReviewSessionPayload(
        generated_at="2026-10-09T00:00:00Z",
        complexity_delta=deltas,
    )

    data = json.loads(payload.model_dump_json())
    assert data["complexity_delta"] == deltas
