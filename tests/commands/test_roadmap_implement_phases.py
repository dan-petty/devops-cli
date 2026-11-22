"""`devops roadmap implement --phase` (#3702): each phase of the run of one item, on a run folder.

The phases are tested end to end in `tests/roadmap/implement/test_roadmap_implement_phases.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]
# A token form in a reason: the Service reads the log of `publish`, so the reason is masked.
TOKEN = "ghp_" + "a1B2c3D4e5" * 3 + "f6G7h8"


@pytest.mark.parametrize(
    ("phase", "runs", "runner"),
    [
        ("prepare", "prepare_implement", "runner"),
        ("agent", "agent_implement", "agent runner"),
        ("publish", "publish_phase", "runner"),
    ],
)
def test_each_phase_makes_its_process_unreadable_before_anything_else(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    phase: str,
    runs: str,
    runner: str,
) -> None:
    """The run starts the code of a pull request as the user of the Job, so each phase clears its
    dumpable flag first, before it reads the settings of the runner or a file of the run (#2667,
    #3702). The agent phase checks that it holds no App key, and the other phases that they act as
    the App. The spy replaces the kernel call, which would change the test run."""
    from devops_cli import ai
    from devops_cli.ai.client import factory
    from devops_cli.core import process_hardening
    from devops_cli.exceptions.roadmap import RoadmapImplementError
    from devops_cli.roadmap import run
    from devops_cli.roadmap.implement import implement, implement_phases, implement_run

    seen: list[str] = []
    monkeypatch.setattr(implement_run, "require_runner", lambda _repo: seen.append("runner"))
    monkeypatch.setattr(implement_run, "require_agent_runner", lambda: seen.append("agent runner"))
    monkeypatch.setattr(
        process_hardening, "deny_environment_reads", lambda: seen.append("unreadable")
    )
    monkeypatch.setattr(factory, "get_task_model", lambda _task: None)
    monkeypatch.setattr(ai.client, "get_llm_client", lambda **_: None)
    monkeypatch.setattr(implement, "plan_implement", lambda *_, **__: _OnePlan())
    monkeypatch.setattr(implement, "render_implement_plan", lambda _plan: "")
    monkeypatch.setattr(run, "model_clone", lambda _repo: tmp_path)

    def step(*_: Any, **__: Any) -> Any:
        seen.append("step")
        raise RoadmapImplementError("The phase ends here.")

    monkeypatch.setattr(implement_phases, runs, step)

    result = cli(
        "roadmap",
        "implement",
        "--repo",
        "example/project",
        "--item",
        "1",
        "--confirm",
        "--phase",
        phase,
        "--work",
        str(tmp_path / "run"),
    )

    assert (result.exit_code, seen) == (1, ["unreadable", runner, "step"])


class _OnePlan:
    """A plan with one selected item, which the spy of `prepare` takes."""

    selected = (object(),)


@pytest.mark.parametrize(
    "args",
    [
        ["--phase", "agent", "--item", "1", "--work", "run"],
        ["--phase", "publish", "--confirm", "--item", "1"],
        ["--phase", "prepare", "--confirm", "--work", "run"],
    ],
    ids=["no-confirm", "no-work", "no-item"],
)
def test_a_phase_needs_its_item_confirm_and_a_run_folder(cli: Cli, args: list[str]) -> None:
    result = cli("roadmap", "implement", "--repo", "example/project", *args)

    assert (result.exit_code, "--work" in result.output) == (1, True)


def test_a_publish_after_a_prepare_that_left_the_item_out_ends_with_its_reason(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The container `publish` runs after each `prepare` (#3700). When the plan leaves the item
    out, `prepare` prints the plan, as `--phase all` does, and writes a state that says the run
    ended and why. `publish` prints the reason, because the Service reads the log of `publish`
    when the pod succeeds, and exits 0, so the pod does not fail (#6743)."""
    from devops_cli.core import process_hardening
    from devops_cli.roadmap import run
    from devops_cli.roadmap.implement import implement, implement_run
    from devops_cli.roadmap.implement.implement import ImplementPlan
    from devops_cli.roadmap.stage.stage import LeftOut

    plan = ImplementPlan(
        repo="example/project",
        left_out=(LeftOut(number=1, title="Item one", reason=f"the item is not Ready {TOKEN}"),),
    )
    monkeypatch.setattr(implement_run, "require_runner", lambda _repo: None)
    monkeypatch.setattr(process_hardening, "deny_environment_reads", lambda: None)
    monkeypatch.setattr(implement, "plan_implement", lambda *_, **__: plan)
    monkeypatch.setattr(run, "model_clone", lambda _repo: tmp_path)
    work = str(tmp_path / "run")
    base = ("roadmap", "implement", "--repo", "example/project", "--item", "1", "--confirm")

    prepared, published = (
        cli(*base, "--phase", phase, "--work", work) for phase in ("prepare", "publish")
    )

    assert (
        prepared.exit_code,
        "Item one" in prepared.output,
        published.exit_code,
        "the item is not Ready" in published.output,
        TOKEN in published.output,
    ) == (0, True, 0, True, False)
