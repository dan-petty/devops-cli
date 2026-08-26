"""Unit tests for kustomize CLI commands (devops_cli.commands.kustomize)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.kustomize import app as kustomize_app

runner = CliRunner()


def test_kustomize_commands(tmp_path: Path) -> None:
    """Verify kustomize build, diff, and apply subcommands."""
    kust_dir = tmp_path / "overlay"
    kust_dir.mkdir()
    (kust_dir / "kustomization.yaml").write_text(
        "resources:\n  - deployment.yaml\n", encoding="utf-8"
    )

    with patch("devops_cli.commands.kustomize.run_subprocess") as mock_subproc:
        mock_subproc.return_value = MagicMock(returncode=0)

        res_build = runner.invoke(kustomize_app, ["build", str(kust_dir)])
        assert res_build.exit_code == 0

        res_build_out = runner.invoke(
            kustomize_app, ["build", str(kust_dir), "--output", "out.yaml"]
        )
        assert res_build_out.exit_code == 0

        res_diff = runner.invoke(kustomize_app, ["diff", str(kust_dir)])
        assert res_diff.exit_code == 0

        res_apply = runner.invoke(
            kustomize_app, ["apply", str(kust_dir), "--dry-run", "--namespace", "staging"]
        )
        assert res_apply.exit_code == 0

        # Apply without dry-run and without namespace
        res_apply_direct = runner.invoke(kustomize_app, ["apply", str(kust_dir)])
        assert res_apply_direct.exit_code == 0

        # Default path invocation when directory exists
        res_build_default = runner.invoke(kustomize_app, ["build"])
        assert res_build_default.exit_code == 0

    # Invalid namespace
    res_bad_ns = runner.invoke(
        kustomize_app, ["apply", str(kust_dir), "--namespace", "INVALID_NAMESPACE!@#"]
    )
    assert res_bad_ns.exit_code != 0
