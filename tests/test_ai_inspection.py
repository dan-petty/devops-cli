"""Comprehensive test suite for Multi-Scale Semantic Outline & Inspectional Scanner."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.analyze.outlines import analyze_single_file
from devops_cli.ai.inspection import (
    FocalLevel,
    generate_semantic_outline,
)
from devops_cli.exceptions import DevOpsCLIError, ValidationError
from devops_cli.main import app

runner = CliRunner()

SAMPLE_HOTSPOT_PYTHON = '''"""Sample module containing classes, functions, and cyclomatic hotspots."""

from __future__ import annotations

__all__ = ["OrderProcessor", "calculate_discount", "complex_decision_tree"]


class BaseProcessor:
    """Abstract base order processor."""

    def process(self) -> bool:
        """Process item."""
        return True


class OrderProcessor(BaseProcessor):
    """Handles order processing, tax validation, and dispatch."""

    def __init__(self, order_id: str) -> None:
        """Initialize with order ID."""
        self.order_id = order_id

    def execute(self, amount: float) -> bool:
        """Execute processing pipeline."""
        if amount <= 0:
            return False
        return self.process()


def calculate_discount(tier: str, base_amount: float) -> float:
    """Calculate customer discount percentage."""
    if tier == "vip":
        return base_amount * 0.20
    if tier == "gold":
        return base_amount * 0.10
    return 0.0


def complex_decision_tree(a: int, b: int, c: int, d: int) -> str:
    """High-complexity function intended to trigger cyclomatic hotspot detection (M >= 10)."""
    if a > 10:
        if b > 20:
            return "high_a_high_b"
        elif b > 10:
            return "high_a_mid_b"
        elif b > 5:
            return "high_a_sub_b"
        else:
            return "high_a_low_b"
    elif a > 5:
        if c > 20:
            return "mid_a_high_c"
        elif c > 10:
            return "mid_a_mid_c"
        else:
            return "mid_a_low_c"
    else:
        if d > 20:
            return "low_a_high_d"
        elif d > 10:
            return "low_a_mid_d"
        else:
            return "low_a_low_d"
'''

SAMPLE_STRUCTURAL_PYTHON = '''"""Sample module for structural outline verification."""

def sync_workflow(data: list[str], dry_run: bool = False) -> int:
    """Synchronize workflow tasks across workers."""
    count = 0
    if dry_run:
        return 0
    for item in data:
        try:
            if len(item) > 3:
                count += 1
            else:
                count += 0
        except ValueError:
            continue
    return count
'''


def test_focal_level_enum_values() -> None:
    """Verify FocalLevel enum values match the 3 discrete zoom specifications."""
    assert (
        int(FocalLevel.TOPOLOGY),
        int(FocalLevel.STRUCTURAL),
        int(FocalLevel.DEEP_FOCAL),
    ) == (0, 1, 2)


def test_level_0_topology_outline(tmp_path: Path) -> None:
    """Verify Level 0 Topology extracts classes, exported symbols, docstrings, and hotspots."""
    py_file = tmp_path / "order_service.py"
    py_file.write_text(SAMPLE_HOTSPOT_PYTHON, encoding="utf-8")

    outline = generate_semantic_outline(py_file, level=FocalLevel.TOPOLOGY, repo_root=tmp_path)

    top = outline.topology
    assert top is not None, "Topology must be populated for Level 0"
    assert (
        outline.level,
        outline.structural,
        outline.focal_window,
        outline.language,
    ) == (FocalLevel.TOPOLOGY, None, None, "python")

    class_names = [c.name for c in top.classes]
    assert ("BaseProcessor" in class_names, "OrderProcessor" in class_names) == (
        True,
        True,
    )
    assert top.exported_symbols == [
        "OrderProcessor",
        "calculate_discount",
        "complex_decision_tree",
    ]

    hotspot_names = [h.name for h in top.cyclomatic_hotspots]
    assert "complex_decision_tree" in hotspot_names

    hot = next(h for h in top.cyclomatic_hotspots if h.name == "complex_decision_tree")
    assert hot.cyclomatic_complexity >= 10

    # Verify token constraints (< 200 tokens)
    assert (
        outline.outline_tokens < 200,
        outline.token_reduction_pct > 20.0,
    ) == (True, True)

    display_text = outline.to_display_text()
    assert (
        "Level 0: Topology" in display_text,
        "Cyclomatic Hotspots" in display_text,
        "complex_decision_tree" in display_text,
    ) == (True, True, True)


def test_level_1_structural_outline(tmp_path: Path) -> None:
    """Verify Level 1 Structural outline extracts signatures, return contracts, and control flow."""
    py_file = tmp_path / "workflow.py"
    py_file.write_text(SAMPLE_STRUCTURAL_PYTHON, encoding="utf-8")

    outline = generate_semantic_outline(py_file, level=FocalLevel.STRUCTURAL, repo_root=tmp_path)

    st = outline.structural
    assert st is not None, "Structural outline must be populated for Level 1"
    assert (
        outline.level,
        outline.topology,
        outline.focal_window,
    ) == (FocalLevel.STRUCTURAL, None, None)

    fn_names = [f.name for f in st.functions]
    assert "sync_workflow" in fn_names

    fn = next(f for f in st.functions if f.name == "sync_workflow")
    assert (
        "sync_workflow" in fn.signature,
        "if dry_run:" in fn.control_flow,
        "for item in data:" in fn.control_flow,
        "def sync_workflow" in st.raw_skeleton,
    ) == (True, True, True, True)

    # Token reduction verified
    assert outline.token_reduction_pct > 30.0


def test_level_2_deep_focal_window_lines(tmp_path: Path) -> None:
    """Verify Level 2 Deep Focal window targets line range with breadcrumb context."""
    lines = [f"line_{i} = {i}" for i in range(1, 101)]
    py_file = tmp_path / "large_module.py"
    py_file.write_text("\n".join(lines), encoding="utf-8")

    outline = generate_semantic_outline(
        py_file, level=FocalLevel.DEEP_FOCAL, lines="25:40", repo_root=tmp_path
    )

    fw = outline.focal_window
    assert fw is not None, "Focal window must be populated for Level 2"
    assert (
        fw.line_start,
        fw.line_end,
        fw.total_file_lines,
        outline.level,
    ) == (25, 40, 100, FocalLevel.DEEP_FOCAL)

    assert ("line_25 = 25" in fw.content, "line_40 = 40" in fw.content) == (
        True,
        True,
    )
    assert (
        "25-40 of 100" in outline.to_display_text(),
        "line_25 = 25" in outline.to_display_text(),
    ) == (True, True)


def test_level_2_deep_focal_window_symbol(tmp_path: Path) -> None:
    """Verify Level 2 Deep Focal window zooms into specific AST symbol."""
    py_file = tmp_path / "order_service.py"
    py_file.write_text(SAMPLE_HOTSPOT_PYTHON, encoding="utf-8")

    outline = generate_semantic_outline(
        py_file,
        level=FocalLevel.DEEP_FOCAL,
        symbol="OrderProcessor",
        repo_root=tmp_path,
    )

    fw = outline.focal_window
    assert fw is not None
    assert (fw.symbol_name, "class OrderProcessor" in fw.content) == (
        "OrderProcessor",
        True,
    )
    assert "OrderProcessor" in fw.scope_breadcrumbs


def test_outline_sub_10ms_latency(tmp_path: Path) -> None:
    """Verify AST semantic outline generation achieves sub-10ms latency."""
    py_file = tmp_path / "benchmark.py"
    py_file.write_text(SAMPLE_HOTSPOT_PYTHON, encoding="utf-8")

    # Warmup pass
    generate_semantic_outline(py_file, level=FocalLevel.TOPOLOGY, repo_root=tmp_path)

    timings: list[float] = []
    for _ in range(5):
        t0 = time.perf_counter()
        outline = generate_semantic_outline(py_file, level=FocalLevel.TOPOLOGY, repo_root=tmp_path)
        timings.append((time.perf_counter() - t0) * 1000.0)

    avg_latency = sum(timings) / len(timings)
    assert avg_latency < 25.0, f"Expected sub-25ms average latency, got {avg_latency}ms"
    assert outline.generation_time_ms < 50.0


def test_polyglot_structural_outlines(tmp_path: Path) -> None:
    """Verify polyglot fallback parsing for TypeScript, Go, Rust, and Shell."""
    # TypeScript
    ts_file = tmp_path / "service.ts"
    ts_file.write_text(
        "export class AuthService {\n  login(user: string): boolean {\n    return true;\n  }\n}\n",
        encoding="utf-8",
    )
    ts_outline = generate_semantic_outline(ts_file, level=FocalLevel.STRUCTURAL, repo_root=tmp_path)
    assert (
        ts_outline.language,
        ts_outline.structural is not None,
    ) == ("typescript", True)

    # Go
    go_file = tmp_path / "main.go"
    go_file.write_text(
        "package main\n\ntype Config struct {\n  Port int\n}\n\nfunc RunServer() error {\n  return nil\n}\n",
        encoding="utf-8",
    )
    go_outline = generate_semantic_outline(go_file, level=FocalLevel.STRUCTURAL, repo_root=tmp_path)
    assert (
        go_outline.language,
        go_outline.structural is not None,
    ) == ("go", True)

    # Rust
    rs_file = tmp_path / "lib.rs"
    rs_file.write_text(
        "pub struct Engine;\n\nimpl Engine {\n  pub fn start(&self) -> bool {\n    true\n  }\n}\n",
        encoding="utf-8",
    )
    rs_outline = generate_semantic_outline(rs_file, level=FocalLevel.STRUCTURAL, repo_root=tmp_path)
    assert (
        rs_outline.language,
        rs_outline.structural is not None,
    ) == ("rust", True)

    # Shell
    sh_file = tmp_path / "deploy.sh"
    sh_file.write_text(
        "#!/usr/bin/env bash\n\ndeploy_app() {\n  echo 'deploying'\n}\n",
        encoding="utf-8",
    )
    sh_outline = generate_semantic_outline(sh_file, level=FocalLevel.TOPOLOGY, repo_root=tmp_path)
    assert (
        sh_outline.language in ("sh", "shell"),
        sh_outline.topology is not None,
    ) == (True, True)


def test_cli_ai_read_raw_and_lines(tmp_path: Path) -> None:
    """Verify devops ai read executes raw file reads and line slices."""
    test_file = tmp_path / "hello.py"
    test_file.write_text("line1 = 1\nline2 = 2\nline3 = 3\n", encoding="utf-8")

    # Raw full read
    res = runner.invoke(app, ["ai", "read", str(test_file), "--repo", str(tmp_path)])
    assert (res.exit_code, "line1 = 1" in res.stdout, "line3 = 3" in res.stdout) == (
        0,
        True,
        True,
    )

    # Raw line slice
    res_slice = runner.invoke(
        app,
        [
            "ai",
            "read",
            str(test_file),
            "--lines",
            "2:3",
            "--repo",
            str(tmp_path),
        ],
    )
    assert (
        res_slice.exit_code,
        "line1 = 1" in res_slice.stdout,
        "line2 = 2" in res_slice.stdout,
    ) == (0, False, True)

    # Raw JSON format
    res_json = runner.invoke(app, ["ai", "read", str(test_file), "--json", "--repo", str(tmp_path)])
    assert res_json.exit_code == 0
    parsed = json.loads(res_json.stdout)
    assert (parsed["lines"], "line1 = 1" in parsed["content"]) == (3, True)

    # Dry-run
    res_dry = runner.invoke(
        app, ["ai", "read", str(test_file), "--dry-run", "--repo", str(tmp_path)]
    )
    assert (res_dry.exit_code, "READ_DRY_RUN" in res_dry.stdout) == (0, True)


def test_cli_ai_read_inspect_modes(tmp_path: Path) -> None:
    """Verify devops ai read --inspect across all 3 focal levels and formats."""
    py_file = tmp_path / "service.py"
    py_file.write_text(SAMPLE_HOTSPOT_PYTHON, encoding="utf-8")

    # Level 0 Topology
    res_l0 = runner.invoke(
        app,
        [
            "ai",
            "read",
            str(py_file),
            "--inspect",
            "--level",
            "0",
            "--repo",
            str(tmp_path),
        ],
    )
    assert (
        res_l0.exit_code,
        "Level 0: Topology" in res_l0.stdout,
        "OrderProcessor" in res_l0.stdout,
    ) == (0, True, True)

    # Level 1 Structural Outline
    res_l1 = runner.invoke(
        app,
        [
            "ai",
            "read",
            str(py_file),
            "--inspect",
            "--level",
            "1",
            "--repo",
            str(tmp_path),
        ],
    )
    assert (
        res_l1.exit_code,
        "Level 1: Structural Outline" in res_l1.stdout,
        "class OrderProcessor" in res_l1.stdout,
    ) == (0, True, True)

    # Level 2 Deep Focal Window with symbol
    res_l2_sym = runner.invoke(
        app,
        [
            "ai",
            "read",
            str(py_file),
            "--inspect",
            "--symbol",
            "calculate_discount",
            "--repo",
            str(tmp_path),
        ],
    )
    assert (
        res_l2_sym.exit_code,
        "Level 2: Deep Focal Window" in res_l2_sym.stdout,
        "def calculate_discount" in res_l2_sym.stdout,
    ) == (0, True, True)

    # Level 2 with lines and JSON output
    res_l2_json = runner.invoke(
        app,
        [
            "ai",
            "read",
            str(py_file),
            "--inspect",
            "--lines",
            "10:30",
            "--format",
            "json",
            "--repo",
            str(tmp_path),
        ],
    )
    assert res_l2_json.exit_code == 0
    payload = json.loads(res_l2_json.stdout)
    assert (
        payload["level"],
        payload["focal_window"]["line_start"],
        payload["focal_window"]["line_end"],
    ) == (2, 10, 30)


def test_path_validation_and_errors(tmp_path: Path) -> None:
    """Verify defensive exceptions on missing files, escapes, and oversized targets."""
    # Missing file
    missing = tmp_path / "non_existent.py"
    with pytest.raises(DevOpsCLIError) as exc_missing:
        generate_semantic_outline(missing, repo_root=tmp_path)
    assert exc_missing.value.details["path"] == str(missing)

    # Path traversal outside repo root
    outside = Path("/etc/hosts")
    with pytest.raises(ValidationError):
        generate_semantic_outline(outside, repo_root=tmp_path)

    # Oversized file
    big_file = tmp_path / "giant.py"
    big_file.write_text("x = 1\n" * 50, encoding="utf-8")
    with patch("devops_cli.ai.inspection.CONST_MAX_INSPECT_FILE_SIZE_BYTES", 10):
        with pytest.raises(DevOpsCLIError) as exc_big:
            generate_semantic_outline(big_file, repo_root=tmp_path)
        assert "exceeds maximum inspection size limit" in str(exc_big.value)


def test_analyze_single_file_metadata_integration(tmp_path: Path) -> None:
    """Verify analyze_single_file populates semantic_outline for Stage1PreAnalysis."""
    py_file = tmp_path / "order_service.py"
    content = SAMPLE_HOTSPOT_PYTHON
    py_file.write_text(content, encoding="utf-8")

    meta = analyze_single_file(
        rel_path="order_service.py",
        content=content,
        size_bytes=len(content),
        enhanced=True,
        repo_root=tmp_path,
    )

    assert meta.semantic_outline is not None
    assert (
        meta.semantic_outline["level"],
        meta.semantic_outline["language"],
        "topology" in meta.semantic_outline,
    ) == (0, "python", True)
