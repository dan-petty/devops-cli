"""Unit tests for declarative @dry_run_command decorator (TDD Specification)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from devops_cli.dry_run.decorator import dry_run_command
from devops_cli.dry_run.state import is_dry_run, set_dry_run


@pytest.fixture(autouse=True)
def reset_dry_run_state() -> None:
    set_dry_run(False)


def test_dry_run_command_executes_when_dry_run_false() -> None:
    """When dry_run=False, the wrapped function executes normally and returns its value."""
    mock_fn = MagicMock(return_value="executed_result")

    @dry_run_command(command="devops test cmd", action="test_action")
    def sample_cmd(arg1: str, dry_run: bool = False) -> str:
        return str(mock_fn(arg1))

    res = sample_cmd("hello", dry_run=False)
    assert res == "executed_result"
    mock_fn.assert_called_once_with("hello")
    assert not is_dry_run()


def test_dry_run_command_intercepts_when_kwarg_dry_run_true() -> None:
    """When dry_run=True is passed as kwarg, function body is NOT executed and dry run is rendered."""
    mock_fn = MagicMock()

    @dry_run_command(
        command="devops test cmd",
        action="deploy_chart",
        target_param="name",
        detail_params=["chart", "ns"],
    )
    def sample_cmd(name: str, chart: str, ns: str = "default", dry_run: bool = False) -> None:
        mock_fn()

    with patch("devops_cli.dry_run.decorator.render_dry_run_result") as mock_render:
        res = sample_cmd("my-release", "nginx", ns="prod", dry_run=True)
        assert res is None
        mock_fn.assert_not_called()
        mock_render.assert_called_once_with(
            command="devops test cmd",
            action="deploy_chart",
            target="my-release",
            details={"chart": "nginx", "ns": "prod"},
        )
        assert is_dry_run()


def test_dry_run_command_intercepts_when_global_dry_run_active() -> None:
    """When global dry run is already set (e.g. from CLI root option), function body is intercepted."""
    set_dry_run(True)
    mock_fn = MagicMock()

    @dry_run_command(
        command="devops test global",
        action="remove_resource",
        target_param="resource_id",
    )
    def sample_cmd(resource_id: str) -> str:
        mock_fn()
        return "not_reached"

    with patch("devops_cli.dry_run.decorator.render_dry_run_result") as mock_render:
        res = sample_cmd("pod-123")
        assert res is None
        mock_fn.assert_not_called()
        mock_render.assert_called_once_with(
            command="devops test global",
            action="remove_resource",
            target="pod-123",
            details={},
        )


def test_dry_run_command_resolves_target_from_positional_args() -> None:
    """Target parameter is correctly resolved from positional args using signature binding."""

    @dry_run_command(
        command="devops delete",
        action="delete_item",
        target_param="item_id",
        detail_params=["force"],
    )
    def delete_item(item_id: str, force: bool = False, dry_run: bool = False) -> None:
        pass

    with patch("devops_cli.dry_run.decorator.render_dry_run_result") as mock_render:
        delete_item("item-abc", True, dry_run=True)
        mock_render.assert_called_once_with(
            command="devops delete",
            action="delete_item",
            target="item-abc",
            details={"force": True},
        )
