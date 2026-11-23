"""The stage agent is stock `Coder` with the three checks of the plan (#6705).

The agent is one pydantic-ai `Agent`: `LocalWorkspace` at the clone of `prepare` with a scratch
home and the configuration of `publish`, `Coder` with no repository context and no `delegate_task`,
`RequireVerification` with the three checks in order and no exempt path, and `Hooks`. It has no
tool of its own.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai import Agent
from pydantic_ai.capabilities import LocalWorkspace
from pydantic_ai_harness.coder import Coder
from pydantic_ai_harness.repo_context import RepoContext
from pydantic_ai_harness.require_verification import RequireVerification
from pydantic_ai_harness.shell import MAX_FOREGROUND_WAIT, Shell
from pydantic_ai_harness.sub_agents import SubAgents

from devops_cli.roadmap.stage.stage_agent import StageRunLog, build_stage_agent
from tests.support.model_script import ModelScript, say

BASE = "0123456789abcdef0123456789abcdef01234567"
CHANGE = "1-the-job-drops-a-comment"
LISTING = "/run/roadmap/work/issues.json"
CANDIDATE = "PLAN_PULL_REQUEST.md"


def _agent(tmp_path: Path, script: ModelScript) -> Agent[None, str]:
    return build_stage_agent(
        script.model(),
        tmp_path / "clone",
        home=tmp_path / "home",
        config=tmp_path / "config.yaml",
        instructions="Plan the item.",
        window=200_000,
        deadline=datetime.now(UTC) + timedelta(hours=1),
        log=StageRunLog(),
    )


def _leaves(agent: Agent[None, str]) -> list[Any]:
    found: list[Any] = []
    agent.root_capability.apply(found.append)
    return found


def _verification(tmp_path: Path) -> RequireVerification[None]:
    (tmp_path / "clone").mkdir(exist_ok=True)
    (check,) = [
        leaf
        for leaf in _leaves(_agent(tmp_path, ModelScript(say("done"))))
        if isinstance(leaf, RequireVerification)
    ]
    return check


def test_the_stage_agent_is_coder_on_the_clone_with_the_three_checks_and_no_stage_tool(
    tmp_path: Path,
) -> None:
    (tmp_path / "clone").mkdir()
    script = ModelScript(say("done"))
    agent = _agent(tmp_path, script)

    top = list(getattr(agent.root_capability, "capabilities", ()))
    workspaces = [cap for cap in top if isinstance(cap, LocalWorkspace)]
    assert [(Path(w.working_dir), dict(w.env or {})) for w in workspaces] == [
        (
            tmp_path / "clone",
            {
                "HOME": str(tmp_path / "home"),
                "DEVOPS_CLI_CONFIG": str(tmp_path / "config.yaml"),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_TERMINAL_PROMPT": "0",
            },
        )
    ]
    leaves = _leaves(agent)
    stock_leaves: list[Any] = []
    Coder(repo_context=False, sub_agents=False).apply(stock_leaves.append)
    assert {type(leaf) for leaf in stock_leaves} <= {type(leaf) for leaf in leaves}
    assert not [leaf for leaf in leaves if isinstance(leaf, RepoContext | SubAgents)]
    shells = [leaf for leaf in leaves if isinstance(leaf, Shell)]
    assert [(list(shell.tools), shell.default_timeout) for shell in shells] == [
        (["shell"], MAX_FOREGROUND_WAIT)
    ]
    (check,) = [leaf for leaf in leaves if isinstance(leaf, RequireVerification)]
    assert tuple(check.exempt_paths) == ()
    assert len(check.verification_commands) == 3

    stock = ModelScript(say("done"))
    Agent(
        stock.model(),
        capabilities=[
            LocalWorkspace(tmp_path / "clone"),
            Coder(repo_context=False, sub_agents=False),
        ],
    ).run_sync("go")
    agent.run_sync("go")
    assert script.tools_offered == stock.tools_offered
    assert "delegate_task" not in script.tools_offered[0]


@pytest.mark.parametrize(
    ("command", "check"),
    [
        pytest.param("devops openspec check", 0, id="openspec-check"),
        pytest.param("uv run devops openspec check", 0, id="openspec-check-uv"),
        pytest.param(f"openspec validate {CHANGE} --strict", 1, id="validate"),
        pytest.param(
            f"devops roadmap plan-recheck --source . --branch HEAD --base {BASE} "
            f"--candidate {CANDIDATE} --issues {LISTING}",
            2,
            id="recheck",
        ),
        pytest.param("devops openspec check --help", None, id="probe"),
        pytest.param(f"openspec validate {CHANGE}", None, id="validate-not-strict"),
        pytest.param("devops roadmap plan-recheck --source . --branch HEAD", None, id="no-base"),
        pytest.param(
            f"devops roadmap plan-recheck --source . --branch HEAD --base {BASE}",
            None,
            id="no-candidate",
        ),
        pytest.param("devops openspec check | tail -5", None, id="piped"),
    ],
)
def test_each_check_counts_and_a_probe_or_a_recheck_with_no_base_does_not(
    tmp_path: Path, command: str, check: int | None
) -> None:
    import re

    verification = _verification(tmp_path)
    matches = [
        index
        for index, pattern in enumerate(verification.verification_commands)
        if re.match(pattern, command)
    ]

    assert verification._verifies(command) is (check is not None)
    if check is not None:
        assert matches == [check]
