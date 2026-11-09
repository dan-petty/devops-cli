"""Each tool hands the command line that its parameters name to the dispatcher."""

from __future__ import annotations

from pathlib import Path

from tests.support.fakes.mcp_dispatcher import DispatcherFake


def test_fastmcp_library_tools_and_resource(mcp_dispatcher: DispatcherFake) -> None:
    """Verify library intelligence FastMCP tools and system resource execution."""

    from devops_cli.ai.mcp.server import (
        ai_ingest_library,
        ai_ingest_query_library,
        get_indexed_libraries_resource,
    )
    from devops_cli.config.defaults import (
        DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
    )

    mcp_dispatcher.answer('{"status": "ok"}')

    res = ai_ingest_library(package_name="typer", max_depth=2)
    assert res == '{"status": "ok"}'
    assert (list(mcp_dispatcher.last.argv), mcp_dispatcher.last.timeout) == (
        [
            "uv",
            "run",
            "devops",
            "ai",
            "ingest",
            "library",
            "typer",
            "--max-depth",
            "2",
            "--format",
            "json",
        ],
        DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
    )

    res = ai_ingest_query_library(query="command", package="typer", exact=True, top_k=3)
    assert res == '{"status": "ok"}'
    assert (list(mcp_dispatcher.last.argv), mcp_dispatcher.last.timeout) == (
        [
            "uv",
            "run",
            "devops",
            "ai",
            "ingest",
            "query-library",
            "command",
            "--package",
            "typer",
            "--exact",
            "--top-k",
            "3",
            "--format",
            "json",
        ],
        DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
    )

    # Test resource returns valid JSON
    resource_data = get_indexed_libraries_resource()
    assert isinstance(resource_data, str)
    assert resource_data.startswith("[")


def test_fastmcp_ast_tools(mcp_dispatcher: DispatcherFake) -> None:
    """Verify ai_ast_parse and ai_ast_graph FastMCP execution contracts."""

    from devops_cli.ai.mcp.server import ai_ast_graph, ai_ast_parse
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    mcp_dispatcher.answer('{"status": "ok"}')

    res = ai_ast_parse(file_path="src/main.py", query="(function_definition) @fn")
    assert res == '{"status": "ok"}'
    assert (list(mcp_dispatcher.last.argv), mcp_dispatcher.last.timeout) == (
        [
            "uv",
            "run",
            "devops",
            "ai",
            "ast",
            "parse",
            str(Path("src/main.py").resolve()),
            "--query",
            "(function_definition) @fn",
            "--format",
            "json",
        ],
        DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
    )

    res = ai_ast_graph(target_dir="src", max_files=20)
    assert res == '{"status": "ok"}'
    assert (list(mcp_dispatcher.last.argv), mcp_dispatcher.last.timeout) == (
        [
            "uv",
            "run",
            "devops",
            "ai",
            "ast",
            "graph",
            "--dir",
            str(Path("src").resolve()),
            "--max-files",
            "20",
            "--format",
            "json",
        ],
        DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
    )


def test_fastmcp_context_packing_tool(mcp_dispatcher: DispatcherFake) -> None:
    """Verify ai_pack_context FastMCP execution contract."""

    from devops_cli.ai.mcp.server import ai_pack_context
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    mcp_dispatcher.answer('{"content": "..."}')

    res = ai_pack_context(
        target_path="src/main.py",
        referenced="main,app",
        max_tokens=500,
        strip_private=True,
        skeletonize=False,
    )
    assert res == '{"content": "..."}'
    assert (list(mcp_dispatcher.last.argv), mcp_dispatcher.last.timeout) == (
        [
            "uv",
            "run",
            "devops",
            "ai",
            "pack-context",
            str(Path("src/main.py").resolve()),
            "--referenced",
            "main,app",
            "--max-tokens",
            "500",
            "--strip-private",
            "--no-skeletonize",
            "--format",
            "json",
        ],
        DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
    )


def test_fastmcp_ai_read_tool(mcp_dispatcher: DispatcherFake) -> None:
    """Verify ai_read FastMCP execution contract."""

    from devops_cli.ai.mcp.server import ai_read
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    mcp_dispatcher.answer("# Outline content")

    res = ai_read(
        target_path="src/main.py",
        inspect=True,
        level=0,
        lines="10:50",
        symbol="App",
        format="markdown",
    )
    assert (res, list(mcp_dispatcher.last.argv)) == (
        "# Outline content",
        [
            "uv",
            "run",
            "devops",
            "ai",
            "read",
            str(Path("src/main.py").resolve()),
            "--inspect",
            "--level",
            "0",
            "--lines",
            "10:50",
            "--symbol",
            "App",
            "--format",
            "markdown",
        ],
    )
    assert mcp_dispatcher.last.timeout == DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS


def test_fastmcp_ai_rag_drift_tool(mcp_dispatcher: DispatcherFake) -> None:
    """Verify ai_rag_drift FastMCP execution contract."""

    from devops_cli.ai.mcp.server import ai_rag_drift
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    mcp_dispatcher.answer('{"drift_score": 0.0}')

    res = ai_rag_drift(path="src", auto_sync=True)
    assert res == '{"drift_score": 0.0}'
    assert (list(mcp_dispatcher.last.argv), mcp_dispatcher.last.timeout) == (
        [
            "uv",
            "run",
            "devops",
            "ai",
            "rag",
            "drift",
            str(Path("src").resolve()),
            "--auto-sync",
            "--format",
            "json",
        ],
        DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
    )


def test_fastmcp_pr_check_readiness_tool(mcp_dispatcher: DispatcherFake) -> None:
    """Verify pr_check_readiness FastMCP execution contract."""

    from devops_cli.ai.mcp.server import pr_check_readiness
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    mcp_dispatcher.answer("PR #187 satisfies merge readiness")

    res = pr_check_readiness(
        number=187,
        allow_blocked_state=True,
        repo="owner/repo",
    )
    expected_cmd = [
        "uv",
        "run",
        "devops",
        "pr",
        "check-readiness",
        "187",
        "--allow-blocked-state",
        "--repo",
        "owner/repo",
    ]
    assert (res, list(mcp_dispatcher.last.argv), mcp_dispatcher.last.timeout) == (
        "PR #187 satisfies merge readiness",
        expected_cmd,
        DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
    )


def test_fastmcp_pr_thread_resolve_tool(mcp_dispatcher: DispatcherFake) -> None:
    """Verify pr_threads_resolve FastMCP execution contract with without_reply option."""

    from devops_cli.ai.mcp.server import pr_threads_resolve
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    mcp_dispatcher.answer("Thread resolved")

    # Test default without_reply=False
    res_default = pr_threads_resolve(thread_ids=["PRRT_1"])
    cmd_default = [
        "uv",
        "run",
        "devops",
        "pr",
        "threads",
        "resolve",
        "PRRT_1",
    ]
    assert (res_default, list(mcp_dispatcher.last.argv), mcp_dispatcher.last.timeout) == (
        "Thread resolved",
        cmd_default,
        DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
    )

    # Test without_reply=True
    res_override = pr_threads_resolve(thread_ids=["PRRT_2"], without_reply=True)
    cmd_override = [
        "uv",
        "run",
        "devops",
        "pr",
        "threads",
        "resolve",
        "PRRT_2",
        "--without-reply",
    ]
    assert (res_override, list(mcp_dispatcher.last.argv), mcp_dispatcher.last.timeout) == (
        "Thread resolved",
        cmd_override,
        DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
    )


def test_fastmcp_pr_ready_tool(mcp_dispatcher: DispatcherFake) -> None:
    """Verify pr_ready FastMCP execution contract."""

    from devops_cli.ai.mcp.server import pr_ready

    mcp_dispatcher.answer("PR #212 is ready for review")

    res = pr_ready(
        number=212,
        monitor=False,
        force=True,
        repo="owner/repo",
    )
    assert "is ready for review" in res
    assert (list(mcp_dispatcher.last.argv), mcp_dispatcher.last.timeout) == (
        [
            "uv",
            "run",
            "devops",
            "pr",
            "ready",
            "212",
            "--repo",
            "owner/repo",
            "--force",
        ],
        180.0,
    )


def test_fastmcp_docker_sign_tool(mcp_dispatcher: DispatcherFake) -> None:
    """Verify docker_sign FastMCP execution contract."""

    from devops_cli.ai.mcp.server import docker_sign
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_TIMEOUT_SECONDS

    mcp_dispatcher.answer("Image signed successfully")

    res = docker_sign(
        image="example.com/app:1.0.0",
        key="/path/to/key.key",
        keyless=False,
        oidc_token="keyring:cosign_oidc",
        annotation=["env=prod"],
        upload=False,
        dry_run=True,
    )
    assert "Image signed successfully" in res
    assert (list(mcp_dispatcher.last.argv), mcp_dispatcher.last.timeout) == (
        [
            "uv",
            "run",
            "devops",
            "docker",
            "sign",
            "example.com/app:1.0.0",
            "--key",
            "/path/to/key.key",
            "--keyed",
            "--oidc-token",
            "keyring:cosign_oidc",
            "--annotation",
            "env=prod",
            "--no-upload",
            "--dry-run",
        ],
        DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
    )


def test_fastmcp_docker_verify_tool(mcp_dispatcher: DispatcherFake) -> None:
    """Verify docker_verify FastMCP execution contract."""

    from devops_cli.ai.mcp.server import docker_verify
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_TIMEOUT_SECONDS

    mcp_dispatcher.answer("Image verified successfully")

    res = docker_verify(
        image="example.com/app:1.0.0",
        key="/path/to/key.pub",
        certificate_identity="https://example.com/build.yml",
        certificate_oidc_issuer="https://example.com/oidc",
        attestation=True,
        predicate_type="slsaprovenance",
        insecure_ignore_tlog=True,
        dry_run=True,
    )
    assert "Image verified successfully" in res
    assert (list(mcp_dispatcher.last.argv), mcp_dispatcher.last.timeout) == (
        [
            "uv",
            "run",
            "devops",
            "docker",
            "verify",
            "example.com/app:1.0.0",
            "--key",
            "/path/to/key.pub",
            "--certificate-identity",
            "https://example.com/build.yml",
            "--certificate-oidc-issuer",
            "https://example.com/oidc",
            "--attestation",
            "--type",
            "slsaprovenance",
            "--insecure-ignore-tlog",
            "--dry-run",
        ],
        DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
    )


def test_docker_sandbox_hands_its_command_over_after_the_options_end(
    tmp_path, monkeypatch, mcp_dispatcher: DispatcherFake
) -> None:
    """`docker_sandbox` appended `command` straight after its own options (#980).

    `devops docker sandbox` parsed a leading `--root` or `--cpus 64` in that list as its own
    option, so a caller turned off the rootless default the tool never offered. `--` ends the
    options, as `sandbox_deploy` and `sandbox_exec` already did.
    """
    from devops_cli.ai.mcp.server import docker_sandbox

    monkeypatch.chdir(tmp_path)
    docker_sandbox(command=["--root", "id"], workspace=str(tmp_path))
    assert list(mcp_dispatcher.last.argv)[-3:] == ["--", "--root", "id"]


def test_a_delegated_command_receives_the_end_of_options_marker(monkeypatch) -> None:
    """The lazy proxy in front of each command group dropped `--` (#980).

    Click consumed the marker while collecting the proxy's extra arguments, so the command
    behind it parsed what followed as options. `sandbox_exec` and `sandbox_deploy` end their
    options with `--`, and `sandbox_exec(command=["--workdir", "/", "id"])` set the workdir.
    """
    from typer.testing import CliRunner

    import devops_cli.main as main_module

    delegated: list[str] = []
    monkeypatch.setattr(
        main_module, "_delegate", lambda _module, _name, args: delegated.extend(args)
    )
    result = CliRunner().invoke(
        main_module.app, ["sandbox", "exec", "abc", "--", "--workdir", "/", "id"]
    )
    assert (result.exit_code, delegated) == (0, ["exec", "abc", "--", "--workdir", "/", "id"])


def test_fastmcp_k8s_security_stream(mcp_dispatcher: DispatcherFake) -> None:
    from devops_cli.ai.mcp.server import k8s_security_stream

    mcp_dispatcher.answer('{"total_alerts": 1}')

    res = k8s_security_stream(namespace="falco", severity="Critical", tail=50, simulate=True)

    cmd = mcp_dispatcher.last.argv
    assert res == '{"total_alerts": 1}'
    assert mcp_dispatcher.call_count == 1
    assert "security-stream" in cmd
    assert "--simulate" in cmd
    assert "--severity" in cmd
    assert "Critical" in cmd


def test_fastmcp_ai_cost_report_range_and_by(mcp_dispatcher: DispatcherFake) -> None:
    """Verify ai_cost_report forwards since, until, and by grouping to the CLI (#2193)."""
    from devops_cli.ai.mcp.server import ai_cost_report

    mcp_dispatcher.answer("[]")

    res = ai_cost_report(since="2026-10-01", until="2026-10-22", by="week")

    cmd = list(mcp_dispatcher.last.argv)
    assert res == "[]"
    assert mcp_dispatcher.call_count == 1
    assert cmd[:6] == ["uv", "run", "devops", "ai", "cost", "report"]
    assert "--since" in cmd
    assert cmd[cmd.index("--since") + 1] == "2026-10-01"
    assert "--until" in cmd
    assert cmd[cmd.index("--until") + 1] == "2026-10-22"
    assert "--by" in cmd
    assert cmd[cmd.index("--by") + 1] == "week"
    assert cmd[-2:] == ["--format", "json"]
