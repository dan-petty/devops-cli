"""The `@dry_run_command` decorator: a dry run prints its result and does not run the command."""

from __future__ import annotations

import json
from typing import Any, ClassVar

import pytest
from pydantic import BaseModel, model_serializer
from pydantic_core import PydanticSerializationError

from devops_cli.dry_run import dry_run_command, is_dry_run, set_dry_run


def _printed_result(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    """The JSON object that the dry run printed after its header line."""
    output = capsys.readouterr().out
    result: dict[str, Any] = json.loads(output[output.index("{") :])
    return result


class _StateProbe(BaseModel):
    """A detail value that records the dry-run state at the moment the result is serialized."""

    seen: ClassVar[list[bool]] = []

    @model_serializer
    def _serialize(self) -> str:
        self.seen.append(is_dry_run())
        return "probe"


def test_the_command_runs_when_no_dry_run_is_active(capsys: pytest.CaptureFixture[str]) -> None:
    @dry_run_command(command="devops test cmd", action="test_action")
    def sample_cmd(arg: str, dry_run: bool = False) -> str:
        return f"executed {arg}"

    assert sample_cmd("hello", dry_run=False) == "executed hello"
    assert capsys.readouterr().out == ""
    assert not is_dry_run()


def test_the_dry_run_argument_prints_the_result_and_does_not_run_the_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    executed: list[str] = []

    @dry_run_command(
        command="devops test cmd",
        action="deploy_chart",
        target_param="name",
        detail_params=["chart", "ns"],
    )
    def sample_cmd(name: str, chart: str, ns: str = "default", dry_run: bool = False) -> None:
        executed.append(name)

    assert sample_cmd("my-release", "nginx", ns="prod", dry_run=True) is None

    assert executed == []
    assert _printed_result(capsys) == {
        "command": "devops test cmd",
        "target": "my-release",
        "dry_run": True,
        "status": "DRY_RUN",
        "action": "deploy_chart",
        "details": {"chart": "nginx", "ns": "prod"},
    }
    assert not is_dry_run(), "the state before the call is back after it"


def test_the_dry_run_state_is_on_while_the_result_is_printed() -> None:
    _StateProbe.seen.clear()

    @dry_run_command(command="devops test cmd", action="probe", detail_params=["probe"])
    def sample_cmd(probe: _StateProbe, dry_run: bool = False) -> None:
        raise AssertionError("a dry run does not run the command")

    sample_cmd(_StateProbe(), dry_run=True)

    assert _StateProbe.seen == [True]


def test_the_state_is_restored_when_the_result_cannot_be_printed() -> None:
    @dry_run_command(command="devops err", action="error_action", detail_params=["value"])
    def sample_cmd(value: object, dry_run: bool = False) -> None:
        raise AssertionError("a dry run does not run the command")

    with pytest.raises(PydanticSerializationError, match="Unable to serialize unknown type"):
        sample_cmd(object(), dry_run=True)

    assert not is_dry_run(), "the state is restored even if the print fails"


def test_an_active_global_dry_run_stops_the_command(capsys: pytest.CaptureFixture[str]) -> None:
    """A global dry run, such as the one the root `--dry-run` option sets, stops the command."""
    set_dry_run(True)
    executed: list[str] = []

    @dry_run_command(
        command="devops test global",
        action="remove_resource",
        target_param="resource_id",
    )
    def sample_cmd(resource_id: str) -> str:
        executed.append(resource_id)
        return "not_reached"

    assert sample_cmd("pod-123") is None

    assert executed == []
    assert _printed_result(capsys) == {
        "command": "devops test global",
        "target": "pod-123",
        "dry_run": True,
        "status": "DRY_RUN",
        "action": "remove_resource",
        "details": {},
    }
    assert is_dry_run(), "the global dry run stays on"


def test_the_target_and_the_details_are_read_from_positional_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    @dry_run_command(
        command="devops delete",
        action="delete_item",
        target_param="item_id",
        detail_params=["force"],
    )
    def delete_item(item_id: str, force: bool = False, dry_run: bool = False) -> None:
        raise AssertionError("a dry run does not run the command")

    delete_item("item-abc", True, dry_run=True)

    result = _printed_result(capsys)
    assert (result["target"], result["details"]) == ("item-abc", {"force": True})
