"""How the OpenSpec runner and the gate fail when the tool itself does: it exits non-zero, runs
past its timeout, or prints something other than JSON (#1844). A recording of the real tool
holds none of these, so the fake is told to answer them."""

from __future__ import annotations

import pytest

from devops_cli.exceptions import ToolExecutionError
from devops_cli.openspec.gate import GateCheck, GateFinding, check_openspec
from tests.support.fakes.openspec import OpenSpecFake


def test_a_setting_the_tool_refuses_stops_the_gate_with_the_command_and_its_reason(
    openspec_fake: OpenSpecFake,
) -> None:
    """The isolated configuration is the gate's ground: without it nothing else is read."""
    tree = openspec_fake.tree("empty")
    openspec_fake.script(("config", "set", "delivery", "skills"), 2, stderr="unknown setting")

    with pytest.raises(ToolExecutionError) as refused:
        check_openspec(tree)

    assert (refused.value.exit_code, refused.value.message, len(openspec_fake.calls)) == (
        1,
        "openspec config set delivery skills failed with exit code 2: unknown setting",
        2,
    )


def test_a_command_that_runs_past_its_timeout_is_stopped_and_named(
    openspec_fake: OpenSpecFake,
) -> None:
    """An earlier release hung `validate --all` under pre-commit: the gate names the command and
    the bound rather than waiting."""
    tree = openspec_fake.tree("empty")
    openspec_fake.hang(("validate", "--all", "--strict"))

    with pytest.raises(ToolExecutionError) as hung:
        check_openspec(tree)

    assert hung.value.message == (
        "openspec validate --all --strict ran past its 120s timeout and was stopped."
    )


def test_a_listing_that_is_not_json_is_reported_with_what_was_printed(
    openspec_fake: OpenSpecFake,
) -> None:
    """The change list is read as JSON; anything else is the tool failing, not an empty tree."""
    tree = openspec_fake.tree("empty")
    openspec_fake.script(("list", "--json"), 0, stdout="Segmentation fault")

    with pytest.raises(ToolExecutionError) as unreadable:
        check_openspec(tree)

    assert unreadable.value.message == (
        "openspec list --json failed with exit code 0: not JSON: Segmentation fault"
    )


def test_a_change_whose_deltas_cannot_be_shown_is_reported_by_the_overlap_check(
    openspec_fake: OpenSpecFake,
) -> None:
    """The overlap check reads every active change; one it cannot read is a finding, not a crash
    that hides the findings of the other checks."""
    tree = openspec_fake.tree("requirement-modified-twice")
    openspec_fake.script(
        ("show", "1914-export-widgets", "--json", "--deltas-only"), 1, stderr="bad delta"
    )

    assert check_openspec(tree) == [
        GateFinding(
            GateCheck.OVERLAP,
            "openspec show 1914-export-widgets --json --deltas-only failed with exit code 1: "
            "bad delta",
        )
    ]
