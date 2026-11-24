"""Tests for roadmap step `infra-apply` (#5130)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

from devops_cli.config.settings import InfraConfig, InfraRepoConfig, Settings
from devops_cli.github.client import IssueComment
from devops_cli.github.repo_ref import RepoRef, ServiceRow
from devops_cli.infra.access import AgentAccess
from devops_cli.models.infra import (
    ApplyReport,
    ApplyResult,
    FailedTask,
    HostApply,
    HostOutcome,
    HostPlan,
    InfraPlan,
    PlanStatus,
)
from devops_cli.roadmap.steps.comment import Target
from devops_cli.roadmap.steps.infra_apply import (
    INFRA_APPLY_MARKER,
    infra_apply_unit,
    launch_infra_apply,
    manage_apply_failure_issue,
    run_infra_apply,
)

REPO = "owner/infra"
COMMIT = "a" * 40
PULL = 123


class _MemoryTarget(Target):
    def __init__(self, repo: str, number: int) -> None:
        super().__init__(repo, number)
        self.comments: list[IssueComment] = []
        self._next_id = 1

    @property
    def session_login(self) -> str:
        return "bot"

    def list_comments(self) -> list[IssueComment]:
        return list(self.comments)

    def create_comment(self, body: str) -> int:
        cid = self._next_id
        self._next_id += 1
        self.comments.append(IssueComment(id=cid, body=body, author="bot"))
        return cid

    def update_comment(self, comment_id: int | None, body: str) -> None:
        for i, c in enumerate(self.comments):
            if c.id == comment_id:
                self.comments[i] = IssueComment(id=c.id, body=body, author=c.author)
                break


def _sample_plan(
    *,
    status: PlanStatus = PlanStatus.OK,
    hosts: tuple[HostPlan, ...] = (),
) -> InfraPlan:
    return InfraPlan(
        id="b" * 64,
        repo=REPO,
        playbook="site.yaml",
        ref="origin/main",
        commit=COMMIT,
        limit=None,
        tags=None,
        status=status,
        created=datetime.now(UTC),
        hosts=hosts,
        host_pattern="all",
        inventory_hash="abc",
        runner_ident="1",
        folder="/var/run/devops-cli/plans/abc",
    )


def _sample_report(
    *,
    result: ApplyResult = ApplyResult.OK,
    reason: str | None = None,
    hosts: tuple[HostApply, ...] = (),
) -> ApplyReport:
    return ApplyReport(
        id="c" * 32,
        repo=REPO,
        plan_id="b" * 64,
        commit=COMMIT,
        ref="refs/heads/main",
        playbook="site.yaml",
        limit=None,
        tags=None,
        caller="agent",
        tool="job",
        level="safe",
        result=result,
        reason=reason,
        hosts=hosts,
        left_out_alerts=(),
        started=datetime.now(UTC),
        duration_seconds=12.5,
        folder="/var/run/devops-cli/apply",
    )


def test_infra_apply_unit_properties() -> None:
    unit = infra_apply_unit(REPO, PULL, COMMIT, playbook="deploy.yaml")
    assert unit.row == ServiceRow.INFRA_APPLY
    assert unit.repo == RepoRef(REPO)
    assert unit.item == PULL
    assert unit.args == (
        "roadmap",
        "step",
        "infra-apply",
        "--repo",
        REPO,
        "--pull",
        str(PULL),
        "--commit",
        COMMIT,
        "--playbook",
        "deploy.yaml",
    )
    assert unit.annotations["roadmap.devops-cli/commit"] == COMMIT


def test_launch_infra_apply_refuses_plan_and_none_levels() -> None:
    settings = Settings(
        infra=InfraConfig(
            repos=[
                InfraRepoConfig(repo="owner/none-repo", agent_access=AgentAccess.NONE),
                InfraRepoConfig(repo="owner/plan-repo", agent_access=AgentAccess.PLAN),
                InfraRepoConfig(repo="owner/safe-repo", agent_access=AgentAccess.SAFE),
            ]
        )
    )
    jobs = MagicMock()
    jobs.create.return_value = "job-123"

    assert launch_infra_apply("owner/none-repo", 1, COMMIT, settings=settings, jobs=jobs) is None
    assert launch_infra_apply("owner/plan-repo", 1, COMMIT, settings=settings, jobs=jobs) is None
    assert (
        launch_infra_apply("owner/safe-repo", 1, COMMIT, settings=settings, jobs=jobs) == "job-123"
    )


def test_run_infra_apply_refuses_repo_below_safe(tmp_path: Path) -> None:
    settings = Settings(
        infra=InfraConfig(
            repos=[InfraRepoConfig(repo=REPO, path=tmp_path, agent_access=AgentAccess.PLAN)]
        )
    )
    target = _MemoryTarget(REPO, PULL)
    plan_mock = MagicMock()
    apply_mock = MagicMock()

    code = run_infra_apply(
        REPO,
        PULL,
        COMMIT,
        settings=settings,
        target=target,
        plan_runner=plan_mock,
        apply_runner=apply_mock,
    )
    assert code == 0
    plan_mock.assert_not_called()
    apply_mock.assert_not_called()
    assert target.comments == []


def test_run_infra_apply_failed_plan_creates_comment_and_issue(tmp_path: Path) -> None:
    settings = Settings(
        infra=InfraConfig(
            repos=[InfraRepoConfig(repo=REPO, path=tmp_path, agent_access=AgentAccess.SAFE)]
        )
    )
    target = _MemoryTarget(REPO, PULL)
    client = MagicMock()
    client.search_issue_bodies.return_value = []
    client.create_issue.return_value = 456

    failed_task = FailedTask(
        name="Install k3s", path="roles/k3s/tasks/main.yaml", action="command", reason="error 500"
    )
    host = HostPlan(host="node-1.example.com", failed=(failed_task,))
    plan_record = _sample_plan(status=PlanStatus.FAILED, hosts=(host,))
    read_mock = MagicMock(ref="origin/main", commit=COMMIT, checkout_differs=False)

    apply_mock = MagicMock()

    code = run_infra_apply(
        REPO,
        PULL,
        COMMIT,
        settings=settings,
        client=client,
        target=target,
        plan_runner=lambda *_: (plan_record, read_mock),
        apply_runner=apply_mock,
    )
    assert code == 1
    apply_mock.assert_not_called()
    assert len(target.comments) == 1
    assert INFRA_APPLY_MARKER in target.comments[0].body
    assert "Plan failed; apply not started" in target.comments[0].body
    client.create_issue.assert_called_once()
    issue_args = client.create_issue.call_args[1]
    assert issue_args["title"] == f"fix(infra): apply failed on node-1.example.com in {REPO}"
    assert "error 500" in issue_args["body"]


def test_run_infra_apply_success(tmp_path: Path) -> None:
    settings = Settings(
        infra=InfraConfig(
            repos=[InfraRepoConfig(repo=REPO, path=tmp_path, agent_access=AgentAccess.SAFE)]
        )
    )
    target = _MemoryTarget(REPO, PULL)
    client = MagicMock()

    host_plan = HostPlan(host="node-1.example.com")
    plan_record = _sample_plan(status=PlanStatus.OK, hosts=(host_plan,))
    read_mock = MagicMock(ref="origin/main", commit=COMMIT, checkout_differs=False)

    host_apply = HostApply(host="node-1.example.com", node="node-1", outcome=HostOutcome.APPLIED)
    report = _sample_report(result=ApplyResult.OK, hosts=(host_apply,))

    code = run_infra_apply(
        REPO,
        PULL,
        COMMIT,
        settings=settings,
        client=client,
        target=target,
        plan_runner=lambda *_: (plan_record, read_mock),
        apply_runner=lambda *_, **__: report,
    )
    assert code == 0
    assert len(target.comments) == 1
    assert INFRA_APPLY_MARKER in target.comments[0].body
    assert "Audit record (infra.apply)" in target.comments[0].body
    client.create_issue.assert_not_called()


def test_run_infra_apply_stopped_own_node_creates_comment_and_issue(tmp_path: Path) -> None:
    settings = Settings(
        infra=InfraConfig(
            repos=[InfraRepoConfig(repo=REPO, path=tmp_path, agent_access=AgentAccess.SAFE)]
        )
    )
    target = _MemoryTarget(REPO, PULL)
    client = MagicMock()
    client.search_issue_bodies.return_value = []
    client.create_issue.return_value = 789

    plan_record = _sample_plan(status=PlanStatus.OK)
    read_mock = MagicMock(ref="origin/main", commit=COMMIT, checkout_differs=False)

    reason = "The host node-2.example.com (node-2) is its pod node. Run devops infra apply on a workstation."
    host_apply = HostApply(
        host="node-2.example.com", node="node-2", outcome=HostOutcome.STOPPED, reason=reason
    )
    report = _sample_report(result=ApplyResult.STOPPED, reason=reason, hosts=(host_apply,))

    code = run_infra_apply(
        REPO,
        PULL,
        COMMIT,
        settings=settings,
        client=client,
        target=target,
        plan_runner=lambda *_: (plan_record, read_mock),
        apply_runner=lambda *_, **__: report,
    )
    assert code == 1
    assert len(target.comments) == 1
    assert INFRA_APPLY_MARKER in target.comments[0].body
    assert "is its pod node" in target.comments[0].body
    client.create_issue.assert_called_once()
    issue_args = client.create_issue.call_args[1]
    assert issue_args["title"] == f"fix(infra): apply failed on node-2.example.com in {REPO}"
    assert "Run devops infra apply on a workstation" in issue_args["body"]


def test_second_run_edits_existing_comment_and_creates_no_second(tmp_path: Path) -> None:
    settings = Settings(
        infra=InfraConfig(
            repos=[InfraRepoConfig(repo=REPO, path=tmp_path, agent_access=AgentAccess.SAFE)]
        )
    )
    target = _MemoryTarget(REPO, PULL)
    client = MagicMock()

    plan_record = _sample_plan(status=PlanStatus.OK)
    read_mock = MagicMock(ref="origin/main", commit=COMMIT, checkout_differs=False)
    report = _sample_report(result=ApplyResult.OK)

    # First run
    code1 = run_infra_apply(
        REPO,
        PULL,
        COMMIT,
        settings=settings,
        client=client,
        target=target,
        plan_runner=lambda *_: (plan_record, read_mock),
        apply_runner=lambda *_, **__: report,
    )
    assert code1 == 0
    assert len(target.comments) == 1

    # Second run with same report
    code2 = run_infra_apply(
        REPO,
        PULL,
        COMMIT,
        settings=settings,
        client=client,
        target=target,
        plan_runner=lambda *_: (plan_record, read_mock),
        apply_runner=lambda *_, **__: report,
    )
    assert code2 == 0
    assert len(target.comments) == 1


def test_manage_apply_failure_issue_updates_existing_open_issue() -> None:
    client = MagicMock()
    existing_issue = MagicMock(
        number=101,
        state="open",
        body="<!-- devops roadmap infra-apply failure: repo=owner/infra host=node-1.example.com -->\nOld body",
    )
    client.search_issue_bodies.return_value = [existing_issue]

    msg = manage_apply_failure_issue(client, REPO, COMMIT, "node-1.example.com", "Timeout reached")
    assert msg == f"Updated issue #101 in {REPO} for host node-1.example.com."
    client.update_issue_body.assert_called_once()
    client.create_issue.assert_not_called()
