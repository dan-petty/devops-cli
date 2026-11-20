"""MCP server image invariants: what the committed `Dockerfile` and `ci.yml` must hold
for the image of the MCP server (#3220).

They read only committed files, so they need no network, no image build and no scanner.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from devops_cli.tools_lock import load_tools_lock
from tests.support.dockerfile import env_of, stages
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.paths import REPO_ROOT


def _stages() -> dict[str, list[list[str]]]:
    return stages((REPO_ROOT / "Dockerfile").read_text(encoding="utf-8"))


def _workflow(name: str) -> dict[str, Any]:
    parsed = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / name).read_text("utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _step(job: dict[str, Any], name: str) -> dict[str, Any]:
    return next(step for step in job["steps"] if step.get("name") == name)


def test_the_mcp_server_stage_runs_as_user_1000_and_keeps_directories_under_home() -> None:
    """The mcp-server target SHALL run as user 1000:1000 and keep data and uv cache under HOME."""
    mcp_stage = _stages()["mcp-server"]
    users = [words[1] for words in mcp_stage if words[0].upper() == "USER"]
    env = env_of(mcp_stage)

    assert users[-1] == "1000:1000"
    assert env["DEVOPS_CLI_DATA_DIR"].startswith(env["HOME"])
    assert env["UV_CACHE_DIR"].startswith(env["HOME"])


def test_the_pull_request_check_builds_the_mcp_server_target_at_or_below_3gb() -> None:
    """The pull request check SHALL build the mcp-server target and keep it at or below 3GB."""
    job = _workflow("ci.yml")["jobs"]["mcp-server-image"]
    build = _step(job, "Build and Load MCP Server Image")
    smoke = _step(job, "Run MCP Server Image Smoke Test")["run"]

    assert build["with"]["target"] == "mcp-server"

    (bound,) = re.findall(r'"\$size" -gt (\d+)', smoke)
    assert int(bound) <= 3000000000


def test_the_kubectl_and_helm_pins_hold_the_go_builds_that_fix_the_stdlib_findings() -> None:
    """tools.lock SHALL pin kubectl 1.37.2 or newer and helm 4.3.2 or newer (#4336, #5573).

    The older releases hold Go standard library findings that no ignore entry lists:
    CVE-2026-78667 and CVE-2026-97031 (kubectl), and CVE-2026-111943 (helm 4.3.1 has Go 1.27.2,
    helm 4.3.2 has Go 1.27.4). A bump back below the floor fails the image scan.
    """
    tools = load_tools_lock().tools()

    def numbers(version: str) -> tuple[int, ...]:
        return tuple(int(part) for part in version.split("."))

    assert numbers(tools["kubectl"].version) >= (1, 37, 2)
    assert numbers(tools["helm"].version) >= (4, 3, 2)


def test_the_tool_version_check_fails_on_mismatch_and_names_the_tool(
    process_fake: ProcessFake,
) -> None:
    """When a tool is off-pin, devops install-tools --check fails and names the tool."""
    process_fake.answer(
        ["devops", "install-tools", "--check", "--tool", "kubectl"],
        ProcessAnswer(returncode=1, stderr="kubectl 1.37.1: not installed\n"),
    )
    from devops_cli.core.process import run_subprocess

    done = run_subprocess(["devops", "install-tools", "--check", "--tool", "kubectl"])
    assert done.returncode == 1
    assert "kubectl" in done.stderr


def test_the_change_records_the_findings_and_the_date() -> None:
    """The proposal of #5582 records the three findings of kubectl v1.37.2 and their proof date."""
    proposals = list((REPO_ROOT / "openspec" / "changes").glob("*5582*/proposal.md")) + list(
        (REPO_ROOT / "openspec" / "changes" / "archive").glob("*5582*/proposal.md")
    )
    assert len(proposals) >= 1
    text = proposals[0].read_text(encoding="utf-8")
    for expected in (
        "CVE-2026-56851",
        "CVE-2026-78669",
        "CVE-2026-78661",
        "golang.org/x/net 0.57.0",
        "golang.org/x/text 0.40.0",
        "0.62.0",
        "0.41.0",
        "2026-11-14",
    ):
        assert expected in text
