"""Library API Drift and Deprecation Usage Auditor."""

from __future__ import annotations

import ast
import json
import logging
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.models.library import FunctionSignature, LibraryContract

logger = logging.getLogger(__name__)


class DriftIssueType(StrEnum):
    """Categorization of API drift defects."""

    REMOVED_METHOD = "removed_method"
    UNKNOWN_ATTRIBUTE = "unknown_attribute"
    MISSING_REQUIRED_ARG = "missing_required_arg"
    UNRECOGNIZED_KWARG = "unrecognized_kwarg"
    DEPRECATED_CALL = "deprecated_call"


class DriftFinding(BaseModel):
    """A single detected API drift or deprecation finding."""

    file_path: str
    line_number: int
    package: str
    symbol: str
    issue_type: DriftIssueType
    message: str
    is_breaking: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "package": self.package,
            "symbol": self.symbol,
            "issue_type": self.issue_type.value,
            "message": self.message,
            "is_breaking": self.is_breaking,
        }


class DriftReport(BaseModel):
    """Aggregated report of workspace API drift and breaking changes."""

    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    packages_audited: list[str] = Field(default_factory=list)
    files_scanned: int = 0
    total_calls_checked: int = 0
    findings: list[DriftFinding] = Field(default_factory=list)
    breaking_count: int = 0
    warning_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "packages_audited": self.packages_audited,
            "files_scanned": self.files_scanned,
            "total_calls_checked": self.total_calls_checked,
            "breaking_count": self.breaking_count,
            "warning_count": self.warning_count,
            "findings": [f.to_dict() for f in self.findings],
        }

    def save(self, path: Path) -> None:
        """Save report to disk in JSON format."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")


def _find_symbol_in_contract(
    contract: LibraryContract, symbol_name: str
) -> FunctionSignature | None:
    for mod in contract.modules.values():
        for fn_name, fn in mod.functions.items():
            if fn_name == symbol_name or fn.qualname.endswith(f".{symbol_name}"):
                return fn
        for cls in mod.classes.values():
            for m_name, m in cls.methods.items():
                if m_name == symbol_name or m.qualname.endswith(f".{symbol_name}"):
                    return m
    return None


def _is_known_class(contract: LibraryContract, symbol_name: str) -> bool:
    return any(symbol_name in mod.classes for mod in contract.modules.values())


def _check_call_kwargs(
    call_node: ast.Call,
    fn_sig: FunctionSignature,
    file_path: str,
    pkg: str,
    sym_name: str,
) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    allowed_params = {p.name for p in fn_sig.parameters}
    has_varkw = any(p.kind in ("VAR_KEYWORD", "**kwargs") for p in fn_sig.parameters)

    if not has_varkw and allowed_params:
        for kw in call_node.keywords:
            if kw.arg and kw.arg not in allowed_params:
                findings.append(
                    DriftFinding(
                        file_path=file_path,
                        line_number=call_node.lineno,
                        package=pkg,
                        symbol=sym_name,
                        issue_type=DriftIssueType.UNRECOGNIZED_KWARG,
                        message=f"Unrecognized keyword argument '{kw.arg}' for symbol '{sym_name}'. Allowed: {sorted(allowed_params)}",
                        is_breaking=True,
                    )
                )
    return findings


def _evaluate_call_symbol(
    call_node: ast.Call,
    sym_name: str,
    pkg: str,
    contract: LibraryContract,
    file_path: str,
) -> list[DriftFinding]:
    fn_sig = _find_symbol_in_contract(contract, sym_name)
    if not fn_sig:
        if _is_known_class(contract, sym_name):
            return []
        return [
            DriftFinding(
                file_path=file_path,
                line_number=call_node.lineno,
                package=pkg,
                symbol=sym_name,
                issue_type=DriftIssueType.REMOVED_METHOD,
                message=f"Symbol '{sym_name}' not found in contract for package '{pkg}'. May be removed or renamed.",
                is_breaking=True,
            )
        ]

    findings: list[DriftFinding] = []
    if fn_sig.docstring and "deprecated" in fn_sig.docstring.lower():
        findings.append(
            DriftFinding(
                file_path=file_path,
                line_number=call_node.lineno,
                package=pkg,
                symbol=sym_name,
                issue_type=DriftIssueType.DEPRECATED_CALL,
                message=f"Symbol '{sym_name}' is deprecated: {fn_sig.docstring[:100]}",
                is_breaking=False,
            )
        )

    findings.extend(_check_call_kwargs(call_node, fn_sig, file_path, pkg, sym_name))
    return findings


def _extract_from_import_node(
    node: ast.ImportFrom, contracts: dict[str, LibraryContract]
) -> dict[str, tuple[str, str]]:
    if not node.module:
        return {}
    root_pkg = node.module.split(".")[0]
    if root_pkg not in contracts:
        return {}
    return {(alias.asname or alias.name): (root_pkg, alias.name) for alias in node.names}


def _extract_plain_import_node(
    node: ast.Import, contracts: dict[str, LibraryContract]
) -> dict[str, tuple[str, str]]:
    res: dict[str, tuple[str, str]] = {}
    for alias in node.names:
        root_pkg = alias.name.split(".")[0]
        if root_pkg in contracts:
            res[alias.asname or alias.name] = (root_pkg, alias.name)
    return res


def _extract_imported_symbols(
    tree: ast.AST, contracts: dict[str, LibraryContract]
) -> dict[str, tuple[str, str]]:
    # maps local_alias -> (package_name, original_name)
    imported: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.update(_extract_from_import_node(node, contracts))
        elif isinstance(node, ast.Import):
            imported.update(_extract_plain_import_node(node, contracts))
    return imported


def _resolve_call_target(
    node: ast.Call, imported: dict[str, tuple[str, str]]
) -> tuple[str, str] | None:
    if isinstance(node.func, ast.Name):
        return imported.get(node.func.id)
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        parent_pkg = node.func.value.id
        if parent_pkg in imported:
            root_pkg, _ = imported[parent_pkg]
            return (root_pkg, node.func.attr)
        if (parent_pkg, parent_pkg) in imported.values():
            return (parent_pkg, node.func.attr)
    return None


def _audit_call_node(
    node: ast.Call,
    imported: dict[str, tuple[str, str]],
    contracts: dict[str, LibraryContract],
    file_path: str,
) -> list[DriftFinding]:
    target = _resolve_call_target(node, imported)
    if not target:
        return []
    pkg, orig_name = target
    contract = contracts.get(pkg)
    if not contract:
        return []
    return _evaluate_call_symbol(node, orig_name, pkg, contract, file_path)


def _audit_file_calls(
    file_path: Path,
    contracts: dict[str, LibraryContract],
) -> tuple[list[DriftFinding], int]:
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=str(file_path))
    except Exception:
        return [], 0

    imported = _extract_imported_symbols(tree, contracts)
    if not imported:
        return [], 0

    findings: list[DriftFinding] = []
    call_count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            call_count += 1
            findings.extend(_audit_call_node(node, imported, contracts, str(file_path)))
    return findings, call_count


class LibraryDriftAuditor:
    """Audits workspace call sites against indexed library contracts to detect drift."""

    def __init__(self, contracts_dir: Path | None = None) -> None:
        self.contracts_dir = contracts_dir or Path(".data/libraries")

    def _load_contracts(self, package_filter: str | None = None) -> dict[str, LibraryContract]:
        contracts: dict[str, LibraryContract] = {}
        if not self.contracts_dir.is_dir():
            return contracts

        for f in self.contracts_dir.glob("*.json"):
            pkg_name = f.stem.replace("-contract", "")
            if package_filter and pkg_name != package_filter:
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                contracts[pkg_name] = LibraryContract.model_validate(data)
            except Exception as exc:
                logger.debug("Failed loading contract %s: %s", f, exc)
        return contracts

    def audit_workspace(
        self,
        workspace_dir: Path,
        package_filter: str | None = None,
    ) -> DriftReport:
        """Scan workspace Python files for library call sites and identify drift."""
        contracts = self._load_contracts(package_filter)
        if not contracts:
            return DriftReport(packages_audited=[], files_scanned=0)

        py_files = [
            p
            for p in workspace_dir.rglob("*.py")
            if not p.is_symlink()
            and not any(
                part in p.parts
                for part in (".venv", ".git", "__pycache__", ".pytest_cache", ".data")
            )
        ]

        all_findings: list[DriftFinding] = []
        total_calls = 0

        for file_path in py_files:
            file_findings, file_calls = _audit_file_calls(file_path, contracts)
            all_findings.extend(file_findings)
            total_calls += file_calls

        breaking_count = sum(1 for f in all_findings if f.is_breaking)
        warning_count = sum(1 for f in all_findings if not f.is_breaking)

        report = DriftReport(
            packages_audited=sorted(contracts.keys()),
            files_scanned=len(py_files),
            total_calls_checked=total_calls,
            findings=all_findings,
            breaking_count=breaking_count,
            warning_count=warning_count,
        )

        default_out = Path(".data/analysis/api_drift_report.json")
        try:
            report.save(default_out)
        except OSError:
            pass

        return report
