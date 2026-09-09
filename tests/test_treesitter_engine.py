"""Tests for Tree-Sitter Multilingual AST Graph & Code Intelligence Engine (Issue #74)."""

from __future__ import annotations

import time
from pathlib import Path

from typer.testing import CliRunner

from devops_cli.ai.ast.engine import TreeSitterEngine, detect_language
from devops_cli.ai.ast.fallback import FallbackASTParser
from devops_cli.ai.ast.graph import CodeGraphBuilder
from devops_cli.ai.ast.models import PolyglotFileMap, SymbolKind
from devops_cli.ai.repomap import generate_repo_map
from devops_cli.main import app

runner = CliRunner()


def test_language_detection() -> None:
    """Verify file extensions map to canonical language identifiers."""
    assert detect_language(Path("app.py")) == "python"
    assert detect_language(Path("types.pyi")) == "python"
    assert detect_language(Path("index.ts")) == "typescript"
    assert detect_language(Path("component.tsx")) == "typescript"
    assert detect_language(Path("script.js")) == "javascript"
    assert detect_language(Path("main.go")) == "go"
    assert detect_language(Path("lib.rs")) == "rust"
    assert detect_language(Path("Service.java")) == "java"
    assert detect_language(Path("main.tf")) == "hcl"
    assert detect_language(Path("config.hcl")) == "hcl"
    assert detect_language(Path("README.md")) is None


def test_fallback_python_parsing() -> None:
    """Verify fallback parser parses Python classes and functions."""
    code = """
class DataProcessor:
    \"\"\"Processes streaming batches.\"\"\"
    def process_item(self, item: str) -> bool:
        return len(item) > 0

async def fetch_feed(url: str) -> list[str]:
    \"\"\"Fetches remote items.\"\"\"
    return [url]
"""
    parser = FallbackASTParser()
    file_map = parser.parse("app.py", code, "python")
    assert file_map.language == "python"
    assert len(file_map.symbols) == 3

    cls_sym = next(s for s in file_map.symbols if s.name == "DataProcessor")
    assert cls_sym.kind == SymbolKind.CLASS
    assert "Processes streaming batches" in cls_sym.docstring

    method_sym = next(s for s in file_map.symbols if s.name == "process_item")
    assert method_sym.kind == SymbolKind.METHOD
    assert method_sym.parent_scope == "DataProcessor"

    fn_sym = next(s for s in file_map.symbols if s.name == "fetch_feed")
    assert fn_sym.kind == SymbolKind.FUNCTION
    assert "Fetches remote items" in fn_sym.docstring


def test_fallback_typescript_parsing() -> None:
    """Verify fallback parser parses TypeScript classes, interfaces, and functions."""
    code = """
export interface UserPayload {
    id: string;
    email: string;
}

export class AuthService {
    login(payload: UserPayload): boolean {
        return true;
    }
}

export function validateEmail(email: string): boolean {
    return email.includes("@");
}
"""
    parser = FallbackASTParser()
    file_map = parser.parse("auth.ts", code, "typescript")
    assert file_map.language == "typescript"

    names = {s.name for s in file_map.symbols}
    assert "UserPayload" in names
    assert "AuthService" in names
    assert "login" in names
    assert "validateEmail" in names

    iface_sym = next(s for s in file_map.symbols if s.name == "UserPayload")
    assert iface_sym.kind == SymbolKind.INTERFACE


def test_fallback_go_parsing() -> None:
    """Verify fallback parser parses Go structs, interfaces, and functions."""
    code = """
package worker

type JobQueue interface {
    Enqueue(id string) error
}

type WorkerPool struct {
    concurrency int
}

func NewWorkerPool(workers int) *WorkerPool {
    return &WorkerPool{concurrency: workers}
}

func (w *WorkerPool) Start() error {
    return nil
}
"""
    parser = FallbackASTParser()
    file_map = parser.parse("worker.go", code, "go")
    assert file_map.language == "go"

    names = {s.name for s in file_map.symbols}
    assert "JobQueue" in names
    assert "WorkerPool" in names
    assert "NewWorkerPool" in names
    assert "Start" in names

    method_sym = next(s for s in file_map.symbols if s.name == "Start")
    assert method_sym.kind == SymbolKind.METHOD
    assert method_sym.parent_scope == "WorkerPool"


def test_fallback_rust_parsing() -> None:
    """Verify fallback parser parses Rust structs, traits, and functions."""
    code = """
pub trait StorageEngine {
    fn write_block(&self, data: &[u8]) -> Result<(), Error>;
}

pub struct MemoryCache {
    capacity: usize,
}

impl MemoryCache {
    pub fn new(capacity: usize) -> Self {
        Self { capacity }
    }
}

pub fn hash_payload(data: &[u8]) -> u64 {
    42
}
"""
    parser = FallbackASTParser()
    file_map = parser.parse("engine.rs", code, "rust")
    assert file_map.language == "rust"

    names = {s.name for s in file_map.symbols}
    assert "StorageEngine" in names
    assert "MemoryCache" in names
    assert "new" in names
    assert "hash_payload" in names


def test_fallback_java_parsing() -> None:
    """Verify fallback parser parses Java classes, interfaces, and methods."""
    code = """
package com.devops;

public interface MetricsRegistry {
    void record(String metric, double value);
}

public class MetricsClient implements MetricsRegistry {
    public void record(String metric, double value) {
        // record
    }

    public static MetricsClient createDefault() {
        return new MetricsClient();
    }
}
"""
    parser = FallbackASTParser()
    file_map = parser.parse("MetricsClient.java", code, "java")
    assert file_map.language == "java"

    names = {s.name for s in file_map.symbols}
    assert "MetricsRegistry" in names
    assert "MetricsClient" in names
    assert "record" in names
    assert "createDefault" in names


def test_fallback_hcl_parsing() -> None:
    """Verify fallback parser parses Terraform / HCL blocks."""
    code = """
resource "aws_s3_bucket" "audit_logs" {
    bucket = "company-audit-logs"
    acl    = "private"
}

variable "region" {
    type    = string
    default = "us-east-1"
}

output "bucket_arn" {
    value = aws_s3_bucket.audit_logs.arn
}
"""
    parser = FallbackASTParser()
    file_map = parser.parse("main.tf", code, "hcl")
    assert file_map.language == "hcl"

    names = {s.name for s in file_map.symbols}
    assert 'resource "aws_s3_bucket" "audit_logs"' in names or "aws_s3_bucket.audit_logs" in names
    assert 'variable "region"' in names or "variable.region" in names


def test_tree_sitter_engine_parse_file_and_cache(tmp_path: Path) -> None:
    """Verify TreeSitterEngine parses source files and caches results."""
    engine = TreeSitterEngine()
    py_file = tmp_path / "service.py"
    py_file.write_text("def compute_total(a: int, b: int) -> int:\n    return a + b\n")

    res1 = engine.parse_file(py_file)
    assert res1 is not None
    assert isinstance(res1, PolyglotFileMap)
    assert any(s.name == "compute_total" for s in res1.symbols)

    # Second call should hit the in-memory cache
    res2 = engine.parse_file(py_file)
    assert res2 is not None
    assert res2.path == res1.path
    assert len(res2.symbols) == len(res1.symbols)


def test_query_tree_execution() -> None:
    """Verify S-expression query execution or structural query matching."""
    engine = TreeSitterEngine()
    code = "def handle_event(event: dict) -> None:\n    pass\n"
    query_sexpr = "(function_definition name: (identifier) @name)"

    matches = engine.query_code(code, "python", query_sexpr)
    assert isinstance(matches, list)
    assert len(matches) >= 1
    assert any("handle_event" in str(m) for m in matches)


def test_query_resolution_latency(tmp_path: Path) -> None:
    """Verify AST query resolution takes < 5ms per file."""
    engine = TreeSitterEngine()
    code = "\n".join([f"def func_{i}(x: int) -> int:\n    return x + {i}" for i in range(10)])
    test_file = tmp_path / "bench.py"
    test_file.write_text(code)

    # Warmup
    engine.parse_file(test_file)

    start = time.perf_counter()
    engine.parse_file(test_file)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert elapsed_ms < 5.0, f"Query resolution exceeded 5ms: {elapsed_ms:.2f}ms"


def test_code_graph_builder(tmp_path: Path) -> None:
    """Verify CodeGraphBuilder synthesizes multi-file code graphs with JSON and DOT exports."""
    file_a = tmp_path / "calc.py"
    file_a.write_text("def add(x: int, y: int) -> int:\n    return x + y\n")

    file_b = tmp_path / "client.ts"
    file_b.write_text("export function runAdd(): number {\n    return 42;\n}\n")

    builder = CodeGraphBuilder(root_dir=tmp_path)
    graph = builder.build()

    assert len(graph.files) >= 2
    assert "add" in graph.nodes or any(k.endswith("add") for k in graph.nodes)

    json_repr = graph.to_json()
    assert "add" in json_repr

    dot_repr = graph.to_dot()
    assert "digraph CodeGraph" in dot_repr


def test_repomap_multilingual(tmp_path: Path) -> None:
    """Verify repomap with multilingual=True indexes polyglot files."""
    (tmp_path / "main.py").write_text("def py_main(): pass\n")
    (tmp_path / "worker.go").write_text("package main\nfunc GoWorker() {}\n")

    nodes = generate_repo_map(root_dir=tmp_path, multilingual=True)
    paths = [n.path for n in nodes]
    assert any("main.py" in p for p in paths)
    assert any("worker.go" in p for p in paths)


def test_cli_ast_parse(tmp_path: Path) -> None:
    """Verify devops ai ast parse CLI command."""
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello() -> str:\n    return 'world'\n")

    res = runner.invoke(app, ["ai", "ast", "parse", str(test_file)])
    assert res.exit_code == 0
    assert "hello" in res.output
