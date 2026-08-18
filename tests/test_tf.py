"""Unit tests for OpenTofu / Terraform CLI commands (devops tf)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from devops_cli.commands.tf import (
    _get_cloud_dir,
    _get_default_var_file,
    _resolve_tf_binary,
    _validate_dir,
    app,
)

runner = CliRunner()


@pytest.fixture
def temp_tf_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with a dummy main.tf."""
    tf_file = tmp_path / "main.tf"
    tf_file.write_text('terraform { required_version = ">= 1.6.0" }\n')
    return tmp_path


def test_resolve_tf_binary_found_tofu() -> None:
    def _mock_which(name: str) -> str | None:
        return "/usr/bin/tofu" if name == "tofu" else None

    with patch("shutil.which", side_effect=_mock_which):
        assert _resolve_tf_binary() == "tofu"


def test_resolve_tf_binary_fallback_terraform() -> None:
    def _mock_which(name: str) -> str | None:
        return "/usr/bin/terraform" if name == "terraform" else None

    with patch("shutil.which", side_effect=_mock_which):
        assert _resolve_tf_binary() == "terraform"


def test_resolve_tf_binary_not_found() -> None:
    with (
        patch("shutil.which", return_value=None),
        patch("devops_cli.commands.tf.is_dry_run", return_value=False),
    ):
        with pytest.raises(typer.Exit):
            _resolve_tf_binary()


def test_resolve_tf_binary_dry_run() -> None:
    with (
        patch("shutil.which", return_value=None),
        patch("devops_cli.commands.tf.is_dry_run", return_value=True),
    ):
        assert _resolve_tf_binary() == "tofu"


def test_validate_dir_valid(temp_tf_dir: Path) -> None:
    assert _validate_dir(temp_tf_dir) == temp_tf_dir.resolve()


def test_validate_dir_invalid(tmp_path: Path) -> None:
    invalid = tmp_path / "non_existent_dir"
    with pytest.raises(typer.Exit):
        _validate_dir(invalid)


def test_get_cloud_dir(tmp_path: Path) -> None:
    aws_dir = _get_cloud_dir("aws", tmp_path)
    assert aws_dir == tmp_path / "tf" / "aws"

    azure_dir = _get_cloud_dir("azure", tmp_path)
    assert azure_dir == tmp_path / "tf" / "azure"

    gcp_dir = _get_cloud_dir("gcp", tmp_path)
    assert gcp_dir == tmp_path / "tf" / "gcp"

    with pytest.raises(typer.Exit):
        _get_cloud_dir("unknown", tmp_path)


def test_get_default_var_file(tmp_path: Path) -> None:
    env_dir = tmp_path / "tf" / "environments"
    env_dir.mkdir(parents=True)
    aws_var = env_dir / "aws.tfvars.example"
    aws_var.write_text("aws_region = 'us-west-2'\n")

    assert _get_default_var_file("aws", tmp_path) == aws_var
    assert _get_default_var_file("azure", tmp_path) is None


def test_tf_init_command(temp_tf_dir: Path) -> None:
    with (
        patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"),
        patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run,
    ):
        result = runner.invoke(app, ["init", str(temp_tf_dir), "--upgrade", "--reconfigure"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["tofu", "init", "-upgrade", "-reconfigure"]


def test_tf_init_dry_run(temp_tf_dir: Path) -> None:
    with (
        patch("devops_cli.commands.tf.is_dry_run", return_value=True),
        patch("subprocess.run") as mock_run,
    ):
        result = runner.invoke(app, ["init", str(temp_tf_dir)])
        assert result.exit_code == 0
        mock_run.assert_not_called()


def test_tf_plan_command(temp_tf_dir: Path) -> None:
    var_file = temp_tf_dir / "test.tfvars"
    var_file.write_text("a = 1\n")
    out_file = temp_tf_dir / "tfplan"

    with (
        patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"),
        patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run,
    ):
        result = runner.invoke(
            app, ["plan", str(temp_tf_dir), "-v", str(var_file), "-o", str(out_file), "--destroy"]
        )
        assert result.exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "plan" in args
        assert "-destroy" in args


def test_tf_apply_command(temp_tf_dir: Path) -> None:
    with (
        patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"),
        patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run,
    ):
        result = runner.invoke(app, ["apply", str(temp_tf_dir), "--auto-approve"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["tofu", "apply", "-auto-approve"]


def test_tf_apply_with_plan_file(temp_tf_dir: Path) -> None:
    plan_file = temp_tf_dir / "tfplan"
    plan_file.write_text("plan")

    with (
        patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"),
        patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run,
    ):
        result = runner.invoke(app, ["apply", str(temp_tf_dir), "-p", str(plan_file)])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert str(plan_file.resolve()) in args


def test_tf_destroy_command(temp_tf_dir: Path) -> None:
    with (
        patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"),
        patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run,
    ):
        result = runner.invoke(app, ["destroy", str(temp_tf_dir), "--auto-approve"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["tofu", "destroy", "-auto-approve"]


def test_tf_output_command(temp_tf_dir: Path) -> None:
    with (
        patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"),
        patch(
            "subprocess.run",
            return_value=MagicMock(returncode=0, stdout='{"cluster_name": "eks"}\n'),
        ) as mock_run,
    ):
        result = runner.invoke(app, ["output", str(temp_tf_dir), "--json"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["tofu", "output", "-json"]


def test_tf_output_raw_command(temp_tf_dir: Path) -> None:
    with (
        patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"),
        patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="eks\n")) as mock_run,
    ):
        result = runner.invoke(app, ["output", str(temp_tf_dir), "--raw"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["tofu", "output", "-raw"]


def test_tf_validate_command(temp_tf_dir: Path) -> None:
    with (
        patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"),
        patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run,
    ):
        result = runner.invoke(app, ["validate", str(temp_tf_dir), "--no-color"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["tofu", "validate", "-no-color"]


def test_tf_fmt_command(temp_tf_dir: Path) -> None:
    with (
        patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"),
        patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run,
    ):
        result = runner.invoke(app, ["fmt", str(temp_tf_dir), "--check"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["tofu", "fmt", "-check", "-recursive"]


def test_tf_status_command(temp_tf_dir: Path) -> None:
    with patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"):
        result = runner.invoke(app, ["status", str(temp_tf_dir)])
        assert result.exit_code == 0
        assert "OpenTofu Status" in result.output


def test_deploy_cloud_command(temp_tf_dir: Path) -> None:
    with (
        patch("devops_cli.commands.tf.find_top_level_repo_root", return_value=temp_tf_dir),
        patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"),
        patch("devops_cli.commands.tf._get_cloud_dir", return_value=temp_tf_dir),
        patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run,
    ):
        result = runner.invoke(app, ["deploy-cloud", "--provider", "aws", "--auto-approve"])
        assert result.exit_code == 0
        assert mock_run.call_count == 2  # init and apply


def test_deploy_cloud_dry_run(temp_tf_dir: Path) -> None:
    with (
        patch("devops_cli.commands.tf.find_top_level_repo_root", return_value=temp_tf_dir),
        patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"),
        patch("devops_cli.commands.tf._get_cloud_dir", return_value=temp_tf_dir),
        patch("devops_cli.commands.tf.is_dry_run", return_value=True),
        patch("subprocess.run") as mock_run,
    ):
        result = runner.invoke(app, ["deploy-cloud", "--provider", "aws", "--auto-approve"])
        assert result.exit_code == 0
        mock_run.assert_not_called()
