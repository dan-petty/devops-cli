"""Tests for install-tools command."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

from devops_cli.commands.install_tools import TOOLS, _current_version


def test_tool_registry_has_required_entries() -> None:
    expected = {"kubectl", "kustomize", "helm", "argo", "argocd", "kubectl-argo-rollouts"}
    assert set(TOOLS.keys()) == expected


def test_tool_spec_fields_populated() -> None:
    for name, tool in TOOLS.items():
        assert tool.name == name, f"{name}: name mismatch"
        assert tool.description, f"{name}: description empty"
        assert tool.bin_name, f"{name}: bin_name empty"
        assert tool.version_cmd, f"{name}: version_cmd empty"
        assert callable(tool.get_latest), f"{name}: get_latest not callable"
        assert callable(tool.install), f"{name}: install not callable"


def test_current_version_returns_none_for_missing_command() -> None:
    assert _current_version(["__nonexistent_binary_xyz_9999__"]) is None


def test_current_version_extracts_semver() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Client Version: v1.30.2\n",
            stderr="",
        )
        result = _current_version(["kubectl", "version", "--client"])
    assert result == "v1.30.2"


def test_current_version_returns_installed_on_no_version_string() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="OK\n",
            stderr="",
        )
        result = _current_version(["sometool"])
    assert result == "installed"


def test_current_version_returns_none_on_nonzero_exit() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="command not found",
        )
        result = _current_version(["sometool"])
    assert result is None
