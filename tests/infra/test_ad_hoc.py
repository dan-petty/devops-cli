"""The ansible-runner ad-hoc tasks of `devops infra` (#5123, #5128).

A fake `ansible-runner` writes one job event for each host of the pattern of the call, in the
artifact folder of the call.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from devops_cli.infra.ad_hoc import AdHoc, AdHocTask, ad_hoc_argv
from devops_cli.infra.ansible_facts import AnsibleTool
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

_SOURCES = ("ansible/inventory/hosts.yaml",)
_HOST = "node-3.example.com"


@pytest.fixture
def tool(tmp_path: Path) -> AnsibleTool:
    return AnsibleTool(bin_dir=tmp_path / "bin")


def test_a_task_that_changes_a_host_runs_with_become_and_its_bound(
    tmp_path: Path, tool: AnsibleTool
) -> None:
    key = tmp_path / "ssh" / "ansible-id_ed25519"
    task = AdHocTask(
        module="ansible.builtin.systemd_service",
        args="name=k3s-agent state=restarted",
        become=True,
        task_timeout=300,
    )

    argv = ad_hoc_argv(
        tool,
        tmp_path / "export",
        _SOURCES,
        key,
        task,
        pattern=_HOST,
        artifact_dir=tmp_path / "artifacts",
        ident="0123",
    )

    assert argv == [
        str(tmp_path / "bin" / "ansible-runner"),
        "run",
        str(tmp_path / "export"),
        "--artifact-dir",
        str(tmp_path / "artifacts"),
        "--ident",
        "0123",
        "--omit-env-files",
        "--quiet",
        "--hosts",
        _HOST,
        "-m",
        "ansible.builtin.systemd_service",
        "-a",
        "name=k3s-agent state=restarted",
        f"--cmdline=-i {_SOURCES[0]} -T 10 --become --task-timeout 300 "
        f"-e ansible_ssh_private_key_file={key}",
    ]


def test_a_task_with_no_become_turns_become_off(tmp_path: Path, tool: AnsibleTool) -> None:
    task = AdHocTask(module="ansible.builtin.debug", args="msg=x")

    argv = ad_hoc_argv(
        tool,
        tmp_path,
        _SOURCES,
        None,
        task,
        pattern="all",
        limit="!offline",
        artifact_dir=tmp_path / "artifacts",
        ident="0123",
    )

    assert argv[argv.index("--hosts") : argv.index("-m")] == [
        "--hosts",
        "all",
        "--limit",
        "!offline",
    ]
    assert argv[-1] == f"--cmdline=-i {_SOURCES[0]} -T 10 -e ansible_become=false"


def _runner(
    events: Mapping[str, tuple[str, dict[str, Any]]], returncode: int = 0
) -> Callable[[ProcessCall], ProcessAnswer]:
    def answer(call: ProcessCall) -> ProcessAnswer:
        argv = call.argv
        folder = Path(argv[argv.index("--artifact-dir") + 1]) / argv[argv.index("--ident") + 1]
        job_events = folder / "job_events"
        job_events.mkdir(parents=True)
        for number, (host, (event, res)) in enumerate(events.items(), start=1):
            body = {"event": event, "counter": number, "event_data": {"host": host, "res": res}}
            (job_events / f"{number}-{host}.json").write_text(json.dumps(body), encoding="utf-8")
        return ProcessAnswer(returncode=returncode, stderr="ERROR! the last line\n")

    return answer


def test_each_host_gives_its_result_and_the_artifacts_go_away(
    tmp_path: Path, tool: AnsibleTool, process_fake: ProcessFake
) -> None:
    process_fake.answer(
        tool.argv("ansible-runner"),
        _runner(
            {
                "node-1.example.com": ("runner_on_ok", {"msg": "k3s"}),
                "node-2.example.com": ("runner_on_failed", {"msg": "Unit k3s-agent not found."}),
                "node-3.example.com": ("runner_on_unreachable", {"msg": "Connection timed out"}),
            },
            returncode=4,
        ),
    )
    hosts = AdHoc(tool=tool, root=tmp_path, sources=_SOURCES, key=None)

    outcome = hosts.run(AdHocTask(module="ansible.builtin.debug", args="msg=x"), "all", timeout=60)

    assert outcome.problem("node-1.example.com") is None
    assert outcome.value("node-1.example.com", "msg") == "k3s"
    assert outcome.problem("node-2.example.com") == (
        "the task ansible.builtin.debug failed on node-2.example.com: Unit k3s-agent not found."
    )
    assert outcome.problem("node-3.example.com") == (
        "the task ansible.builtin.debug did not reach node-3.example.com: Connection timed out"
    )
    assert outcome.problem("node-4.example.com") == (
        "ansible-runner gave no result of node-4.example.com (exit code 4): ERROR! the last line"
    )
    [call] = process_fake.calls
    assert call.timeout == 60
    assert call.env is not None
    assert call.env["ANSIBLE_HOST_KEY_CHECKING"] == "True"
    artifacts = Path(call.argv[call.argv.index("--artifact-dir") + 1])
    assert not artifacts.exists()
