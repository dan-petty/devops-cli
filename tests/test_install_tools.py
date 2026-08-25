"""Tests for install-tools command and registry."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.install_tools import (
    TOOLS,
    _current_version,
    _parse_checksum_file,
    _verify_sha256,
)
from devops_cli.commands.install_tools import app as install_tools_app
from devops_cli.main import app as main_app

runner = CliRunner()


def test_tool_registry_has_required_entries() -> None:
    expected = {
        "kubectl",
        "kustomize",
        "helm",
        "argo",
        "argocd",
        "kubectl-argo-rollouts",
        "trivy",
        "kube-linter",
        "popeye",
        "pluto",
        "k9s",
    }
    assert expected.issubset(set(TOOLS.keys()))


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


# ── SHA-256 verification ──────────────────────────────────────────────────────


def test_verify_sha256_passes_for_correct_hash() -> None:
    data = b"hello world"
    expected = hashlib.sha256(data).hexdigest()
    _verify_sha256(data, expected)  # must not raise


def test_verify_sha256_passes_with_surrounding_whitespace() -> None:
    data = b"hello world"
    expected = "  " + hashlib.sha256(data).hexdigest() + "\n"
    _verify_sha256(data, expected)


def test_verify_sha256_raises_on_mismatch() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        _verify_sha256(b"hello", "deadbeef" * 8)


# ── Checksum file parsing ─────────────────────────────────────────────────────


def test_parse_checksum_file_finds_entry() -> None:
    text = "abc123  kubectl\ndef456  kubectl.sha256\n"
    assert _parse_checksum_file(text, "kubectl") == "abc123"


def test_parse_checksum_file_handles_asterisk_prefix() -> None:
    """Some tools emit `hash *filename` (binary mode marker)."""
    text = "abc123 *myfile.tar.gz\n"
    assert _parse_checksum_file(text, "myfile.tar.gz") == "abc123"


def test_parse_checksum_file_raises_when_not_found() -> None:
    with pytest.raises(ValueError, match="No checksum entry"):
        _parse_checksum_file("abc123  other-file\n", "missing-file")


def test_install_tools_commands(tmp_path: Path) -> None:
    """Verify install-tools status and all subcommands."""
    with (
        patch("shutil.which", return_value="/usr/local/bin/kubectl"),
        patch("devops_cli.commands.install_tools._current_version", return_value="v1.28.0"),
    ):
        res_stat = runner.invoke(main_app, ["install-tools", "status"])
        assert res_stat.exit_code == 0

        res_all = runner.invoke(main_app, ["--dry-run", "install-tools", "all"])
        assert res_all.exit_code == 0

        res_direct = runner.invoke(install_tools_app, ["status"])
        assert res_direct.exit_code == 0
