"""Tests for diff hunk extraction."""

from __future__ import annotations

from devops_cli.ai.review.chunker import extract_diff_hunks, extract_file_diff_hunks


def test_extract_diff_hunks() -> None:
    """Verify that extract_diff_hunks accurately parses various unified diff headers."""
    diff_sample = """
--- a/app.py
+++ b/app.py
@@ -1,5 +1,10 @@
@@ -10,3 +20 @@
@@ -30,5 +40,0 @@
"""
    hunks = extract_diff_hunks(diff_sample)
    assert hunks == [(1, 10), (20, 20), (40, 40)]


def test_extract_file_diff_hunks() -> None:
    """Verify that extract_file_diff_hunks associates hunks with respective files."""
    segments = [
        """diff --git a/pkg/mod1.py b/pkg/mod1.py
--- a/pkg/mod1.py
+++ b/pkg/mod1.py
@@ -5,2 +5,4 @@
def foo(): pass
""",
        """diff --git a/pkg/mod2.py b/pkg/mod2.py
--- a/pkg/mod2.py
+++ b/pkg/mod2.py
@@ -10,5 +15,0 @@
""",
    ]
    file_hunks = extract_file_diff_hunks(segments)
    assert (
        file_hunks.get("pkg/mod1.py"),
        file_hunks.get("pkg/mod2.py"),
    ) == (
        [(5, 8)],
        [(15, 15)],
    )
