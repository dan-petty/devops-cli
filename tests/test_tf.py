"""Unit tests for OpenTofu / Terraform CLI commands (devops tf)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from devops_cli.commands.tf import (
    _get_cloud_dir,
    _get_default_var_file,
    _resolve_tf_binary,
    app,
)
from devops_cli.config.constants import CONST_TF_AWS_DIR
from devops_cli.core.validation import validate_dir
from devops_cli.lang import MESSAGES

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
    assert validate_dir(temp_tf_dir) == temp_tf_dir.resolve()


def test_validate_dir_invalid(tmp_path: Path) -> None:
    invalid = tmp_path / "non_existent_dir"
    with pytest.raises(typer.Exit):
        validate_dir(invalid)


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
        patch("devops_cli.commands.tf.find_worktree_root", return_value=temp_tf_dir),
        patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"),
        patch("devops_cli.commands.tf._get_cloud_dir", return_value=temp_tf_dir),
        patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run,
    ):
        result = runner.invoke(app, ["deploy-cloud", "--provider", "aws", "--auto-approve"])
        assert result.exit_code == 0
        assert mock_run.call_count == 2  # init and apply


def test_deploy_cloud_dry_run(temp_tf_dir: Path) -> None:
    with (
        patch("devops_cli.commands.tf.find_worktree_root", return_value=temp_tf_dir),
        patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"),
        patch("devops_cli.commands.tf._get_cloud_dir", return_value=temp_tf_dir),
        patch("devops_cli.commands.tf.is_dry_run", return_value=True),
        patch("subprocess.run") as mock_run,
    ):
        result = runner.invoke(app, ["deploy-cloud", "--provider", "aws", "--auto-approve"])
        assert result.exit_code == 0
        mock_run.assert_not_called()


def test_tf_subcommands_dry_run(temp_tf_dir: Path) -> None:
    """Verify plan, apply, destroy, output, validate, and fmt in dry-run mode."""
    with (
        patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"),
        patch("devops_cli.commands.tf.is_dry_run", return_value=True),
        patch("subprocess.run") as mock_run,
    ):
        assert runner.invoke(app, ["plan", str(temp_tf_dir)]).exit_code == 0
        assert runner.invoke(app, ["apply", str(temp_tf_dir)]).exit_code == 0
        assert runner.invoke(app, ["destroy", str(temp_tf_dir)]).exit_code == 0
        assert runner.invoke(app, ["output", str(temp_tf_dir)]).exit_code == 0
        assert runner.invoke(app, ["validate", str(temp_tf_dir)]).exit_code == 0
        assert runner.invoke(app, ["fmt", str(temp_tf_dir)]).exit_code == 0
        mock_run.assert_not_called()


def test_tf_lint_command(temp_tf_dir: Path) -> None:
    """Verify devops tf lint subcommand."""
    from devops_cli.ai.review_schema import Finding

    mock_finding = Finding(
        severity="HIGH",
        location="main.tf:1",
        title="Unused variable",
        description="Var declared but not used",
        fix="Remove var",
    )

    # Dry run
    res_dry = runner.invoke(app, ["lint", str(temp_tf_dir), "--dry-run"])
    assert res_dry.exit_code == 0

    # With findings and JSON
    with patch("devops_cli.security.tflint.run_tflint_scan", return_value=[mock_finding]):
        res_json = runner.invoke(app, ["lint", str(temp_tf_dir), "--json"])
        assert res_json.exit_code == 0
        assert "Unused variable" in res_json.output

        res_table = runner.invoke(app, ["lint", str(temp_tf_dir)])
        assert res_table.exit_code == 0

    # Clean
    with patch("devops_cli.security.tflint.run_tflint_scan", return_value=[]):
        res_clean = runner.invoke(app, ["lint", str(temp_tf_dir)])
        assert res_clean.exit_code == 0
        assert "No Terraform" in res_clean.output


def test_deploy_cloud_targets_the_nested_worktrees_configuration(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `devops tf deploy-cloud` from a worktree under `.claude/worktrees/` initialises
    and applies that worktree's provider configuration, not the checkout's (#582)."""
    _, nested = nested_worktree
    monkeypatch.chdir(nested)

    with (
        patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"),
        patch("devops_cli.commands.tf.is_dry_run", return_value=True),
        patch("devops_cli.commands.tf.render_dry_run_result") as render,
    ):
        result = runner.invoke(app, ["deploy-cloud", "--provider", "aws"])

    targets = [call.kwargs["target"] for call in render.call_args_list]
    assert (result.exit_code, targets) == (0, [str(nested.resolve() / CONST_TF_AWS_DIR)] * 2)


def _deploy_from_the_worktree(
    nested_worktree: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    args: list[str],
    *,
    answer: str = "",
    state_in: tuple[Path, ...] = (),
    checkout_state: tuple[str, str] = ("terraform.tfstate", "{}"),
) -> tuple[int, list[Path], str]:
    """Run `devops tf deploy-cloud --provider aws` from a nested worktree, with the main
    checkout's tf/aws holding `checkout_state` (a relative path and its contents, local state
    by default); the exit code, the tofu cwds and the output."""
    main, nested = nested_worktree
    for tree in (main, nested):
        (tree / CONST_TF_AWS_DIR).mkdir(parents=True)
    state_name, state_text = checkout_state
    (main / CONST_TF_AWS_DIR / state_name).parent.mkdir(parents=True, exist_ok=True)
    (main / CONST_TF_AWS_DIR / state_name).write_text(state_text, encoding="utf-8")
    for tree in state_in:
        (tree / CONST_TF_AWS_DIR / "terraform.tfstate").write_text("{}", encoding="utf-8")
    cwds: list[Path] = []

    def record(_cmd: list[str], **kwargs: Any) -> MagicMock:
        cwds.append(Path(kwargs["cwd"]))
        return MagicMock(returncode=0)

    monkeypatch.chdir(nested)
    with (
        patch("devops_cli.commands.tf._resolve_tf_binary", return_value="tofu"),
        patch("devops_cli.commands.tf.run_subprocess", side_effect=record),
    ):
        result = runner.invoke(app, ["deploy-cloud", "--provider", "aws", *args], input=answer)
    return result.exit_code, cwds, "".join(result.output.split())


def test_deploy_cloud_refuses_to_auto_approve_a_worktree_without_the_checkouts_state(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify an auto-approved deploy from a worktree with no local state, while the main
    checkout holds that provider's state, stops before `init` rather than planning to create
    every resource again from empty state."""
    main, _ = nested_worktree

    exit_code, cwds, output = _deploy_from_the_worktree(
        nested_worktree, monkeypatch, ["--auto-approve"]
    )

    main_state = "".join(str((main / CONST_TF_AWS_DIR).resolve()).split())
    assert (exit_code, cwds, main_state in output) == (1, [], True)


@pytest.mark.parametrize(("answer", "expected_exit", "runs"), [("n\n", 1, 0), ("y\n", 0, 2)])
def test_deploy_cloud_asks_before_deploying_a_worktree_without_the_checkouts_state(
    nested_worktree: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    answer: str,
    expected_exit: int,
    runs: int,
) -> None:
    """Verify a deploy from such a worktree asks first: declining stops it, and confirming
    runs `init` and `apply` in the worktree's own configuration."""
    _, nested = nested_worktree

    exit_code, cwds, _ = _deploy_from_the_worktree(nested_worktree, monkeypatch, [], answer=answer)

    assert (exit_code, cwds) == (expected_exit, [(nested / CONST_TF_AWS_DIR).resolve()] * runs)


def test_deploy_cloud_runs_unprompted_where_the_worktree_holds_its_own_state(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a worktree with a state file of its own deploys without the empty-state guard."""
    _, nested = nested_worktree

    exit_code, cwds, _ = _deploy_from_the_worktree(
        nested_worktree, monkeypatch, ["--auto-approve"], state_in=(nested,)
    )

    assert (exit_code, cwds) == (0, [(nested / CONST_TF_AWS_DIR).resolve()] * 2)


def test_a_dry_run_deploy_warns_of_the_missing_state_without_asking(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a dry run from a worktree without the checkout's state warns, targets the
    worktree's provider directory rather than the main checkout's, and runs nothing."""
    main, nested = nested_worktree
    monkeypatch.setattr("devops_cli.commands.tf.is_dry_run", lambda: True)

    exit_code, cwds, output = _deploy_from_the_worktree(
        nested_worktree, monkeypatch, ["--auto-approve"]
    )

    cloud_dir, checkout_dir = ((tree / CONST_TF_AWS_DIR).resolve() for tree in (nested, main))
    warning = MESSAGES.tf.deploy_cloud_state_in_checkout.format(
        path=cloud_dir, checkout=checkout_dir
    )
    header = MESSAGES.tf.deploy_cloud_header.format(provider="AWS", path=cloud_dir)
    expected = [
        "".join(text.replace("[cyan]", "").replace("[/cyan]", "").split())
        for text in (warning, header)
    ]
    assert (exit_code, cwds, [text in output for text in expected]) == (0, [], [True, True])


_S3_BACKEND_CACHE = json.dumps(
    {"version": 3, "backend": {"type": "s3", "config": {"bucket": "state"}}, "modules": []}
)


@pytest.mark.parametrize(
    ("checkout_state", "expected_exit", "runs"),
    [
        ((".terraform/terraform.tfstate", _S3_BACKEND_CACHE), 0, 2),
        ((".terraform/terraform.tfstate", json.dumps({"version": 4, "resources": []})), 1, 0),
    ],
    ids=["remote-backend-cache", "local-state-under-dot-terraform"],
)
def test_deploy_cloud_guards_only_local_resource_state_in_the_checkout(
    nested_worktree: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    checkout_state: tuple[str, str],
    expected_exit: int,
    runs: int,
) -> None:
    """Verify the empty-state guard ignores the backend configuration that `init` caches in
    `.terraform/terraform.tfstate` for a remote backend, whose state no worktree lacks, and
    still stops an auto-approved deploy when that file holds local resource state."""
    _, nested = nested_worktree

    exit_code, cwds, _ = _deploy_from_the_worktree(
        nested_worktree, monkeypatch, ["--auto-approve"], checkout_state=checkout_state
    )

    assert (exit_code, cwds) == (expected_exit, [(nested / CONST_TF_AWS_DIR).resolve()] * runs)
