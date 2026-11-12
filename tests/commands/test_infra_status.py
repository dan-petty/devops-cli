"""`devops infra status`: the hosts of an infra repo with the state of their nodes, and the SSH
check of `--ping` (#5123).

The command layer owns the options, the access level of `--ping`, the dry run and the output
formats. The join of hosts and nodes and the read of the job events are the domain's
(`tests/infra/test_status.py`). The repo is the homelab-shaped fixture, read at the head of its
default branch (`answer_default_branch`), and the nodes come from the Kubernetes API's fake.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from tests.support.fakes.kubernetes import FakeCluster, node
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.infra import (
    KUBE_CONTEXT,
    ORIGIN_COMMIT,
    answer_default_branch,
    in_export,
    recorded_read,
)

REPO = "example-org/infra"
_RUNNER = "ansible-runner"


def _nodes() -> list[Any]:
    """node-1 to node-4 of the inventory, node-2 cordoned and node-3 not Ready, and node-9, which
    no inventory host names."""
    resources = {"memory": "16310540Ki", "nvidia.com/gpu": "1"}
    return [
        node(
            name,
            ready="False" if name == "node-3" else "True",
            unschedulable=name == "node-2",
            kernel="7.2.8" if name == "node-1" else "7.2.15",
            kubelet="v1.34.1+k3s1",
            capacity=resources,
            allocatable=resources,
        )
        for name in ("node-1", "node-2", "node-3", "node-4", "node-9")
    ]


@pytest.fixture
def ready(
    infra_repo: Path,
    ansible_installed: Path,
    cluster: FakeCluster,
    process_fake: ProcessFake,
    config: Callable[..., Path],
) -> Callable[..., Path]:
    """The repo at the head of origin/main with its inventory, the nodes in the kube context of
    the entry, and a way to write the entry at an agent access level."""
    cluster.context_names.append(KUBE_CONTEXT)
    cluster.core.answers["list_node"] = _nodes()
    answer_default_branch(process_fake, infra_repo)
    listing = json.dumps(recorded_read("inventory", infra_repo))
    process_fake.answer(
        [str(ansible_installed / "ansible-inventory")], in_export(listing, infra_repo)
    )

    def entry(level: str = "none", **options: Any) -> Path:
        fields = {"repo": REPO, "path": str(infra_repo), "kube_context": KUBE_CONTEXT}
        return config(infra={"repos": [fields | {"agent_access": level} | options]})

    entry()
    return entry


def _ran(process_fake: ProcessFake, program: str) -> bool:
    return any(call.argv[0].endswith(f"/{program}") for call in process_fake.calls)


def test_status_gives_one_row_for_each_host_and_node(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    process_fake: ProcessFake,
    person_caller: None,
) -> None:
    result = cli("infra", "status", REPO, "--format", "json")

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert (report["read"]["commit"], report["kube_context"]) == (ORIGIN_COMMIT, KUBE_CONTEXT)
    assert [
        (
            row["host"],
            row["in_service"],
            row["node"] and (row["node"]["ready"], row["node"]["cordoned"], row["node"]["kernel"]),
        )
        for row in report["rows"]
    ] == [
        ("node-1.example.com", True, ("True", False, "7.2.8")),
        ("node-2.example.com", True, ("True", True, "7.2.15")),
        ("node-3.example.com", True, ("False", False, "7.2.15")),
        ("node-4.example.com", True, ("True", False, "7.2.15")),
        ("node-5.example.com", False, None),
        ("node-6.example.com", False, None),
        (None, None, ("True", False, "7.2.15")),
    ]
    assert report["rows"][1]["node"]["memory_allocatable_bytes"] == 16310540 * 1024
    assert not _ran(process_fake, _RUNNER)


def test_the_table_names_the_commit_and_each_host(
    cli: Callable[..., Any], ready: Callable[..., Path], person_caller: None
) -> None:
    result = cli("infra", "status", REPO)

    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[:2] == [
        f"Hosts of {REPO} (kube context {KUBE_CONTEXT})",
        f"Reads origin/main at {ORIGIN_COMMIT}, not the working tree of the checkout.",
    ]
    assert "node-5.example.com" in result.output
    assert "15.6 / 15.6" in result.output


def test_ping_from_an_agent_on_a_repo_at_none_is_refused(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    cluster: FakeCluster,
    process_fake: ProcessFake,
    agent_caller: None,
) -> None:
    """The refusal comes before the Kubernetes API, git and SSH."""
    result = cli("infra", "status", REPO, "--ping")

    assert result.exit_code == 1
    assert "needs plan" in result.output
    assert "infra.repos[].agent_access" in result.output
    assert (process_fake.calls, cluster.core.calls) == ([], [])


def _runner_answer(call: ProcessCall) -> ProcessAnswer:
    """`ansible-runner run`: node-1 waits for a reboot, the other hosts in service do not."""
    argv = call.argv
    folder = Path(argv[argv.index("--artifact-dir") + 1]) / argv[argv.index("--ident") + 1]
    events = folder / "job_events"
    events.mkdir(parents=True)
    for number in range(1, 5):
        host = f"node-{number}.example.com"
        body = {
            "event": "runner_on_ok",
            "event_data": {"host": host, "res": {"stat": {"exists": number == 1}}},
        }
        (events / f"{number}-{host}.json").write_text(json.dumps(body), encoding="utf-8")
    return ProcessAnswer()


def test_ping_from_an_agent_at_plan_reads_each_host_in_service(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    ansible_installed: Path,
    process_fake: ProcessFake,
    agent_caller: None,
) -> None:
    ready("plan")
    process_fake.answer([str(ansible_installed / _RUNNER)], _runner_answer)

    result = cli("infra", "status", REPO, "--ping", "--format", "json")

    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)["rows"]
    assert [(row["host"], row["ping"]) for row in rows[:2]] == [
        ("node-1.example.com", {"state": "reachable", "reboot_required": True, "reason": None}),
        ("node-2.example.com", {"state": "reachable", "reboot_required": False, "reason": None}),
    ]
    assert [row["ping"] for row in rows[4:]] == [None, None, None]


def test_a_repo_with_no_kube_context_names_the_step(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    cluster: FakeCluster,
    person_caller: None,
) -> None:
    ready(kube_context=None)

    result = cli("infra", "status", REPO)

    assert result.exit_code == 1
    assert f"devops infra onboard {REPO} --kube-context <name> --confirm" in result.output
    assert cluster.core.calls == []


def test_dry_run_sends_no_request(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    cluster: FakeCluster,
    process_fake: ProcessFake,
    tmp_path: Path,
    agent_caller: None,
    snapshot: SnapshotAssertion,
) -> None:
    """An agent at level none may plan `--ping`: the plan reaches no host."""
    result = cli("infra", "status", REPO, "--ping", "--dry-run")

    assert result.exit_code == 0, result.output
    assert (process_fake.calls, cluster.core.calls) == ([], [])
    assert result.output.replace(str(tmp_path), "<tmp>") == snapshot
