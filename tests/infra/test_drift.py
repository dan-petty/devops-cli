"""Unit tests for infra drift detection, marker comments and issue lifecycle (#5127)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from devops_cli.exceptions.infra import InfraAccessRefusedError
from devops_cli.github.client import IssueSearchHit
from devops_cli.infra.access import AgentAccess
from devops_cli.infra.drift import (
    drift_entry,
    drift_marker,
    find_marker,
    manage_drift_issue,
    render_drift_issue_body,
)
from devops_cli.models.infra import (
    ChangedTask,
    HostPlan,
    InfraPlan,
    PlanContent,
    PlanStatus,
    PlanTask,
)

REPO = "dan-petty/homelab"
PLAN_ID = "a" * 64
COMMIT = "b" * 40


def _sample_plan(hosts: tuple[HostPlan, ...] = (), status: PlanStatus = PlanStatus.OK) -> InfraPlan:
    from datetime import UTC, datetime

    content = PlanContent(
        repo=REPO,
        ref="origin/main",
        commit=COMMIT,
        playbook="site.yaml",
        limit=None,
        host_pattern="all:!offline",
        tags=None,
        inventory_hash="hash",
        status=status,
        hosts=hosts,
    )
    return InfraPlan(
        **content.model_dump(),
        id=PLAN_ID,
        created=datetime.now(UTC),
        runner_ident="ident",
        folder="/var/run/devops-cli/plan",
    )


def test_drift_marker_round_trip() -> None:
    """The marker string can be extracted from arbitrary text."""
    marker = drift_marker(REPO, PLAN_ID)
    body = f"Issue header\n\n{marker}\n\nSome other notes."
    assert find_marker(body) == (REPO, PLAN_ID)


def test_find_marker_returns_none_when_absent() -> None:
    assert find_marker("A normal issue body without marker.") is None
    assert find_marker(None) is None


def test_render_drift_issue_body_contains_required_fields() -> None:
    """Issue body names the marker, the hosts, changed tasks, unchecked tasks, and plan id."""
    host = HostPlan(
        host="node-1.example.com",
        changed=(
            ChangedTask(
                name="Configure kubelet service",
                path="ansible/roles/kubelet/tasks/main.yaml:25",
                action="ansible.builtin.template",
            ),
        ),
        unchecked=(
            PlanTask(
                name="Verify cluster membership",
                path="ansible/roles/k8s/tasks/main.yaml:50",
                action="ansible.builtin.command",
            ),
        ),
    )
    body = render_drift_issue_body(REPO, COMMIT, PLAN_ID, [host])

    assert drift_marker(REPO, PLAN_ID) in body
    assert "node-1.example.com" in body
    assert "Configure kubelet service" in body
    assert "ansible/roles/kubelet/tasks/main.yaml:25" in body
    assert "Verify cluster membership" in body
    assert PLAN_ID in body


def test_manage_drift_issue_creates_when_drift_and_no_marker_open() -> None:
    client = MagicMock()
    client.search_issue_bodies.return_value = []
    client.create_issue.return_value = 42

    host = HostPlan(
        host="node-1.example.com",
        changed=(
            ChangedTask(
                name="Deploy config",
                path="roles/test:10",
                action="template",
            ),
        ),
    )
    plan = _sample_plan(hosts=(host,))

    result = manage_drift_issue(client, REPO, plan, [host])

    assert "#42" in (result or "")
    client.create_issue.assert_called_once()
    args, kwargs = client.create_issue.call_args
    assert args[0] == REPO
    assert drift_marker(REPO, PLAN_ID) in kwargs["body"]


def test_manage_drift_issue_sends_no_write_when_plan_id_matches() -> None:
    """A second run with the exact same plan id sends no write request."""
    client = MagicMock()
    existing_marker = drift_marker(REPO, PLAN_ID)
    hit = IssueSearchHit(
        number=42,
        state="open",
        body=f"Previous text\n{existing_marker}\nMore text",
    )
    client.search_issue_bodies.return_value = [hit]

    host = HostPlan(
        host="node-1.example.com",
        changed=(
            ChangedTask(
                name="Deploy config",
                path="roles/test:10",
                action="template",
            ),
        ),
    )
    plan = _sample_plan(hosts=(host,))

    result = manage_drift_issue(client, REPO, plan, [host])

    assert "unchanged" in (result or "").lower()
    client.create_issue.assert_not_called()
    client.update_issue_body.assert_not_called()
    client.close_issue.assert_not_called()


def test_manage_drift_issue_updates_when_plan_id_differs() -> None:
    """A run with new drift facts updates the existing open issue."""
    client = MagicMock()
    old_marker = drift_marker(REPO, "old" + "0" * 61)
    hit = IssueSearchHit(
        number=42,
        state="open",
        body=f"Previous text\n{old_marker}\nMore text",
    )
    client.search_issue_bodies.return_value = [hit]

    host = HostPlan(
        host="node-1.example.com",
        changed=(
            ChangedTask(
                name="Deploy config",
                path="roles/test:10",
                action="template",
            ),
        ),
    )
    plan = _sample_plan(hosts=(host,))

    result = manage_drift_issue(client, REPO, plan, [host])

    assert "updated" in (result or "").lower()
    client.create_issue.assert_not_called()
    client.update_issue_body.assert_called_once_with(
        REPO, 42, render_drift_issue_body(REPO, COMMIT, PLAN_ID, [host])
    )


def test_manage_drift_issue_closes_issue_when_drift_cleared() -> None:
    """When a run finds no drift, any open marker issue is closed."""
    client = MagicMock()
    marker = drift_marker(REPO, "old" + "0" * 61)
    hit = IssueSearchHit(
        number=42,
        state="open",
        body=f"Previous text\n{marker}\nMore text",
    )
    client.search_issue_bodies.return_value = [hit]

    plan = _sample_plan(hosts=())

    result = manage_drift_issue(client, REPO, plan, [])

    assert "closed" in (result or "").lower()
    client.close_issue.assert_called_once_with(REPO, 42, reason="completed")


def test_drift_entry_enforces_agent_access(agent_caller: None) -> None:
    from pathlib import Path

    from devops_cli.config.settings import Settings
    from devops_cli.github.repo_ref import RepoRef
    from devops_cli.infra.onboard import OnboardTarget

    target = OnboardTarget(
        repo=RepoRef(REPO),
        path=Path("/var/run/devops-cli/homelab"),
        default_path=Path("/var/run/devops-cli/homelab"),
    )

    # Access level none raises
    settings_none = Settings(infra={"repos": [{"repo": REPO, "agent_access": "none"}]})
    with pytest.raises(InfraAccessRefusedError) as exc_info:
        drift_entry(target, settings_none)
    assert "devops infra drift" in str(exc_info.value)

    # Access level plan succeeds
    settings_plan = Settings(infra={"repos": [{"repo": REPO, "agent_access": "plan"}]})
    entry = drift_entry(target, settings_plan)
    assert entry.agent_access is AgentAccess.PLAN
