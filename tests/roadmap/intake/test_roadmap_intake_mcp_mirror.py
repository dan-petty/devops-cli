"""The MCP mirror of `devops roadmap intake`: it plans by default and builds a command line that
the CLI accepts (#1335).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from devops_cli.ai.mcp import server as mcp_server
from devops_cli.ai.mcp.dispatcher import get_mcp_dispatcher, install_mcp_dispatcher
from tests.support.roadmap_intake import REPO, FakeModel, Roadmap

# ── Agent candidates (#1959) ──────────────────────────────────────────────────


PARENT = "https://github.com/example/roadmap/issues/1"


class _RecordingDispatcher:
    """The MCP dispatcher, in this process, that notes each exit code and each body file the
    command line names while the file exists."""

    def __init__(self, exits: list[int], body_files: list[Path]) -> None:
        self._real = get_mcp_dispatcher()
        self._exits = exits
        self._body_files = body_files

    def dispatch(
        self, cmd: list[str], timeout: float = 30.0, env: dict[str, str] | None = None
    ) -> tuple[int, str]:
        if "--body-file" in cmd:
            self._body_files.append(Path(cmd[cmd.index("--body-file") + 1]))
        code, output = self._real.dispatch(cmd, timeout=timeout, env=env)
        self._exits.append(code)
        return code, output


def test_the_mcp_mirror_plans_by_default_and_builds_a_command_line_the_cli_accepts(
    opened: Roadmap, fake_model: FakeModel, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened.issue("feat: from mcp")
    monkeypatch.chdir(tmp_path)
    tool = asyncio.run(mcp_server.mcp.get_tool("roadmap_intake"))
    names = {listed.name for listed in asyncio.run(mcp_server.mcp._list_tools())}
    exits: list[int] = []
    body_files: list[Path] = []
    before = len(opened.store.job_writes())
    temp_body = tmp_path / "body.txt"
    temp_body.write_text("text", encoding="utf-8")
    install_mcp_dispatcher(_RecordingDispatcher(exits, body_files))
    planned = mcp_server.roadmap_intake(repo=REPO)
    mcp_server.roadmap_intake(repo=REPO, issue=[1])
    mcp_server.roadmap_intake(
        repo=REPO,
        title="feat: via mcp",
        body_file=temp_body,
        source=PARENT,
    )
    previewed = len(opened.store.job_writes())
    mcp_server.roadmap_intake(repo=REPO, confirm=True)
    properties = tool.parameters["properties"] if tool else {}
    assert (
        "roadmap_intake" in names,
        "confirm" in properties,
        "proposal call(s)" in planned,
        exits,
        previewed - before,
        len(opened.store.job_writes()) > previewed,
        [path.exists() for path in body_files],
    ) == (True, True, True, [0, 0, 0, 0], 0, True, [True])


def test_the_mcp_mirror_dry_run_makes_no_request(no_requests: None) -> None:
    exits: list[int] = []
    install_mcp_dispatcher(_RecordingDispatcher(exits, []))
    output = mcp_server.roadmap_intake(repo=REPO, dry_run=True, issue=[3])
    assert (exits, "Dry run: no request was made" in output) == ([0], True)
