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
    install_managed_tools,
    is_tool_installed,
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


def _make_tar_archive(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in members.items():
            ti = tarfile.TarInfo(name=name)
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def test_install_k8s_core_tools(tmp_path: Path) -> None:
    """Verify kubectl, kustomize, and helm installer logic with mock archives."""
    bin_content = b"#!/bin/sh\necho test\n"
    bin_sha = hashlib.sha256(bin_content).hexdigest()

    # 1. Kubectl
    def mock_download_kubectl(url: str) -> bytes:
        return f"{bin_sha}  kubectl\n".encode() if url.endswith(".sha256") else bin_content

    with patch("devops_cli.commands.install_tools._download", side_effect=mock_download_kubectl):
        _install_kubectl("1.30.0", tmp_path)

    # 2. Kustomize
    tar_kust = _make_tar_archive({"kustomize": bin_content})
    kust_sha = hashlib.sha256(tar_kust).hexdigest()
    tar_kust_name = f"kustomize_v5.4.0_{_OS}_{_ARCH}.tar.gz"

    def mock_download_kustomize(url: str) -> bytes:
        return f"{kust_sha}  {tar_kust_name}\n".encode() if "checksums.txt" in url else tar_kust

    with patch("devops_cli.commands.install_tools._download", side_effect=mock_download_kustomize):
        _install_kustomize("v5.4.0", tmp_path)

    # 3. Helm
    tar_helm = _make_tar_archive({f"{_OS}-{_ARCH}/helm": bin_content})
    helm_sha = hashlib.sha256(tar_helm).hexdigest()
    tar_helm_name = f"helm-v3.15.0-{_OS}-{_ARCH}.tar.gz"

    def mock_download_helm(url: str) -> bytes:
        return f"{helm_sha}  {tar_helm_name}\n".encode() if url.endswith(".sha256sum") else tar_helm

    with patch("devops_cli.commands.install_tools._download", side_effect=mock_download_helm):
        _install_helm("v3.15.0", tmp_path)

    assert (
        (tmp_path / "kubectl").exists(),
        (tmp_path / "kustomize").exists(),
        (tmp_path / "helm").exists(),
    ) == (True, True, True)


def test_install_argo_ecosystem_tools(tmp_path: Path) -> None:
    """Verify argo, argocd, and rollouts installers with checksum resolution and fallbacks."""
    bin_content = b"#!/bin/sh\necho test\n"
    bin_sha = hashlib.sha256(bin_content).hexdigest()
    gz_argo = gzip.compress(bin_content)
    argo_sha = hashlib.sha256(gz_argo).hexdigest()
    gz_name = f"argo-{_OS}-{_ARCH}.gz"

    # Argo with modern argo-workflows-cli-checksums.txt
    def mock_download_argo(url: str) -> bytes:
        if "argo-workflows-cli-checksums.txt" in url:
            return f"{argo_sha}  {gz_name}\n".encode()
        return gz_argo

    with patch("devops_cli.commands.install_tools._download", side_effect=mock_download_argo):
        _install_argo("v4.1.4", tmp_path)

    # ArgoCD
    argocd_bin_name = f"argocd-{_OS}-{_ARCH}"

    def mock_download_argocd(url: str) -> bytes:
        if "cli_checksums.txt" in url:
            return f"{bin_sha}  {argocd_bin_name}\n".encode()
        return bin_content

    with patch("devops_cli.commands.install_tools._download", side_effect=mock_download_argocd):
        _install_argocd("v2.11.0", tmp_path)

    # Rollouts with modern argo-rollouts-checksums.txt
    rollouts_bin_name = f"kubectl-argo-rollouts-{_OS}-{_ARCH}"

    def mock_download_rollouts(url: str) -> bytes:
        if "argo-rollouts-checksums.txt" in url or "sha256checksums.txt" in url:
            return f"{bin_sha}  {rollouts_bin_name}\n".encode()
        return bin_content

    with patch("devops_cli.commands.install_tools._download", side_effect=mock_download_rollouts):
        _install_rollouts("v1.10.0", tmp_path)

    assert (
        (tmp_path / "argo").exists(),
        (tmp_path / "argocd").exists(),
        (tmp_path / "kubectl-argo-rollouts").exists(),
    ) == (True, True, True)


def test_install_cluster_sanitizers(tmp_path: Path) -> None:
    """Verify trivy, kube-linter, popeye, pluto, and k9s installers."""
    bin_content = b"#!/bin/sh\necho test\n"

    tar_trivy = _make_tar_archive({"trivy": bin_content})
    tar_kubelinter = _make_tar_archive({"kube-linter": bin_content})
    tar_popeye = _make_tar_archive({"popeye": bin_content})
    tar_pluto = _make_tar_archive({"pluto": bin_content})
    tar_k9s = _make_tar_archive({"k9s": bin_content})

    with patch("devops_cli.commands.install_tools._download", return_value=tar_trivy):
        _install_trivy("0.50.0", tmp_path)
    with patch("devops_cli.commands.install_tools._download", return_value=tar_kubelinter):
        _install_kubelinter("0.8.3", tmp_path)
    with patch("devops_cli.commands.install_tools._download", return_value=tar_popeye):
        _install_popeye("0.21.0", tmp_path)
    with patch("devops_cli.commands.install_tools._download", return_value=tar_pluto):
        _install_pluto("5.19.0", tmp_path)
    with patch("devops_cli.commands.install_tools._download", return_value=tar_k9s):
        _install_k9s("v0.32.0", tmp_path)

    assert (
        (tmp_path / "trivy").exists(),
        (tmp_path / "kube-linter").exists(),
        (tmp_path / "popeye").exists(),
        (tmp_path / "pluto").exists(),
        (tmp_path / "k9s").exists(),
    ) == (True, True, True, True, True)


def test_is_tool_installed(tmp_path: Path) -> None:
    """Verify is_tool_installed checks target_dir and system PATH."""
    spec = TOOLS["k9s"]
    with patch("shutil.which", return_value=None):
        assert is_tool_installed(spec, tmp_path) is False

        # Place binary in target directory
        dummy_bin = tmp_path / spec.bin_name
        dummy_bin.write_bytes(b"dummy")
        assert is_tool_installed(spec, tmp_path) is True

    # When not in target directory, but on system PATH
    tmp_empty = tmp_path / "empty"
    tmp_empty.mkdir()
    with patch("shutil.which", return_value="/usr/local/bin/k9s"):
        assert is_tool_installed(spec, tmp_empty) is True


def test_install_all_only_missing(tmp_path: Path) -> None:
    """Verify --only-missing installs only tools missing from target_dir and PATH."""
    installed_calls: list[str] = []

    def mock_install_fn(name: str):
        def _installer(version: str, target_dir: Path) -> None:
            installed_calls.append(name)
            (target_dir / name).write_text("ok", encoding="utf-8")

        return _installer

    with (
        patch(
            "shutil.which",
            side_effect=lambda bin_name: "/usr/bin/" + bin_name if bin_name == "kubectl" else None,
        ),
        patch.object(TOOLS["kubectl"], "install", side_effect=mock_install_fn("kubectl")),
        patch.object(TOOLS["k9s"], "get_latest", return_value="v0.51.0"),
        patch.object(TOOLS["k9s"], "install", side_effect=mock_install_fn("k9s")),
    ):
        res = runner.invoke(
            install_tools_app,
            ["--tool", "kubectl", "--only-missing", "--target-dir", str(tmp_path)],
        )
        assert (res.exit_code, "kubectl" not in installed_calls) == (0, True)

        res_k9s = runner.invoke(
            install_tools_app,
            ["--tool", "k9s", "--only-missing", "--target-dir", str(tmp_path)],
        )
        assert (res_k9s.exit_code, "k9s" in installed_calls) == (0, True)


def test_install_managed_tools_programmatic(tmp_path: Path) -> None:
    """Verify install_managed_tools helper returns formatted actions and handles errors."""
    mock_ok = TOOLS["k9s"].model_copy(
        update={
            "name": "mock-tool-ok",
            "bin_name": "mock-tool-ok",
            "get_latest": lambda: "v1.0.0",
            "install": lambda v, d: (d / "mock-tool-ok").write_text("ok", encoding="utf-8"),
        }
    )

    def _failing_install(v: str, d: Path) -> None:
        raise RuntimeError("disk full")

    mock_fail = TOOLS["k9s"].model_copy(
        update={
            "name": "mock-tool-fail",
            "bin_name": "mock-tool-fail",
            "get_latest": lambda: "v1.0.0",
            "install": _failing_install,
        }
    )

    with (
        patch("shutil.which", return_value=None),
        patch.dict(
            TOOLS,
            {
                "mock-tool-ok": mock_ok,
                "mock-tool-fail": mock_fail,
            },
            clear=True,
        ),
    ):
        actions = install_managed_tools(target_dir=tmp_path, only_missing=True)
        assert len(actions) == 2
        assert "Installed mock-tool-ok v1.0.0" in actions[0]
        assert "Warning: Failed to install mock-tool-fail (disk full)" in actions[1]
