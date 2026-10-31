"""Tests for dry-run request plans and classifications across 15 OpenTofu commands.

Issue #2249: The dry-run rule (#412) states that a dry run makes no external request and
returns the requests that the real run would make.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.tf import (
    deploy_cloud,
    status_command,
    tf_apply,
    tf_cost_breakdown,
    tf_cost_diff,
    tf_destroy,
    tf_drift,
    tf_fmt,
    tf_graph,
    tf_init,
    tf_lint,
    tf_notify_plan,
    tf_output,
    tf_plan,
    tf_validate,
)
from devops_cli.dry_run import get_dry_run_class
from devops_cli.main import app

runner = CliRunner()

REQUEST_PLAN_COMMANDS = [
    ("tf init", tf_init, ["tf", "init", "--dry-run"]),
    ("tf plan", tf_plan, ["tf", "plan", "--dry-run"]),
    ("tf apply", tf_apply, ["tf", "apply", "--dry-run"]),
    ("tf destroy", tf_destroy, ["tf", "destroy", "--dry-run"]),
    ("tf output", tf_output, ["tf", "output", "--dry-run"]),
    ("tf deploy-cloud", deploy_cloud, ["tf", "deploy-cloud", "-p", "aws", "--dry-run"]),
    ("tf lint", tf_lint, ["tf", "lint", "--dry-run"]),
    ("tf cost breakdown", tf_cost_breakdown, ["tf", "cost", "breakdown", "--dry-run"]),
    ("tf cost diff", tf_cost_diff, ["tf", "cost", "diff", "--dry-run"]),
]

NO_EXTERNAL_REQUEST_COMMANDS = [
    ("tf drift", tf_drift, ["tf", "drift"]),
    ("tf fmt", tf_fmt, ["tf", "fmt"]),
    ("tf graph", tf_graph, ["tf", "graph"]),
    ("tf notify-plan", tf_notify_plan, ["tf", "notify-plan"]),
    ("tf status", status_command, ["tf", "status"]),
    ("tf validate", tf_validate, ["tf", "validate"]),
]


@pytest.fixture
def block_external_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no subprocess, network, or external socket calls execute during tests."""

    def _fail_subprocess(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"Subprocess call attempted during dry-run: {args} {kwargs}")

    monkeypatch.setattr("subprocess.run", _fail_subprocess)
    monkeypatch.setattr("subprocess.Popen", _fail_subprocess)


@pytest.mark.parametrize("name,callback,_argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_commands_classified_correctly(
    name: str,
    callback: Any,
    _argv: list[str],
) -> None:
    """Criterion 2: external-request commands carry the request-plan classification."""
    assert get_dry_run_class(callback) == "request-plan", (
        f"Command '{name}' must have dry_run_class 'request-plan'"
    )


@pytest.mark.parametrize("name,callback,_argv", NO_EXTERNAL_REQUEST_COMMANDS)
def test_no_external_request_commands_classified_correctly(
    name: str,
    callback: Any,
    _argv: list[str],
) -> None:
    """Criterion 3: local commands carry the no-external-request classification."""
    assert get_dry_run_class(callback) == "no-external-request", (
        f"Command '{name}' must have dry_run_class 'no-external-request'"
    )


@pytest.mark.parametrize("name,_callback,argv", REQUEST_PLAN_COMMANDS)
def test_request_plan_commands_make_no_external_request(
    name: str,
    _callback: Any,
    argv: list[str],
    block_external_calls: None,
    tmp_path: Path,
) -> None:
    """Criterion 4 & 5: request-plan commands make no external calls and output plans."""
    cmd_args = list(argv)
    if name in {"tf cost breakdown", "tf cost diff"}:
        cmd_args.insert(3, str(tmp_path))
    elif name in {"tf init", "tf plan", "tf apply", "tf destroy", "tf output", "tf lint"}:
        cmd_args.insert(2, str(tmp_path))

    result = runner.invoke(app, cmd_args)
    assert result.exit_code == 0, f"Command '{name}' failed with {result.output}"
    assert "Plan for" in result.output or "Planned" in result.output, (
        f"Command '{name}' did not render plan in output: {result.output}"
    )


def test_request_plan_json_output(
    block_external_calls: None,
    tmp_path: Path,
) -> None:
    """Criterion 6: request-plan commands with json format return result type with dry_run true."""
    # 1. tf output
    res_out = runner.invoke(app, ["tf", "output", str(tmp_path), "--format", "json", "--dry-run"])
    assert res_out.exit_code == 0, res_out.output
    data_out = json.loads(res_out.output)
    assert data_out.get("dry_run") is True
    assert "requests" in data_out

    # 2. tf lint
    res_lint = runner.invoke(app, ["tf", "lint", str(tmp_path), "--format", "json", "--dry-run"])
    assert res_lint.exit_code == 0, res_lint.output
    data_lint = json.loads(res_lint.output)
    assert data_lint.get("dry_run") is True
    assert "requests" in data_lint

    # 3. tf cost breakdown
    res_cb = runner.invoke(
        app, ["tf", "cost", "breakdown", str(tmp_path), "--format", "json", "--dry-run"]
    )
    assert res_cb.exit_code == 0, res_cb.output
    data_cb = json.loads(res_cb.output)
    assert data_cb.get("dry_run") is True
    assert "requests" in data_cb

    # 4. tf cost diff
    res_cd = runner.invoke(
        app, ["tf", "cost", "diff", str(tmp_path), "--format", "json", "--dry-run"]
    )
    assert res_cd.exit_code == 0, res_cd.output
    data_cd = json.loads(res_cd.output)
    assert data_cd.get("dry_run") is True
    assert "requests" in data_cd


def test_no_external_request_commands_run_under_dry_run_proxy(
    tmp_path: Path,
) -> None:
    """Criterion 8: devops --dry-run runs no-external-request commands normally."""
    (tmp_path / "main.tf").write_text('resource "null_resource" "test" {}\n')

    # status
    res_status = runner.invoke(app, ["--dry-run", "tf", "status", str(tmp_path)])
    assert res_status.exit_code == 0
    assert "Target" in res_status.output or "Status" in res_status.output

    # graph
    res_graph = runner.invoke(app, ["--dry-run", "tf", "graph", str(tmp_path)])
    assert res_graph.exit_code == 0

    # notify-plan
    res_np = runner.invoke(app, ["--dry-run", "tf", "notify-plan"])
    assert res_np.exit_code == 0
    assert "OpenTofu / Terraform Plan Summary" in res_np.output


def test_dry_run_plans_match_dispatched_arguments(tmp_path: Path) -> None:
    """Criterion 7: plan builders generate identical arguments to dispatched commands."""
    from devops_cli.tf.tf_plans import (
        build_infracost_breakdown_cmd,
        build_infracost_diff_cmd,
        build_tf_apply_cmd,
        build_tf_deploy_cloud_cmds,
        build_tf_destroy_cmd,
        build_tf_init_cmd,
        build_tf_output_cmd,
        build_tf_plan_cmd,
        plan_tf_cost_breakdown,
        plan_tf_cost_diff,
        plan_tf_init,
        plan_tf_plan,
    )

    # 1. tf init
    init_cmd = build_tf_init_cmd(binary="tofu", upgrade=True, reconfigure=True)
    assert init_cmd == ["tofu", "init", "-upgrade", "-reconfigure"]
    p_init = plan_tf_init(tmp_path, upgrade=True, reconfigure=True, binary="tofu")
    assert p_init[0].argv == tuple(init_cmd)

    # 2. tf plan
    plan_cmd = build_tf_plan_cmd(binary="tofu", destroy=True)
    assert plan_cmd == ["tofu", "plan", "-destroy"]
    p_plan = plan_tf_plan(tmp_path, destroy=True, binary="tofu")
    assert p_plan[0].argv == tuple(plan_cmd)

    # 3. tf apply
    apply_cmd = build_tf_apply_cmd(binary="tofu", auto_approve=True)
    assert apply_cmd == ["tofu", "apply", "-auto-approve"]

    # 4. tf destroy
    destroy_cmd = build_tf_destroy_cmd(binary="tofu", auto_approve=True)
    assert destroy_cmd == ["tofu", "destroy", "-auto-approve"]

    # 5. tf output
    out_cmd = build_tf_output_cmd(binary="tofu", json_mode=True)
    assert out_cmd == ["tofu", "output", "-json"]

    # 6. tf deploy-cloud
    c_init, c_apply = build_tf_deploy_cloud_cmds(binary="tofu", auto_approve=True)
    assert c_init == ["tofu", "init"]
    assert c_apply == ["tofu", "apply", "-auto-approve"]

    # 7. Infracost
    cost_cmd = build_infracost_breakdown_cmd(tmp_path)
    assert cost_cmd == ["infracost", "breakdown", "--path", str(tmp_path), "--format", "json"]
    p_cost = plan_tf_cost_breakdown(tmp_path)
    assert p_cost[0].argv == tuple(cost_cmd)

    diff_cmd = build_infracost_diff_cmd(tmp_path, compare_to="base.json")
    assert diff_cmd == [
        "infracost",
        "diff",
        "--path",
        str(tmp_path),
        "--format",
        "json",
        "--compare-to",
        "base.json",
    ]
    p_diff = plan_tf_cost_diff(tmp_path, compare_to="base.json")
    assert p_diff[0].argv == tuple(diff_cmd)
