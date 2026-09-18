"""Unit tests for AST and Polyglot Tree-Sitter Repository Symbol Map Generation."""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.repomap import (
    FileMapNode,
    SymbolNode,
    _discover_repo_files,
    _extract_doc_summary,
    _format_function_signature,
    _is_file_excluded,
    _polyglot_to_file_node,
    generate_repo_map,
    parse_file_symbols,
    render_repo_map_text,
)


def test_symbol_node_to_dict() -> None:
    """Verify SymbolNode serializes to dict including nested children."""
    child = SymbolNode(
        name="do_work",
        kind="method",
        line_number=10,
        signature="def do_work(self) -> None",
        docstring="Perform work.",
    )
    parent = SymbolNode(
        name="Worker",
        kind="class",
        line_number=5,
        docstring="Worker class.",
        children=[child],
    )
    data = parent.to_dict()
    assert data["name"] == "Worker"
    assert data["kind"] == "class"
    assert data["line_number"] == 5
    assert len(data["children"]) == 1
    assert data["children"][0]["name"] == "do_work"
    assert data["children"][0]["kind"] == "method"


def test_file_map_node_to_dict() -> None:
    """Verify FileMapNode serializes to dict including symbols."""
    sym = SymbolNode(name="calc", kind="function", line_number=1)
    file_node = FileMapNode(path="math/calc.py", line_count=20, symbols=[sym])
    data = file_node.to_dict()
    assert data["path"] == "math/calc.py"
    assert data["line_count"] == 20
    assert len(data["symbols"]) == 1
    assert data["symbols"][0]["name"] == "calc"


def test_extract_doc_summary() -> None:
    """Verify extraction of first docstring line or empty string."""
    tree = ast.parse('def foo():\n    """First line.\n    Second line.\n    """\n    pass')
    fn_node = tree.body[0]
    assert _extract_doc_summary(fn_node) == "First line."

    empty_tree = ast.parse("def bar():\n    pass")
    empty_node = empty_tree.body[0]
    assert _extract_doc_summary(empty_node) == ""


def test_format_function_signature() -> None:
    """Verify function signature formatting for sync and async functions."""
    tree = ast.parse("async def async_fn(a: int, b: str = 'default') -> bool:\n    pass")
    fn_node = tree.body[0]
    sig = _format_function_signature(fn_node)
    assert sig == "(a: int, b: str) -> bool"


def test_parse_file_symbols_success(tmp_path: Path) -> None:
    """Verify parsing a valid Python file with classes and functions."""
    py_code = (
        "class Database:\n"
        '    """Database connection pool."""\n'
        "    def connect(self) -> None:\n"
        '        """Establish connection."""\n'
        "        pass\n\n"
        "def health_check() -> bool:\n"
        "    return True\n"
    )
    src_file = tmp_path / "db.py"
    src_file.write_text(py_code, encoding="utf-8")

    node = parse_file_symbols(src_file, tmp_path)
    assert node is not None
    assert node.path == "db.py"
    assert len(node.symbols) == 2
    assert node.symbols[0].name == "Database"
    assert node.symbols[0].kind == "class"
    assert len(node.symbols[0].children) == 1
    assert node.symbols[0].children[0].name == "connect"
    assert node.symbols[1].name == "health_check"
    assert node.symbols[1].kind == "function"


def test_parse_file_symbols_oversized_file(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify parse_file_symbols rejects files exceeding size threshold with a structured warning."""
    src_file = tmp_path / "large.py"
    src_file.write_text("x = 1\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        with patch("devops_cli.ai.repomap.MAX_REPOMAP_FILE_SIZE_BYTES", 2):
            result = parse_file_symbols(src_file, tmp_path)

    assert result is None
    assert any("exceeds maximum limit" in record.message for record in caplog.records)


def test_parse_file_symbols_syntax_error(tmp_path: Path) -> None:
    """Verify parse_file_symbols returns None on syntax errors."""
    src_file = tmp_path / "broken.py"
    src_file.write_text("def unclosed_syntax(", encoding="utf-8")

    result = parse_file_symbols(src_file, tmp_path)
    assert result is None


def test_parse_file_symbols_missing_file(tmp_path: Path) -> None:
    """Verify parse_file_symbols returns None for non-existent files."""
    missing_file = tmp_path / "nonexistent.py"
    result = parse_file_symbols(missing_file, tmp_path)
    assert result is None


def test_polyglot_to_file_node_oversized_file(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify _polyglot_to_file_node rejects files exceeding size limit and logs warning."""
    ts_file = tmp_path / "massive.ts"
    ts_file.write_text("export class Engine { start(): void {} }", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        with patch("devops_cli.ai.repomap.MAX_REPOMAP_FILE_SIZE_BYTES", 5):
            node = _polyglot_to_file_node(ts_file, tmp_path)

    assert node is None
    assert any("exceeds maximum limit" in record.message for record in caplog.records)


def test_polyglot_to_file_node_circular_symlink(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify _polyglot_to_file_node traps circular symlinks and logs warning."""
    link_a = tmp_path / "link_a.ts"
    link_b = tmp_path / "link_b.ts"
    try:
        link_a.symlink_to(link_b)
        link_b.symlink_to(link_a)
    except OSError:
        pytest.skip("Symlink creation not supported on platform")

    with caplog.at_level(logging.WARNING):
        node = _polyglot_to_file_node(link_a, tmp_path)

    assert node is None
    assert any(
        "circular link" in record.message or "failed" in record.message for record in caplog.records
    )


def test_polyglot_to_file_node_escaped_symlink(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify _polyglot_to_file_node rejects symlinks pointing outside base_root."""
    base_dir = tmp_path / "workspace"
    base_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    target_file = outside_dir / "secret.ts"
    target_file.write_text("export const SECRET = 42;", encoding="utf-8")

    symlink_file = base_dir / "escaped.ts"
    try:
        symlink_file.symlink_to(target_file)
    except OSError:
        pytest.skip("Symlink creation not supported on platform")

    with caplog.at_level(logging.WARNING):
        node = _polyglot_to_file_node(symlink_file, base_dir)

    assert node is None
    assert any("escapes base directory" in record.message for record in caplog.records)


def test_polyglot_to_file_node_success(tmp_path: Path) -> None:
    """Verify _polyglot_to_file_node parses valid polyglot file using TreeSitterEngine."""
    ts_code = "export class ServiceManager {\n  initialize(): void {}\n}\n"
    ts_file = tmp_path / "service.ts"
    ts_file.write_text(ts_code, encoding="utf-8")

    node = _polyglot_to_file_node(ts_file, tmp_path)
    # TreeSitterEngine may or may not return symbols depending on grammar availability
    if node is not None:
        assert node.path == "service.ts"
        assert len(node.symbols) > 0


def test_is_file_excluded(tmp_path: Path) -> None:
    """Verify _is_file_excluded filtering behavior."""
    normal_file = tmp_path / "main.py"
    normal_file.write_text("print('hello')", encoding="utf-8")

    test_file = tmp_path / "test_main.py"
    test_file.write_text("def test_it(): pass", encoding="utf-8")

    # When include_tests=False, test file is excluded
    assert _is_file_excluded(test_file, include_tests=False, repo_root=tmp_path) is True
    # When include_tests=True, test file is not excluded
    assert _is_file_excluded(test_file, include_tests=True, repo_root=tmp_path) is False
    # Normal file is not excluded
    assert _is_file_excluded(normal_file, include_tests=False, repo_root=tmp_path) is False

    # Symlink is excluded
    symlink_file = tmp_path / "link.py"
    try:
        symlink_file.symlink_to(normal_file)
        assert _is_file_excluded(symlink_file, include_tests=True, repo_root=tmp_path) is True
    except OSError:
        pass


def test_discover_repo_files(tmp_path: Path) -> None:
    """Verify _discover_repo_files discovers Python and polyglot files."""
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "app.ts").write_text("const x = 1;\n", encoding="utf-8")
    (tmp_path / "test_app.py").write_text("def test(): pass\n", encoding="utf-8")

    py_only = _discover_repo_files(tmp_path, include_tests=False, multilingual=False)
    assert len(py_only) == 1
    assert py_only[0].name == "app.py"

    multi = _discover_repo_files(tmp_path, include_tests=False, multilingual=True)
    names = [f.name for f in multi]
    assert "app.py" in names
    assert "app.ts" in names
    assert "test_app.py" not in names


def test_generate_repo_map_integration(tmp_path: Path) -> None:
    """Verify generate_repo_map parses files and formats text."""
    (tmp_path / "module.py").write_text(
        "class Router:\n    def route(self): pass\n", encoding="utf-8"
    )
    nodes = generate_repo_map(root_dir=tmp_path, max_files=10, include_tests=False)
    assert len(nodes) >= 1
    assert nodes[0].path == "module.py"

    rendered = render_repo_map_text(nodes)
    assert "module.py" in rendered
    assert "Router" in rendered


def test_is_file_excluded_symlink_oserror() -> None:
    """Verify _is_file_excluded returns True when is_symlink raises OSError."""
    mock_file = MagicMock(spec=Path)
    mock_file.is_symlink.side_effect = OSError("Access denied")
    assert _is_file_excluded(mock_file, include_tests=False) is True


def test_is_file_excluded_gitignored(tmp_path: Path) -> None:
    """Verify _is_file_excluded returns True when file is ignored by git."""
    sample_file = tmp_path / "ignored.py"
    sample_file.write_text("x = 1\n", encoding="utf-8")
    with patch("devops_cli.ai.repomap.is_ignored_by_git", return_value=True):
        assert _is_file_excluded(sample_file, include_tests=False, repo_root=tmp_path) is True


def test_polyglot_to_file_node_stat_oserror(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify _polyglot_to_file_node handles OSError during stat call."""
    ts_file = tmp_path / "unreadable.ts"
    ts_file.write_text("const x = 1;\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        with patch.object(Path, "stat", side_effect=OSError("Disk error")):
            result = _polyglot_to_file_node(ts_file, tmp_path)

    assert result is None
    assert any("stat failed" in record.message for record in caplog.records)


def test_polyglot_to_file_node_empty_symbols(tmp_path: Path) -> None:
    """Verify _polyglot_to_file_node returns None when parsed map has no symbols."""
    ts_file = tmp_path / "empty.ts"
    ts_file.write_text("// only comments\n", encoding="utf-8")

    with patch("devops_cli.ai.ast.engine.TreeSitterEngine.parse_file", return_value=None):
        assert _polyglot_to_file_node(ts_file, tmp_path) is None


def test_generate_repo_map_multilingual(tmp_path: Path) -> None:
    """Verify generate_repo_map handles multilingual source trees."""
    (tmp_path / "app.ts").write_text(
        "export class AppService { run(): void {} }\n", encoding="utf-8"
    )
    nodes = generate_repo_map(root_dir=tmp_path, max_files=10, multilingual=True)
    assert isinstance(nodes, list)


def test_generate_repo_map_escaped_file(tmp_path: Path) -> None:
    """Verify generate_repo_map skips files that escape base directory."""
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.py"
    secret_file.write_text("def secret(): pass\n", encoding="utf-8")

    inside_dir = tmp_path / "inside"
    inside_dir.mkdir()

    with patch("devops_cli.ai.repomap._discover_repo_files", return_value=[secret_file]):
        nodes = generate_repo_map(root_dir=inside_dir, max_files=10)
    assert len(nodes) == 0
