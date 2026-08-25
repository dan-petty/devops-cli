"""Comprehensive tests for AI CLI subcommands and native tools."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.analyze.outlines import (
    _calculate_complexity_score,
    _extract_json_pseudocode,
    _extract_python_pseudocode_outline,
    analyze_single_file,
)
from devops_cli.ai.client import LLMClient
from devops_cli.ai.tools.builtin_tools import list_files, read_file, search_code
from devops_cli.ai.tools.registry import get_default_tools
from devops_cli.commands.ai import app as ai_app

runner = CliRunner()


def _mock_proc(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["cmd"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_ai_subcommands_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )
    mock_resp = MagicMock()
    mock_resp.__str__.return_value = "OK"
    mock_resp.wall_seconds = 0.5
    mock_resp.backend_info = "mock"

    from devops_cli.config.settings import Settings

    with (
        patch.object(LLMClient, "chat", return_value=mock_resp),
        patch.object(LLMClient, "list_models", return_value=["gemma4:26b"]),
        patch("devops_cli.config.settings.load_settings", return_value=Settings()),
    ):
        res_config = runner.invoke(ai_app, ["config"])
        assert res_config.exit_code == 0

        res_test = runner.invoke(ai_app, ["test", "--prompt", "Ping"])
        assert res_test.exit_code == 0

        res_models = runner.invoke(ai_app, ["models"])
        assert res_models.exit_code == 0

        res_agents = runner.invoke(ai_app, ["agents", "--template", "--repo", str(tmp_path)])
        assert res_agents.exit_code == 0


def test_native_tools_and_registry(tmp_path: Path) -> None:
    tools = get_default_tools()
    assert isinstance(tools, list)
    assert len(tools) > 0

    test_file = tmp_path / "sample.py"
    test_file.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")

    with patch("devops_cli.ai.tools.builtin_tools._is_safe_workspace_path", return_value=True):
        res_read = read_file(str(test_file))
        assert "add" in res_read

        res_list = list_files(str(tmp_path))
        assert res_list is not None

        res_search = search_code("def add", directory=str(tmp_path))
        assert res_search is not None


def test_outline_extractor(tmp_path: Path) -> None:
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
