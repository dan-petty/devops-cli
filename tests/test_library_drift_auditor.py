"""Tests for Library API Drift & Deprecation Usage Auditor (Issue #79)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from devops_cli.ai.library.drift_auditor import DriftIssueType, LibraryDriftAuditor
from devops_cli.main import app
from devops_cli.models.library import (
    ClassSignature,
    FunctionSignature,
    LibraryContract,
    ModuleContract,
    ParameterSignature,
)

runner = CliRunner()


def _create_mock_contract(pkg_dir: Path, pkg_name: str = "demolib") -> LibraryContract:
    module = ModuleContract(
        name=pkg_name,
        functions={
            "compute": FunctionSignature(
                name="compute",
                qualname=f"{pkg_name}.compute",
                parameters=[
                    ParameterSignature(name="x", kind="POSITIONAL_OR_KEYWORD"),
                    ParameterSignature(name="mode", kind="KEYWORD_ONLY", default="'fast'"),
                ],
                return_annotation="int",
            ),
            "legacy_calc": FunctionSignature(
                name="legacy_calc",
                qualname=f"{pkg_name}.legacy_calc",
                parameters=[ParameterSignature(name="val", kind="POSITIONAL_OR_KEYWORD")],
                docstring="Deprecated: use compute instead.",
            ),
        },
        classes={
            "Client": ClassSignature(
                name="Client",
                qualname=f"{pkg_name}.Client",
                methods={
                    "connect": FunctionSignature(
                        name="connect",
                        qualname=f"{pkg_name}.Client.connect",
                        parameters=[
                            ParameterSignature(name="host", kind="POSITIONAL_OR_KEYWORD"),
                            ParameterSignature(name="port", kind="KEYWORD_ONLY", default="8080"),
                        ],
                    )
                },
            )
        },
    )
    contract = LibraryContract(
        package_name=pkg_name,
        version="1.0.0",
        timestamp="2026-09-09T00:00:00Z",
        modules={pkg_name: module},
        symbols_index={
            f"{pkg_name}.compute": "function",
            f"{pkg_name}.legacy_calc": "function",
            f"{pkg_name}.Client": "class",
            f"{pkg_name}.Client.connect": "method",
        },
        total_modules=1,
        total_functions=3,
        total_classes=1,
    )
    pkg_dir.mkdir(parents=True, exist_ok=True)
    contract_path = pkg_dir / f"{pkg_name}.json"
    contract_path.write_text(contract.model_dump_json(indent=2))
    return contract


def test_drift_auditor_clean_pass(tmp_path: Path) -> None:
    """Verify clean pass when workspace code calls valid API functions and parameters."""
    contracts_dir = tmp_path / "libraries"
    _create_mock_contract(contracts_dir, "demolib")

    code = """
from demolib import compute

def run():
    return compute(x=10, mode="turbo")
"""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    (ws_dir / "main.py").write_text(code)

    auditor = LibraryDriftAuditor(contracts_dir=contracts_dir)
    report = auditor.audit_workspace(ws_dir)

    assert report.files_scanned >= 1
    assert report.breaking_count == 0


def test_drift_auditor_detects_removed_method(tmp_path: Path) -> None:
    """Verify drift auditor detects calls to non-existent or removed methods."""
    contracts_dir = tmp_path / "libraries"
    _create_mock_contract(contracts_dir, "demolib")

    code = """
from demolib import nonexistent_function

def run():
    return nonexistent_function(123)
"""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    (ws_dir / "worker.py").write_text(code)

    auditor = LibraryDriftAuditor(contracts_dir=contracts_dir)
    report = auditor.audit_workspace(ws_dir)

    assert report.breaking_count >= 1
    finding = next(f for f in report.findings if f.symbol == "nonexistent_function")
    assert finding.issue_type == DriftIssueType.REMOVED_METHOD
    assert finding.is_breaking is True


def test_drift_auditor_detects_unrecognized_kwarg(tmp_path: Path) -> None:
    """Verify drift auditor detects calls passing unrecognized keyword arguments."""
    contracts_dir = tmp_path / "libraries"
    _create_mock_contract(contracts_dir, "demolib")

    code = """
from demolib import compute

def run():
    return compute(x=10, invalid_parameter=99)
"""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    (ws_dir / "app.py").write_text(code)

    auditor = LibraryDriftAuditor(contracts_dir=contracts_dir)
    report = auditor.audit_workspace(ws_dir)

    assert report.breaking_count >= 1
    finding = next(f for f in report.findings if "invalid_parameter" in f.message)
    assert finding.issue_type == DriftIssueType.UNRECOGNIZED_KWARG
    assert finding.is_breaking is True


def test_drift_auditor_detects_deprecated_symbol(tmp_path: Path) -> None:
    """Verify drift auditor flags deprecated calls as warnings."""
    contracts_dir = tmp_path / "libraries"
    _create_mock_contract(contracts_dir, "demolib")

    code = """
from demolib import legacy_calc

def run():
    return legacy_calc(val=42)
"""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    (ws_dir / "legacy.py").write_text(code)

    auditor = LibraryDriftAuditor(contracts_dir=contracts_dir)
    report = auditor.audit_workspace(ws_dir)

    assert report.warning_count >= 1
    finding = next(f for f in report.findings if f.symbol == "legacy_calc")
    assert finding.issue_type == DriftIssueType.DEPRECATED_CALL
    assert finding.is_breaking is False


def test_cli_audit_library_usage(tmp_path: Path) -> None:
    """Verify devops ai audit-library-usage CLI command."""
    contracts_dir = tmp_path / "libraries"
    _create_mock_contract(contracts_dir, "demolib")

    ws_dir = tmp_path / "ws"
    ws_dir.mkdir()
    (ws_dir / "index.py").write_text("from demolib import compute\ndef main(): compute(1)\n")

    res = runner.invoke(
        app,
        [
            "ai",
            "audit-library-usage",
            "--contracts-dir",
            str(contracts_dir),
            "--dir",
            str(ws_dir),
            "--json",
        ],
    )
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["files_scanned"] == 1
    assert data["breaking_count"] == 0


def test_drift_auditor_handles_module_import_and_alias(tmp_path: Path) -> None:
    """Verify drift auditor catches calls from `import pkg` and `import pkg as alias`."""
    contracts_dir = tmp_path / "libraries"
    _create_mock_contract(contracts_dir, "demolib")

    code = """
import demolib
import demolib as d

def run():
    a = demolib.compute(x=10, mode="turbo")
    b = d.legacy_calc(val=99)
    return a, b
"""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    (ws_dir / "app.py").write_text(code)

    auditor = LibraryDriftAuditor(contracts_dir=contracts_dir)
    report = auditor.audit_workspace(ws_dir)

    assert report.files_scanned == 1
    assert report.total_calls_checked >= 2
    assert report.warning_count >= 1
    assert any(f.symbol == "legacy_calc" for f in report.findings)
