"""Tests for install-tools command and registry."""

from __future__ import annotations

import gzip
import hashlib
import io
import subprocess
import tarfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.install_tools import (
    _ARCH,
    _OS,
    TOOLS,
    _current_version,
    _install_argo,
    _install_argocd,
    _install_helm,
    _install_k9s,
    _install_kubectl,
    _install_kubelinter,
    _install_kustomize,
    _install_pluto,
    _install_popeye,
    _install_rollouts,
    _install_trivy,
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


def test_verify_sha256_passes_for_correct_hash() -> None:
    data = b"hello world"
    expected = hashlib.sha256(data).hexdigest()
    _verify_sha256(data, expected)


def test_verify_sha256_passes_with_surrounding_whitespace() -> None:
    data = b"hello world"
    expected = "  " + hashlib.sha256(data).hexdigest() + "\n"
    _verify_sha256(data, expected)


def test_verify_sha256_raises_on_mismatch() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        _verify_sha256(b"hello", "deadbeef" * 8)


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

        res_direct = runner.invoke(install_tools_app, ["status"])
        assert res_direct.exit_code == 0


def test_install_tool_execution(tmp_path: Path) -> None:
    """Verify install callback with specific tool."""
    with patch.object(TOOLS["kubectl"], "install") as mock_inst:
        res = runner.invoke(
            install_tools_app,
            ["--tool", "kubectl", "--version", "v1.30.0", "--target-dir", str(tmp_path)],
        )
        assert res.exit_code == 0
        mock_inst.assert_called_once()


def test_install_all_and_error_branches(tmp_path: Path) -> None:
    """Verify install callback validation errors, get_latest failures, and path hints."""
    # Invalid version format
    res_bad_ver = runner.invoke(install_tools_app, ["--version", "invalid_ver!"])
    assert res_bad_ver.exit_code == 1

    # Unknown tool
    res_unk = runner.invoke(install_tools_app, ["--tool", "unknown_tool_xyz"])
    assert res_unk.exit_code == 1

    # Tool get_latest error & install error handled gracefully
    with (
        patch.object(TOOLS["kubectl"], "get_latest", side_effect=Exception("Network error")),
        patch.object(TOOLS["helm"], "get_latest", return_value="v3.15.0"),
        patch.object(TOOLS["helm"], "install", side_effect=Exception("Write error")),
    ):
        res = runner.invoke(install_tools_app, ["--tool", "kubectl", "--target-dir", str(tmp_path)])
        assert res.exit_code == 0


def test_individual_tool_installers(tmp_path: Path) -> None:
    """Verify individual tool installer logic with mock downloaded archives."""

    def _make_tar(members: dict[str, bytes]) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            for name, data in members.items():
                ti = tarfile.TarInfo(name=name)
                ti.size = len(data)
                tf.addfile(ti, io.BytesIO(data))
        return buf.getvalue()

    bin_content = b"#!/bin/sh\necho test\n"
    bin_sha = hashlib.sha256(bin_content).hexdigest()

    # 1. Kubectl
    def mock_download_kubectl(url: str) -> bytes:
        if url.endswith(".sha256"):
            return f"{bin_sha}  kubectl\n".encode()
        return bin_content

    with patch("devops_cli.commands.install_tools._download", side_effect=mock_download_kubectl):
        _install_kubectl("1.30.0", tmp_path)
        assert (tmp_path / "kubectl").exists()

    # 2. Kustomize
    tar_kust = _make_tar({"kustomize": bin_content})
    kust_sha = hashlib.sha256(tar_kust).hexdigest()
    tar_kust_name = f"kustomize_v5.4.0_{_OS}_{_ARCH}.tar.gz"

    def mock_download_kustomize(url: str) -> bytes:
        if "checksums.txt" in url:
            return f"{kust_sha}  {tar_kust_name}\n".encode()
        return tar_kust

    with patch("devops_cli.commands.install_tools._download", side_effect=mock_download_kustomize):
        _install_kustomize("v5.4.0", tmp_path)
        assert (tmp_path / "kustomize").exists()

    # 3. Helm
    tar_helm = _make_tar({f"{_OS}-{_ARCH}/helm": bin_content})
    helm_sha = hashlib.sha256(tar_helm).hexdigest()
    tar_helm_name = f"helm-v3.15.0-{_OS}-{_ARCH}.tar.gz"

    def mock_download_helm(url: str) -> bytes:
        if url.endswith(".sha256sum"):
            return f"{helm_sha}  {tar_helm_name}\n".encode()
        return tar_helm

    with patch("devops_cli.commands.install_tools._download", side_effect=mock_download_helm):
        _install_helm("v3.15.0", tmp_path)
        assert (tmp_path / "helm").exists()

    # 4. Argo
    gz_argo = gzip.compress(bin_content)
    argo_sha = hashlib.sha256(gz_argo).hexdigest()

    def mock_download_argo(url: str) -> bytes:
        if url.endswith(".sha256"):
            return f"{argo_sha}  argo.gz\n".encode()
        return gz_argo

    with patch("devops_cli.commands.install_tools._download", side_effect=mock_download_argo):
        _install_argo("v3.5.0", tmp_path)
        assert (tmp_path / "argo").exists()

    # 5. ArgoCD
    argocd_bin_name = f"argocd-{_OS}-{_ARCH}"

    def mock_download_argocd(url: str) -> bytes:
        if "cli_checksums.txt" in url:
            return f"{bin_sha}  {argocd_bin_name}\n".encode()
        return bin_content

    with patch("devops_cli.commands.install_tools._download", side_effect=mock_download_argocd):
        _install_argocd("v2.11.0", tmp_path)
        assert (tmp_path / "argocd").exists()

    # 6. Rollouts
    rollouts_bin_name = f"kubectl-argo-rollouts-{_OS}-{_ARCH}"

    def mock_download_rollouts(url: str) -> bytes:
        if "sha256checksums.txt" in url:
            return f"{bin_sha}  {rollouts_bin_name}\n".encode()
        return bin_content

    with patch("devops_cli.commands.install_tools._download", side_effect=mock_download_rollouts):
        _install_rollouts("v1.7.0", tmp_path)
        assert (tmp_path / "kubectl-argo-rollouts").exists()

    # 7. Trivy
    tar_trivy = _make_tar({"trivy": bin_content})
    with patch("devops_cli.commands.install_tools._download", return_value=tar_trivy):
        _install_trivy("0.50.0", tmp_path)
        assert (tmp_path / "trivy").exists()

    # 8. Kube-linter
    tar_kubelinter = _make_tar({"kube-linter": bin_content})
    with patch("devops_cli.commands.install_tools._download", return_value=tar_kubelinter):
        _install_kubelinter("0.6.8", tmp_path)
        assert (tmp_path / "kube-linter").exists()

    # 9. Popeye
    tar_popeye = _make_tar({"popeye": bin_content})
    with patch("devops_cli.commands.install_tools._download", return_value=tar_popeye):
        _install_popeye("0.21.0", tmp_path)
        assert (tmp_path / "popeye").exists()

    # 10. Pluto
    tar_pluto = _make_tar({"pluto": bin_content})
    with patch("devops_cli.commands.install_tools._download", return_value=tar_pluto):
        _install_pluto("5.19.0", tmp_path)
        assert (tmp_path / "pluto").exists()

    # 11. K9s
    tar_k9s = _make_tar({"k9s": bin_content})
    with patch("devops_cli.commands.install_tools._download", return_value=tar_k9s):
        _install_k9s("v0.32.0", tmp_path)
        assert (tmp_path / "k9s").exists()
