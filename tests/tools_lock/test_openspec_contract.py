"""The recorded OpenSpec the fake replays is the pinned tool's, and is the record of the commands
the gate and `devops openspec archive` run and no others (#1844, ADR 0007). The listing of the
capabilities that the fake makes from a tree is the listing of the real tool (#4622)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from devops_cli.openspec.tool import isolated_openspec
from devops_cli.tools_lock import load_tools_lock
from tests.support.fakes.openspec import LIST_SPECS, OpenSpecFake, spec_listing
from tests.support.openspec_recording import run_scenario
from tests.support.openspec_scenarios import SCENARIOS

if TYPE_CHECKING:
    from pathlib import Path

# A tree of each form of spec file that the discovery of OpenSpec reads or skips.
_SPEC = "# x Specification\n\n## Purpose\nA spec of the contract test, long enough to pass.\n"
_TREE = {
    "openspec/config.yaml": "schema: spec-driven\n",
    "openspec/specs/alpha/spec.md": _SPEC,
    "openspec/specs/area/cap-one/spec.md": _SPEC,
    "openspec/specs/area/deeper/cap-two/spec.md": _SPEC,
    "openspec/specs/.hidden/spec.md": _SPEC,
    "openspec/specs/spec.md": _SPEC,
    "openspec/specs/empty/README.md": "x\n",
}


def test_the_record_is_of_the_openspec_the_tools_lock_pins(openspec_fake: OpenSpecFake) -> None:
    """A bump of the pin fails here until the real tool is recorded again
    (tests/support/openspec_recording.py)."""
    assert openspec_fake.version == load_tools_lock().npm["openspec"].version


def test_every_scenario_is_recorded_and_no_other(openspec_fake: OpenSpecFake) -> None:
    """The scenarios a test builds are the scenarios the real tool ran over."""
    assert sorted(openspec_fake.scenarios) == sorted(SCENARIOS)


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_a_scenario_records_the_commands_run_over_it_and_no_others(
    openspec_fake: OpenSpecFake, scenario: str
) -> None:
    """The fake fails a command the record lacks. The other way: a run the record holds for a
    scenario that the gate or the archive no longer starts there is stale, and is dropped by
    recording again."""
    run_scenario(SCENARIOS[scenario], openspec_fake.tree(scenario))

    started = {call.argv for call in openspec_fake.calls}
    assert sorted(set(openspec_fake.scenarios[scenario]) - started) == []


def _listed(text: str) -> list[str]:
    return [spec["id"] for spec in json.loads(text)["specs"]]


@pytest.mark.live("openspec")
def test_the_fake_lists_the_capabilities_that_the_real_tool_lists(tmp_path: Path) -> None:
    for path, text in _TREE.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(text, encoding="utf-8")

    with isolated_openspec() as tool:
        real = tool.read_json(list(LIST_SPECS), tmp_path)

    assert [spec["id"] for spec in real["specs"]] == _listed(spec_listing(tmp_path))
    assert _listed(spec_listing(tmp_path)) == ["alpha", "area/cap-one", "area/deeper/cap-two"]
