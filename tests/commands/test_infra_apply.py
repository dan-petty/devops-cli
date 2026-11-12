"""`devops infra apply`: the apply of a saved plan, one disruptive node at a time (#5125).

Each test plans first with `devops infra plan`, so the apply reads a real plan record. The repo is
the homelab-shaped fixture at the head of its default branch. `ansible-runner` writes the recorded
events of the run `site` of the hosts of each limit (`answer_runs`), and a fake `kubectl` answers
from a set of nodes (`FakeCluster`). Both write each step in one list. The `clock` fixture makes
each wait return at once.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from tests.support.fakes.clock import ClockFake
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.infra import (
    KUBE_CONTEXT,
    ORIGIN_COMMIT,
    SSH_KEY_NAME,
    FakeCluster,
    FakeNode,
    answer_default_branch,
    answer_runs,
    git_command,
    in_export,
    is_check_run,
    limit_hosts,
    recorded_read,
    site_events,
)

REPO = "example-org/infra"
PLAYBOOK = "ansible/playbooks/03_k3s.yaml"
NODE_1 = "node-1.example.com"
NODE_2 = "node-2.example.com"
NODE_3 = "node-3.example.com"
NODE_4 = "node-4.example.com"
_PR_COMMIT = "0123456789abcdef0123456789abcdef01234567"


class Lab:
    """The repo, its entry, the runs and the cluster of one test."""

    def __init__(
        self,
        cli: Callable[..., Any],
        process_fake: ProcessFake,
        write_entry: Callable[[str], Path],
        cluster: FakeCluster,
        steps: list[str],
        bin_dir: Path,
    ) -> None:
        self.cli = cli
        self.process_fake = process_fake
        self.write_entry = write_entry
        self.cluster = cluster
        self.steps = steps
        self.bin_dir = bin_dir

    def plan(self, limit: str, *extra: str) -> dict[str, Any]:
        """Plan the playbook on `limit` at the level full, and give the plan record."""
        self.write_entry("full")
        result = self.cli("infra", "plan", REPO, PLAYBOOK, "--limit", limit, *extra, "-f", "json")
        assert result.exit_code == 0, result.output
        self.steps.clear()
        return dict(json.loads(result.output))

    def apply(self, plan: dict[str, Any], *extra: str, level: str = "full") -> Any:
        self.write_entry(level)
        limit = ("--limit", plan["limit"]) if plan["limit"] else ()
        return self.cli(
            "infra", "apply", REPO, PLAYBOOK, "--plan", plan["id"], *limit, *extra, "--auto-approve"
        )

    def apply_json(self, plan: dict[str, Any], *extra: str, level: str = "full") -> Any:
        return self.apply(plan, *extra, "-f", "json", level=level)

    def runs(self, events: Callable[[ProcessCall, Path], list[dict[str, Any]]]) -> None:
        """Answer the next runs with `events`."""
        answer_runs(self.process_fake, self.bin_dir, events=events, steps=self.steps)


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
    """The repo at the head of origin/main with its inventory, the key of `devops ssh`, nodes
    node-1 to node-4 in the kube context, and a way to write the entry at an agent access
    level."""
    answer_default_branch(process_fake, infra_repo)
    listing = json.dumps(recorded_read("inventory", infra_repo))
    process_fake.answer(
        [str(ansible_installed / "ansible-inventory")], in_export(listing, infra_repo)
    )
    process_fake.answer([str(ansible_installed / "ansible-galaxy")], ProcessAnswer())
    process_fake.answer(
        [str(ansible_installed / "ansible-config")],
        in_export(json.dumps(recorded_read("config", infra_repo)), infra_repo),
    )
    steps: list[str] = []
    cluster = FakeCluster.of(*(FakeNode(f"node-{n}") for n in range(1, 5)))
    cluster.steps = steps
    cluster.install(process_fake)
    answer_runs(process_fake, ansible_installed, steps=steps)

    def entry(level: str) -> Path:
        fields = {
            "repo": REPO,
            "path": str(infra_repo),
            "kube_context": KUBE_CONTEXT,
            "agent_access": level,
        }
        return config(infra={"repos": [fields]}, ssh={"key_dir": str(ssh_key_dir)})

    entry("full")
    return Lab(cli, process_fake, entry, cluster, steps, ansible_installed)


def _hosts(result: Any) -> dict[str, dict[str, Any]]:
    report = json.loads(result.output)
    return {host["host"]: host for host in report["hosts"]}


def test_each_disruptive_host_drains_runs_and_uncordons_alone_in_plan_order(
    lab: Lab, person_caller: None
) -> None:
    plan = lab.plan(f"{NODE_2},{NODE_1}")

    result = lab.apply_json(plan)

    assert result.exit_code == 0, result.output
    assert lab.steps == [
        "drain check node-1",
        "drain node-1",
        f"check {NODE_1}",
        f"run {NODE_1}",
        "uncordon node-1",
        "drain check node-2",
        "drain node-2",
        f"check {NODE_2}",
        f"run {NODE_2}",
        "uncordon node-2",
    ]
    report = json.loads(result.output)
    assert (report["result"], report["commit"], report["caller"], report["level"]) == (
        "ok",
        ORIGIN_COMMIT,
        "person",
        "full",
    )
    hosts = _hosts(result)
    assert [hosts[h]["outcome"] for h in (NODE_1, NODE_2)] == ["applied", "applied"]
    assert hosts[NODE_2]["disruptive"] == ["reboot"]
    assert len(hosts[NODE_1]["runner_idents"]) == 2
    assert not any(node.cordoned for node in lab.cluster.nodes.values())
    assert not (Path(report["folder"]) / "project").exists()


def test_a_node_that_was_cordoned_before_stays_cordoned(lab: Lab, person_caller: None) -> None:
    lab.cluster.nodes["node-3"].cordoned = True
    plan = lab.plan(NODE_3)

    result = lab.apply_json(plan)

    assert result.exit_code == 0, result.output
    assert lab.steps == ["drain check node-3", "drain node-3", f"check {NODE_3}", f"run {NODE_3}"]
    host = _hosts(result)[NODE_3]
    assert (host["before"]["cordoned"], host["after"]["cordoned"]) == (True, True)
    assert lab.cluster.nodes["node-3"].cordoned


def test_the_hosts_with_no_disruptive_class_run_together_with_no_drain(
    lab: Lab, person_caller: None
) -> None:
    plan = lab.plan(f"{NODE_4},{NODE_3}")

    result = lab.apply_json(plan)

    assert result.exit_code == 0, result.output
    assert lab.steps[0] == f"run {NODE_4}"
    assert lab.steps[1:3] == ["drain check node-3", "drain node-3"]
    assert "drain node-4" not in lab.steps


def test_a_fresh_check_that_differs_stops_before_the_run_of_the_host(
    lab: Lab, person_caller: None
) -> None:
    plan = lab.plan(NODE_3)

    def fewer_changes(call: ProcessCall, project: Path) -> list[dict[str, Any]]:
        events = site_events(project, limit_hosts(call))
        dropped = "Deploy K3s agent configuration file"
        return [e for e in events if (e.get("event_data") or {}).get("task") != dropped]

    lab.runs(fewer_changes)

    result = lab.apply(plan)

    assert result.exit_code == 1
    assert lab.steps == ["drain check node-3", "drain node-3", f"check {NODE_3}"]
    assert f"{NODE_3} stopped at the step fresh check" in result.output
    assert "changed tasks: the plan has Deploy K3s agent configuration file" in result.output
    assert lab.cluster.nodes["node-3"].cordoned


def test_a_task_that_changed_and_is_not_in_the_plan_stops_the_apply(
    lab: Lab, person_caller: None
) -> None:
    plan = lab.plan(f"{NODE_3},{NODE_1}")

    def one_more_change(call: ProcessCall, project: Path) -> list[dict[str, Any]]:
        events = site_events(project, limit_hosts(call))
        if is_check_run(call):
            return events
        for event in events:
            data = event.get("event_data") or {}
            if (
                event["event"] == "runner_on_ok"
                and data["task"] == "Check if K3s agent binary exists"
            ):
                data["res"]["changed"] = True
        return events

    lab.runs(one_more_change)

    result = lab.apply_json(plan)

    assert result.exit_code == 1
    hosts = _hosts(result)
    assert (hosts[NODE_1]["outcome"], hosts[NODE_3]["outcome"]) == ("applied", "stopped")
    assert hosts[NODE_3]["step"] == "run"
    assert [task["name"] for task in hosts[NODE_3]["unplanned"]] == [
        "Check if K3s agent binary exists"
    ]
    assert "uncordon node-3" not in lab.steps
    assert lab.cluster.nodes["node-3"].cordoned


def test_a_health_failure_after_a_host_stops_the_apply_and_leaves_the_node_cordoned(
    lab: Lab, person_caller: None
) -> None:
    plan = lab.plan(f"{NODE_1},{NODE_2}")

    def after(call: ProcessCall) -> None:
        if not is_check_run(call):
            lab.cluster.nodes["node-4"].ready = "False"

    answer_runs(lab.process_fake, lab.bin_dir, steps=lab.steps, after=after)

    result = lab.apply_json(plan)

    assert result.exit_code == 1
    hosts = _hosts(result)
    assert (hosts[NODE_1]["outcome"], hosts[NODE_1]["step"]) == ("stopped", "health")
    assert "node-4 is not Ready (False)" in hosts[NODE_1]["reason"]
    assert hosts[NODE_2]["outcome"] == "not run"
    assert "uncordon node-1" not in lab.steps
    assert "drain node-2" not in lab.steps
    assert lab.cluster.nodes["node-1"].cordoned


def test_the_waits_go_on_through_a_restart_of_the_api_server(lab: Lab, person_caller: None) -> None:
    """node-1 is the control plane: the API server is down for a short time after its run."""
    plan = lab.plan(NODE_1)

    def after(call: ProcessCall) -> None:
        if not is_check_run(call):
            lab.cluster.down = 3

    answer_runs(lab.process_fake, lab.bin_dir, steps=lab.steps, after=after)

    result = lab.apply_json(plan)

    assert result.exit_code == 0, result.output
    assert lab.steps[-1] == "uncordon node-1"


def test_a_drain_that_a_budget_blocks_stops_before_the_node_is_cordoned(
    lab: Lab, person_caller: None
) -> None:
    lab.cluster.blocked.add("node-3")
    plan = lab.plan(NODE_3)

    result = lab.apply(plan)

    assert result.exit_code == 1
    assert lab.steps == ["drain check node-3"]
    assert "global timeout reached" in result.output
    assert not lab.cluster.nodes["node-3"].cordoned


def test_the_drain_waits_for_the_longest_grace_period_of_a_pod_of_the_node(
    lab: Lab, person_caller: None
) -> None:
    """A pod with a grace period of 660 s makes the drain bound 720 s, above the setting of
    180 s."""
    lab.cluster.graces["node-3"] = 660
    plan = lab.plan(NODE_3)

    result = lab.apply(plan)

    assert result.exit_code == 0, result.output
    [drain] = [
        call.argv
        for call in lab.process_fake.calls
        if call.argv[:5] == ("kubectl", "--context", KUBE_CONTEXT, "--request-timeout=30s", "drain")
        and "--dry-run=server" not in call.argv
    ]
    assert "--timeout=720s" in drain


def test_the_workloads_that_only_the_node_can_run_are_named_and_audited(
    lab: Lab, person_caller: None
) -> None:
    """A pod whose volume only node-3 can mount is down while node-3 is cordoned; the apply goes on
    and names its workload."""
    from devops_cli.config.settings import load_settings
    from devops_cli.core.repo import resolve_data_path

    lab.cluster.pinned["node-3"] = "roadmap"
    lab.cluster.pinned["node-1"] = "other"
    plan = lab.plan(NODE_3)

    result = lab.apply(plan)

    assert result.exit_code == 0, result.output
    assert (
        f"Down during the apply of {NODE_3}, because only its node can mount their volumes: "
        "apps/roadmap (Deployment)"
    ) in result.output
    log = resolve_data_path(load_settings().data.audit_log_path)
    [host] = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])["details"]["hosts"]
    assert host["down_during_apply"] == ["apps/roadmap (Deployment)"]


def test_a_cluster_that_is_not_healthy_before_refuses_the_apply(
    lab: Lab, person_caller: None
) -> None:
    plan = lab.plan(NODE_3)
    lab.cluster.nodes["node-2"].pressure = ("MemoryPressure",)

    result = lab.apply(plan)

    assert result.exit_code == 1
    assert "The cluster is not healthy" in result.output
    assert "node-2 has MemoryPressure" in result.output
    assert lab.steps == []


@pytest.mark.parametrize(
    ("caller", "level", "limit", "refused"),
    [
        pytest.param("agent", "none", NODE_3, "needs safe", id="agent-none"),
        pytest.param("agent", "plan", NODE_3, "needs safe", id="agent-plan"),
        pytest.param("agent", "safe", NODE_3, "needs full", id="agent-safe-disruptive"),
        pytest.param("agent", "safe", NODE_4, None, id="agent-safe-no-disruptive-class"),
        pytest.param("agent", "full", NODE_3, None, id="agent-full"),
        pytest.param("person", "none", NODE_3, None, id="person-none"),
    ],
)
def test_the_access_level_that_an_apply_needs(
    lab: Lab,
    monkeypatch: pytest.MonkeyPatch,
    person_caller: None,
    caller: str,
    level: str,
    limit: str,
    refused: str | None,
) -> None:
    plan = lab.plan(limit)
    if caller == "agent":
        monkeypatch.setenv("AI_AGENT", "claude-code_2.1.0_agent")
    calls = len(lab.process_fake.calls)

    result = lab.apply_json(plan, level=level)

    if refused is None:
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["caller"] == caller
    else:
        assert result.exit_code == 1
        assert refused in result.output
        assert "infra.repos[].agent_access" in result.output
        assert len(lab.process_fake.calls) == calls


def _edit_record(plan: dict[str, Any], change: Callable[[dict[str, Any]], None]) -> None:
    record = Path(plan["folder"]) / "plan.json"
    data = json.loads(record.read_text(encoding="utf-8"))
    change(data)
    record.write_text(json.dumps(data), encoding="utf-8")


def test_a_plan_record_that_changed_is_refused(lab: Lab, person_caller: None) -> None:
    plan = lab.plan(NODE_3)
    _edit_record(plan, lambda data: data["hosts"][0].update(disruptive=[]))

    result = lab.apply(plan)

    assert result.exit_code == 1
    assert "the record changed after the plan" in result.output
    assert lab.steps == []


def test_a_plan_older_than_the_limit_is_refused(
    lab: Lab, clock: ClockFake, person_caller: None
) -> None:
    plan = lab.plan(NODE_3)
    clock.shift(25 * 3600)

    result = lab.apply(plan)

    assert result.exit_code == 1
    assert "more than 24 hours ago (infra.plan_max_age_hours)" in result.output


def test_another_limit_than_the_plan_is_refused(lab: Lab, person_caller: None) -> None:
    plan = lab.plan(NODE_3)

    result = lab.apply({**plan, "limit": NODE_4})

    assert result.exit_code == 1
    assert f"The limit of the plan {plan['id']} is {NODE_3}, not {NODE_4}" in result.output


def test_a_commit_that_origin_does_not_hold_is_refused(
    lab: Lab, infra_repo: Path, person_caller: None
) -> None:
    plan = lab.plan(NODE_3)
    lab.process_fake.answer(
        git_command(infra_repo, "merge-base", "--is-ancestor"), ProcessAnswer(returncode=1)
    )

    result = lab.apply(plan)

    assert result.exit_code == 1
    assert f"The remote origin holds no commit {ORIGIN_COMMIT}" in result.output
    assert not any("archive" in call.argv for call in lab.process_fake.calls[-3:])


def test_an_agent_with_host_key_checks_off_is_refused(
    lab: Lab, infra_repo: Path, ansible_installed: Path, agent_caller: None
) -> None:
    plan = lab.plan(NODE_3)
    listing = recorded_read("inventory", infra_repo)
    listing["_meta"]["hostvars"][NODE_3]["ansible_ssh_common_args"] = "-o StrictHostKeyChecking=no"
    lab.process_fake.answer(
        [str(ansible_installed / "ansible-inventory")], in_export(json.dumps(listing), infra_repo)
    )

    result = lab.apply(plan)

    assert result.exit_code == 1
    assert "An agent apply needs host key checks on" in result.output
    assert "StrictHostKeyChecking=no" in result.output
    assert lab.steps == []


@pytest.mark.parametrize(("state", "exit_code"), [("open", 0), ("closed", 1)])
def test_an_agent_applies_the_head_of_a_pull_request_only_while_it_is_open(
    lab: Lab,
    infra_repo: Path,
    github_api: GitHubApiFake,
    agent_caller: None,
    state: str,
    exit_code: int,
) -> None:
    lab.process_fake.answer(
        git_command(infra_repo, "rev-parse", "--verify"), ProcessAnswer(stdout=f"{_PR_COMMIT}\n")
    )
    plan = lab.plan(NODE_3, "--ref", "pull/19/head")
    lab.process_fake.answer(
        git_command(infra_repo, "merge-base", "--is-ancestor"), ProcessAnswer(returncode=1)
    )
    github_api.route(
        "GET",
        f"https://api.github.com/repos/{REPO}/pulls/19",
        github_json({"state": state, "head": {"sha": _PR_COMMIT, "ref": "fix/k3s"}}),
    )

    result = lab.apply(plan)

    assert result.exit_code == exit_code, result.output
    if exit_code:
        assert "Pull request 19 is closed" in result.output
        assert lab.steps == []


def test_an_agent_cannot_apply_a_commit_of_another_branch(
    lab: Lab, infra_repo: Path, agent_caller: None
) -> None:
    plan = lab.plan(NODE_3, "--ref", "fix/k3s")

    def holds(call: ProcessCall) -> ProcessAnswer:
        return ProcessAnswer(returncode=1 if call.argv[-1] == "refs/remotes/origin/HEAD" else 0)

    lab.process_fake.answer(git_command(infra_repo, "merge-base", "--is-ancestor"), holds)

    result = lab.apply(plan)

    assert result.exit_code == 1
    assert "An agent applies only a commit of the default branch" in result.output


def test_the_audit_record_holds_each_field_and_no_secret(
    lab: Lab, ssh_key_dir: Path, agent_caller: None
) -> None:
    from devops_cli.config.settings import load_settings
    from devops_cli.core.repo import resolve_data_path

    plan = lab.plan(NODE_3)

    result = lab.apply_json(plan)

    assert result.exit_code == 0, result.output
    log = resolve_data_path(load_settings().data.audit_log_path)
    text = log.read_text(encoding="utf-8")
    record = json.loads(text.splitlines()[-1])
    assert (record["command"], record["status"]) == ("infra.apply", "ok")
    details = record["details"]
    assert set(details) == {
        "id",
        "caller",
        "tool",
        "level",
        "repo",
        "commit",
        "ref",
        "plan_id",
        "playbook",
        "limit",
        "tags",
        "result",
        "reason",
        "hosts",
        "duration_seconds",
    }
    assert (details["caller"], details["tool"], details["level"], details["plan_id"]) == (
        "agent",
        "claude_code",
        "full",
        plan["id"],
    )
    assert details["id"] == json.loads(result.output)["id"]
    [host] = details["hosts"]
    assert (host["host"], host["disruptive"], host["outcome"]) == (
        NODE_3,
        ["service-restart:k3s-agent"],
        "applied",
    )
    assert len(host["runner_idents"]) == 2
    assert SSH_KEY_NAME not in text
    assert str(ssh_key_dir) not in text


def test_a_refusal_writes_an_audit_record(lab: Lab, agent_caller: None) -> None:
    from devops_cli.config.settings import load_settings
    from devops_cli.core.repo import resolve_data_path

    plan = lab.plan(NODE_3)

    result = lab.apply(plan, level="plan")

    assert result.exit_code == 1
    log = resolve_data_path(load_settings().data.audit_log_path)
    record = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert (record["status"], record["details"]["result"]) == ("refused", "refused")
    assert "needs safe" in record["details"]["reason"]


def test_a_person_who_says_no_changes_nothing(lab: Lab, person_caller: None) -> None:
    plan = lab.plan(NODE_3)
    calls = len(lab.process_fake.calls)

    result = lab.cli(
        "infra", "apply", REPO, PLAYBOOK, "--plan", plan["id"], "--limit", NODE_3, input="n\n"
    )

    assert result.exit_code == 1
    assert "was not approved" in result.output
    assert len(lab.process_fake.calls) == calls


def test_the_table_names_each_host_with_its_node_and_memory(lab: Lab, person_caller: None) -> None:
    plan = lab.plan(NODE_3)

    result = lab.apply(plan)

    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0] == f"Apply of {REPO}: {PLAYBOOK} at {ORIGIN_COMMIT} (plan {plan['id']})"
    row = next(line for line in lines if line.strip().startswith(NODE_3))
    assert "node-3" in row
    assert "no -> no" in row
    assert "16.0 / 15.0" in row
    assert any(line.startswith("Apply ") and ": ok, in " in line for line in lines)


def test_dry_run_starts_no_process(
    lab: Lab,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    person_caller: None,
    snapshot: SnapshotAssertion,
) -> None:
    """An agent at level none may run a dry run: it reaches no host."""
    plan = lab.plan(f"{NODE_4},{NODE_3}")
    lab.write_entry("none")
    monkeypatch.setenv("AI_AGENT", "claude-code_2.1.0_agent")
    calls = len(lab.process_fake.calls)

    result = lab.cli(
        "infra",
        "apply",
        REPO,
        PLAYBOOK,
        "--plan",
        plan["id"],
        "--limit",
        plan["limit"],
        "--dry-run",
    )

    assert result.exit_code == 0, result.output
    assert len(lab.process_fake.calls) == calls
    shown = result.output.replace(str(tmp_path), "<tmp>").replace(plan["id"], "<plan id>")
    assert shown == snapshot
