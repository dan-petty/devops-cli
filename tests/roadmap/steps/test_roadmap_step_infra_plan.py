"""Tests for devops_cli.roadmap.steps.infra_plan: plan open infra PR and post marked comment (#5129)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from devops_cli.config.settings import InfraConfig, InfraRepoConfig, Settings
from devops_cli.github.repo_ref import ServiceRow
from devops_cli.infra.access import AgentAccess
from devops_cli.lang import MESSAGES
from devops_cli.models.infra import (
    ChangedTask,
    HostPlan,
    InfraPlan,
    PlanStatus,
    ReadCommit,
)
from devops_cli.roadmap.job_launcher import RunnerUnit
from devops_cli.roadmap.steps.infra_plan import (
    INFRA_PLAN_MARKER,
    infra_plan_unit,
    run_infra_plan,
)
from devops_cli.roadmap.stores.store import IssueComment

REPO = "owner/infra"
HEAD = "1234567890abcdef1234567890abcdef12345678"
PULL = 42


class FakeCommentTarget:
    """A test target for marked pull request comments."""

    def __init__(
        self,
        comments: list[IssueComment] | None = None,
        session_login: str = "devops-cli[bot]",
    ) -> None:
        self.comments: list[IssueComment] = list(comments or [])
        self.session_login = session_login

    def list_comments(self) -> list[IssueComment]:
        return list(self.comments)

    def create_comment(self, body: str) -> int:
        comment_id = len(self.comments) + 1
        self.comments.append(
            IssueComment(
                id=comment_id,
                body=body,
                created_at=datetime.now(UTC),
                author_login=self.session_login,
            )
        )
        return comment_id

    def update_comment(self, comment_id: int, body: str) -> None:
        for i, c in enumerate(self.comments):
            if c.id == comment_id:
                self.comments[i] = IssueComment(
                    id=comment_id,
                    body=body,
                    created_at=c.created_at,
                    author_login=c.author_login,
                )
                return


def _sample_plan(node_count: int = 1) -> tuple[InfraPlan, ReadCommit]:
    plan = InfraPlan(
        repo=REPO,
        ref="origin/main",
        commit=HEAD,
        playbook="site.yaml",
        limit=None,
        host_pattern="all",
        tags=None,
        inventory_hash="abcdef123456",
        status=PlanStatus.OK,
        error=None,
        hosts=tuple(
            HostPlan(
                host=f"node-{i}.example.com",
                changed=(
                    ChangedTask(
                        name="Configure node",
                        path="site.yaml:10",
                        action="ansible.builtin.template",
                    ),
                ),
            )
            for i in range(1, node_count + 1)
        ),
        id="plan123",
        created=datetime.now(UTC),
        runner_ident="ident123",
        folder="/var/run/devops-cli/plan",
    )
    read = ReadCommit(
        ref="main",
        commit=HEAD,
        checkout_branch="main",
        checkout_commit=HEAD,
    )
    return plan, read


def test_infra_plan_unit_returns_runner_unit() -> None:
    """The unit has row ServiceRow.INFRA_PLAN and points to the step."""
    unit = infra_plan_unit(REPO, PULL, HEAD)
    assert isinstance(unit, RunnerUnit)
    assert unit.row == ServiceRow.INFRA_PLAN
    assert unit.item == PULL
    assert unit.deadline == 7200
    assert unit.args == (
        "roadmap",
        "step",
        "infra-plan",
        "--repo",
        REPO,
        "--pull",
        str(PULL),
        "--head",
        HEAD,
        "--playbook",
        "site.yaml",
    )


def test_second_run_edits_existing_comment_and_creates_no_second(tmp_path: Path) -> None:
    """The first run creates one marked comment; the second run edits that comment."""
    settings = Settings(
        infra=InfraConfig(
            repos=[InfraRepoConfig(repo=REPO, path=tmp_path, agent_access=AgentAccess.PLAN)]
        )
    )
    target = FakeCommentTarget()

    # First run
    code1 = run_infra_plan(
        REPO,
        PULL,
        HEAD,
        settings=settings,
        target=target,
        plan_runner=lambda *_: _sample_plan(1),
    )
    assert code1 == 0
    assert len(target.comments) == 1
    assert INFRA_PLAN_MARKER in target.comments[0].body
    assert "node-1.example.com" in target.comments[0].body

    # Second run with different plan (node-2)
    code2 = run_infra_plan(
        REPO,
        PULL,
        HEAD,
        settings=settings,
        target=target,
        plan_runner=lambda *_: _sample_plan(2),
    )
    assert code2 == 0
    assert len(target.comments) == 1
    assert INFRA_PLAN_MARKER in target.comments[0].body
    assert "node-2.example.com" in target.comments[0].body


def test_repo_at_none_access_gets_no_plan_and_records_refusal(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A repo with agent_access 'none' exits 0, posts no comment, and records refusal."""
    settings = Settings(
        infra=InfraConfig(repos=[InfraRepoConfig(repo=REPO, agent_access=AgentAccess.NONE)])
    )
    target = FakeCommentTarget()

    with caplog.at_level(logging.INFO):
        code = run_infra_plan(REPO, PULL, HEAD, settings=settings, target=target)

    assert code == 0
    assert len(target.comments) == 0
    expected_msg = MESSAGES.infra.infra_plan_refused.format(repo=REPO)
    assert any(expected_msg in record.message for record in caplog.records)
