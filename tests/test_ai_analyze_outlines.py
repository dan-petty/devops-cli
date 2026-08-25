"""Unit tests for AI analyze outlines and pseudocode extraction."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.analyze.outlines import (
    _calculate_complexity_score,
    _extract_json_pseudocode,
    _extract_python_pseudocode_outline,
    analyze_single_file,
)


def test_outline_extractor(tmp_path: Path) -> None:
    """Verify python and json pseudocode outline extraction and complexity scoring."""
    py_code = """
class MyService:
    \"\"\"Service class docstring.\"\"\"
    def __init__(self, name: str) -> None:
        self.name = name

    def process(self, data: dict) -> bool:
        return True

def standalone_helper(x: int) -> int:
    return x * 2
"""
    py_file = tmp_path / "service.py"
    py_file.write_text(py_code, encoding="utf-8")

    py_outline = _extract_python_pseudocode_outline(py_code)
    assert len(py_outline) > 0

    json_code = '{"name": "test", "version": "1.0.0", "dependencies": {"pkg": "1.0"}}'
    json_outline = _extract_json_pseudocode(json_code)
    assert json_outline is not None
    assert len(json_outline) > 0

    complexity = _calculate_complexity_score(py_code, 15, ["MyService", "standalone_helper"])
    assert complexity in ("Low", "Medium", "High")

    meta = analyze_single_file(
        rel_path="service.py",
        content=py_code,
        size_bytes=len(py_code),
        repo_root=tmp_path,
        ai_client=None,
        enhanced=False,
    )
    assert meta.path == "service.py"
    assert meta.language == "python"
