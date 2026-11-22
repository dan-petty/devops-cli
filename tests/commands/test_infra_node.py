"""`devops infra node drain|uncordon|restart|reboot`: one node at a time (#5128).

The repo is the homelab-shaped fixture at the head of its default branch. A fake `kubectl` answers
from the nodes node-1 to node-4 (`FakeCluster`), and a fake ad-hoc `ansible-runner` answers the
tasks on their hosts (`FakeHosts`). Both write each step in one list, with each read of the nodes.
The `clock` fixture makes each wait return at once.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from devops_cli.telemetry.instruments import INFRA_RUNS_TOTAL
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.process import ProcessCall, ProcessFake
from tests.support.infra import (
    KUBE_CONTEXT,
    ORIGIN_COMMIT,
    FakeCluster,
    FakeHosts,
    FakeNode,
    ad_hoc_option,
    ad_hoc_words,
    answer_default_branch,
    in_export,
    is_ad_hoc,
    recorded_read,
)

REPO = "example-org/infra"
NODE_3 = "node-3.example.com"
NODE_4 = "node-4.example.com"
_SERVICE = "devops_infra_node_service"
_TEMPLATE = "{{ 'k3s' if node_role == 'server' else 'k3s-agent' }}"
_HEALTH_AFTER = ["get nodes", "get nodes"]


class Lab:
    """The repo, its entry, the cluster and the hosts of one test."""

    def __init__(
        self,
        cli: Callable[..., Any],
        process_fake: ProcessFake,
        write_entry: Callable[..., Path],
        cluster: FakeCluster,
        hosts: FakeHosts,
        infra_repo: Path,
        bin_dir: Path,
    ) -> None:
        self.cli = cli
        self.process_fake = process_fake
        self.write_entry = write_entry
        self.cluster = cluster
        self.hosts = hosts
        self.infra_repo = infra_repo
        self.bin_dir = bin_dir

    @property
    def steps(self) -> list[str]:
        return self.cluster.steps

    def node(self, operation: str, *hosts: str, level: str = "full") -> Any:
        """Run `devops infra node <operation>` on `hosts` with JSON output."""
        self.write_entry(level)
        return self.cli("infra", "node", operation, REPO, *hosts, "-f", "json")

    def host_vars(self, host: str, change: Callable[[dict[str, Any]], None]) -> None:
        """Answer the inventory read with the host variables of `host` changed by `change`."""
        listing = recorded_read("inventory", self.infra_repo)
        change(listing["_meta"]["hostvars"][host])
        self.process_fake.answer(
            [str(self.bin_dir / "ansible-inventory")],
            in_export(json.dumps(listing), self.infra_repo),
        )

    def kubectl_calls(self) -> list[tuple[str, ...]]:
        """The words of each kubectl call after the context and the request bound."""
        return [call.argv[4:] for call in self.process_fake.calls if call.argv[0] == "kubectl"]

    def ad_hoc_calls(self) -> list[ProcessCall]:
        return [call for call in self.process_fake.calls if is_ad_hoc(call)]


@pytest.fixture
def lab(
    cli: Callable[..., Any],
    infra_repo: Path,
    ansible_installed: Path,
    ssh_key_dir: Path,
    process_fake: ProcessFake,
    config: Callable[..., Path],
    clock: ClockFake,
) -> Lab:
    """The repo at the head of origin/main with its inventory, the key of `devops ssh`, the nodes
    node-1 to node-4 in the kube context with their hosts, and a way to write the entry at an
    agent access level."""
    answer_default_branch(process_fake, infra_repo)
    listing = json.dumps(recorded_read("inventory", infra_repo))
    process_fake.answer(
        [str(ansible_installed / "ansible-inventory")], in_export(listing, infra_repo)
    )
    process_fake.answer(
        [str(ansible_installed / "ansible-config")],
        in_export(json.dumps(recorded_read("config", infra_repo)), infra_repo),
    )
    cluster = FakeCluster.of(*(FakeNode(f"node-{n}") for n in range(1, 5)))
    cluster.reads = True
    cluster.install(process_fake)
    hosts = FakeHosts(cluster)
    hosts.install(process_fake)

    def entry(level: str, **infra: Any) -> Path:
        fields = {
            "repo": REPO,
            "path": str(infra_repo),
            "kube_context": KUBE_CONTEXT,
            "agent_access": level,
        }
        return config(infra={"repos": [fields], **infra}, ssh={"key_dir": str(ssh_key_dir)})

    entry("full")
    return Lab(cli, process_fake, entry, cluster, hosts, infra_repo, ansible_installed)


def _report(result: Any) -> dict[str, Any]:
    return dict(json.loads(result.output))


def _drains(lab: Lab) -> list[tuple[str, ...]]:
    return [words for words in lab.kubectl_calls() if words[0] == "drain"]


def _audit_records() -> list[dict[str, Any]]:
    from devops_cli.config.settings import load_settings
    from devops_cli.core.repo import resolve_data_path

    log = resolve_data_path(load_settings().data.audit_log_path)
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def test_drain_checks_before_it_cordons(lab: Lab, person_caller: None) -> None:
    result = lab.node("drain", NODE_3)

    assert result.exit_code == 0, result.output
    assert lab.steps == [
        "get nodes",
        "get node node-3",
        "drain check node-3",
        "drain node-3",
        "get node node-3",
    ]
    assert _drains(lab)[-1] == (
        "drain",
        "node-3",
        "--ignore-daemonsets",
        "--delete-emptydir-data",
        "--timeout=180s",
    )
    assert lab.cluster.nodes["node-3"].cordoned
    report = _report(result)
    assert (report["operation"], report["result"], report["commit"]) == (
        "drain",
        "ok",
        ORIGIN_COMMIT,
    )
    [host] = report["hosts"]
    assert (host["host"], host["node"], host["outcome"]) == (NODE_3, "node-3", "done")
    assert (host["before"]["cordoned"], host["after"]["cordoned"]) == (False, True)


def test_a_long_grace_period_extends_the_bound(lab: Lab, person_caller: None) -> None:
    lab.cluster.graces["node-3"] = 900

    result = lab.node("drain", NODE_3)

    assert result.exit_code == 0, result.output
    assert _drains(lab)[-1][-1] == "--timeout=960s"


def test_force_goes_to_the_drain_only_when_a_person_gives_it(lab: Lab, person_caller: None) -> None:
    first = lab.node("drain", NODE_3)
    lab.cluster.nodes["node-3"].cordoned = False
    calls = len(_drains(lab))
    lab.write_entry("full")

    second = lab.cli("infra", "node", "drain", REPO, NODE_3, "--force", "-f", "json")

    assert (first.exit_code, second.exit_code) == (0, 0), second.output
    assert not any("--force" in words for words in _drains(lab)[:calls])
    assert all("--force" in words for words in _drains(lab)[calls:])
    assert len(_drains(lab)[calls:]) == 2
    assert _report(second)["force"] is True


def test_an_agent_that_gives_force_is_refused(lab: Lab, agent_caller: None) -> None:
    calls = len(lab.process_fake.calls)

    result = lab.cli("infra", "node", "drain", REPO, NODE_3, "--force")

    assert result.exit_code == 1
    assert "Only a person gives --force" in result.output
    assert len(lab.process_fake.calls) == calls
    [record] = _audit_records()
    assert (record["command"], record["status"]) == ("infra.node.drain", "refused")


def test_a_host_that_the_inventory_does_not_have_is_refused(lab: Lab, person_caller: None) -> None:
    result = lab.cli("infra", "node", "drain", REPO, "node-9.example.com")

    assert result.exit_code == 1
    assert "node-9.example.com is not a host of the inventory" in result.output
    assert lab.kubectl_calls() == []


def test_a_host_out_of_service_is_refused(lab: Lab, person_caller: None) -> None:
    result = lab.cli("infra", "node", "reboot", REPO, "node-5.example.com")

    assert result.exit_code == 1
    assert "node-5.example.com is in the group offline" in result.output
    assert lab.kubectl_calls() == []
    assert lab.ad_hoc_calls() == []


def test_uncordon_comes_before_the_health_gate(lab: Lab, person_caller: None) -> None:
    lab.cluster.nodes["node-3"].cordoned = True

    result = lab.node("uncordon", NODE_3)

    assert result.exit_code == 0, result.output
    assert lab.steps == ["get node node-3", "uncordon node-3", *_HEALTH_AFTER, "get node node-3"]
    assert not lab.cluster.nodes["node-3"].cordoned


def test_restart_follows_the_drain(lab: Lab, person_caller: None) -> None:
    result = lab.node("restart", NODE_3)

    assert result.exit_code == 0, result.output
    assert lab.steps == [
        "get nodes",
        "get node node-3",
        "drain check node-3",
        "drain node-3",
        f"restart {NODE_3} k3s-agent",
        "get node node-3",
        "get node node-3",
        "uncordon node-3",
        *_HEALTH_AFTER,
        "get node node-3",
    ]
    [call] = lab.ad_hoc_calls()
    assert (ad_hoc_option(call, "--hosts"), ad_hoc_option(call, "-m")) == (
        NODE_3,
        "ansible.builtin.systemd_service",
    )
    assert ad_hoc_option(call, "-a") == "name=k3s-agent state=restarted"
    assert "--become" in ad_hoc_words(call)
    [host] = _report(result)["hosts"]
    assert (host["unit"], host["after"]["cordoned"]) == ("k3s-agent", False)


def test_a_template_unit_is_rendered_before_the_drain(lab: Lab, person_caller: None) -> None:
    lab.host_vars(NODE_3, lambda variables: variables.update({_SERVICE: _TEMPLATE}))
    lab.hosts.units[NODE_3] = "k3s-agent.service"

    result = lab.node("restart", NODE_3)

    assert result.exit_code == 0, result.output
    assert lab.steps[:2] == [f"render {NODE_3}", "get nodes"]
    assert f"restart {NODE_3} k3s-agent.service" in lab.steps
    render = lab.ad_hoc_calls()[0]
    assert (ad_hoc_option(render, "-m"), ad_hoc_option(render, "-a")) == (
        "ansible.builtin.debug",
        "msg={{ devops_infra_node_service }}",
    )
    assert "--become" not in ad_hoc_words(render)


def test_a_cordoned_node_stays_cordoned(lab: Lab, person_caller: None) -> None:
    lab.cluster.nodes["node-3"].cordoned = True

    result = lab.node("restart", NODE_3)

    assert result.exit_code == 0, result.output
    assert not any(step.startswith("uncordon") for step in lab.steps)
    assert lab.cluster.nodes["node-3"].cordoned


def test_a_restart_needs_a_unit(lab: Lab, person_caller: None) -> None:
    lab.host_vars(NODE_3, lambda variables: variables.pop(_SERVICE))

    result = lab.cli("infra", "node", "restart", REPO, NODE_3)

    assert result.exit_code == 1
    assert _SERVICE in result.output
    assert lab.kubectl_calls() == []
    assert lab.ad_hoc_calls() == []


def test_a_unit_that_is_not_a_unit_name_is_refused(lab: Lab, person_caller: None) -> None:
    lab.host_vars(NODE_3, lambda variables: variables.update({_SERVICE: "k3s state=stopped"}))

    result = lab.cli("infra", "node", "restart", REPO, NODE_3)

    assert result.exit_code == 1
    assert "not a systemd unit name" in result.output
    assert lab.kubectl_calls() == []


def test_reboot_shows_both_kernels(lab: Lab, person_caller: None) -> None:
    lab.write_entry("full")

    result = lab.cli("infra", "node", "reboot", REPO, NODE_3)

    assert result.exit_code == 0, result.output
    assert "6.12.0 -> 6.12.1" in result.output
    assert "Audit record infra.node.reboot" in result.output
    uncordon = lab.steps.index("uncordon node-3")
    assert lab.steps[uncordon - 3 : uncordon + 3] == [
        f"reboot {NODE_3}",
        "get node node-3",
        "get node node-3",
        "uncordon node-3",
        *_HEALTH_AFTER,
    ]
    [call] = lab.ad_hoc_calls()
    assert (ad_hoc_option(call, "-m"), ad_hoc_option(call, "-a")) == (
        "ansible.builtin.reboot",
        "reboot_timeout=600",
    )
    assert "--become" in ad_hoc_words(call)


def test_the_second_host_waits_for_the_first(lab: Lab, person_caller: None) -> None:
    lab.cluster.blocked.add("node-3")

    result = lab.node("drain", NODE_3, NODE_4)

    assert result.exit_code == 1
    report = _report(result)
    assert report["result"] == "refused"
    assert [host["outcome"] for host in report["hosts"]] == ["stopped", "not run"]
    assert not any("node-4" in " ".join(words) for words in lab.kubectl_calls())


def test_a_failed_ready_wait_keeps_the_cordon(lab: Lab, person_caller: None) -> None:
    lab.write_entry("full", node_ready_timeout_seconds=60)
    lab.hosts.not_ready.add("node-3")

    result = lab.cli("infra", "node", "restart", REPO, NODE_3, NODE_4, "-f", "json")

    assert result.exit_code == 1
    report = _report(result)
    assert report["result"] == "stopped"
    first, second = report["hosts"]
    assert (first["outcome"], first["step"]) == ("stopped", "ready")
    assert "node-3 is not Ready (False)" in first["reason"]
    assert second["outcome"] == "not run"
    assert not any(step.startswith("uncordon") for step in lab.steps)
    assert lab.cluster.nodes["node-3"].cordoned
    assert not any("node-4" in step for step in lab.steps)


def test_a_failed_reboot_stops_with_the_message_of_its_task(lab: Lab, person_caller: None) -> None:
    lab.hosts.failed[NODE_3] = "Reboot command failed. Error was: sudo: a password is required"

    result = lab.node("reboot", NODE_3)

    assert result.exit_code == 1
    [host] = _report(result)["hosts"]
    assert (host["step"], host["after"]["cordoned"]) == ("reboot", True)
    assert "sudo: a password is required" in host["reason"]


@pytest.mark.parametrize(
    ("operation", "refused"),
    [("uncordon", False), ("drain", True), ("restart", True), ("reboot", True)],
)
def test_the_safe_level_allows_only_the_uncordon(
    lab: Lab, agent_caller: None, operation: str, refused: bool
) -> None:
    lab.cluster.nodes["node-3"].cordoned = True
    calls = len(lab.process_fake.calls)

    result = lab.node(operation, NODE_3, level="safe")

    if refused:
        assert result.exit_code == 1
        assert f"devops infra node {operation}" in result.output
        assert "needs full" in result.output
        assert "infra.repos[].agent_access" in result.output
        assert len(lab.process_fake.calls) == calls
    else:
        assert result.exit_code == 0, result.output
        assert "uncordon node-3" in lab.steps
        assert (_report(result)["caller"], _report(result)["tool"]) == ("agent", "claude_code")


def test_a_person_drains_at_the_level_none(lab: Lab, person_caller: None) -> None:
    result = lab.node("drain", NODE_3, level="none")

    assert result.exit_code == 0, result.output
    assert _report(result)["caller"] == "person"


def test_an_agent_restart_with_host_key_checks_off_is_refused(lab: Lab, agent_caller: None) -> None:
    lab.host_vars(
        NODE_3,
        lambda variables: variables.update(ansible_ssh_common_args="-o StrictHostKeyChecking=no"),
    )

    result = lab.cli("infra", "node", "restart", REPO, NODE_3)

    assert result.exit_code == 1
    assert "needs host key checks on" in result.output
    assert lab.kubectl_calls() == []


def test_one_record_and_one_count_for_each_run(
    lab: Lab, person_caller: None, otlp: FakeCollector
) -> None:
    done = lab.node("drain", NODE_3)
    lab.cluster.blocked.add("node-4")
    lab.cluster.nodes["node-3"].cordoned = False

    stopped = lab.node("drain", NODE_3, NODE_4)

    assert (done.exit_code, stopped.exit_code) == (0, 1)
    records = _audit_records()
    assert [(r["command"], r["status"]) for r in records] == [
        ("infra.node.drain", "ok"),
        ("infra.node.drain", "stopped"),
    ]
    details = records[-1]["details"]
    assert set(details) == {
        "id",
        "operation",
        "caller",
        "tool",
        "level",
        "repo",
        "commit",
        "ref",
        "requested",
        "force",
        "result",
        "reason",
        "hosts",
        "left_out_alerts",
        "duration_seconds",
    }
    assert (details["operation"], details["caller"], details["level"]) == (
        "drain",
        "person",
        "full",
    )
    assert details["requested"] == [NODE_3, NODE_4]
    assert [(h["host"], h["outcome"], h["step"]) for h in details["hosts"]] == [
        (NODE_3, "done", None),
        (NODE_4, "stopped", "drain check"),
    ]
    assert details["hosts"][0]["cordoned_before"] is False
    assert details["hosts"][0]["kernel_after"] == "6.12.0"
    points = otlp.points(INFRA_RUNS_TOTAL.name)
    assert sorted((attributes["result"], value) for attributes, value in points) == [
        ("ok", 1.0),
        ("stopped", 1.0),
    ]
    assert {(attributes["repo"], attributes["command"]) for attributes, _ in points} == {
        (REPO, "node drain")
    }


@pytest.mark.parametrize("operation", ["drain", "uncordon", "restart", "reboot"])
def test_dry_run_starts_no_process(
    lab: Lab,
    tmp_path: Path,
    agent_caller: None,
    operation: str,
    snapshot: SnapshotAssertion,
) -> None:
    """An agent at level none may run a dry run: it reaches no host."""
    lab.write_entry("none")
    calls = len(lab.process_fake.calls)

    result = lab.cli("infra", "node", operation, REPO, NODE_3, NODE_4, "--dry-run")

    assert result.exit_code == 0, result.output
    assert len(lab.process_fake.calls) == calls
    shown = result.output.replace(str(tmp_path), "<tmp>")
    assert shown == snapshot


def test_infra_help_gives_the_node_group_its_help(cli: Callable[..., Any]) -> None:
    """`devops infra --help` lists the node group with the first words of its help (#5128)."""
    result = cli("infra", "--help")

    assert result.exit_code == 0, result.output
    rows = [line for line in result.output.splitlines() if line.lstrip("│ ").startswith("node ")]
    assert rows, result.output
    assert "Drain, uncordon" in rows[0], rows[0]
