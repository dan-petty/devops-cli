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
    _render_topology_markdown,
    estimate_tokens,
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

SAMPLE_TYPESCRIPT_SERVICE = """export interface UserPayload {
  id: string;
}

export class AuthService {
  login(payload: UserPayload): boolean {
    return true;
  }

  logout(): void {}
}

export function validateEmail(email: string): boolean {
  return email.includes("@");
}

export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}
"""

SAMPLE_RUST_QUALIFIED_FNS = """pub fn plain(x: i32) -> i32 { x }
pub fn process<T: Clone>(x: T) -> T { x }
pub const fn c() -> u8 { 1 }
unsafe fn u() {}
"""

# Server is declared in another file of the package.
SAMPLE_GO_RECEIVERS = """package pool

type WorkerPool struct {
\tworkers int
}

func NewWorkerPool(workers int) *WorkerPool {
\treturn &WorkerPool{workers: workers}
}

func (w *WorkerPool) Start() error {
\treturn nil
}

func (w WorkerPool) Stop() {}

func (s *Server) Close() {}
"""

SAMPLE_CPP_OUT_OF_CLASS = """class Widget {
 public:
  void draw();
  int width() const { return 1; }
};

void Widget::draw() {}

int helper() { return 0; }
"""

SAMPLE_CPP_HEADER = """namespace fmt {
class writer {
 public:
  void write(const char* s);
  int size() const { return 0; }
};
}
"""

SAMPLE_C_HEADER = """struct point { int x; int y; };
int add(int a, int b);
static inline int twice(int a) { return a * 2; }
"""

SAMPLE_JAVA_ANNOTATED = """public class OrderService {
    @Override
    public String toString() { return ""; }

    @Transactional @Deprecated
    public Order placeOrder(Cart cart) throws OrderException { return null; }
}
"""

SAMPLE_CSHARP_ATTRIBUTED = """[ApiController]
public class UsersController : ControllerBase
{
    [HttpGet("{id}")]
    public ActionResult<User> Get(int id)
    {
        return null;
    }
}
"""


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

    # The rendered outline measures 149 tokens; the symbol-count guess it replaced said 33 (#959).
    assert (
        100 < outline.outline_tokens < 200,
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
    assert avg_latency < 2000.0, f"Runaway bound exceeded: {avg_latency:.2f}ms >= 2000.0ms"
    assert outline.generation_time_ms < 5000.0, (
        f"Runaway bound exceeded: {outline.generation_time_ms:.2f}ms >= 5000.0ms"
    )


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
        # Shell is parsed by the bash grammar (#506).
        sh_outline.language == "bash",
        sh_outline.topology is not None,
    ) == (True, True)


def test_polyglot_structural_skeleton_keeps_names_and_return_types(tmp_path: Path) -> None:
    """Verify a TypeScript skeleton line is the declaration, with its name and return type; the
    regex fallback rendered only the parameter list, `  (x: string, y: number)` (#959)."""
    ts_file = tmp_path / "service.ts"
    ts_file.write_text(
        "export function a(x: string, y: number): Promise<void> {}\n", encoding="utf-8"
    )

    outline = generate_semantic_outline(ts_file, level=FocalLevel.STRUCTURAL, repo_root=tmp_path)
    skeleton = outline.structural.raw_skeleton if outline.structural else ""

    assert ("a(" in skeleton, "Promise<void>" in skeleton) == (True, True)


def test_rust_outline_finds_generic_const_unsafe_fns(tmp_path: Path) -> None:
    """Verify generic, const and unsafe Rust functions are outlined and can be focused on; the
    regex fallback found only `plain`, and `--symbol process` fell back to lines 1-4 (#959)."""
    rs_file = tmp_path / "lib.rs"
    rs_file.write_text(SAMPLE_RUST_QUALIFIED_FNS, encoding="utf-8")

    topology = generate_semantic_outline(
        rs_file, level=FocalLevel.TOPOLOGY, repo_root=tmp_path
    ).topology
    focal = generate_semantic_outline(
        rs_file, level=FocalLevel.DEEP_FOCAL, symbol="process", repo_root=tmp_path
    ).focal_window

    assert (
        {f.name for f in topology.functions} if topology else set(),
        focal.line_start if focal else None,
        "process" in (focal.scope_breadcrumbs if focal else ""),
    ) == ({"plain", "process", "c", "u"}, 2, True)


def test_polyglot_outlines_come_from_tree_sitter(tmp_path: Path) -> None:
    """Verify a TypeScript class lists its methods at Level 0 and `--symbol` spans the whole
    function, which only tree-sitter gives: the regex fallback scopes no TypeScript method to
    its class and spans each symbol by its declaration line alone (#959)."""
    ts_file = tmp_path / "service.ts"
    ts_file.write_text(SAMPLE_TYPESCRIPT_SERVICE, encoding="utf-8")

    topology = generate_semantic_outline(
        ts_file, level=FocalLevel.TOPOLOGY, repo_root=tmp_path
    ).topology
    focal = generate_semantic_outline(
        ts_file, level=FocalLevel.DEEP_FOCAL, symbol="validateEmail", repo_root=tmp_path
    ).focal_window

    assert (
        [(c.name, c.methods) for c in topology.classes] if topology else [],
        [f.name for f in topology.functions] if topology else [],
        (focal.line_start, focal.line_end) if focal else None,
    ) == (
        [("UserPayload", []), ("AuthService", ["login", "logout"])],
        ["validateEmail", "normalizeEmail"],
        (13, 15),
    )


def test_polyglot_topology_keeps_go_receiver_and_cpp_out_of_class_methods(
    tmp_path: Path,
) -> None:
    """Verify a Go method is listed under its receiver's struct, or as `Type.Method` when the
    type is declared in another file, and a C++ out-of-class definition among the functions;
    tree-sitter gave both no owner, and Level 0 dropped every method without one (#959)."""
    (tmp_path / "pool.go").write_text(SAMPLE_GO_RECEIVERS, encoding="utf-8")
    (tmp_path / "widget.cpp").write_text(SAMPLE_CPP_OUT_OF_CLASS, encoding="utf-8")

    def level_0(name: str) -> tuple[list[tuple[str, list[str]]], list[str]]:
        top = generate_semantic_outline(
            tmp_path / name, level=FocalLevel.TOPOLOGY, repo_root=tmp_path
        ).topology
        return (
            ([(c.name, c.methods) for c in top.classes], [f.name for f in top.functions])
            if top
            else ([], [])
        )

    focal = generate_semantic_outline(
        tmp_path / "pool.go", level=FocalLevel.DEEP_FOCAL, symbol="Start", repo_root=tmp_path
    ).focal_window

    assert (
        level_0("pool.go"),
        level_0("widget.cpp"),
        focal.scope_breadcrumbs if focal else "",
    ) == (
        ([("WorkerPool", ["Start", "Stop"])], ["NewWorkerPool", "Server.Close"]),
        ([("Widget", ["width"])], ["Widget::draw", "helper"]),
        "WorkerPool > Start",
    )


def test_polyglot_outline_reads_a_header_as_cpp_only_when_its_content_is(tmp_path: Path) -> None:
    """Verify a `.h` header is outlined in the language `devops ai ast parse` reads it in: C++
    when its content uses C++, C otherwise. Inspection took every `.h` for C, so a C++ header's
    namespace and class were listed as functions and `--symbol size` was not found (#959)."""
    (tmp_path / "fmt.h").write_text(SAMPLE_CPP_HEADER, encoding="utf-8")
    (tmp_path / "point.h").write_text(SAMPLE_C_HEADER, encoding="utf-8")

    def level_0(name: str) -> tuple[str, list[tuple[str, list[str]]], list[str]]:
        outline = generate_semantic_outline(
            tmp_path / name, level=FocalLevel.TOPOLOGY, repo_root=tmp_path
        )
        top = outline.topology
        return (
            outline.language,
            [(c.name, c.methods) for c in top.classes] if top else [],
            [f.name for f in top.functions] if top else [],
        )

    focal = generate_semantic_outline(
        tmp_path / "fmt.h", level=FocalLevel.DEEP_FOCAL, symbol="size", repo_root=tmp_path
    ).focal_window

    assert (
        level_0("fmt.h"),
        level_0("point.h"),
        (focal.line_start, focal.scope_breadcrumbs) if focal else None,
    ) == (
        ("cpp", [("writer", ["size"])], []),
        ("c", [("point", [])], ["add", "twice"]),
        (5, "writer > size"),
    )


def test_polyglot_skeleton_signs_annotated_methods_with_their_declaration(tmp_path: Path) -> None:
    """Verify a Java or C# method's skeleton line is its declaration, not the annotation or
    attribute above it; tree-sitter signed a symbol with the line it starts on, so the skeleton
    read `  @Override` (#959)."""
    (tmp_path / "OrderService.java").write_text(SAMPLE_JAVA_ANNOTATED, encoding="utf-8")
    (tmp_path / "UsersController.cs").write_text(SAMPLE_CSHARP_ATTRIBUTED, encoding="utf-8")

    def skeleton(name: str) -> list[str]:
        structural = generate_semantic_outline(
            tmp_path / name, level=FocalLevel.STRUCTURAL, repo_root=tmp_path
        ).structural
        return structural.raw_skeleton.splitlines() if structural else []

    assert (skeleton("OrderService.java"), skeleton("UsersController.cs")) == (
        [
            "class OrderService",
            '  public String toString() { return ""; }',
            "  public Order placeOrder(Cart cart) throws OrderException { return null; }",
        ],
        ["class UsersController", "  public ActionResult<User> Get(int id)"],
    )


@pytest.mark.parametrize(
    ("file_name", "content"),
    [("order_service.py", SAMPLE_HOTSPOT_PYTHON), ("service.ts", SAMPLE_TYPESCRIPT_SERVICE)],
    ids=["python", "polyglot"],
)
def test_topology_outline_tokens_match_rendered_markdown(
    tmp_path: Path, file_name: str, content: str
) -> None:
    """Verify a Level 0 outline reports the tokens of the markdown it renders, for Python and
    through the polyglot path; a guess from the symbol count left out the docstrings, bases,
    methods, exports and hotspots, and reported 279 tokens for inspection.py's 1317 (#959)."""
    target = tmp_path / file_name
    target.write_text(content, encoding="utf-8")

    outline = generate_semantic_outline(target, level=FocalLevel.TOPOLOGY, repo_root=tmp_path)
    rendered_tokens = estimate_tokens(_render_topology_markdown(outline))

    assert (
        outline.outline_tokens,
        outline.topology.estimated_tokens if outline.topology else None,
    ) == (rendered_tokens, rendered_tokens)


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
