"""Tests for Tree-Sitter Multilingual AST Graph & Code Intelligence Engine (Issue #74)."""

from __future__ import annotations

from pathlib import Path

import pytest
from tree_sitter import QueryError
from typer.testing import CliRunner

from devops_cli.ai.ast.engine import TreeSitterEngine, detect_language
from devops_cli.ai.ast.graph import CodeGraphBuilder, _link_call_edges
from devops_cli.ai.ast.models import PolyglotFileMap
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


# What each fixture's symbols are signed with: the line holding the name, never the annotation,
# attribute or decorator above it.
DECLARATION_LINES: dict[str, list[tuple[str, str]]] = {
    "python": [
        ("DataProcessor", "class DataProcessor:"),
        ("fetch_feed", "async def fetch_feed(url: str) -> list[str]:"),
        ("process_item", "def process_item(item: str) -> bool:"),
    ],
    "typescript": [
        ("AuthService", "export class AuthService {"),
        ("TokenStore", "class TokenStore {}"),
        ("a", "export function a(x: string, y: number): Promise<void> {}"),
        ("login", "login(payload: UserPayload): boolean {"),
    ],
    "go": [
        ("NewWorkerPool", "func NewWorkerPool(workers int) *WorkerPool {"),
        ("Start", "func (w *WorkerPool) Start() error {"),
        ("WorkerPool", "type WorkerPool struct {"),
    ],
    "rust": [
        ("MemoryCache", "pub struct MemoryCache {"),
        ("hash_payload", "pub fn hash_payload(data: &[u8]) -> u64 {"),
    ],
    "java": [
        ("MetricsClient", "public class MetricsClient {"),
        ("createDefault", "public static MetricsClient createDefault() {"),
        ("placeOrder", "public Order placeOrder(Cart cart) throws OrderException {"),
        ("toString", "public String toString() {"),
    ],
    "csharp": [
        ("Get", "public ActionResult<User> Get(int id)"),
        ("UsersController", "public class UsersController : ControllerBase"),
    ],
}


@pytest.mark.parametrize("language", list(SIGNED_DECLARATIONS))
def test_symbols_are_signed_with_their_declaration_line(language: str) -> None:
    """Verify tree-sitter gives a symbol the line holding its name as its signature, not the Java
    annotation, C# attribute or TypeScript decorator above the declaration, `@Override` (#959)."""
    symbols = TreeSitterEngine().parse_code(SIGNED_DECLARATIONS[language], language).symbols

    assert sorted((s.name, s.signature) for s in symbols) == DECLARATION_LINES[language]


def test_go_methods_belong_to_their_receiver_type() -> None:
    """Verify tree-sitter scopes a Go method to the type its receiver names, through a pointer,
    type arguments or parentheses; it gave every Go method no owner, so Level 0 listed none of
    them (#959)."""
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


def test_query_answers_with_the_nodes_it_captures() -> None:
    """Verify a query returns the nodes it captures, each named by its capture, in source order;
    the callee query answered with the enclosing function `f` because the engine matched the
    query text against its symbols whenever the native query raised."""
    code = "def f(x):\n    return g(x)\n\n\ndef h():\n    return k()\n"
    engine = TreeSitterEngine()
    callees = "(call function: (identifier) @callee)"
    function_parts = "(function_definition name: (identifier) @name body: (block) @body)"

    assert (
        engine.query_code(code, "python", callees),
        [
            (m["symbol"], m["kind"], m["line"])
            for m in engine.query_code(code, "python", function_parts)
        ],
    ) == (
        [
            {"symbol": "g", "kind": "callee", "line": 2, "signature": "g", "query": callees},
            {"symbol": "k", "kind": "callee", "line": 6, "signature": "k", "query": callees},
        ],
        [
            ("f", "name", 1),
            ("return g(x)", "body", 2),
            ("h", "name", 5),
            ("return k()", "body", 6),
        ],
    )


def test_a_malformed_query_raises_instead_of_answering_with_symbols() -> None:
    """Verify an S-expression the grammar cannot compile raises tree-sitter's QueryError; the
    engine swallowed it and answered every query with every symbol of the file."""
    with pytest.raises(QueryError):
        TreeSitterEngine().query_code("def f(): ...\n", "python", "(((")


def test_a_language_without_a_grammar_has_no_captures() -> None:
    """Verify a query over a language no grammar parses answers with no captures."""
    assert TreeSitterEngine().query_code("puts 1\n", "ruby", "(call) @c") == []


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


def test_a_second_parse_of_an_unchanged_file_returns_the_first_map(tmp_path: Path) -> None:
    """A file parsed again with the same mtime is not parsed again: the engine returns the map it
    cached, so the test shows the fast path without a clock (#1902)."""
    engine = TreeSitterEngine()
    code = "\n".join([f"def func_{i}(x: int) -> int:\n    return x + {i}" for i in range(10)])
    test_file = tmp_path / "bench.py"
    test_file.write_text(code)

    first = engine.parse_file(test_file)
    second = engine.parse_file(test_file)

    assert (
        second is first,
        [symbol.name for symbol in first.symbols] if first else None,
    ) == (True, [f"func_{i}" for i in range(10)])


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


def test_a_symbol_serialises_the_fields_tree_sitter_fills() -> None:
    """Verify a symbol's JSON, as `devops ai ast parse --json` and the code graph print it, has
    no `docstring`: only the deleted regex parser ever filled it (#1839)."""
    (symbol,) = (
        TreeSitterEngine().parse_code("def add(x, y):\n    return x + y\n", "python").symbols
    )

    assert symbol.to_dict() == {
        "name": "add",
        "kind": "function",
        "line_start": 1,
        "line_end": 2,
        "signature": "def add(x, y):",
        "language": "python",
        "parent_scope": None,
    }


def test_code_graph_links_a_call_and_skips_a_file_it_cannot_read(tmp_path: Path) -> None:
    """Verify a function that calls another in the file is linked to it, and a file that is gone
    by the time its calls are read links nothing."""
    source = tmp_path / "calc.py"
    source.write_text("def add(x, y):\n    return x + y\n\n\ndef twice(x):\n    return add(x, x)\n")

    graph = CodeGraphBuilder(root_dir=tmp_path).build()
    file_map = TreeSitterEngine().parse_file(source)
    assert file_map is not None
    source.unlink()

    assert (
        [(e.source_symbol, e.target_symbol) for e in graph.edges],
        _link_call_edges(graph.nodes, file_map),
    ) == (
        [(f"{source}::twice", f"{source}::add")],
        [],
    )


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
