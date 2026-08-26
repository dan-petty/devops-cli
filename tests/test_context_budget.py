"""Unit tests for local context budgeting and tiktoken BPE tokenizer engine."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from devops_cli.ai.context_budget import (
    TokenBudgetReport,
    budget_diff_chunks,
    count_file_tokens,
    count_tokens,
    truncate_to_token_limit,
)
from devops_cli.commands.ai import app as ai_app

runner = CliRunner()


def test_count_tokens_empty_and_text() -> None:
    assert count_tokens("") == 0
    assert count_tokens("Hello, world!") > 0
    code_text = (
        "def calculate_hash(data: bytes) -> str:\n    return hashlib.sha256(data).hexdigest()"
    )
    assert count_tokens(code_text) >= 10


def test_count_file_tokens(tmp_path: Path) -> None:
    test_file = tmp_path / "sample.py"
    test_file.write_text("import sys\nprint(sys.version)\n", encoding="utf-8")

    assert count_file_tokens(test_file) > 0
    assert count_file_tokens(tmp_path / "non_existent.py") == 0


def test_truncate_to_token_limit() -> None:
    long_text = "word " * 500
    truncated = truncate_to_token_limit(long_text, max_tokens=20)
    assert count_tokens(truncated) <= 30
    assert "...[truncated" in truncated

    short_text = "Short sentence."
    assert truncate_to_token_limit(short_text, max_tokens=100) == short_text
    assert truncate_to_token_limit("", max_tokens=10) == ""


def test_budget_diff_chunks_small_diff() -> None:
    diff = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,4 @@
+import os
 def main():
     pass
"""
    chunks = budget_diff_chunks(diff, max_tokens=500)
    assert len(chunks) == 1
    assert chunks[0] == diff
    assert budget_diff_chunks("") == []


def test_budget_diff_chunks_large_multi_file_diff() -> None:
    file_diff_1 = "diff --git a/file1.py b/file1.py\n" + ("+ line in file 1\n" * 50)
    file_diff_2 = "diff --git a/file2.py b/file2.py\n" + ("+ line in file 2\n" * 50)
    multi_diff = f"{file_diff_1}\n{file_diff_2}"

    chunks = budget_diff_chunks(multi_diff, max_tokens=60)
    assert len(chunks) >= 2


def test_token_budget_report_model() -> None:
    rep = TokenBudgetReport(
        text_length=100,
        estimated_tokens=25,
        max_budget=1000,
        fits_budget=True,
        model="gpt-4o",
        chunk_count=1,
    )
    assert rep.fits_budget is True
    assert rep.estimated_tokens == 25


def test_ai_token_count_cli(tmp_path: Path) -> None:
    sample_file = tmp_path / "code.py"
    sample_file.write_text("x = 42\ny = 100\n", encoding="utf-8")

    res_file = runner.invoke(ai_app, ["token-count", str(sample_file)])
    assert res_file.exit_code == 0
    assert "AI Context Token Budget Report" in res_file.stdout

    res_json = runner.invoke(ai_app, ["token-count", str(sample_file), "--json"])
    assert res_json.exit_code == 0
    assert '"estimated_tokens"' in res_json.stdout

    res_text = runner.invoke(ai_app, ["token-count", "some raw prompt text", "--budget", "100"])
    assert res_text.exit_code == 0
    assert "AI Context Token Budget Report" in res_text.stdout


def test_budget_diff_chunks_single_file_hunks() -> None:
    """Verify hunk-level partitioning when a single file diff exceeds token limits."""
    header = "diff --git a/big.py b/big.py\nindex 123..456 100644\n--- a/big.py\n+++ b/big.py"
    hunk1 = "\n@@ -1,10 +1,20 @@\n" + ("+ line 1\n" * 40)
    hunk2 = "\n@@ -50,10 +60,20 @@\n" + ("+ line 2\n" * 40)
    hunk3 = "\n@@ -100,10 +120,20 @@\n" + ("+ line 3\n" * 40)
    big_diff = header + hunk1 + hunk2 + hunk3

    chunks = budget_diff_chunks(big_diff, max_tokens=50)
    assert len(chunks) >= 2
    for c in chunks:
        assert "diff --git a/big.py b/big.py" in c
