"""The shadow Jev tier choice of the stage job (#4284).

With `roadmap.stage.jev_shadow` on, the stage job makes one Jev routing call for each item before
its first plan call, logs one line and counts the tier choice in
`devops_cli_roadmap_stage_jev_total`. The call is a record only: it changes no plan, no model and
no item list. A Jev error is logged, counts `choice=error` and never stops the item.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.ai.jev import JevRouteDecision
from devops_cli.config.settings import load_settings
from devops_cli.roadmap.agent_run import RunTrace, ToolCallRecord
from devops_cli.roadmap.stage import stage as stage_module
from devops_cli.roadmap.stage.stage import PlanFiles, StageTarget
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stage.stage_plan_record import delete_plan_record, plan_record_path
from devops_cli.roadmap.stage.stage_request import StageRequest
from devops_cli.roadmap.stage.stage_specs import BaseSpec
from devops_cli.roadmap.stage.stage_toolbox import ToolboxClient
from devops_cli.roadmap.stores.store import Item
from tests.support.builders import make_stage_proposal
from tests.support.paths import REPO_ROOT

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from devops_cli.roadmap.item_comments import HeldComment
    from tests.support.roadmap_stage import StageRepo

PLAN_ROW = "stage"
REPO = "example/repo"
TOOLSET = "extended"
CLAIM = "The run read `src/devops_cli/sample.py`."
_SAMPLE = "src/devops_cli/sample.py"
_METRIC = "devops_cli_roadmap_stage_jev_total"


class _ScriptedToolbox(ToolboxClient):
    """A toolbox client whose runs are scripted: each call returns the next reply and records the
    trace of a run that read the sample file."""

    def __init__(self, replies: list[Any]) -> None:
        self._replies = list(replies)
        self.calls = 0
        self.traces: list[RunTrace] = []

    def hold_comments(self, comments: Sequence[HeldComment]) -> None:
        """The scripted runs read no comment (#6167)."""

    def chat_structured(
        self, system: str, prompt: str, schema: type[Any], *, max_retries: int
    ) -> Any:
        self.calls += 1
        call = ToolCallRecord("read_file", json.dumps({"path": _SAMPLE}))
        self.traces.append(RunTrace(tool_calls=[call], row=PLAN_ROW))
        return self._replies.pop(0)


class _StubbedPlanner(stage_module._Planner):
    """A planner whose request is fixed, so that a run needs no checkout."""

    def _request(self, target: StageTarget) -> StageRequest:
        return StageRequest(
            number=1,
            title="feat: sample",
            body="",
            context="",
            capabilities=["comment-thread"],
            budget=20000,
        )


def _plan() -> Any:
    return make_stage_proposal(groups=[make_stage_proposal().groups[0]], feasibility=[CLAIM])


def _clear_kept() -> None:
    """Remove the plan file that a run of item 1 wrote, so the next run misses it."""
    delete_plan_record(plan_record_path(REPO, 1))


def _target() -> StageTarget:
    item = Item(number=1, title="feat: sample", url="https://example.com/1", body="")
    return StageTarget(item, "feat", "sample")


def _planner(client: ToolboxClient, source: Path, jev: Any) -> Any:
    specs = {"comment-thread": BaseSpec(purpose="Defines thread comments.", requirements=())}
    return _StubbedPlanner(
        client=client,
        source=source,
        sha="",
        specs=specs,
        tree=StagedTree([_SAMPLE]),
        budget=20000,
        window=100000,
        tool=None,
        plan_files=PlanFiles(REPO, "model-a", TOOLSET),
        jev_route=jev,
    )


class _Jev:
    """A fake Jev route that records its calls and answers `decision`, or raises `error`."""

    def __init__(self, decision: JevRouteDecision | None = None, error: Exception | None = None):
        self._decision = decision
        self._error = error
        self.calls: list[dict[str, Any]] = []

    def __call__(self, state: Any, **kwargs: Any) -> JevRouteDecision:
        self.calls.append({"state": state, **kwargs})
        if self._error is not None:
            raise self._error
        assert self._decision is not None
        return self._decision


def _decision(picked: str = "sonnet", *, concrete: float = 0.9) -> JevRouteDecision:
    return JevRouteDecision(
        selected_model=picked,
        picked_model=picked,
        route_probability=0.8,
        route_confidence=0.9,
        probabilities={picked: 0.8},
        complexity_score=2.0,
        high_risk_probability=0.2,
        reasoning_effort="high",
        escalated=False,
        extra_probabilities={"concrete_files": concrete},
    )


def _enable_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    base = load_settings()
    stage = base.roadmap.stage.model_copy(update={"jev_shadow": True})
    roadmap = base.roadmap.model_copy(update={"stage": stage})
    monkeypatch.setattr(
        stage_module, "load_settings", lambda: base.model_copy(update={"roadmap": roadmap})
    )


@pytest.fixture
def samples(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, float, dict[str, Any] | None]]:
    """The counter samples of the stage job, in order."""
    found: list[tuple[str, float, dict[str, Any] | None]] = []

    def fake_emit(instrument: Any, value: float, attributes: dict[str, Any] | None = None) -> None:
        found.append((instrument.name, value, attributes))

    monkeypatch.setattr(stage_module, "emit", fake_emit)
    return found


def _jev_samples(
    samples: list[tuple[str, float, dict[str, Any] | None]],
) -> list[dict[str, Any] | None]:
    return [attrs for name, _, attrs in samples if name == _METRIC]


def test_the_switch_off_makes_no_jev_call(
    stage_repo: StageRepo, samples: list[tuple[str, float, dict[str, Any] | None]]
) -> None:
    jev = _Jev(_decision())
    planner = _planner(_ScriptedToolbox([_plan()]), stage_repo.clone, jev)

    planner.plan(_target())

    assert jev.calls == []
    assert _jev_samples(samples) == []


def test_the_switch_on_logs_and_counts_the_choice(
    stage_repo: StageRepo,
    samples: list[tuple[str, float, dict[str, Any] | None]],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_shadow(monkeypatch)
    jev = _Jev(_decision("sonnet"))
    planner = _planner(_ScriptedToolbox([_plan()]), stage_repo.clone, jev)

    with caplog.at_level(logging.INFO, logger="devops_cli.roadmap.stage.stage"):
        planner.plan(_target())

    assert len(jev.calls) == 1
    assert _jev_samples(samples) == [{"choice": "sonnet"}]
    line = next(r.getMessage() for r in caplog.records if r.levelno == logging.INFO)
    assert "#1" in line
    assert "sonnet" in line
    assert "2.00" in line
    assert "0.20" in line
    assert "0.90" in line


def test_the_shadow_changes_nothing(
    stage_repo: StageRepo, monkeypatch: pytest.MonkeyPatch, samples: list[tuple[str, float, Any]]
) -> None:
    off_client = _ScriptedToolbox([_plan()])
    off = _planner(off_client, stage_repo.clone, _Jev(_decision()))
    off_result = off.plan(_target())
    _clear_kept()

    _enable_shadow(monkeypatch)
    on_client = _ScriptedToolbox([_plan()])
    on = _planner(on_client, stage_repo.clone, _Jev(_decision()))
    on_result = on.plan(_target())

    assert on_result == off_result
    assert on_client.calls == off_client.calls == 1


def test_a_jev_error_counts_and_never_stops_the_item(
    stage_repo: StageRepo,
    samples: list[tuple[str, float, dict[str, Any] | None]],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    off = _planner(_ScriptedToolbox([_plan()]), stage_repo.clone, _Jev(_decision()))
    off_result = off.plan(_target())
    _clear_kept()

    _enable_shadow(monkeypatch)
    jev = _Jev(error=OSError("the Jev call broke"))
    planner = _planner(_ScriptedToolbox([_plan()]), stage_repo.clone, jev)

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.stage.stage"):
        result = planner.plan(_target())

    assert result == off_result
    assert _jev_samples(samples) == [{"choice": "error"}]
    assert any("the Jev call broke" in r.getMessage() for r in caplog.records)


def test_the_metric_has_three_series() -> None:
    from devops_cli.telemetry.instruments import ROADMAP_STAGE_JEV_TOTAL

    assert "3 series" in ROADMAP_STAGE_JEV_TOTAL.description
    telemetry = (REPO_ROOT / "docs" / "TELEMETRY.md").read_text(encoding="utf-8")
    assert ROADMAP_STAGE_JEV_TOTAL.name in telemetry
