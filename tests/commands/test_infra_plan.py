"""`devops infra plan`: a check-mode run of a playbook of an infra repo and its plan record (#5124).

The command layer owns the options, the access level, the dry run, the output formats and the exit
code. What the job events show on each host is the domain's (`tests/infra/test_plan.py`). The repo
is the homelab-shaped fixture, read at the head of its default branch (`answer_default_branch`),
and `ansible-runner` writes the events of a recorded run (`answer_runner`).
"""

from __future__ import annotations

import json
import shlex
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.infra import (
    ORIGIN_COMMIT,
    SSH_KEY_NAME,
    answer_default_branch,
    answer_runner,
    git_command,
    in_export,
    recorded_read,
)

REPO = "example-org/infra"
PLAYBOOK = "ansible/playbooks/03_k3s.yaml"
_RUNNER = "ansible-runner"
_GALAXY = "ansible-galaxy"
_PR_COMMIT = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture
def ready(
    infra_repo: Path,
    ansible_installed: Path,
    ssh_key_dir: Path,
    process_fake: ProcessFake,
    config: Callable[..., Path],
) -> Callable[..., Path]:
    """The repo at the head of origin/main with its inventory, the key of `devops ssh`, and a way
    to write the entry at an agent access level."""
    answer_default_branch(process_fake, infra_repo)
    listing = json.dumps(recorded_read("inventory", infra_repo))
    process_fake.answer(
        [str(ansible_installed / "ansible-inventory")], in_export(listing, infra_repo)
    )
    process_fake.answer([str(ansible_installed / _GALAXY)], ProcessAnswer())

    def entry(level: str = "none") -> Path:
        fields = {"repo": REPO, "path": str(infra_repo), "agent_access": level}
        return config(infra={"repos": [fields]}, ssh={"key_dir": str(ssh_key_dir)})

    entry()
    return entry


def _calls(process_fake: ProcessFake, program: str) -> list[ProcessCall]:
    return [call for call in process_fake.calls if call.argv[0].endswith(f"/{program}")]


def _option(argv: tuple[str, ...], name: str) -> str:
    return argv[argv.index(name) + 1]


def _cmdline(argv: tuple[str, ...]) -> list[str]:
    prefix = "--cmdline="
    return shlex.split(next(word[len(prefix) :] for word in argv if word.startswith(prefix)))


def test_plan_shows_the_changes_of_each_host_and_keeps_the_record(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    ansible_installed: Path,
    process_fake: ProcessFake,
    person_caller: None,
) -> None:
    answer_runner(process_fake, ansible_installed, "agent")

    result = cli("infra", "plan", REPO, PLAYBOOK, "--limit", "node-3.example.com", "-f", "json")

    assert result.exit_code == 0, result.output
    plan = json.loads(result.output)
    assert (plan["status"], plan["commit"], plan["ref"], plan["ansible_core"]) == (
        "ok",
        ORIGIN_COMMIT,
        "origin/main",
        "2.22.0",
    )
    [host] = plan["hosts"]
    assert (host["host"], host["disruptive"], [t["diff_hidden"] for t in host["changed"]]) == (
        "node-3.example.com",
        ["service-restart:k3s-agent"],
        [True, False],
    )
    folder = Path(plan["folder"])
    assert folder.name == plan["id"]
    assert json.loads((folder / "plan.json").read_text(encoding="utf-8")) == plan
    assert not (folder / "project").exists()
    assert (folder / "artifacts" / plan["runner_ident"] / "job_events").is_dir()
    assert (folder / "env" / "settings").read_text(encoding="utf-8") == "job_timeout: 1740\n"
    assert oct(folder.stat().st_mode & 0o777) == oct(0o700)


def test_the_run_is_check_mode_on_the_limit_without_offline_hosts_with_the_key(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    ansible_installed: Path,
    ssh_key_dir: Path,
    process_fake: ProcessFake,
    person_caller: None,
) -> None:
    answer_runner(process_fake, ansible_installed, "agent")

    result = cli("infra", "plan", REPO, PLAYBOOK, "--limit", "node-5.example.com", "--tags", "k3s")

    assert result.exit_code == 0, result.output
    [galaxy] = _calls(process_fake, _GALAXY)
    [run] = _calls(process_fake, _RUNNER)
    assert process_fake.calls.index(galaxy) < process_fake.calls.index(run)
    project = Path(run.argv[2]) / "project"
    assert (_option(run.argv, "--playbook"), _option(run.argv, "--limit")) == (
        PLAYBOOK,
        "node-5.example.com:!offline",
    )
    assert _cmdline(run.argv) == [
        "--check",
        "--diff",
        "-v",
        "-i",
        "ansible/inventory/hosts.yaml",
        "--tags",
        "k3s",
        "-e",
        f"ansible_ssh_private_key_file={ssh_key_dir / SSH_KEY_NAME}",
    ]
    assert run.env is not None
    assert {
        name: run.env[name]
        for name in (
            "ANSIBLE_HOST_KEY_CHECKING",
            "ANSIBLE_CONFIG",
            "ANSIBLE_INJECT_INVOCATION",
            "ANSIBLE_CALLBACK_RESULT_FORMAT",
            "ANSIBLE_DISPLAY_SKIPPED_HOSTS",
            "ANSIBLE_NOCOLOR",
        )
    } == {
        "ANSIBLE_HOST_KEY_CHECKING": "True",
        "ANSIBLE_CONFIG": str(project / "ansible.cfg"),
        "ANSIBLE_INJECT_INVOCATION": "True",
        "ANSIBLE_CALLBACK_RESULT_FORMAT": "json",
        "ANSIBLE_DISPLAY_SKIPPED_HOSTS": "True",
        "ANSIBLE_NOCOLOR": "True",
    }
    collections = Path(run.env["ANSIBLE_COLLECTIONS_PATH"])
    assert collections.parent == Path(_option(galaxy.argv, "-p")).parent
    assert collections.is_dir()


def test_the_collections_install_once_for_each_version_of_the_requirements(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    ansible_installed: Path,
    process_fake: ProcessFake,
    person_caller: None,
) -> None:
    answer_runner(process_fake, ansible_installed, "agent")

    for _ in range(2):
        assert cli("infra", "plan", REPO, PLAYBOOK).exit_code == 0

    assert len(_calls(process_fake, _GALAXY)) == 1
    assert len(_calls(process_fake, _RUNNER)) == 2


def test_a_failed_task_marks_the_plan_failed_and_exits_1(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    ansible_installed: Path,
    process_fake: ProcessFake,
    person_caller: None,
) -> None:
    answer_runner(process_fake, ansible_installed, "site")

    result = cli("infra", "plan", REPO, PLAYBOOK, "-f", "json")

    assert result.exit_code == 1
    plan = json.loads(result.output)
    assert (plan["status"], plan["error"], plan["host_pattern"]) == ("failed", None, "all:!offline")
    assert [host["host"] for host in plan["hosts"] if host["failed"]] == ["node-4.example.com"]
    assert (Path(plan["folder"]) / "plan.json").is_file()


def test_the_table_names_the_commit_the_tasks_and_the_plan_id(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    ansible_installed: Path,
    process_fake: ProcessFake,
    person_caller: None,
) -> None:
    answer_runner(process_fake, ansible_installed, "agent")

    result = cli("infra", "plan", REPO, PLAYBOOK, "--limit", "node-3.example.com")

    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[:2] == [
        f"Plan of {REPO}: {PLAYBOOK} on node-3.example.com:!offline (check mode)",
        f"Reads origin/main at {ORIGIN_COMMIT}, not the working tree of the checkout.",
    ]
    assert "service-restart:k3s-agent" in result.output
    assert "changed, diff hidden" in result.output
    assert lines[-1].startswith("Plan ")
    assert " (ok), in " in lines[-1]


def test_an_agent_on_a_repo_at_none_is_refused_before_any_process(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    process_fake: ProcessFake,
    agent_caller: None,
) -> None:
    result = cli("infra", "plan", REPO, PLAYBOOK)

    assert result.exit_code == 1
    assert "devops infra plan" in result.output
    assert "needs plan" in result.output
    assert "infra.repos[].agent_access" in result.output
    assert process_fake.calls == []


def test_an_agent_on_a_repo_at_plan_may_plan(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    ansible_installed: Path,
    process_fake: ProcessFake,
    agent_caller: None,
) -> None:
    ready("plan")
    answer_runner(process_fake, ansible_installed, "agent")

    result = cli("infra", "plan", REPO, PLAYBOOK, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == "ok"


def test_a_playbook_outside_the_repo_is_refused_before_the_run(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    process_fake: ProcessFake,
    person_caller: None,
) -> None:
    result = cli("infra", "plan", REPO, "../outside.yaml")

    assert result.exit_code == 1
    assert "../outside.yaml is not a playbook file of the infra repo" in result.output
    assert _calls(process_fake, _RUNNER) == []


def test_ref_plans_the_head_of_a_pull_request(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    infra_repo: Path,
    ansible_installed: Path,
    process_fake: ProcessFake,
    person_caller: None,
) -> None:
    process_fake.answer(
        git_command(infra_repo, "rev-parse", "--verify"),
        ProcessAnswer(stdout=f"{_PR_COMMIT}\n"),
    )
    answer_runner(process_fake, ansible_installed, "agent")

    result = cli("infra", "plan", REPO, PLAYBOOK, "--ref", "pull/19/head", "-f", "json")

    assert result.exit_code == 0, result.output
    plan = json.loads(result.output)
    assert (plan["ref"], plan["commit"]) == ("pull/19/head", _PR_COMMIT)
    fetch = next(c for c in process_fake.calls if "refs/pull/19/head" in c.argv)
    assert fetch.argv[-4:] == ("fetch", "--quiet", "origin", "refs/pull/19/head")
    archive = next(c for c in process_fake.calls if "archive" in c.argv)
    assert archive.argv[-1] == _PR_COMMIT


def test_a_branch_that_origin_does_not_hold_is_refused_before_the_export(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    infra_repo: Path,
    process_fake: ProcessFake,
    person_caller: None,
) -> None:
    process_fake.answer(
        git_command(infra_repo, "rev-parse", "--verify"),
        ProcessAnswer(returncode=128, stderr="fatal: Needed a single revision\n"),
    )

    result = cli("infra", "plan", REPO, PLAYBOOK, "--ref", "no-such-branch")

    assert result.exit_code == 1
    assert "holds no ref no-such-branch" in result.output
    assert not any("archive" in call.argv for call in process_fake.calls)


def test_dry_run_starts_no_process(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    process_fake: ProcessFake,
    tmp_path: Path,
    agent_caller: None,
    snapshot: SnapshotAssertion,
) -> None:
    """An agent at level none may run a dry run: it reaches no host."""
    result = cli(
        "infra",
        "plan",
        REPO,
        PLAYBOOK,
        "--limit",
        "node-3.example.com",
        "--ref",
        "fix/k3s",
        "--dry-run",
    )

    assert result.exit_code == 0, result.output
    assert process_fake.calls == []
    assert result.output.replace(str(tmp_path), "<tmp>") == snapshot
