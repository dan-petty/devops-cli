"""Tests for Tree-Sitter Multilingual AST Graph & Code Intelligence Engine (Issue #74)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
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
    # TSX has its own grammar: the TypeScript one rejects JSX.
    assert detect_language(Path("component.tsx")) == "tsx"
    assert detect_language(Path("script.js")) == "javascript"
    assert detect_language(Path("main.go")) == "go"
    assert detect_language(Path("lib.rs")) == "rust"
    assert detect_language(Path("Service.java")) == "java"
    assert detect_language(Path("main.tf")) == "hcl"
    assert detect_language(Path("config.hcl")) == "hcl"
    assert detect_language(Path("README.md")) == "markdown"
    assert detect_language(Path("notes.txt")) is None


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


def test_fallback_finds_generic_and_qualified_rust_and_typescript_functions() -> None:
    """Verify the regex fallback names generic, const, unsafe and extern Rust functions and
    generic and default-exported TypeScript ones; it wanted `(` straight after the name and
    allowed only `pub` and `async` before `fn` (#959)."""
    rust = (
        "pub fn plain(x: i32) -> i32 { x }\n"
        "pub fn process<T: Clone>(x: T) -> T { x }\n"
        "pub const fn c() -> u8 { 1 }\n"
        "unsafe fn u() {}\n"
        'pub(crate) unsafe extern "C" fn g() {}\n'
        "pub async fn f<'a>(x: &'a str) {}\n"
    )
    typescript = (
        "export function identity<T>(value: T): T { return value; }\n"
        "export default function main(): void {}\n"
    )
    parser = FallbackASTParser()

    assert (
        [s.name for s in parser.parse("lib.rs", rust, "rust").symbols],
        [s.name for s in parser.parse("main.ts", typescript, "typescript").symbols],
    ) == (["plain", "process", "c", "u", "g", "f"], ["identity", "main"])


SIGNED_DECLARATIONS: dict[str, str] = {
    "python": (
        "class DataProcessor:\n"
        "    @staticmethod\n"
        "    def process_item(item: str) -> bool:\n"
        "        return True\n\n\n"
        "async def fetch_feed(url: str) -> list[str]:\n"
        "    return [url]\n"
    ),
    "typescript": (
        "export class AuthService {\n"
        "  login(payload: UserPayload): boolean {\n"
        "    return true;\n"
        "  }\n"
        "}\n"
        "export function a(x: string, y: number): Promise<void> {}\n"
        "@Injectable()\n"
        "class TokenStore {}\n"
    ),
    "go": (
        "package worker\n\n"
        "type WorkerPool struct {\n}\n\n"
        "func NewWorkerPool(workers int) *WorkerPool {\n  return nil\n}\n\n"
        "func (w *WorkerPool) Start() error {\n  return nil\n}\n"
    ),
    "rust": "pub struct MemoryCache {\n}\n\npub fn hash_payload(data: &[u8]) -> u64 {\n    42\n}\n",
    "java": (
        "public class MetricsClient {\n"
        "    public static MetricsClient createDefault() {\n"
        "        return INSTANCE;\n"
        "    }\n"
        "    @Override\n"
        "    public String toString() {\n"
        '        return "";\n'
        "    }\n"
        "    @Transactional @Deprecated\n"
        "    public Order placeOrder(Cart cart) throws OrderException {\n"
        "        return null;\n"
        "    }\n"
        "}\n"
    ),
    "csharp": (
        "[ApiController]\n"
        "public class UsersController : ControllerBase\n"
        "{\n"
        '    [HttpGet("{id}")]\n'
        "    public ActionResult<User> Get(int id)\n"
        "    {\n"
        "        return null;\n"
        "    }\n"
        "}\n"
    ),
}


@pytest.mark.parametrize(
    ("language", "code"), list(SIGNED_DECLARATIONS.items()), ids=list(SIGNED_DECLARATIONS)
)
def test_fallback_signs_symbols_with_their_declaration_line_as_tree_sitter_does(
    language: str, code: str
) -> None:
    """Verify the regex fallback and tree-sitter give a symbol the same signature, its
    declaration line; the fallback kept only the parameter list, `(x: string, y: number)`, with
    no name or return type, and tree-sitter took a Java annotation, C# attribute or TypeScript
    decorator above the declaration, `@Override`, for it (#959)."""
    fallback = FallbackASTParser().parse("snippet", code, language).symbols
    native = TreeSitterEngine().parse_code(code, language).symbols

    assert sorted((s.name, s.signature) for s in fallback) == sorted(
        (s.name, s.signature) for s in native
    )


def test_go_methods_belong_to_their_receiver_type() -> None:
    """Verify tree-sitter scopes a Go method to the type its receiver names, through a pointer,
    type arguments or parentheses, as the regex fallback does; it gave every Go method no
    owner, so Level 0 listed none of them (#959)."""
    code = (
        "package p\n\n"
        "func (w *WorkerPool) Start() error { return nil }\n"
        "func (s Stack) Len() int { return 0 }\n"
        "func (l *List[T]) Push(v T) {}\n"
        "func (c (*Cache)) Get() {}\n"
        "func New() *WorkerPool { return nil }\n"
    )

    assert [
        (s.name, s.parent_scope) for s in TreeSitterEngine().parse_code(code, "go").symbols
    ] == [
        ("Start", "WorkerPool"),
        ("Len", "Stack"),
        ("Push", "List"),
        ("Get", "Cache"),
        ("New", None),
    ]


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


def test_query_file_checks_size_and_language_before_reading(tmp_path: Path) -> None:
    """Verify a file query refuses a file over the size cap, in no known language or missing,
    and reads a header as the language it is written in, as parse_file does (#959)."""
    engine = TreeSitterEngine(max_file_size_bytes=100)
    (tmp_path / "small.py").write_text("def f(x): ...\n")
    (tmp_path / "big.py").write_text("def f(x): ...\n" + "# padding\n" * 100)
    (tmp_path / "notes.txt").write_text("def f(x): ...\n")
    (tmp_path / "format.h").write_text("namespace fmt {\nclass writer {\n};\n}\n")
    functions = "(function_definition name: (identifier) @name)"

    def symbols(name: str, query: str = functions) -> list[str] | None:
        matches = engine.query_file(tmp_path / name, query)
        return None if matches is None else [m["symbol"] for m in matches]

    assert (
        symbols("small.py"),
        symbols("big.py"),
        symbols("notes.txt"),
        symbols("missing.py"),
        symbols("format.h", "(class_specifier name: (type_identifier) @name)"),
    ) == (["f"], None, None, None, ["writer"])


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


def test_code_graph_indexes_a_nested_worktree(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the code graph of a worktree under `.claude/worktrees/`, given or run from, is
    read with that worktree's ignore rules; the checkout's `.claude/` rule emptied it (#582)."""
    _, nested = nested_worktree
    (nested / "src").mkdir()
    (nested / "src" / "calc.py").write_text("def add(x: int, y: int) -> int:\n    return x + y\n")
    monkeypatch.chdir(nested)

    indexed = (CodeGraphBuilder(root_dir=nested).build().files, CodeGraphBuilder().build().files)

    assert [[Path(file).name for file in files] for files in indexed] == [["calc.py"]] * 2
