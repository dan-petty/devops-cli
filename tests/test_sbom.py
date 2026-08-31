"""Tests for SBOM generation and devops scan sbom command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from devops_cli.commands.scan import app as scan_app
from devops_cli.security.sbom import (
    extract_workspace_components,
    generate_cyclonedx_sbom,
    generate_spdx_sbom,
)

runner = CliRunner()


def test_extract_workspace_components(tmp_path: Path) -> None:
    """Extract components from mock uv.lock file."""
    mock_lock = tmp_path / "uv.lock"
    mock_lock.write_text(
        '[[package]]\nname = "pydantic"\nversion = "2.13.4"\n\n'
        '[[package]]\nname = "rich"\nversion = "15.0.0"\n',
        encoding="utf-8",
    )
    components = extract_workspace_components(tmp_path)
    assert len(components) == 2
    names = [c.name for c in components]
    assert "pydantic" in names
    assert "rich" in names
    assert any(c.purl == "pkg:pypi/pydantic@2.13.4" for c in components)


def test_generate_cyclonedx_sbom(tmp_path: Path) -> None:
    """Generate CycloneDX 1.5 JSON SBOM."""
    mock_lock = tmp_path / "uv.lock"
    mock_lock.write_text(
        '[[package]]\nname = "typer"\nversion = "0.27.1"\n',
        encoding="utf-8",
    )
    sbom = generate_cyclonedx_sbom(tmp_path, project_name="devops-cli", project_version="0.2.6")
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    assert sbom["metadata"]["component"]["name"] == "devops-cli"
    assert len(sbom["components"]) == 1
    assert sbom["components"][0]["name"] == "typer"


def test_generate_spdx_sbom(tmp_path: Path) -> None:
    """Generate SPDX 2.3 JSON SBOM."""
    mock_lock = tmp_path / "uv.lock"
    mock_lock.write_text(
        '[[package]]\nname = "cryptography"\nversion = "50.0.1"\n',
        encoding="utf-8",
    )
    sbom = generate_spdx_sbom(tmp_path, project_name="devops-cli", project_version="0.2.6")
    assert sbom["spdxVersion"] == "SPDX-2.3"
    assert len(sbom["packages"]) == 2  # Root + 1 dependency
    assert len(sbom["relationships"]) == 1


def test_scan_sbom_cli(tmp_path: Path) -> None:
    """Test devops scan sbom command in CycloneDX, SPDX, and file output modes."""
    mock_lock = tmp_path / "uv.lock"
    mock_lock.write_text(
        '[[package]]\nname = "httpx2"\nversion = "2.9.0"\n',
        encoding="utf-8",
    )
    # Output to stdout
    res = runner.invoke(scan_app, ["sbom", str(tmp_path)])
    assert res.exit_code == 0
    assert "CycloneDX" in res.output
    assert "httpx2" in res.output

    # Output to file in SPDX format
    out_file = tmp_path / "sbom.spdx.json"
    res_file = runner.invoke(
        scan_app, ["sbom", str(tmp_path), "--format", "spdx", "--output", str(out_file)]
    )
    assert res_file.exit_code == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["spdxVersion"] == "SPDX-2.3"

    # Dry run
    res_dry = runner.invoke(scan_app, ["sbom", str(tmp_path), "--dry-run"])
    assert res_dry.exit_code == 0
