"""MCP server image invariants: what the committed `ci.yml` must hold
for the image of the MCP server (#3220).

They read only committed files, so they need no network, no image build and no scanner.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from tests.support.paths import REPO_ROOT


def _workflow(name: str) -> dict[str, Any]:
    parsed = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / name).read_text("utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _step(job: dict[str, Any], name: str) -> dict[str, Any]:
    return next(step for step in job["steps"] if step.get("name") == name)


def test_the_pull_request_check_builds_the_mcp_server_target_at_or_below_3gb() -> None:
    """The pull request check SHALL build the mcp-server target and keep it at or below 3GB."""
    job = _workflow("ci.yml")["jobs"]["mcp-server-image"]
    build = _step(job, "Build and Load MCP Server Image")
    smoke = _step(job, "Run MCP Server Image Smoke Test")["run"]

    assert build["with"]["target"] == "mcp-server"

    (bound,) = re.findall(r'"\$size" -gt (\d+)', smoke)
    assert int(bound) <= 3000000000


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
