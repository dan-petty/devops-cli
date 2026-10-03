"""`devops ai ast` reads a source file only once it is within the engine's size cap (#959)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.ast.engine import TreeSitterEngine
from devops_cli.commands.ai_ast import app as ast_app

runner = CliRunner()

FUNCTION_QUERY = "(function_definition name: (identifier) @n)"


def test_ast_parse_query_respects_size_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify `ai ast parse --query` refuses a file over the size cap, as a plain parse does, and
    still queries one within it; it read and parsed the whole file whatever its size."""
    big, small = tmp_path / "big.py", tmp_path / "small.py"
    big.write_text("def f(x): ...\n" + "# padding\n" * 100, encoding="utf-8")
    small.write_text("def f(x): ...\n", encoding="utf-8")
    monkeypatch.setattr(
        "devops_cli.commands.ai_ast.TreeSitterEngine",
        lambda: TreeSitterEngine(max_file_size_bytes=100),
    )

    capped = runner.invoke(ast_app, ["parse", str(big), "--query", FUNCTION_QUERY])
    within = runner.invoke(ast_app, ["parse", str(small), "--query", FUNCTION_QUERY])

    assert (
        capped.exit_code,
        '"symbol"' in capped.output,
        "file size exceeded" in capped.output,
        within.exit_code,
        '"symbol": "f"' in within.output,
    ) == (1, False, True, 0, True)
