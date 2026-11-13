"""What a check-mode run of a playbook shows on each host, and the id of a plan (#5124).

The job events are recorded runs of the pinned `ansible-runner` on the probe in
`tests/fixtures/infra/runner_events/probe/` (`tests/support/infra.py`): node-3 runs the k3s agent
role of dan-petty/homelab, node-1 a demo unit with a diff, a hidden diff, a `no_log` change, two
skips and a restart handler, node-2 a reboot, and node-4 a task that fails.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from devops_cli.infra.ansible_facts import parse_inventory
from devops_cli.infra.plan import (
    host_pattern,
    host_plans,
    nondisruptive_units,
    plan_id,
    plan_outcome,
    read_job_events,
)
from devops_cli.models.infra import (
    ChangedTask,
    FailedTask,
    HostPlan,
    PlanContent,
    PlanStatus,
    PlanTask,
)
from tests.support.infra import recorded_events, recorded_read

_K3S_AGENT = "ansible/roles/k3s_agent/tasks/main.yaml"
_DEMO = "ansible/roles/demo/tasks/main.yaml"


def _hosts(
    run: str, project: Path, units: dict[str, frozenset[str]] | None = None
) -> dict[str, HostPlan]:
    plans = host_plans(recorded_events(run, project), project, units or {})
    return {plan.host: plan for plan in plans}


def test_the_k3s_agent_role_shows_a_hidden_diff_and_a_restart_of_its_unit(tmp_path: Path) -> None:
    """The two `no_log` reads of the join token change nothing: the stats count 2 changes."""
    assert _hosts("agent", tmp_path) == {
        "node-3.example.com": HostPlan(
            host="node-3.example.com",
            changed=(
                ChangedTask(
                    name="Deploy K3s agent configuration file",
                    path=f"{_K3S_AGENT}:18",
                    action="ansible.builtin.template",
                    diff_hidden=True,
                ),
                ChangedTask(
                    name="Ensure K3s-agent systemd service is started and enabled",
                    path=f"{_K3S_AGENT}:43",
                    action="ansible.builtin.systemd",
                ),
            ),
            disruptive=("service-restart:k3s-agent",),
        )
    }


def test_each_change_skip_and_handler_of_a_host_is_in_the_plan(tmp_path: Path) -> None:
    """A template with a diff, a copy with `diff: false`, a `no_log` copy that the stats count, a
    `command` that check mode skips, a `command` whose `when` is false, and the restart handler
    that the template notifies."""
    assert _hosts("site", tmp_path)["node-1.example.com"] == HostPlan(
        host="node-1.example.com",
        changed=(
            ChangedTask(
                name="Write the demo config", path=f"{_DEMO}:2", action="ansible.builtin.template"
            ),
            ChangedTask(
                name="Write the demo token with the diff hidden",
                path=f"{_DEMO}:9",
                action="ansible.builtin.copy",
                diff_hidden=True,
            ),
            ChangedTask(
                name="Write the demo secret with no log",
                path=f"{_DEMO}:16",
                action="ansible.builtin.copy",
                diff_hidden=True,
            ),
            ChangedTask(
                name="Restart the demo unit",
                path="ansible/roles/demo/handlers/main.yaml:2",
                action="ansible.builtin.systemd_service",
            ),
        ),
        disruptive=("service-restart:demo",),
        unchecked=(
            PlanTask(
                name="Load the demo module", path=f"{_DEMO}:23", action="ansible.builtin.command"
            ),
        ),
    )


def test_a_skip_result_in_color_stays_unchecked(tmp_path: Path) -> None:
    """In a color terminal the callback puts color codes around the text of each skip, so the
    result after `=> ` does not read as JSON, and a skip by a false `when` is unchecked: the safe
    side. The run turns the color off (#5352), so a plan does not read such a skip."""
    remove_unit = PlanTask(
        name="Remove the old demo unit", path=f"{_DEMO}:27", action="ansible.builtin.command"
    )
    install_agent = PlanTask(
        name="Download and execute K3s agent installation script",
        path=f"{_K3S_AGENT}:31",
        action="ansible.builtin.shell",
    )
    added = {"node-1.example.com": (remove_unit,), "node-3.example.com": (install_agent,)}
    plain = _hosts("site", tmp_path)

    assert _hosts("site_color", tmp_path) == {
        host: plan.model_copy(update={"unchecked": plan.unchecked + added.get(host, ())})
        for host, plan in plain.items()
    }


def test_a_reboot_task_is_disruptive(tmp_path: Path) -> None:
    assert _hosts("site", tmp_path)["node-2.example.com"] == HostPlan(
        host="node-2.example.com",
        changed=(
            ChangedTask(
                name="Reboot the host",
                path="ansible/playbooks/site.yaml:22",
                action="ansible.builtin.reboot",
            ),
        ),
        disruptive=("reboot",),
    )


def test_a_failed_task_marks_the_plan_failed(tmp_path: Path) -> None:
    hosts = _hosts("site", tmp_path)

    assert hosts["node-4.example.com"].failed == (
        FailedTask(
            name="Read the cluster state",
            path="ansible/playbooks/site.yaml:35",
            action="ansible.builtin.command",
            reason="The command exited with a non-zero return code.",
        ),
    )
    assert plan_outcome(tuple(hosts.values()), "failed", 2, "") == (PlanStatus.FAILED, None)


@pytest.mark.parametrize(
    ("status", "returncode", "detail", "outcome"),
    [
        pytest.param("successful", 0, "", (PlanStatus.OK, None), id="successful"),
        pytest.param(
            "timeout",
            254,
            "",
            (PlanStatus.FAILED, "The check-mode run passed its time limit and stopped."),
            id="timeout",
        ),
        pytest.param(
            "failed",
            1,
            "ERROR! the playbook: site.yaml could not be found",
            (PlanStatus.FAILED, "ERROR! the playbook: site.yaml could not be found"),
            id="no-host-event",
        ),
    ],
)
def test_a_run_that_does_not_end_successful_is_a_failed_plan(
    status: str, returncode: int, detail: str, outcome: tuple[PlanStatus, str | None]
) -> None:
    assert plan_outcome((), status, returncode, detail) == outcome


def test_a_unit_that_the_host_lists_as_nondisruptive_is_not_disruptive(tmp_path: Path) -> None:
    listing = recorded_read("inventory", tmp_path)
    listing["_meta"]["hostvars"]["node-1.example.com"]["devops_infra_nondisruptive_units"] = [
        "demo"
    ]
    units = nondisruptive_units(parse_inventory(listing))

    node = _hosts("site", tmp_path, units)["node-1.example.com"]

    assert units == {"node-1.example.com": frozenset({"demo"})}
    assert (len(node.changed), node.disruptive) == (4, ())


def test_a_templated_list_of_nondisruptive_units_is_not_read(tmp_path: Path) -> None:
    """Only Ansible renders a template, so every restart stays disruptive."""
    listing = recorded_read("inventory", tmp_path)
    listing["_meta"]["hostvars"]["node-1.example.com"]["devops_infra_nondisruptive_units"] = (
        "{{ units }}"
    )

    assert nondisruptive_units(parse_inventory(listing)) == {}


def _event(action: str, res: dict[str, Any]) -> dict[str, Any]:
    data = {
        "host": "node-1.example.com",
        "task": "Drain the node",
        "task_path": "/repo/site.yaml:5",
        "resolved_action": action,
        "res": res,
    }
    return {"event": "runner_on_ok", "counter": 1, "event_data": data}


@pytest.mark.parametrize(
    ("action", "res", "disruptive"),
    [
        pytest.param(
            "kubernetes.core.k8s_drain",
            {"changed": True, "invocation": {"module_args": {"state": "drain"}}},
            ("drain",),
            id="drain",
        ),
        pytest.param(
            "kubernetes.core.k8s_drain",
            {"changed": True, "invocation": {"module_args": {"state": "cordon"}}},
            (),
            id="cordon",
        ),
        pytest.param(
            "ansible.builtin.service",
            {
                "changed": True,
                "name": "chrony",
                "invocation": {"module_args": {"state": "stopped"}},
            },
            ("service-restart:chrony",),
            id="stop",
        ),
        pytest.param(
            "ansible.builtin.systemd_service",
            {
                "changed": True,
                "name": "chrony",
                "invocation": {"module_args": {"state": "started"}},
            },
            (),
            id="start",
        ),
        pytest.param(
            "ansible.builtin.systemd",
            {"changed": True, "name": "chrony", "state": "started"},
            ("service-restart:chrony",),
            id="no-arguments-safe-side",
        ),
        pytest.param(
            "ansible.builtin.systemd",
            {
                "changed": False,
                "name": "chrony",
                "invocation": {"module_args": {"state": "restarted"}},
            },
            (),
            id="unchanged",
        ),
    ],
)
def test_the_disruptive_class_comes_from_the_action_and_its_arguments(
    action: str, res: dict[str, Any], disruptive: tuple[str, ...]
) -> None:
    [plan] = host_plans([_event(action, res)], Path("/repo"), {})

    assert plan.disruptive == disruptive


@pytest.mark.parametrize(
    ("limit", "offline", "pattern"),
    [
        pytest.param(None, "offline", "all:!offline", id="all-hosts"),
        pytest.param(
            "node-5.example.com", "offline", "node-5.example.com:!offline", id="offline-host"
        ),
        pytest.param("k3s_agent", None, "k3s_agent", id="no-offline-group"),
    ],
)
def test_a_host_in_the_offline_group_is_never_in_the_limit(
    limit: str | None, offline: str | None, pattern: str
) -> None:
    assert host_pattern(limit, offline) == pattern


def _content(tmp_path: Path, **changes: Any) -> PlanContent:
    hosts = tuple(_hosts("agent", tmp_path).values())
    fields: dict[str, Any] = {
        "repo": "example-org/infra",
        "ref": "origin/main",
        "commit": "a" * 40,
        "playbook": "ansible/playbooks/site.yaml",
        "limit": "node-3.example.com",
        "host_pattern": "node-3.example.com:!offline",
        "tags": None,
        "ansible_core": "2.22.0",
        "inventory_hash": "b" * 64,
        "status": PlanStatus.OK,
        "hosts": hosts,
    }
    return PlanContent(**(fields | changes))


def test_the_same_events_give_the_same_plan_id(tmp_path: Path) -> None:
    first, second = _content(tmp_path / "one"), _content(tmp_path / "two")

    assert plan_id(first) == plan_id(second)
    assert len(plan_id(first)) == 64


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"commit": "c" * 40}, id="commit"),
        pytest.param(
            {"limit": "node-4.example.com", "host_pattern": "node-4.example.com:!offline"},
            id="limit",
        ),
    ],
)
def test_another_commit_or_limit_gives_another_plan_id(
    tmp_path: Path, changes: dict[str, Any]
) -> None:
    assert plan_id(_content(tmp_path, **changes)) != plan_id(_content(tmp_path))


def test_the_events_read_in_counter_order_without_a_partial_file(tmp_path: Path) -> None:
    """ansible-runner renames each event file into place; a stopped run can leave the callback's
    `<uuid>-partial.json`."""
    events = recorded_events("agent", tmp_path)
    for event in reversed(events):
        name = f"{event['counter']}-{event['uuid']}.json"
        (tmp_path / name).write_text(json.dumps(event), encoding="utf-8")
    (tmp_path / f"{events[0]['uuid']}-partial.json").write_text("{}", encoding="utf-8")

    assert read_job_events(tmp_path) == events
