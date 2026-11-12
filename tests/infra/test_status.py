"""The hosts of an infra repo joined with the state of their Kubernetes nodes, and the SSH check of
`--ping` (#5123).

The inventory is the recorded listing of `tests/fixtures/infra/homelab_shape/`: four hosts in
service, `node-1` to `node-4.example.com`, and two in the group `offline`. The nodes are the SDK's
models (`tests/support/fakes/kubernetes.py`). The SSH check runs `ansible-runner`, which the
process fake answers with the job events that the real run writes.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from devops_cli.infra.ansible_facts import AnsibleTool, parse_inventory
from devops_cli.infra.status import (
    host_statuses,
    node_state,
    ping_hosts,
    status_caption,
    status_table,
)
from devops_cli.models.infra import HostPing, NodeState, PingState, ReadCommit, StatusReport
from tests.support.fakes.kubernetes import node
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.infra import recorded_read

GIB = 1024**3
OFFLINE = "offline"
_SOURCES = ("ansible/inventory/hosts.yaml",)


def _node(name: str, **options: Any) -> NodeState:
    """The state of a node with 16 GiB, one GPU, kernel 7.2.15 and the given options."""
    options.setdefault("kernel", "7.2.15")
    return node_state(
        node(
            name,
            kubelet="v1.34.1+k3s1",
            capacity={"memory": "16Gi", "nvidia.com/gpu": "1"},
            allocatable={"memory": "16Gi", "nvidia.com/gpu": "1"},
            **options,
        )
    )


def _inventory(root: Path, **hostvars: dict[str, Any]) -> Any:
    listing = recorded_read("inventory", root)
    for host, variables in hostvars.items():
        listing["_meta"]["hostvars"][host].update(variables)
    return parse_inventory(listing)


def test_a_node_gives_its_state() -> None:
    state = node_state(
        node(
            "node-1",
            unschedulable=True,
            kernel="7.2.8",
            kubelet="v1.34.1+k3s1",
            capacity={"memory": "16310540Ki", "nvidia.com/gpu": "2", "cpu": "8"},
            allocatable={"memory": "15000Mi", "nvidia.com/gpu": "2", "cpu": "8"},
        )
    )

    assert state == NodeState(
        name="node-1",
        ready="True",
        cordoned=True,
        kernel="7.2.8",
        kubelet="v1.34.1+k3s1",
        memory_capacity_bytes=16310540 * 1024,
        memory_allocatable_bytes=15000 * 1024**2,
        gpu_allocatable=2,
    )


def test_a_node_with_no_status_gives_unknown() -> None:
    bare = node("node-1")
    bare.status.conditions = None

    assert node_state(bare) == NodeState(name="node-1", ready="Unknown", cordoned=False)


def test_each_host_gets_its_node_and_a_node_with_no_host_comes_last(tmp_path: Path) -> None:
    """A cordoned node, a node that is not Ready, two hosts in `offline` with no node, and a node
    that no inventory host names."""
    nodes = [
        _node("node-9"),
        _node("node-3", ready="False"),
        _node("node-2", unschedulable=True),
        _node("node-1"),
        _node("node-4"),
    ]

    rows = host_statuses(_inventory(tmp_path), OFFLINE, nodes)

    assert [
        (row.host, row.in_service, row.node_name, row.node and row.node.ready) for row in rows
    ] == [
        ("node-1.example.com", True, "node-1", "True"),
        ("node-2.example.com", True, "node-2", "True"),
        ("node-3.example.com", True, "node-3", "False"),
        ("node-4.example.com", True, "node-4", "True"),
        ("node-5.example.com", False, "node-5", None),
        ("node-6.example.com", False, "node-6", None),
        (None, None, "node-9", "True"),
    ]
    assert rows[1].node is not None
    assert rows[1].node.cordoned
    assert rows[0].groups == ("debian_nodes", "gpu_nodes", "k3s_cluster", "k3s_server")


def test_the_node_name_comes_from_the_host_variable(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, **{"node-4.example.com": {"devops_infra_node_name": "gpu-4"}})

    rows = host_statuses(inventory, OFFLINE, [_node("gpu-4")])

    assert [(row.host, row.node_name, row.node is not None) for row in rows[2:4]] == [
        ("node-3.example.com", "node-3", False),
        ("node-4.example.com", "gpu-4", True),
    ]


def test_a_templated_node_name_is_not_rendered(tmp_path: Path) -> None:
    """Only Ansible renders a template; the default name stands in for it."""
    inventory = _inventory(
        tmp_path, **{"node-1.example.com": {"devops_infra_node_name": "{{ inventory_hostname }}"}}
    )

    assert host_statuses(inventory, OFFLINE, [])[0].node_name == "node-1"


def test_the_table_shows_memory_in_gib_and_the_ping_columns(tmp_path: Path) -> None:
    rows = host_statuses(_inventory(tmp_path), OFFLINE, [_node("node-2", unschedulable=True)])
    pinged = rows[1].model_copy(
        update={"ping": HostPing(state=PingState.REACHABLE, reboot_required=True)}
    )
    read = ReadCommit(
        ref="origin/main", commit="a" * 40, checkout_branch="main", checkout_commit="a" * 40
    )
    report = StatusReport(
        repo="example-org/infra",
        path=str(tmp_path),
        read=read,
        kube_context="ctx",
        rows=(rows[0], pinged),
    )

    columns, cells = status_table(report, ping=True)

    assert columns[-2:] == ["SSH", "Reboot"]
    assert cells == [
        ["node-1.example.com", "yes", "node-1", "no node", "", "", "", "", "", "", ""],
        [
            "node-2.example.com",
            "yes",
            "node-2",
            "True",
            "yes",
            "7.2.15",
            "v1.34.1+k3s1",
            "16.0 / 16.0",
            "1",
            "reachable",
            "yes",
        ],
    ]


@pytest.mark.parametrize(
    ("ping", "caption"),
    [
        (False, "Memory GiB: capacity / allocatable. GPU: allocatable."),
        (
            True,
            "Memory GiB: capacity / allocatable. GPU: allocatable. "
            "Reboot: /run/reboot-required exists.",
        ),
    ],
)
def test_the_caption_says_what_the_columns_hold(ping: bool, caption: str) -> None:
    assert status_caption(ping=ping) == caption


# --ping: one ansible-runner ad-hoc run of `stat /run/reboot-required` on the hosts in service.


def _option(argv: tuple[str, ...], name: str) -> str:
    return argv[argv.index(name) + 1]


def _runner(
    events: Mapping[str, tuple[str, dict[str, Any]]], returncode: int = 0
) -> Callable[[ProcessCall], ProcessAnswer]:
    """An answer of `ansible-runner run` that writes one job event for each host of `events`:
    `(event, res)`."""

    def answer(call: ProcessCall) -> ProcessAnswer:
        folder = Path(_option(call.argv, "--artifact-dir")) / _option(call.argv, "--ident")
        job_events = folder / "job_events"
        job_events.mkdir(parents=True)
        for number, (host, (event, res)) in enumerate(events.items(), start=1):
            body = {"event": event, "counter": number, "event_data": {"host": host, "res": res}}
            (job_events / f"{number}-{host}.json").write_text(json.dumps(body), encoding="utf-8")
        return ProcessAnswer(returncode=returncode)

    return answer


@pytest.fixture
def tool(tmp_path: Path) -> AnsibleTool:
    return AnsibleTool(bin_dir=tmp_path / "bin", installed=True, version="2.22.0")


def test_ping_reads_each_host_in_service(
    tmp_path: Path, tool: AnsibleTool, process_fake: ProcessFake
) -> None:
    process_fake.answer(
        [str(tool.bin_dir / "ansible-runner")],
        _runner(
            {
                "node-1.example.com": ("runner_on_ok", {"stat": {"exists": False}}),
                "node-2.example.com": ("runner_on_ok", {"stat": {"exists": True}}),
                "node-3.example.com": (
                    "runner_on_unreachable",
                    {"unreachable": True, "msg": "Failed to connect to the host via ssh"},
                ),
                "node-4.example.com": ("runner_on_failed", {"msg": "No python interpreter"}),
            },
            returncode=4,
        ),
    )
    key = tmp_path / "ssh" / "ansible-id_ed25519"

    pings = ping_hosts(tool, tmp_path, _SOURCES, OFFLINE, key)

    assert pings == {
        "node-1.example.com": HostPing(state=PingState.REACHABLE, reboot_required=False),
        "node-2.example.com": HostPing(state=PingState.REACHABLE, reboot_required=True),
        "node-3.example.com": HostPing(
            state=PingState.UNREACHABLE, reason="Failed to connect to the host via ssh"
        ),
        "node-4.example.com": HostPing(state=PingState.FAILED, reason="No python interpreter"),
    }
    [call] = process_fake.calls
    assert call.argv[1:3] == ("run", str(tmp_path))
    assert _option(call.argv, "--hosts") == "all"
    assert _option(call.argv, "--limit") == f"!{OFFLINE}"
    assert (_option(call.argv, "-m"), _option(call.argv, "-a")) == (
        "ansible.builtin.stat",
        "path=/run/reboot-required",
    )
    assert (
        f"--cmdline=-i {_SOURCES[0]} -T 10 -e ansible_become=false -e ansible_ssh_private_key_file={key}"
        in call.argv
    )
    assert call.env is not None
    assert call.env["ANSIBLE_HOST_KEY_CHECKING"] == "True"
    assert call.env["PATH"].split(":")[0] == str(tool.bin_dir)
    assert not Path(_option(call.argv, "--artifact-dir")).exists()


def test_a_host_with_no_event_has_no_answer(
    tmp_path: Path, tool: AnsibleTool, process_fake: ProcessFake
) -> None:
    process_fake.answer(
        [str(tool.bin_dir / "ansible-runner")],
        _runner({"node-1.example.com": ("runner_on_ok", {"stat": {"exists": False}})}),
    )

    pings = ping_hosts(tool, tmp_path, _SOURCES, OFFLINE, None)

    assert pings["node-1.example.com"].state is PingState.REACHABLE
    assert set(pings) == {"node-1.example.com"}
    [call] = process_fake.calls
    assert "ansible_ssh_private_key_file" not in " ".join(call.argv)
