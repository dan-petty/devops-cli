"""Unit tests for AST import extraction (Issue #78)."""

from __future__ import annotations

from devops_cli.ai.review.ast_imports import (
    extract_imports_from_diff,
    extract_imports_from_source,
    group_imports_by_package,
)


def test_extract_imports_from_source_ast() -> None:
    source = """
import os
import sys as system
from pathlib import Path, PurePath
from devops_cli.models.library import LibraryContract, FunctionSignature as FnSig
from typing import *

def some_code():
    import json
    return True
"""
    imports = extract_imports_from_source(source)
    assert ("os", None) in imports
    assert ("sys", None) in imports
    assert ("pathlib", "Path") in imports
    assert ("pathlib", "PurePath") in imports
    assert ("devops_cli.models.library", "LibraryContract") in imports
    assert ("devops_cli.models.library", "FunctionSignature") in imports
    assert ("json", None) in imports


def test_extract_imports_from_source_syntax_error_fallback() -> None:
    broken_source = """
def broken_syntax(
    import math
    from collections import defaultdict
"""
    imports = extract_imports_from_source(broken_source)
    assert ("math", None) in imports
    assert ("collections", "defaultdict") in imports


def test_extract_imports_from_diff_patch() -> None:
    diff_text = """diff --git a/app.py b/app.py
index 1234..5678 100644
--- a/app.py
+++ b/app.py
@@ -1,5 +1,8 @@
-from os import getenv
+import typer
+from typer import Typer, Option
+import yaml
 def run():
     pass
"""
    imports = extract_imports_from_diff(diff_text)
    assert ("typer", None) in imports
    assert ("typer", "Typer") in imports
    assert ("typer", "Option") in imports
    assert ("yaml", None) in imports
    # Unchanged or deleted lines should not be included
    assert ("os", "getenv") not in imports


def test_group_imports_by_package() -> None:
    imports = [
        ("pathlib", "Path"),
        ("pathlib", "PurePath"),
        ("devops_cli.models.library", "LibraryContract"),
        ("os", None),
    ]
    grouped = group_imports_by_package(imports)
    assert "pathlib" in grouped
    assert "Path" in grouped["pathlib"]
    assert "PurePath" in grouped["pathlib"]
    assert "devops_cli" in grouped
    assert "LibraryContract" in grouped["devops_cli"]
    assert "os" in grouped
