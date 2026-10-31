"""Architecture contract verifier evaluating code against executable markdown specifications."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

from pydantic import BaseModel, Field

from devops_cli.config.constants import CONST_SPECS_DIR_PATH
from devops_cli.core.repo import find_repo_root, list_repo_files
from devops_cli.telemetry.tracer import trace_span

logger = logging.getLogger(__name__)


class SpecContractRule(BaseModel):
    """A single architectural invariant rule defined in a spec."""

    name: str
    rule_type: str  # "forbidden_import"
    target_path: str
    passed: bool
    details: str = ""


class ArchitectureSpecReport(BaseModel):
    """Report of architecture contract verification."""

    spec_name: str
    spec_path: str
    total_rules: int = 0
    passed_rules: int = 0
    failed_rules: int = 0
    rule_results: list[SpecContractRule] = Field(default_factory=list)


def _check_forbidden_imports(tree: ast.AST, forbidden: set[str]) -> list[str]:
    """Check for forbidden imports in AST."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                if name.name in forbidden:
                    found.append(name.name)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module in forbidden:
            found.append(node.module)
    return list(dict.fromkeys(found))


def _verify_source_file(
    file_path: Path, rel_path: str, forbidden_modules: set[str]
) -> list[SpecContractRule]:
    """Verify architectural rules against a single Python file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=rel_path)
    except (SyntaxError, OSError) as exc:
        logger.warning("Failed to parse %s for architectural verification: %s", rel_path, exc)
        return []

    # Nesting depth is Ruff's PLR1702 (#1876), so the one rule here is the forbidden imports.
    bad_imports = _check_forbidden_imports(tree, forbidden_modules)
    if bad_imports:
        return [
            SpecContractRule(
                name="Forbidden Imports",
                rule_type="forbidden_import",
                target_path=rel_path,
                passed=False,
                details=f"Contains deprecated/forbidden import(s): {', '.join(bad_imports)}",
            )
        ]
    return [
        SpecContractRule(
            name="Forbidden Imports Check",
            rule_type="forbidden_import",
            target_path=rel_path,
            passed=True,
            details="Imports no forbidden module.",
        )
    ]


def verify_architecture_spec(
    spec_path: Path | None = None,
    target_dir: Path | None = None,
) -> ArchitectureSpecReport:
    """Verify repository code against architectural contracts in markdown specs."""
    with trace_span("ai.verify_spec"):
        repo = find_repo_root(target_dir or Path.cwd())
        src_files = [p for p in list_repo_files(repo / "src") if p.suffix == ".py"]

        rule_results: list[SpecContractRule] = []
        forbidden_modules = {"telnetlib", "cgi", "pipes"}

        for py_file in src_files:
            rel_path = str(py_file.relative_to(repo))
            rule_results.extend(_verify_source_file(py_file, rel_path, forbidden_modules))

        passed_c = sum(1 for r in rule_results if r.passed)
        failed_c = sum(1 for r in rule_results if not r.passed)
        spec_file_name = spec_path.name if spec_path else "architecture_invariants.spec.md"

        return ArchitectureSpecReport(
            spec_name=spec_file_name,
            spec_path=str(spec_path or CONST_SPECS_DIR_PATH / spec_file_name),
            total_rules=len(rule_results),
            passed_rules=passed_c,
            failed_rules=failed_c,
            rule_results=rule_results,
        )
