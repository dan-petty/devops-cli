"""The roadmap tools publish the parameters of their commands and build the argv of each."""

from __future__ import annotations

from tests.support.fakes.mcp_dispatcher import DispatcherFake


def _roadmap_tool_parameters(name: str) -> dict[str, object]:
    import asyncio

    from devops_cli.ai.mcp import server as mcp_server

    tool = asyncio.run(mcp_server.mcp.get_tool(name))
    assert tool is not None
    return dict(tool.parameters["properties"])


def test_the_roadmap_tools_are_registered_and_the_planner_tools_are_gone() -> None:
    """Roadmap tools publish Click parameters and default preview options; no tool renders,
    migrates, reprioritizes or closes, since those commands are gone."""
    import asyncio

    from devops_cli.ai.mcp import server as mcp_server

    run = _roadmap_tool_parameters("roadmap_run")
    gone = [
        asyncio.run(mcp_server.mcp.get_tool(name))
        for name in ("roadmap_render", "roadmap_migrate", "roadmap_reprioritize", "roadmap_close")
    ]
    assert (sorted(run), gone) == (["confirm", "dry_run", "repo"], [None] * 4)


def test_the_roadmap_tools_hydrate_with_the_roadmap_domain() -> None:
    from devops_cli.ai.mcp import server as mcp_server

    before = mcp_server._is_advertised("roadmap_refine")
    hydrated = mcp_server.hydrate_tool_domain("roadmap")["hydrated"]
    after = (mcp_server._is_advertised("roadmap_refine"), mcp_server._is_advertised("roadmap_run"))
    mcp_server.reset_hydrated_domains()
    assert (before, hydrated, after) == (False, True, (True, True))


def test_the_roadmap_tools_build_the_commands_argv(mcp_dispatcher: DispatcherFake) -> None:
    from devops_cli.ai.mcp.server import roadmap_run

    roadmap_run()
    roadmap_run(repo="dan-petty/devops-cli", dry_run=True)
    head = ["uv", "run", "devops", "roadmap"]
    assert [list(call.argv) for call in mcp_dispatcher.calls] == [
        [*head, "run"],
        [*head, "run", "--repo", "dan-petty/devops-cli", "--dry-run"],
    ]


def test_roadmap_refine_contract_and_argv(
    tmp_path, monkeypatch, mcp_dispatcher: DispatcherFake
) -> None:
    from devops_cli.ai.mcp.server import roadmap_refine

    monkeypatch.chdir(tmp_path)
    params = _roadmap_tool_parameters("roadmap_refine")
    assert "confirm" in params

    roadmap_refine(dry_run=True)
    roadmap_refine(
        repo="dan-petty/devops-cli",
        item=744,
        limit=1,
        source=".",
        dry_run=True,
    )

    head = ["uv", "run", "devops", "roadmap", "refine"]
    calls = [list(call.argv) for call in mcp_dispatcher.calls]
    assert (
        calls[0],
        calls[1],
        all(c[-1] == "--dry-run" for c in calls),
        any("--confirm" in c for c in calls),
    ) == (
        [*head, "--source", str(tmp_path), "--limit", "7", "--dry-run"],
        [
            *head,
            "--repo",
            "dan-petty/devops-cli",
            "--source",
            str(tmp_path),
            "--item",
            "744",
            "--limit",
            "1",
            "--dry-run",
        ],
        True,
        False,
    )


def test_roadmap_intake_argv_keeps_its_order_and_writes_only_on_confirm(
    mcp_dispatcher: DispatcherFake,
) -> None:
    """Verify roadmap_intake names each option and mode flag as written, in the CLI's order."""
    from devops_cli.ai.mcp.server import roadmap_intake

    roadmap_intake(
        repo="dan-petty/devops-cli",
        ref="feat/868-example",
        issue=[868],
        title="fix: example",
        source="https://example.com",
        confirm=True,
    )
    roadmap_intake(plan_only=True)
    roadmap_intake(dry_run=True)

    head = ["uv", "run", "devops", "roadmap", "intake"]
    assert [list(call.argv) for call in mcp_dispatcher.calls] == [
        [
            *head,
            "--repo",
            "dan-petty/devops-cli",
            "--ref",
            "feat/868-example",
            "--issue",
            "868",
            "--title",
            "fix: example",
            "--source",
            "https://example.com",
            "--filed-by",
            "agent",
            "--confirm",
        ],
        [*head, "--filed-by", "agent", "--plan"],
        [*head, "--filed-by", "agent", "--dry-run"],
    ]


def test_roadmap_consolidate_is_a_read_only_mirror_of_the_plan_run(
    mcp_dispatcher: DispatcherFake,
) -> None:
    """The tool publishes the options of the plan run only, so no argv holds a write (#3745)."""
    import asyncio

    from devops_cli.ai.mcp import server as mcp_server
    from devops_cli.ai.mcp.server import roadmap_consolidate

    tool = asyncio.run(mcp_server.mcp.get_tool("roadmap_consolidate"))
    read_only = tool.annotations.read_only_hint if tool and tool.annotations else None

    roadmap_consolidate()
    roadmap_consolidate(repo="dan-petty/devops-cli", ref="main", limit=2, dry_run=True)

    head = ["uv", "run", "devops", "roadmap", "consolidate"]
    calls = [list(call.argv) for call in mcp_dispatcher.calls]
    writes = {"--apply", "--confirm", "--decline"}
    assert (
        sorted(_roadmap_tool_parameters("roadmap_consolidate")),
        read_only,
        calls,
        [sorted(writes.intersection(c)) for c in calls],
    ) == (
        ["dry_run", "limit", "ref", "repo"],
        True,
        [
            head,
            [*head, "--repo", "dan-petty/devops-cli", "--ref", "main", "--limit", "2", "--dry-run"],
        ],
        [[], []],
    )
