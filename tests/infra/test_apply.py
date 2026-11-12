"""The level that an apply needs, and how a fresh check and a run compare with the plan (#5125).

The plans of each host come from the recorded runs of `tests/fixtures/infra/runner_events/`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.exceptions.infra import InfraApplyRefusedError
from devops_cli.github.repo_ref import RepoRef
from devops_cli.infra.access import AgentAccess, apply_level
from devops_cli.infra.apply import (
    ApplyRequest,
    fresh_differences,
    read_plan,
    unplanned_changes,
)
from devops_cli.infra.plan import host_plans
from devops_cli.models.infra import ChangedTask, HostPlan, PlanTask
from tests.support.infra import recorded_events


def _hosts(tmp_path: Path) -> dict[str, HostPlan]:
    plans = host_plans(recorded_events("site", tmp_path), tmp_path, {})
    return {plan.host: plan for plan in plans}


def test_a_plan_with_no_disruptive_class_and_no_unchecked_task_needs_safe(tmp_path: Path) -> None:
    hosts = _hosts(tmp_path)
    quiet = hosts["node-4.example.com"].model_copy(update={"failed": ()})

    assert apply_level([quiet]) is AgentAccess.SAFE
    assert apply_level([quiet, hosts["node-2.example.com"]]) is AgentAccess.FULL


def test_an_unchecked_task_needs_full(tmp_path: Path) -> None:
    host = _hosts(tmp_path)["node-1.example.com"]
    unchecked_only = host.model_copy(update={"disruptive": ()})

    assert unchecked_only.unchecked
    assert apply_level([unchecked_only]) is AgentAccess.FULL


def test_a_fresh_check_with_the_same_plan_has_no_difference(tmp_path: Path) -> None:
    host = _hosts(tmp_path)["node-3.example.com"]

    assert fresh_differences(host, host) == []


def test_a_fresh_check_names_each_part_that_differs(tmp_path: Path) -> None:
    host = _hosts(tmp_path)["node-3.example.com"]
    fresh = host.model_copy(update={"changed": host.changed[1:], "disruptive": ()})

    assert fresh_differences(host, fresh) == [
        "changed tasks: the plan has Deploy K3s agent configuration file, Ensure K3s-agent "
        "systemd service is started and enabled, the fresh check has Ensure K3s-agent systemd "
        "service is started and enabled",
        "disruptive classes: the plan has service-restart:k3s-agent, the fresh check has -",
    ]
    assert fresh_differences(host, None) == ["the fresh check did not reach the host"]


def test_a_task_that_check_mode_skipped_may_change_in_the_run(tmp_path: Path) -> None:
    planned = _hosts(tmp_path)["node-1.example.com"]
    [skipped] = planned.unchecked
    other = PlanTask(name="Write another file", path="site.yaml:9", action="ansible.builtin.copy")
    in_run = (ChangedTask(**skipped.model_dump()), ChangedTask(**other.model_dump()))
    ran = planned.model_copy(update={"changed": (*planned.changed, *in_run)})

    assert unplanned_changes(planned, ran) == (other,)


@pytest.mark.parametrize("given", ["../../etc", "abc", "A" * 64])
def test_an_id_that_is_not_a_plan_id_is_refused_before_a_read(given: str) -> None:
    with pytest.raises(InfraApplyRefusedError, match="is not a plan id"):
        read_plan(RepoRef("example-org/infra"), ApplyRequest(plan_id=given, playbook="site.yaml"))
