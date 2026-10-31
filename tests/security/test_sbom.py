"""Tests for SBOM generation and devops scan sbom command (#1439)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

import devops_cli.security.sbom as sbom
from tests.support.fakes.process import ProcessAnswer, ProcessFake


def test_build_trivy_sbom_cmd(tmp_path: Path) -> None:
    """Verify build_trivy_sbom_cmd formats argv for CycloneDX and SPDX."""
    from devops_cli.config.commands import build_trivy_sbom_cmd

    cmd_cyclonedx = build_trivy_sbom_cmd(tmp_path, "cyclonedx")
    assert cmd_cyclonedx == ["trivy", "fs", "--format", "cyclonedx", str(tmp_path)]

    cmd_spdx = build_trivy_sbom_cmd(tmp_path, "spdx")
    assert cmd_spdx == ["trivy", "fs", "--format", "spdx-json", str(tmp_path)]

    cmd_spdx_json = build_trivy_sbom_cmd(tmp_path, "spdx-json")
    assert cmd_spdx_json == ["trivy", "fs", "--format", "spdx-json", str(tmp_path)]


def test_scan_sbom_cyclonedx_argv_and_output_to_file(
    process_fake: ProcessFake, tmp_path: Path, cli: Callable[..., Any], snapshot: SnapshotAssertion
) -> None:
    """Verify devops scan sbom invokes Trivy with CycloneDX format and writes output unchanged."""
    recorded_output = '{"bomFormat": "CycloneDX", "specVersion": "1.5"}'
    process_fake.answer(
        ("trivy", "fs", "--format", "cyclonedx"),
        ProcessAnswer(returncode=0, stdout=recorded_output),
    )

    out_file = tmp_path / "sbom.cdx.json"
    res = cli(["scan", "sbom", str(tmp_path), "--output", str(out_file)])
    assert res.exit_code == 0
    assert any(
        call.argv == ("trivy", "fs", "--format", "cyclonedx", str(tmp_path.resolve()))
        for call in process_fake.calls
    )
    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8") == recorded_output
    assert json.loads(out_file.read_text(encoding="utf-8")) == snapshot


def test_scan_sbom_spdx_argv_and_output_to_file(
    process_fake: ProcessFake, tmp_path: Path, cli: Callable[..., Any], snapshot: SnapshotAssertion
) -> None:
    """Verify devops scan sbom invokes Trivy with SPDX format and writes output unchanged."""
    recorded_output = '{"spdxVersion": "SPDX-2.3", "SPDXID": "SPDXRef-DOCUMENT"}'
    process_fake.answer(
        ("trivy", "fs", "--format", "spdx-json"),
        ProcessAnswer(returncode=0, stdout=recorded_output),
    )

    out_file = tmp_path / "sbom.spdx.json"
    res = cli(["scan", "sbom", str(tmp_path), "--format", "spdx", "--output", str(out_file)])
    assert res.exit_code == 0
    assert any(
        call.argv == ("trivy", "fs", "--format", "spdx-json", str(tmp_path.resolve()))
        for call in process_fake.calls
    )
    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8") == recorded_output
    assert json.loads(out_file.read_text(encoding="utf-8")) == snapshot


def test_scan_sbom_stdout(
    process_fake: ProcessFake, tmp_path: Path, cli: Callable[..., Any]
) -> None:
    """Verify devops scan sbom outputs Trivy SBOM content unchanged to stdout."""
    recorded_output = '{"bomFormat": "CycloneDX", "version": 1}'
    process_fake.answer(
        ("trivy", "fs", "--format", "cyclonedx"),
        ProcessAnswer(returncode=0, stdout=recorded_output),
    )

    res = cli(["scan", "sbom", str(tmp_path)])
    assert res.exit_code == 0
    assert recorded_output in res.output


def test_scan_sbom_missing_trivy_reports_not_installed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, cli: Callable[..., Any]
) -> None:
    """Verify devops scan sbom exits non-zero and reports not installed when Trivy is missing."""
    empty_bin = tmp_path / "bin-without-trivy"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))

    res = cli(["scan", "sbom", str(tmp_path)])
    assert res.exit_code != 0
    assert "not installed" in res.output


def test_scan_sbom_unsupported_format(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """Verify devops scan sbom rejects unsupported format."""
    res = cli(["scan", "sbom", str(tmp_path), "--format", "invalid_fmt"])
    assert res.exit_code == 1
    assert "Unsupported SBOM format" in res.output


def test_scan_sbom_dry_run(
    process_fake: ProcessFake, tmp_path: Path, cli: Callable[..., Any]
) -> None:
    """Verify devops scan sbom previews execution plan in dry-run mode."""
    res = cli(["--dry-run", "scan", "sbom", str(tmp_path)])
    assert res.exit_code == 0


def test_security_sbom_deletes_hand_rolled_builders() -> None:
    """Verify custom SBOM data classes and dictionary generators are deleted."""
    assert not hasattr(sbom, "extract_workspace_components")
    assert not hasattr(sbom, "generate_cyclonedx_sbom")
    assert not hasattr(sbom, "generate_spdx_sbom")
    assert not hasattr(sbom, "SBOMComponent")
    assert not hasattr(sbom, "SBOMDocument")
