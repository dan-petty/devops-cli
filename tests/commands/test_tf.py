"""Unit tests for OpenTofu / Terraform CLI commands (devops tf)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

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
from tests.support.fakes.process import ProcessAnswer, ProcessFake

runner = CliRunner()


@pytest.fixture
def fake_tf_binaries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make tofu, terraform and tflint appear on PATH."""
    old_which = shutil.which
    monkeypatch.setattr(
        shutil,
        "which",
        lambda cmd: f"/usr/bin/{cmd}" if cmd in ("tofu", "terraform", "tflint") else old_which(cmd),
    )


@pytest.fixture
def nested_worktree(tmp_path: Path, process_fake: ProcessFake) -> tuple[Path, Path]:
    """A checkout and a linked worktree nested under it, built with pure Python."""
    main = tmp_path / "checkout"
    nested = main / ".claude" / "worktrees" / "nested"
    (main / ".git" / "worktrees" / "nested").mkdir(parents=True)
    (main / "pyproject.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")
    nested.mkdir(parents=True)
    (main / ".git" / "worktrees" / "nested" / "commondir").write_text("../..\n", encoding="utf-8")
    (main / ".git" / "worktrees" / "nested" / "gitdir").write_text(
        f"{nested}/.git\n", encoding="utf-8"
    )
    (nested / ".git").write_text(f"gitdir: {main}/.git/worktrees/nested\n", encoding="utf-8")
    process_fake.answer("tofu", ProcessAnswer(returncode=0))
    process_fake.answer("terraform", ProcessAnswer(returncode=0))
    return main, nested


@pytest.fixture
def temp_tf_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with a dummy main.tf."""
    tf_file = tmp_path / "main.tf"
    tf_file.write_text('terraform { required_version = ">= 1.6.0" }\n')
    return tmp_path


@pytest.mark.parametrize(
    ("available_binary", "expected_binary"),
    [
        pytest.param("tofu", "tofu", id="opentofu-preferred"),
        pytest.param("terraform", "terraform", id="terraform-fallback"),
    ],
)
def test_resolve_tf_binary_precedence(
    available_binary: str, expected_binary: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _mock_which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name == available_binary else None

    monkeypatch.setattr(shutil, "which", _mock_which)
    assert _resolve_tf_binary() == expected_binary


def test_resolve_tf_binary_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.delenv("DEVOPS_CLI_DRY_RUN", raising=False)
    with pytest.raises(typer.Exit) as raised:
        _resolve_tf_binary()
    assert raised.value.exit_code == 1


def test_resolve_tf_binary_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "1")
    assert _resolve_tf_binary() == "tofu"


def test_validate_dir_valid(temp_tf_dir: Path) -> None:
    assert validate_dir(temp_tf_dir) == temp_tf_dir.resolve()


def test_validate_dir_invalid(tmp_path: Path) -> None:
    invalid = tmp_path / "non_existent_dir"
    with pytest.raises(typer.Exit) as raised:
        validate_dir(invalid)
    assert raised.value.exit_code == 1


def test_get_cloud_dir(tmp_path: Path) -> None:
    aws_dir = _get_cloud_dir("aws", tmp_path)
    assert aws_dir == tmp_path / "tf" / "aws"

    azure_dir = _get_cloud_dir("azure", tmp_path)
    assert azure_dir == tmp_path / "tf" / "azure"

    gcp_dir = _get_cloud_dir("gcp", tmp_path)
    assert gcp_dir == tmp_path / "tf" / "gcp"

    with pytest.raises(typer.Exit) as raised:
        _get_cloud_dir("unknown", tmp_path)
    assert raised.value.exit_code == 1


def test_get_default_var_file(tmp_path: Path) -> None:
    env_dir = tmp_path / "tf" / "environments"
    env_dir.mkdir(parents=True)
    aws_var = env_dir / "aws.tfvars.example"
    aws_var.write_text("aws_region = 'us-west-2'\n")

    assert _get_default_var_file("aws", tmp_path) == aws_var
    assert _get_default_var_file("azure", tmp_path) is None


def test_tf_init_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    result = runner.invoke(app, ["init", str(temp_tf_dir), "--upgrade", "--reconfigure"])
    assert result.exit_code == 0
    assert any(c.argv == ("tofu", "init", "-upgrade", "-reconfigure") for c in process_fake.calls)


def test_tf_init_dry_run(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    result = runner.invoke(app, ["init", str(temp_tf_dir), "--dry-run"])
    assert result.exit_code == 0
    assert len(process_fake.calls) == 0


def test_tf_plan_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    var_file = temp_tf_dir / "test.tfvars"
    var_file.write_text("a = 1\n")
    out_file = temp_tf_dir / "tfplan"

    result = runner.invoke(
        app, ["plan", str(temp_tf_dir), "-v", str(var_file), "-o", str(out_file), "--destroy"]
    )
    assert result.exit_code == 0
    assert any("plan" in c.argv and "-destroy" in c.argv for c in process_fake.calls)


def test_tf_apply_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    result = runner.invoke(app, ["apply", str(temp_tf_dir), "--auto-approve"])
    assert result.exit_code == 0
    assert any(c.argv == ("tofu", "apply", "-auto-approve") for c in process_fake.calls)


def test_tf_apply_with_plan_file(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    plan_file = temp_tf_dir / "tfplan"
    plan_file.write_text("plan")

    result = runner.invoke(app, ["apply", str(temp_tf_dir), "-p", str(plan_file)])
    assert result.exit_code == 0
    assert any(str(plan_file.resolve()) in c.argv for c in process_fake.calls)


def test_tf_destroy_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    result = runner.invoke(app, ["destroy", str(temp_tf_dir), "--auto-approve"])
    assert result.exit_code == 0
    assert any(c.argv == ("tofu", "destroy", "-auto-approve") for c in process_fake.calls)


def test_tf_output_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    process_fake.answer("tofu", ProcessAnswer(stdout='{"cluster_name": "eks"}\n'))
    result = runner.invoke(app, ["output", str(temp_tf_dir), "--json"])
    assert result.exit_code == 0
    assert any(c.argv == ("tofu", "output", "-json") for c in process_fake.calls)


def test_tf_output_raw_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    process_fake.answer("tofu", ProcessAnswer(stdout="eks\n"))
    result = runner.invoke(app, ["output", str(temp_tf_dir), "--raw"])
    assert result.exit_code == 0
    assert any(c.argv == ("tofu", "output", "-raw") for c in process_fake.calls)


def test_tf_validate_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    result = runner.invoke(app, ["validate", str(temp_tf_dir), "--no-color"])
    assert result.exit_code == 0
    assert any(c.argv == ("tofu", "validate", "-no-color") for c in process_fake.calls)


def test_tf_fmt_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    result = runner.invoke(app, ["fmt", str(temp_tf_dir), "--check"])
    assert result.exit_code == 0
    assert any(c.argv == ("tofu", "fmt", "-check", "-recursive") for c in process_fake.calls)


def test_tf_status_command(temp_tf_dir: Path, fake_tf_binaries: None) -> None:
    result = runner.invoke(app, ["status", str(temp_tf_dir)])
    assert result.exit_code == 0
    assert "OpenTofu Status" in result.output


def test_deploy_cloud_command(
    temp_tf_dir: Path,
    fake_tf_binaries: None,
    monkeypatch: pytest.MonkeyPatch,
    process_fake: ProcessFake,
) -> None:
    (temp_tf_dir / ".git").mkdir()
    (temp_tf_dir / "tf" / "aws").mkdir(parents=True)
    monkeypatch.chdir(temp_tf_dir)
    result = runner.invoke(app, ["deploy-cloud", "--provider", "aws", "--auto-approve"])
    assert result.exit_code == 0
    assert (
        len([c for c in process_fake.calls if c.argv and c.argv[0] in ("tofu", "terraform")]) == 2
    )


def test_deploy_cloud_dry_run(
    temp_tf_dir: Path,
    fake_tf_binaries: None,
    monkeypatch: pytest.MonkeyPatch,
    process_fake: ProcessFake,
) -> None:
    (temp_tf_dir / ".git").mkdir()
    (temp_tf_dir / "tf" / "aws").mkdir(parents=True)
    monkeypatch.chdir(temp_tf_dir)
    result = runner.invoke(
        app, ["deploy-cloud", "--provider", "aws", "--auto-approve", "--dry-run"]
    )
    assert result.exit_code == 0
    assert len(process_fake.calls) == 0


def test_tf_subcommands_dry_run(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    """Verify plan, apply, destroy, and output in dry-run mode."""
    assert runner.invoke(app, ["plan", str(temp_tf_dir), "--dry-run"]).exit_code == 0
    assert runner.invoke(app, ["apply", str(temp_tf_dir), "--dry-run"]).exit_code == 0
    assert runner.invoke(app, ["destroy", str(temp_tf_dir), "--dry-run"]).exit_code == 0
    assert runner.invoke(app, ["output", str(temp_tf_dir), "--dry-run"]).exit_code == 0
    assert len(process_fake.calls) == 0


def test_tf_lint_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    """Verify devops tf lint subcommand."""
    # Dry run
    res_dry = runner.invoke(app, ["lint", str(temp_tf_dir), "--dry-run"])
    assert res_dry.exit_code == 0

    # With findings and JSON
    tflint_issues = {
        "issues": [
            {
                "rule": {"name": "terraform-unused-declarations", "severity": "ERROR"},
                "message": "Unused variable",
                "range": {"filename": "main.tf", "start": {"line": 1}},
            }
        ]
    }
    process_fake.answer("tflint", ProcessAnswer(stdout=json.dumps(tflint_issues)))

    res_json = runner.invoke(app, ["lint", str(temp_tf_dir), "--json"])
    assert res_json.exit_code == 0
    assert "Unused variable" in res_json.output

    res_table = runner.invoke(app, ["lint", str(temp_tf_dir)])
    assert res_table.exit_code == 0

    # Clean
    process_fake.answer("tflint", ProcessAnswer(stdout=json.dumps({"issues": []})))
    res_clean = runner.invoke(app, ["lint", str(temp_tf_dir)])
    assert res_clean.exit_code == 0
    assert "No Terraform" in res_clean.output


@pytest.mark.parametrize("output_args", [[], ["--json"]], ids=["table", "json"])
def test_a_lint_that_did_not_run_says_so_and_fails(
    temp_tf_dir: Path, output_args: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no tflint on PATH, the command says that the lint did not run and why, says no pass,
    prints no findings list, and exits 1, in each output format (#2427)."""
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    result = runner.invoke(app, ["lint", str(temp_tf_dir), *output_args])

    assert (result.exit_code, "No Terraform" in result.output, "[]" in result.output) == (
        1,
        False,
        False,
    )
    assert (
        "TFLint lint unavailable: Binary 'tflint' not found on PATH. tflint linted no file, so "
        "the check did not pass."
    ) in " ".join(result.output.split())


def test_deploy_cloud_targets_the_nested_worktrees_configuration(
    nested_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `devops tf deploy-cloud` from a worktree under `.claude/worktrees/` initialises
    and applies that worktree's provider configuration, not the checkout's (#582)."""
    _, nested = nested_worktree
    monkeypatch.chdir(nested)

    result = runner.invoke(app, ["deploy-cloud", "--provider", "aws", "--dry-run"])

    assert result.exit_code == 0
    assert str(nested.resolve() / CONST_TF_AWS_DIR) in result.output


def _deploy_from_the_worktree(
    nested_worktree: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    process_fake: ProcessFake,
    args: list[str],
    *,
    answer: str = "",
    state_in: tuple[Path, ...] = (),
    checkout_state: tuple[str, str] = ("terraform.tfstate", "{}"),
) -> tuple[int, list[Path], str]:
    """Run `devops tf deploy-cloud --provider aws` from a nested worktree, with the main
    checkout's tf/aws holding `checkout_state` (a relative path and its contents, local state
    by default); the exit code, the tofu cwds and the output."""
    import shutil

    main, nested = nested_worktree
    for tree in (main, nested):
        (tree / CONST_TF_AWS_DIR).mkdir(parents=True)
    state_name, state_text = checkout_state
    (main / CONST_TF_AWS_DIR / state_name).parent.mkdir(parents=True, exist_ok=True)
    (main / CONST_TF_AWS_DIR / state_name).write_text(state_text, encoding="utf-8")
    for tree in state_in:
        (tree / CONST_TF_AWS_DIR / "terraform.tfstate").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        shutil, "which", lambda cmd: f"/usr/bin/{cmd}" if cmd in ("tofu", "terraform") else None
    )
    monkeypatch.chdir(nested)
    calls_before = len(process_fake.calls)
    result = runner.invoke(app, ["deploy-cloud", "--provider", "aws", *args], input=answer)
    cwds = [
        Path(call.cwd)
        for call in process_fake.calls[calls_before:]
        if call.cwd and call.argv and call.argv[0] in ("tofu", "terraform")
    ]
    return result.exit_code, cwds, "".join(result.output.split())


def test_deploy_cloud_refuses_to_auto_approve_a_worktree_without_the_checkouts_state(
    nested_worktree: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    process_fake: ProcessFake,
) -> None:
    """Verify an auto-approved deploy from a worktree with no local state, while the main
    checkout holds that provider's state, stops before `init` rather than planning to create
    every resource again from empty state."""
    main, _ = nested_worktree

    exit_code, cwds, output = _deploy_from_the_worktree(
        nested_worktree, monkeypatch, process_fake, ["--auto-approve"]
    )

    main_state = "".join(str((main / CONST_TF_AWS_DIR).resolve()).split())
    assert (exit_code, cwds, main_state in output) == (1, [], True)


@pytest.mark.parametrize(("answer", "expected_exit", "runs"), [("n\n", 1, 0), ("y\n", 0, 2)])
def test_deploy_cloud_asks_before_deploying_a_worktree_without_the_checkouts_state(
    nested_worktree: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    process_fake: ProcessFake,
    answer: str,
    expected_exit: int,
    runs: int,
) -> None:
    """Verify a deploy from such a worktree asks first: declining stops it, and confirming
    runs `init` and `apply` in the worktree's own configuration."""
    _, nested = nested_worktree

    exit_code, cwds, _ = _deploy_from_the_worktree(
        nested_worktree, monkeypatch, process_fake, [], answer=answer
    )

    assert (exit_code, cwds) == (expected_exit, [(nested / CONST_TF_AWS_DIR).resolve()] * runs)


def test_deploy_cloud_runs_unprompted_where_the_worktree_holds_its_own_state(
    nested_worktree: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    process_fake: ProcessFake,
) -> None:
    """Verify a worktree with a state file of its own deploys without the empty-state guard."""
    _, nested = nested_worktree

    exit_code, cwds, _ = _deploy_from_the_worktree(
        nested_worktree, monkeypatch, process_fake, ["--auto-approve"], state_in=(nested,)
    )

    assert (exit_code, cwds) == (0, [(nested / CONST_TF_AWS_DIR).resolve()] * 2)


def test_a_dry_run_deploy_warns_of_the_missing_state_without_asking(
    nested_worktree: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    process_fake: ProcessFake,
) -> None:
    """Verify a dry run from a worktree without the checkout's state warns, targets the
    worktree's provider directory rather than the main checkout's, and runs nothing."""
    main, nested = nested_worktree

    exit_code, cwds, output = _deploy_from_the_worktree(
        nested_worktree, monkeypatch, process_fake, ["--dry-run", "--auto-approve"]
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
    process_fake: ProcessFake,
    checkout_state: tuple[str, str],
    expected_exit: int,
    runs: int,
) -> None:
    """Verify the empty-state guard ignores the backend configuration that `init` caches in
    `.terraform/terraform.tfstate` for a remote backend, whose state no worktree lacks, and
    still stops an auto-approved deploy when that file holds local resource state."""
    _, nested = nested_worktree

    exit_code, cwds, _ = _deploy_from_the_worktree(
        nested_worktree,
        monkeypatch,
        process_fake,
        ["--auto-approve"],
        checkout_state=checkout_state,
    )

    assert (exit_code, cwds) == (expected_exit, [(nested / CONST_TF_AWS_DIR).resolve()] * runs)
