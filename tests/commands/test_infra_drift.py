"""`devops infra drift`: report drift of an infra repo against in-service hosts (#5127).

The command checks live drift using Ansible check mode at the default branch head,
sets Prometheus metrics, and manages one marker issue in the target repository.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest

from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.infra.drift import DRIFT_MARKER_PREFIX, drift_marker
from devops_cli.telemetry.instruments import INFRA_DRIFT_HOSTS, INFRA_RUNS_TOTAL
from tests.support.fakes.github import GitHubApiFake, github_json, quota_headers
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.infra import (
    answer_default_branch,
    answer_runner,
    in_export,
    recorded_read,
)

REPO = "example-org/infra"
_RUNNER = "ansible-runner"
_GALAXY = "ansible-galaxy"


@pytest.fixture(autouse=True)
def _seed_quota() -> None:
    """Seed rate limit quota so GitHub session pacing never falls back to gh CLI."""
    limiter = get_github_rate_limiter()
    limiter.update_quota("search", remaining=30, limit=30, reset_epoch=time.time() + 600.0)
    limiter.update_quota("core", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0)


@pytest.fixture
def ready(
    infra_repo: Path,
    ansible_installed: Path,
    ssh_key_dir: Path,
    process_fake: ProcessFake,
    config: Callable[..., Path],
) -> Callable[..., Path]:
    """The repo at origin/main with its inventory, SSH key, and configurable agent access."""
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


def _search_url(repo: str) -> str:
    query = f'"{DRIFT_MARKER_PREFIX}" in:body is:issue repo:{repo}'
    return f"/search/issues?{urlencode({'q': query, 'per_page': 100, 'page': 1})}"


def _route_search(github_api: GitHubApiFake, repo: str, *issues: dict[str, Any]) -> None:
    payload = {"total_count": len(issues), "incomplete_results": False, "items": list(issues)}
    quota = quota_headers(30, resource="search", limit=30)
    github_api.route("GET", _search_url(repo), github_json(payload, headers=quota))


def _answer_no_drift(fake: ProcessFake, bin_dir: Path, host: str = "node-3.example.com") -> None:
    def answer(call: ProcessCall) -> ProcessAnswer:
        private = Path(call.argv[2])
        ident = call.argv[call.argv.index("--ident") + 1]
        artifacts = private / "artifacts" / ident
        job_events = artifacts / "job_events"
        job_events.mkdir(parents=True)
        event = {
            "counter": 1,
            "uuid": "00000000-0000-0000-0000-000000000001",
            "event": "runner_on_ok",
            "stdout": f'ok: [{host}] => {{"changed": false}}',
            "event_data": {
                "host": host,
                "task": "Check configuration",
                "task_path": "ansible/playbooks/site.yaml:10",
                "resolved_action": "ansible.builtin.debug",
                "res": {"changed": False},
            },
        }
        (job_events / "1-00000000-0000-0000-0000-000000000001.json").write_text(
            json.dumps(event), encoding="utf-8"
        )
        stats = {
            "counter": 2,
            "uuid": "00000000-0000-0000-0000-000000000002",
            "event": "playbook_on_stats",
            "event_data": {"changed": {host: 0}, "failures": {host: 0}},
        }
        (job_events / "2-00000000-0000-0000-0000-000000000002.json").write_text(
            json.dumps(stats), encoding="utf-8"
        )
        (artifacts / "status").write_text("successful", encoding="utf-8")
        (artifacts / "rc").write_text("0", encoding="utf-8")
        return ProcessAnswer(returncode=0)

    fake.answer([str(bin_dir / "ansible-runner"), "run"], answer)


def test_drift_exits_2_when_one_host_drifts(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    ansible_installed: Path,
    process_fake: ProcessFake,
    github_api: GitHubApiFake,
    person_caller: None,
) -> None:
    """When a host drifts, the command exits 2 and prints the host name and changed task."""
    answer_runner(process_fake, ansible_installed, "agent")
    _route_search(github_api, REPO)
    github_api.route("POST", f"/repos/{REPO}/issues", github_json({"number": 10}, status=201))

    result = cli("infra", "drift", REPO)

    assert result.exit_code == 2, result.output
    assert "node-3.example.com" in result.output
    assert "Deploy K3s agent configuration file" in result.output


def test_drift_host_gauge_and_counter_samples(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    ansible_installed: Path,
    process_fake: ProcessFake,
    github_api: GitHubApiFake,
    otlp: FakeCollector,
    person_caller: None,
) -> None:
    """Gauge is set to drift count and counter records result drift then ok."""
    # First run: drift on node-3
    answer_runner(process_fake, ansible_installed, "agent")
    _route_search(github_api, REPO)
    github_api.route("POST", f"/repos/{REPO}/issues", github_json({"number": 10}, status=201))

    res1 = cli("infra", "drift", REPO)
    assert res1.exit_code == 2

    gauge_points = otlp.points(INFRA_DRIFT_HOSTS.name)
    assert [(attr["repo"], val) for attr, val in gauge_points] == [(REPO.casefold(), 1.0)]

    counter_points = otlp.points(INFRA_RUNS_TOTAL.name)
    assert [
        (attr["repo"], attr["command"], attr["result"], val) for attr, val in counter_points
    ] == [(REPO.casefold(), "drift", "drift", 1.0)]

    # Second run: no drift
    _answer_no_drift(process_fake, ansible_installed)
    _route_search(github_api, REPO)

    res2 = cli("infra", "drift", REPO)
    assert res2.exit_code == 0

    gauge_points2 = otlp.points(INFRA_DRIFT_HOSTS.name)
    assert [(attr["repo"], val) for attr, val in gauge_points2] == [
        (REPO.casefold(), 1.0),
        (REPO.casefold(), 0.0),
    ]

    counter_points2 = otlp.points(INFRA_RUNS_TOTAL.name)
    assert [
        (attr["repo"], attr["command"], attr["result"], val) for attr, val in counter_points2
    ] == [
        (REPO.casefold(), "drift", "drift", 1.0),
        (REPO.casefold(), "drift", "ok", 1.0),
    ]


def test_drift_issue_first_run_creates_issue(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    ansible_installed: Path,
    process_fake: ProcessFake,
    github_api: GitHubApiFake,
    person_caller: None,
) -> None:
    """First run with drift opens 1 issue holding marker, host, tasks, and plan id."""
    answer_runner(process_fake, ansible_installed, "agent")
    _route_search(github_api, REPO)
    github_api.route("POST", f"/repos/{REPO}/issues", github_json({"number": 55}, status=201))

    result = cli("infra", "drift", REPO)
    assert result.exit_code == 2

    posts = [req for req in github_api.sent if req.method == "POST"]
    assert len(posts) == 1
    assert posts[0].url.path == f"/repos/{REPO}/issues"
    payload = json.loads(posts[0].content)
    body = payload["body"]
    assert "node-3.example.com" in body
    assert "Deploy K3s agent configuration file" in body
    assert DRIFT_MARKER_PREFIX in body
    assert "#55" in result.output


def test_drift_second_run_with_same_plan_id_sends_no_write(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    ansible_installed: Path,
    process_fake: ProcessFake,
    github_api: GitHubApiFake,
    person_caller: None,
) -> None:
    """A run whose plan id matches the existing marker issue sends no write request."""
    answer_runner(process_fake, ansible_installed, "agent")
    # First get plan id from a dry run
    dr_result = cli("infra", "drift", REPO, "--dry-run")
    assert dr_result.exit_code == 2
    plan_line = next(line for line in dr_result.output.splitlines() if line.startswith("Plan ID: "))
    plan_id = plan_line.split("Plan ID: ")[1].strip()

    # Now simulate second run where GitHub already has an open issue with this plan id
    existing_issue = {
        "number": 77,
        "state": "open",
        "state_reason": None,
        "body": f"Report\n{drift_marker(REPO, plan_id)}\n",
    }
    _route_search(github_api, REPO, existing_issue)

    result = cli("infra", "drift", REPO)
    assert result.exit_code == 2

    # HTTP requests sent: only the search GET, no POST or PATCH
    writes = [req for req in github_api.sent if req.method in ("POST", "PATCH")]
    assert writes == []
    assert "unchanged" in result.output.lower()


def test_drift_clears_closes_open_marker_issue(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    ansible_installed: Path,
    process_fake: ProcessFake,
    github_api: GitHubApiFake,
    person_caller: None,
) -> None:
    """When a run finds no drift and an open marker issue exists, it closes the issue."""
    _answer_no_drift(process_fake, ansible_installed)
    existing_issue = {
        "number": 88,
        "state": "open",
        "state_reason": None,
        "body": f"Report\n{drift_marker(REPO, 'prev' + '0' * 60)}\n",
    }
    _route_search(github_api, REPO, existing_issue)
    github_api.route(
        "PATCH", f"/repos/{REPO}/issues/88", github_json({"number": 88, "state": "closed"})
    )

    result = cli("infra", "drift", REPO)
    assert result.exit_code == 0

    patches = [req for req in github_api.sent if req.method == "PATCH"]
    assert len(patches) == 1
    assert patches[0].url.path == f"/repos/{REPO}/issues/88"
    patch_body = json.loads(patches[0].content)
    assert patch_body["state"] == "closed"
    assert patch_body["state_reason"] == "completed"
    assert "closed" in result.output.lower()


def test_drift_failed_plan_exits_1_and_writes_no_issue(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    ansible_installed: Path,
    process_fake: ProcessFake,
    github_api: GitHubApiFake,
    person_caller: None,
) -> None:
    """A failed plan exits 1 and sends no issue create or update requests."""
    answer_runner(process_fake, ansible_installed, "site")

    result = cli("infra", "drift", REPO)
    assert result.exit_code == 1

    writes = [req for req in github_api.sent if req.method in ("POST", "PATCH")]
    assert writes == []


def test_drift_dry_run_sends_no_http_requests(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    ansible_installed: Path,
    process_fake: ProcessFake,
    github_api: GitHubApiFake,
    person_caller: None,
) -> None:
    """With --dry-run, zero HTTP requests are sent and exit code is 2 when drift exists."""
    answer_runner(process_fake, ansible_installed, "agent")

    result = cli("infra", "drift", REPO, "--dry-run")
    assert result.exit_code == 2

    assert github_api.sent == []


def test_drift_agent_access_gate_refuses_level_none(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    github_api: GitHubApiFake,
    agent_caller: None,
) -> None:
    """An agent caller on a repo at level none is refused before any plan run."""
    ready("none")

    result = cli("infra", "drift", REPO)
    assert result.exit_code == 1
    assert "devops infra drift" in result.output
    assert "needs plan" in result.output
    assert github_api.sent == []


def test_drift_agent_at_plan_may_run(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    ansible_installed: Path,
    process_fake: ProcessFake,
    github_api: GitHubApiFake,
    agent_caller: None,
) -> None:
    """An agent caller on a repo at level plan succeeds."""
    ready("plan")
    answer_runner(process_fake, ansible_installed, "agent")
    _route_search(github_api, REPO)
    github_api.route("POST", f"/repos/{REPO}/issues", github_json({"number": 12}, status=201))

    result = cli("infra", "drift", REPO)
    assert result.exit_code == 2


def test_drift_explicit_playbook_option(
    cli: Callable[..., Any],
    ready: Callable[..., Path],
    ansible_installed: Path,
    process_fake: ProcessFake,
    github_api: GitHubApiFake,
    person_caller: None,
) -> None:
    """--playbook option is respected during execution."""
    answer_runner(process_fake, ansible_installed, "agent")
    _route_search(github_api, REPO)
    github_api.route("POST", f"/repos/{REPO}/issues", github_json({"number": 15}, status=201))

    result = cli("infra", "drift", REPO, "--playbook", "ansible/playbooks/site.yaml")
    assert result.exit_code == 2

    calls = [c for c in process_fake.calls if c.argv[0].endswith(f"/{_RUNNER}")]
    assert len(calls) == 1
    assert "--playbook" in calls[0].argv
    idx = calls[0].argv.index("--playbook")
    assert calls[0].argv[idx + 1] == "ansible/playbooks/site.yaml"
