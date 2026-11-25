"""Unit tests for OpenTofu / Terraform CLI commands (devops tf)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

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
    """Each provider has its example root module in `tf/examples/<provider>`, the infra layout."""
    assert [_get_cloud_dir(provider, tmp_path) for provider in ("aws", "azure", "gcp")] == [
        tmp_path / "tf" / "examples" / provider for provider in ("aws", "azure", "gcp")
    ]

    with pytest.raises(typer.Exit) as raised:
        _get_cloud_dir("unknown", tmp_path)
    assert raised.value.exit_code == 1


def test_get_default_var_file(tmp_path: Path) -> None:
    """The values of an example are `<provider>.tfvars.example` beside its root module."""
    (tmp_path / "tf" / "examples" / "azure").mkdir(parents=True)
    aws_var = tmp_path / "tf" / "examples" / "aws" / "aws.tfvars.example"
    aws_var.parent.mkdir(parents=True)
    aws_var.write_text("aws_region = 'us-west-2'\n")

    assert _get_default_var_file("aws", tmp_path) == aws_var
    assert _get_default_var_file("azure", tmp_path) is None


def test_tf_init_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    result = runner.invoke(app, ["init", "--upgrade", "--reconfigure", str(temp_tf_dir)])
    assert result.exit_code == 0
    assert any(c.argv == ("tofu", "init", "-upgrade", "-reconfigure") for c in process_fake.calls)


def test_tf_init_dry_run(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    result = runner.invoke(app, ["init", "--dry-run", str(temp_tf_dir)])
    assert result.exit_code == 0
    assert len(process_fake.calls) == 0


def test_tf_plan_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    var_file = temp_tf_dir / "test.tfvars"
    var_file.write_text("a = 1\n")
    out_file = temp_tf_dir / "tfplan"

    result = runner.invoke(
        app,
        [
            "plan",
            "--var-file",
            str(var_file),
            "--out",
            str(out_file),
            "--destroy",
            str(temp_tf_dir),
        ],
    )
    assert result.exit_code == 0
    assert any("plan" in c.argv and "-destroy" in c.argv for c in process_fake.calls)


def test_tf_apply_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    result = runner.invoke(app, ["apply", "--auto-approve", str(temp_tf_dir)])
    assert result.exit_code == 0
    assert any(c.argv == ("tofu", "apply", "-auto-approve") for c in process_fake.calls)


def test_tf_apply_with_plan_file(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    plan_file = temp_tf_dir / "tfplan"
    plan_file.write_text("plan")

    result = runner.invoke(app, ["apply", "--plan-file", str(plan_file), str(temp_tf_dir)])
    assert result.exit_code == 0
    assert any(str(plan_file.resolve()) in c.argv for c in process_fake.calls)


def test_tf_destroy_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    result = runner.invoke(app, ["destroy", "--auto-approve", str(temp_tf_dir)])
    assert result.exit_code == 0
    assert any(c.argv == ("tofu", "destroy", "-auto-approve") for c in process_fake.calls)


def test_tf_output_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    process_fake.answer("tofu", ProcessAnswer(stdout='{"cluster_name": "eks"}\n'))
    result = runner.invoke(app, ["output", "--json", str(temp_tf_dir)])
    assert result.exit_code == 0
    assert any(c.argv == ("tofu", "output", "-json") for c in process_fake.calls)


def test_tf_output_raw_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    process_fake.answer("tofu", ProcessAnswer(stdout="eks\n"))
    result = runner.invoke(app, ["output", "--raw", str(temp_tf_dir)])
    assert result.exit_code == 0
    assert any(c.argv == ("tofu", "output", "-raw") for c in process_fake.calls)


def test_tf_validate_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    result = runner.invoke(app, ["validate", "--no-color", str(temp_tf_dir)])
    assert result.exit_code == 0
    assert any(c.argv == ("tofu", "validate", "-no-color") for c in process_fake.calls)


def test_tf_fmt_command(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    result = runner.invoke(app, ["fmt", "--check", str(temp_tf_dir)])
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
    (temp_tf_dir / "tf" / "examples" / "aws").mkdir(parents=True)
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
    (temp_tf_dir / "tf" / "examples" / "aws").mkdir(parents=True)
    monkeypatch.chdir(temp_tf_dir)
    result = runner.invoke(
        app, ["deploy-cloud", "--provider", "aws", "--auto-approve", "--dry-run"]
    )
    assert result.exit_code == 0
    assert len(process_fake.calls) == 0


def test_a_dry_run_in_an_infra_checkout_plans_init_and_apply_of_its_example(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    """`devops tf deploy-cloud -p aws --dry-run` in an infra checkout plans `tofu init` and
    `tofu apply` with the values of `tf/examples/aws`, and starts no process (#6679)."""
    (tmp_path / ".git").mkdir()
    example = tmp_path / "tf" / "examples" / "aws"
    example.mkdir(parents=True)
    (example / "aws.tfvars.example").write_text('aws_region = "us-west-2"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["deploy-cloud", "--provider", "aws", "--dry-run"])

    output = "".join(result.output.split())
    assert (
        result.exit_code,
        str(example.resolve()) in output,
        "tofuinit" in output,
        f"tofuapply-var-file{example.resolve() / 'aws.tfvars.example'}" in output,
        process_fake.calls,
    ) == (0, True, True, True, [])


@pytest.mark.parametrize("args", [[], ["--dry-run"]], ids=["run", "dry-run"])
def test_deploy_cloud_outside_an_infra_checkout_names_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    process_fake: ProcessFake,
    fake_tf_binaries: None,
    args: list[str],
) -> None:
    """A checkout with no `tf/examples/<provider>` stops the command before any plan or
    process, and the error names the missing folder and an infra checkout (#6679)."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["deploy-cloud", "--provider", "aws", "--auto-approve", *args])

    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        "".join(str((tmp_path / "tf" / "examples" / "aws").resolve()).split())
        in "".join(output.split()),
        "infra checkout" in output,
        "tofu apply" in output,
        process_fake.calls,
    ) == (1, True, True, False, [])


def test_tf_subcommands_dry_run(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    """Verify plan, apply, destroy, and output in dry-run mode."""
    assert runner.invoke(app, ["plan", "--dry-run", str(temp_tf_dir)]).exit_code == 0
    assert runner.invoke(app, ["apply", "--dry-run", str(temp_tf_dir)]).exit_code == 0
    assert runner.invoke(app, ["destroy", "--dry-run", str(temp_tf_dir)]).exit_code == 0
    assert runner.invoke(app, ["output", "--dry-run", str(temp_tf_dir)]).exit_code == 0
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
    (nested / CONST_TF_AWS_DIR).mkdir(parents=True)
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
    checkout's tf/examples/aws holding `checkout_state` (a relative path and its contents, local
    state by default); the exit code, the tofu cwds and the output."""
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


def test_tf_plan_forwards_trailing_args_to_tofu(
    temp_tf_dir: Path, fake_tf_binaries: None, process_fake: ProcessFake
) -> None:
    """Every token after `<directory>` passes unchanged to `tofu plan` in that directory (#5318)."""
    result = runner.invoke(app, ["plan", str(temp_tf_dir), "-out=x.plan", "-lock=false"])

    assert result.exit_code == 0, result.output
    assert any(
        c.argv == ("tofu", "plan", "-out=x.plan", "-lock=false")
        and Path(c.cwd) == temp_tf_dir.resolve()
        for c in process_fake.calls
        if c.cwd
    )


@pytest.mark.parametrize(
    ("subcommand", "trailing"),
    [
        ("init", ["-upgrade=false"]),
        ("apply", ["-lock=false", "x.plan"]),
        ("destroy", ["-target=null_resource.x"]),
        ("output", ["-json", "cluster_name"]),
        ("validate", ["-json"]),
        ("fmt", ["-diff"]),
    ],
)
def test_tf_mirror_verbs_forward_trailing_args(
    subcommand: str,
    trailing: list[str],
    temp_tf_dir: Path,
    fake_tf_binaries: None,
    process_fake: ProcessFake,
) -> None:
    """All mirror verbs pass every token after `<directory>` unchanged to `tofu` (#5318)."""
    if subcommand == "fmt":
        # fmt defaults recursive=True via -recursive when wrapper --recursive is not disabled.
        expected_tail = ("-recursive", *trailing)
    else:
        expected_tail = tuple(trailing)

    result = runner.invoke(app, [subcommand, str(temp_tf_dir), *trailing])

    assert result.exit_code == 0, result.output
    assert any(
        c.argv == ("tofu", subcommand, *expected_tail) and Path(c.cwd) == temp_tf_dir.resolve()
        for c in process_fake.calls
        if c.cwd
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["plan", "-o", "x.plan"],
        ["plan", "-v", "vars.tfvars"],
        ["apply", "-p", "x.plan"],
        ["apply", "-v", "vars.tfvars"],
        ["destroy", "-v", "vars.tfvars"],
        ["init", "-u"],
        ["deploy-cloud", "-p", "aws"],
        ["deploy-cloud", "--provider", "aws", "-v", "vars.tfvars"],
        ["notify-plan", "-p", "plan.txt"],
    ],
)
def test_tf_removed_short_aliases_are_rejected(
    argv: list[str],
    temp_tf_dir: Path,
    fake_tf_binaries: None,
    process_fake: ProcessFake,
) -> None:
    """Short options `-o`, `-v`, `-p`, and `-u` are rejected before `<directory>` (#5318)."""
    if argv[0] == "notify-plan":
        plan_file = temp_tf_dir / "plan.txt"
        plan_file.write_text("No changes.\n", encoding="utf-8")
        cmd = ["notify-plan", "-p", str(plan_file)]
    elif argv[0] == "deploy-cloud":
        cmd = argv
    else:
        cmd = [*argv, str(temp_tf_dir)]
    result = runner.invoke(app, cmd)

    assert result.exit_code == 2
    assert "No such option:" in result.output
    assert process_fake.calls == []


@pytest.mark.parametrize(
    ("subcommand", "trailing"),
    [
        ("import", ["aws_instance.web", "i-123"]),
        ("state", ["list"]),
        ("show", ["-json"]),
        ("force-unlock", ["-force", "123456"]),
    ],
)
def test_tf_passthrough_subcommands_forward_to_tofu(
    subcommand: str,
    trailing: list[str],
    temp_tf_dir: Path,
    fake_tf_binaries: None,
    process_fake: ProcessFake,
) -> None:
    """`import`, `state`, `show`, and `force-unlock` pass trailing tokens to `tofu` (#5318)."""
    result = runner.invoke(app, [subcommand, str(temp_tf_dir), *trailing])

    assert result.exit_code == 0, result.output
    assert any(
        c.argv == ("tofu", subcommand, *trailing) and Path(c.cwd) == temp_tf_dir.resolve()
        for c in process_fake.calls
        if c.cwd
    )


@pytest.mark.parametrize(
    ("subcommand", "trailing"),
    [
        ("init", ["-upgrade=false"]),
        ("plan", ["-out=x.plan"]),
        ("apply", ["-auto-approve", "x.plan"]),
        ("destroy", ["-target=null_resource.x"]),
        ("output", ["-raw", "cluster_name"]),
        ("import", ["aws_instance.web", "i-123"]),
        ("state", ["list"]),
        ("show", ["-json"]),
        ("force-unlock", ["-force", "123456"]),
    ],
)
def test_tf_mirror_verbs_dry_run_prints_full_argv_and_directory(
    subcommand: str,
    trailing: list[str],
    temp_tf_dir: Path,
    fake_tf_binaries: None,
    process_fake: ProcessFake,
) -> None:
    """Dry run prints the full `tofu` command with trailing args and target directory (#5318)."""
    result = runner.invoke(app, [subcommand, "--dry-run", str(temp_tf_dir), *trailing])

    assert result.exit_code == 0, result.output
    assert process_fake.calls == []
    expected_cmd = " ".join(["tofu", subcommand, *trailing])
    assert expected_cmd in result.output
    assert str(temp_tf_dir.resolve()) in result.output


def test_tf_github_stack_agent_and_person_access_controls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_tf_binaries: None,
    process_fake: ProcessFake,
    keyring_store: Any,
    github_api: Any,
    config: Any,
    cli: Any,
    agent_caller: None,
) -> None:
    """Verify agent plan uses reader App, agent apply/destroy refuse at plan level, person apply
    passes, agent apply passes when configured, budget below 250 refuses, missing reader
    credentials refuse, and dry-run runs zero tofu calls (#5320)."""
    import time

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    from devops_cli.github.rate_limiter import get_github_rate_limiter
    from tests.support.fakes.github import github_json

    stack = tmp_path / "tf" / "github" / "dan-petty"
    stack.mkdir(parents=True)
    (stack / "main.tf").write_text('terraform { required_version = ">= 1.13.0" }\n')

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")
    keyring_store.values["tf_github_reader_private_key"] = pem
    keyring_store.values["service_github_app_private_key"] = "unused-writer-key"
    config(
        tf={
            "stacks": [{"path": "tf/github/dan-petty"}],
            "github_reader": {"app_id": 2001, "installation_id": 77},
        }
    )
    get_github_rate_limiter().update_quota(
        "core", remaining=500, limit=5000, reset_epoch=time.time() + 1800.0
    )
    github_api.route(
        "POST",
        "/app/installations/77/access_tokens",
        github_json(
            {
                "token": "ghs_reader_tok",
                "expires_at": "2026-11-25T12:35:00Z",
                "permissions": {"metadata": "read"},
            }
        ),
    )

    # 1. Agent plan succeeds with reader token and no writer key read.
    res_plan = cli("tf", "plan", str(stack))
    assert res_plan.exit_code == 0, res_plan.output
    assert len(process_fake.calls) == 1
    assert process_fake.calls[0].argv == ("tofu", "plan")
    assert process_fake.calls[0].env == {"GITHUB_TOKEN": "ghs_reader_tok"}
    assert "service_github_app_private_key" not in keyring_store.secret_reads()

    # 2. Agent apply and destroy are refused at plan level before invoking tofu.
    calls_before = len(process_fake.calls)
    for verb in ("apply", "destroy"):
        res_refused = cli("tf", verb, str(stack))
        assert res_refused.exit_code == 1
        assert "tf.stacks[].agent_access" in res_refused.output
        assert len(process_fake.calls) == calls_before

    # 3. Core budget below floor (249 < 250) refuses plan before invoking tofu.
    get_github_rate_limiter().update_quota(
        "core", remaining=249, limit=5000, reset_epoch=time.time() + 1800.0
    )
    res_budget = cli("tf", "plan", str(stack))
    assert res_budget.exit_code == 1
    assert "249" in res_budget.output
    assert "250" in res_budget.output
    assert len(process_fake.calls) == calls_before

    # 4. Missing reader App settings/key refuse plan naming all three settings with no tofu call.
    get_github_rate_limiter().update_quota(
        "core", remaining=500, limit=5000, reset_epoch=time.time() + 1800.0
    )
    keyring_store.values.pop("tf_github_reader_private_key")
    res_no_reader = cli("tf", "plan", str(stack))
    assert res_no_reader.exit_code == 1
    assert "tf.github_reader.app_id" in res_no_reader.output
    assert "tf.github_reader.installation_id" in res_no_reader.output
    assert "tf.github_reader.private_key" in res_no_reader.output
    assert len(process_fake.calls) == calls_before

    # 5. Agent apply allowed when stack configured with agent_access=apply.
    config(tf={"stacks": [{"path": "tf/github/dan-petty", "agent_access": "apply"}]})
    res_agent_apply = cli("tf", "apply", str(stack))
    assert res_agent_apply.exit_code == 0, res_agent_apply.output
    assert process_fake.calls[-1].argv == ("tofu", "apply")


def test_tf_github_stack_person_apply_and_dry_run_work_at_plan_level(
    tmp_path: Path,
    fake_tf_binaries: None,
    process_fake: ProcessFake,
    config: Any,
    cli: Any,
    person_caller: None,
) -> None:
    """Person apply passes on a plan-level tf/github stack, and --dry-run starts no tofu (#5320)."""
    stack = tmp_path / "tf" / "github" / "dan-petty"
    stack.mkdir(parents=True)
    (stack / "main.tf").write_text('terraform { required_version = ">= 1.13.0" }\n')
    config(tf={"stacks": [{"path": "tf/github/dan-petty", "agent_access": "plan"}]})

    res_dry = cli("tf", "apply", "--dry-run", str(stack))
    assert res_dry.exit_code == 0, res_dry.output
    assert "tofu apply" in res_dry.output
    assert process_fake.calls == []

    res_person_apply = cli("tf", "apply", str(stack))
    assert res_person_apply.exit_code == 0, res_person_apply.output
    assert len(process_fake.calls) == 1
    assert process_fake.calls[0].argv == ("tofu", "apply")
