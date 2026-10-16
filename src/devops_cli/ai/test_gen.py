"""Unit test scaffold generator."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.defaults import DEFAULT_SYNTHESIZED_TEST_STATUS


class SynthesizedTestSuite(BaseModel):
    """Generated unit test scaffold suite for a source module or function."""

    target_file: str
    function_names: list[str] = Field(default_factory=list)
    test_code: str
    test_count: int
    validation_status: str = DEFAULT_SYNTHESIZED_TEST_STATUS
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_file": self.target_file,
            "function_names": self.function_names,
            "test_code": self.test_code,
            "test_count": self.test_count,
            "validation_status": self.validation_status,
            "metadata": self.metadata,
        }


def _resolve_import_path(target_file: Path) -> str:
    """Resolve a valid Python dotted import path for `target_file`, falling back to its stem."""
    raw = target_file.with_suffix("").as_posix().lstrip("./").replace("/", ".")
    candidate = raw.split("src.", 1)[1] if "src." in raw else target_file.stem
    if candidate and all(part.isidentifier() for part in candidate.split(".")):
        return candidate
    return target_file.stem if target_file.stem.isidentifier() else "target_module"


def synthesize_unit_tests(
    target_file: Path,
    function_filter: str | None = None,
) -> SynthesizedTestSuite:
    """Analyze a source file via AST and generate failing pytest unit test scaffolds."""
    resolved = target_file.resolve()
    if not resolved.is_file():
        return SynthesizedTestSuite(
            target_file=str(target_file),
            function_names=[],
            test_code="",
            test_count=0,
            validation_status="NOT_FOUND",
        )
    content = resolved.read_text(encoding="utf-8", errors="replace")
    module_stem = target_file.stem if target_file.stem.isidentifier() else "target_module"
    import_path = _resolve_import_path(target_file)

    functions_found: list[str] = []
    test_cases: list[str] = []

    try:
        tree = ast.parse(content, filename=str(target_file))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue
                if function_filter and node.name != function_filter:
                    continue
                functions_found.append(node.name)

                test_fn_name = f"test_{node.name}_isolated_behavior"
                test_cases.append(f'''def {test_fn_name}() -> None:
    """Verify standard behavior for {node.name}."""
    pytest.fail("expected behaviour of {node.name} not written")
''')
    except Exception:
        pass

    if not functions_found:
        functions_found.append("default_behavior")
        test_cases.append(f'''def test_{module_stem}_scaffold() -> None:
    """Verify standard behavior for {module_stem}."""
    pytest.fail("expected behaviour of {module_stem} not written")
''')

    import_line = (
        f"import {import_path}\n"
        if import_path == module_stem
        else f"import {import_path} as {module_stem}\n"
    )
    header = f'''"""Unit test scaffold suite for {target_file.name}."""

from __future__ import annotations

import pytest
{import_line}
'''
    full_code = header + "\n".join(test_cases)
    return SynthesizedTestSuite(
        target_file=str(target_file),
        function_names=functions_found,
        test_code=full_code,
        test_count=len(test_cases),
        validation_status=DEFAULT_SYNTHESIZED_TEST_STATUS,
        metadata={"import_path": import_path, "functions_count": len(functions_found)},
    )
