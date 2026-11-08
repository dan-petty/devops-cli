"""MCP server image invariants: what the committed `Dockerfile` and `ci.yml` must hold
for the image of the MCP server (#3220).

They read only committed files, so they need no network, no image build and no scanner.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import yaml

from devops_cli.tools_lock import load_tools_lock
from tests.support.dockerfile import env_of, stages
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.paths import REPO_ROOT
from tests.support.trivyignore import trivyignore_problems as _trivyignore_problems


def _stages() -> dict[str, list[list[str]]]:
    return stages((REPO_ROOT / "Dockerfile").read_text(encoding="utf-8"))


def _workflow(name: str) -> dict[str, Any]:
    parsed = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / name).read_text("utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _step(job: dict[str, Any], name: str) -> dict[str, Any]:
    return next(step for step in job["steps"] if step.get("name") == name)


def test_the_mcp_server_stage_inherits_runner() -> None:
    """The Dockerfile SHALL add an mcp-server target that inherits the runner stage."""
    all_stages = _stages()
    assert "mcp-server" in all_stages
    mcp_stage = all_stages["mcp-server"]
    from_line = next(words for words in mcp_stage if words[0].upper() == "FROM")
    assert from_line[1] == "runner"


def test_the_mcp_server_stage_installs_kubectl_and_helm_at_pinned_versions() -> None:
    """The mcp-server target SHALL install kubectl and helm at the versions that tools.lock pins."""
    mcp_stage = _stages()["mcp-server"]
    runs = [" ".join(words[1:]) for words in mcp_stage if words[0].upper() == "RUN"]
    joined = " ".join(runs)

    assert "install-tools" in joined
    assert "--tool kubectl" in joined
    assert "--tool helm" in joined
    assert "--check" in joined

    lock = load_tools_lock().tools()
    assert "kubectl" in lock
    assert "helm" in lock


def test_the_mcp_server_stage_runs_as_user_1000_and_keeps_directories_under_home() -> None:
    """The mcp-server target SHALL run as user 1000:1000 and keep data and uv cache under HOME."""
    mcp_stage = _stages()["mcp-server"]
    users = [words[1] for words in mcp_stage if words[0].upper() == "USER"]
    env = env_of(mcp_stage)

    assert users[-1] == "1000:1000"
    assert env["DEVOPS_CLI_DATA_DIR"].startswith(env["HOME"])
    assert env["UV_CACHE_DIR"].startswith(env["HOME"])


def test_the_service_stage_is_last_and_mcp_server_comes_before_it() -> None:
    """The service stage SHALL stay the last stage of the Dockerfile."""
    names = list(_stages())
    assert names[-1] == "service"
    assert names.index("mcp-server") < names.index("service")


def test_the_pull_request_check_builds_and_scans_mcp_server_image() -> None:
    """The mcp-server image SHALL pass the HIGH and CRITICAL scan and stay at or below 3GB."""
    job = _workflow("ci.yml")["jobs"]["mcp-server-image"]
    build = _step(job, "Build and Load MCP Server Image")
    trivy = _step(job, "Scan MCP Server Image for Vulnerabilities")["with"]
    smoke = _step(job, "Run MCP Server Image Smoke Test")["run"]

    assert build["with"]["target"] == "mcp-server"
    assert (
        trivy["scanners"],
        trivy["severity"],
        trivy["ignore-unfixed"],
        trivy["trivyignores"],
        str(trivy["exit-code"]),
    ) == ("vuln", "HIGH,CRITICAL", True, ".trivyignore,.trivyignore-mcp-server", "1")

    (bound,) = re.findall(r'"\$size" -gt (\d+)', smoke)
    assert int(bound) <= 3000000000


def test_every_mcp_server_trivyignore_entry_has_a_reason_and_an_exp_date_that_is_not_past() -> None:
    """Verify that each entry in `.trivyignore-mcp-server` has a reason and a future exp date."""
    text = (REPO_ROOT / ".trivyignore-mcp-server").read_text(encoding="utf-8")
    assert _trivyignore_problems(text, datetime.now(UTC).date()) == []


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
