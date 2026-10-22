"""The recorded OpenSpec the fake replays is the pinned tool's, and is the record of the commands
the gate runs and no others (#1844, ADR 0007)."""

from __future__ import annotations

import pytest

from devops_cli.openspec.gate import check_openspec
from devops_cli.tools_lock import load_tools_lock
from tests.support.fakes.openspec import OpenSpecFake
from tests.support.openspec_scenarios import SCENARIOS


def test_the_record_is_of_the_openspec_the_tools_lock_pins(openspec_fake: OpenSpecFake) -> None:
    """A bump of the pin fails here until the real tool is recorded again
    (tests/support/openspec_recording.py)."""
    assert openspec_fake.version == load_tools_lock().npm["openspec"].version


def test_every_scenario_is_recorded_and_no_other(openspec_fake: OpenSpecFake) -> None:
    """The scenarios a test builds are the scenarios the real tool ran over."""
    assert sorted(openspec_fake.scenarios) == sorted(SCENARIOS)


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_a_scenario_records_the_commands_the_gate_runs_over_it_and_no_others(
    openspec_fake: OpenSpecFake, scenario: str
) -> None:
    """The fake fails a command the record lacks. The other way: a run the record holds for a
    scenario that the gate no longer starts there is stale, and is dropped by recording again."""
    check_openspec(openspec_fake.tree(scenario))

    started = {call.argv for call in openspec_fake.calls}
    assert sorted(set(openspec_fake.scenarios[scenario]) - started) == []
