"""Unit tests for AST import extraction, contract resolution, and prompt grounding (Issue #78)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from devops_cli.ai.rag.library_store import LibraryVectorStore
from devops_cli.ai.review.ast_imports import (
    extract_imports_from_diff,
    extract_imports_from_source,
    group_imports_by_package,
)
from devops_cli.ai.review.contract_grounding import (
    format_contract_grounding_for_prompt,
    resolve_grounded_contracts,
)
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator, _build_page_review_prompt
from devops_cli.models.library import (
    ClassSignature,
    FunctionSignature,
    LibraryContract,
    ModuleContract,
    ParameterSignature,
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
import requests
from pydantic import BaseModel
def broken_syntax(:
    invalid = [1, 2
"""
    imports = extract_imports_from_source(broken_source)
    assert ("requests", None) in imports
    assert ("pydantic", "BaseModel") in imports


def test_extract_imports_from_diff() -> None:
    diff_text = """
--- a/src/app.py
+++ b/src/app.py
@@ -1,5 +1,7 @@
 import sys
-from os import getenv
+from os import environ
+import httpx2
+from typer import Typer, Option

 def main():
+    import yaml
     pass
"""
    imports = extract_imports_from_diff(diff_text)
    assert ("os", "environ") in imports
    assert ("httpx2", None) in imports
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


def test_resolve_grounded_contracts_with_mock_store() -> None:
    mock_store = MagicMock(spec=LibraryVectorStore)
    fn_sig = FunctionSignature(
        name="lookup_item",
        qualname="demo_pkg.lookup_item",
        parameters=[ParameterSignature(name="key", annotation="str")],
        return_annotation="dict[str, Any]",
        docstring="Lookup item by key.",
    )
    mock_store.lookup_symbol.side_effect = lambda sym, package=None: (
        fn_sig if sym == "lookup_item" else None
    )

    imports = [("demo_pkg", "lookup_item"), ("unknown_pkg", "missing_sym")]
    contracts = resolve_grounded_contracts(imports, store=mock_store, max_contracts=3)

    assert len(contracts) == 1
    assert contracts[0].name == "lookup_item"
    assert contracts[0].return_annotation == "dict[str, Any]"


def test_resolve_grounded_contracts_local_dir(tmp_path: Path) -> None:
    contract = LibraryContract(
        package_name="test_lib",
        version="1.0.0",
        timestamp="2026-09-09T00:00:00Z",
        modules={
            "test_lib.core": ModuleContract(
                name="test_lib.core",
                functions={
                    "execute_op": FunctionSignature(
                        name="execute_op",
                        qualname="test_lib.core.execute_op",
                        parameters=[ParameterSignature(name="target", annotation="str")],
                        return_annotation="bool",
                    )
                },
                classes={
                    "Client": ClassSignature(
                        name="Client",
                        qualname="test_lib.core.Client",
                        methods={},
                    )
                },
            )
        },
    )
    contract_file = tmp_path / "test_lib.json"
    contract_file.write_text(contract.model_dump_json(), encoding="utf-8")

    imports = [("test_lib", "execute_op"), ("test_lib", "Client")]
    contracts = resolve_grounded_contracts(imports, contracts_dir=tmp_path)

    assert len(contracts) == 2
    names = {c.name for c in contracts}
    assert "execute_op" in names
    assert "Client" in names


def test_format_contract_grounding_for_prompt() -> None:
    fn_sig = FunctionSignature(
        name="authenticate",
        qualname="auth_pkg.authenticate",
        parameters=[
            ParameterSignature(name="user", annotation="str"),
            ParameterSignature(name="token", annotation="str", has_default=True, default="None"),
        ],
        return_annotation="bool",
        docstring="Authenticate credentials.",
    )
    cls_sig = ClassSignature(
        name="Session",
        qualname="auth_pkg.Session",
        bases=["BaseSession"],
        docstring="Active session state.",
        methods={
            "close": FunctionSignature(
                name="close",
                qualname="auth_pkg.Session.close",
                parameters=[],
                return_annotation="None",
            )
        },
    )

    prompt_str = format_contract_grounding_for_prompt([fn_sig, cls_sig])
    assert "Verified Third-Party API Contracts" in prompt_str
    assert "def authenticate(user: str, token: str) -> bool:" in prompt_str
    assert "class Session(BaseSession):" in prompt_str
    assert "def close() -> None: ..." in prompt_str
    assert "Anti-Hallucination Guardrail" in prompt_str


def test_build_page_review_prompt_with_grounding() -> None:
    prompt = _build_page_review_prompt(
        fpath="src/main.py",
        p_idx=1,
        total_pages=1,
        page_content="import typer\napp = typer.Typer()",
        symbols="main, app",
        rag_context_str="\n[RAG Context]",
        contract_context_str="\n[Contract Grounding]",
    )
    assert "Review File: src/main.py" in prompt
    assert "Key Symbols: main, app" in prompt
    assert "[RAG Context]" in prompt
    assert "[Contract Grounding]" in prompt
    assert "Code Content / Diff:" in prompt


def test_orchestrator_ground_contracts_flag(tmp_path: Path) -> None:
    orch_enabled = ReviewPipelineOrchestrator(session_dir=tmp_path / "s1", ground_contracts=True)
    assert orch_enabled.ground_contracts is True

    orch_disabled = ReviewPipelineOrchestrator(session_dir=tmp_path / "s2", ground_contracts=False)
    assert orch_disabled.ground_contracts is False
