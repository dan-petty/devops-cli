"""Regression suite verifying schema contracts, parameters, and docstrings across all FastMCP tools."""

from __future__ import annotations

import pytest

from devops_cli.ai.mcp.server import list_mcp_tools


def test_fastmcp_tools_registration() -> None:
    """Verify that all expected FastMCP tools are registered on the server."""
    tools = list_mcp_tools()
    assert len(tools) >= 70, f"Expected at least 70 registered FastMCP tools, got {len(tools)}"

    tool_names = {t.name for t in tools}
    expected_core_tools = {
        # Code Review
        "review_path",
        "review_branch",
        "review_pr",
        "review_findings",
        "verify_finding",
        "review_stats",
        "review_export_feedback",
        # Repositories & Workspace
        "repos_list",
        "repos_status",
        "repos_sync",
        "workspace_list",
        "branches_list",
        "pr_list",
        "pr_checks",
        # SSH & Keyring
        "ssh_status",
        "ssh_audit",
        "config_audit_keys",
        "config_show",
        "config_output",
        # Kubernetes & GitOps
        "k8s_pods",
        "k8s_status",
        "k8s_bootstrap",
        "k8s_deploy_stack",
        "k8s_teardown_stack",
        "k8s_jaeger_info",
        "k8s_create_tls_secret",
        "k8s_enable_tls",
        "k8s_chaos",
        "k8s_audit",
        "k8s_lint",
        "k8s_validate",
        "k8s_diff_helm",
        "argo_list",
        "argo_status",
        # Monitoring & Tracing
        "grafana_dashboards",
        "prometheus_query",
        "telemetry_status",
        "telemetry_test_span",
        "telemetry_profile",
        "telemetry_logfire_status",
        # Docker & Isolation
        "docker_stats",
        "docker_sandbox",
        "docker_sign",
        "docker_verify",
        # CI, Release & Quality
        "ci_run",
        "release_status",
        "docs_compact",
        # Terraform / OpenTofu
        "tf_plan",
        "tf_apply",
        "tf_output",
        "tf_notify_plan",
        # RAG & Embeddings
        "rag_search",
        "rag_index",
        "rag_drift",
        "benchmark_embeddings",
        # Security Intel & Scanners
        "security_intel_package",
        "security_intel_network",
        "scan_uv_audit",
        "scan_fix",
        "scan_trivy",
        "scan_gitleaks",
        "scan_semgrep",
        "scan_checkov",
        "scan_complexity",
        "scan_aibom",
        "scan_sbom",
        # TLS & Certificates
        "tls_generate_ca",
        "tls_generate_cert",
        "tls_inspect_cert",
        # AI Architecture & AST
        "ai_repomap",
        "ai_diagram",
        "ai_test_gen",
        "ai_harness_status",
        "ai_subagent_offload",
        "ai_chaos_model",
        "ai_quiesce",
        "ai_failover",
        "ai_resume",
        "ai_constellation_status",
        "ai_ingest_library",
        "ai_query_library",
        "ai_inspect_symbol",
        "ai_ast_parse",
        "ai_ast_graph",
        "ai_pack_context",
        "ai_read",
        "ai_spend_report",
        # HashiCorp Vault
        "vault_status",
        "vault_get",
        "vault_set",
        "vault_sync",
        # GitHub Projects, Pages, Issues & Views
        "gh_views_sync",
        "gh_pages_status",
        "gh_pages_build",
        "gh_pages_verify",
        "gh_issue_list",
        "gh_issue_create",
        "gh_issue_triage",
        "gh_issue_status",
        "gh_issue_edit",
        "gh_project_list",
        "gh_project_audit",
        "gh_views_audit",
        "gh_rate_limit",
        "gh_runs_list",
        "gh_run_view",
        "roadmap_migrate",
        "roadmap_render",
        "roadmap_reprioritize",
        "pr_ready",
        "pr_diff",
        "pr_close",
        "pr_edit",
        "pr_check_readiness",
    }

    for expected in expected_core_tools:
        assert expected in tool_names, (
            f"Expected tool '{expected}' to be registered on FastMCP server"
        )


def test_fastmcp_prompts_and_resources_registration() -> None:
    """Verify FastMCP prompt templates and dynamic system resources are registered."""
    import asyncio

    from devops_cli.ai.mcp.server import mcp

    # Check prompts
    prompts = asyncio.run(mcp.list_prompts())
    prompt_names = {p.name for p in prompts}
    expected_prompts = {
        "code_review_prompt",
        "security_audit_prompt",
        "k8s_diagnostics_prompt",
        "architecture_analysis_prompt",
    }
    assert expected_prompts.issubset(prompt_names), (
        f"Missing FastMCP prompts: {expected_prompts - prompt_names}"
    )

    # Check resources
    resources = asyncio.run(mcp.list_resources())
    resource_uris = {str(r.uri) for r in resources}
    expected_resources = {
        "resource://workspace/status",
        "resource://config/active",
        "resource://telemetry/status",
        "resource://telemetry/logfire",
        "resource://release/status",
        "resource://vault/status",
        "resource://ai/constellation",
        "resource://ai/spend",
        "resource://mcp/tools",
        "resource://gh/pages/status",
        "resource://gh/issues/status",
        "resource://gh/project/status",
        "resource://gh/views/status",
        "resource://libraries/indexed",
    }
    assert expected_resources.issubset(resource_uris), (
        f"Missing FastMCP resources: {expected_resources - resource_uris}"
    )


def test_fastmcp_tool_docstrings_and_parameters() -> None:
    """Verify that every FastMCP tool has a non-empty docstring and typed parameter signatures."""
    tools = list_mcp_tools()
    for tool_info in tools:
        assert tool_info.description, (
            f"FastMCP tool '{tool_info.name}' is missing a docstring description"
        )
        assert len(tool_info.description.strip()) > 10, (
            f"FastMCP tool '{tool_info.name}' has too short description"
        )


def test_fastmcp_arg_validation() -> None:
    """Verify that _validate_mcp_arg catches flag injection attempts."""
    import pytest

    from devops_cli.ai.mcp.server import _validate_mcp_arg
    from devops_cli.exceptions import ValidationError

    # Clean arguments pass
    _validate_mcp_arg("branch", "main")
    _validate_mcp_arg("path", "src/devops_cli")

    # Hyphen flags raise ValidationError
    with pytest.raises(ValidationError, match="must not start with a hyphen"):
        _validate_mcp_arg("branch", "--all")


def test_fastmcp_prompts_rendering() -> None:
    """Verify that FastMCP prompt templates correctly interpolate parameters from task markdown files."""
    from devops_cli.ai.mcp.server import (
        architecture_analysis_prompt,
        code_review_prompt,
        k8s_diagnostics_prompt,
        security_audit_prompt,
    )

    cr = code_review_prompt(persona="architect", target="src/core")
    assert "architect" in cr
    assert "src/core" in cr
    assert "OWASP" in cr

    sa = security_audit_prompt(target="src/security")
    assert "src/security" in sa
    assert "CVEs" in sa

    k8s = k8s_diagnostics_prompt(namespace="kube-system")
    assert "kube-system" in k8s
    assert "pod status" in k8s

    arch = architecture_analysis_prompt(target="src/devops_cli")
    assert "src/devops_cli" in arch
    assert "cyclic imports" in arch


def test_fastmcp_messages_and_errors_localization() -> None:
    """Verify localized error and message catalog integration for FastMCP."""
    from unittest.mock import AsyncMock, patch

    import pytest

    from devops_cli.ai.mcp.server import _validate_mcp_arg, list_mcp_tools, run_mcp_server
    from devops_cli.exceptions import SecurityError, ValidationError
    from devops_cli.lang import ERRORS, MESSAGES

    # 1. Fallback tool description uses localized catalog string
    dummy_tool = AsyncMock()
    dummy_tool.name = "sample_tool"
    dummy_tool.description = None
    with patch("devops_cli.ai.mcp.server.mcp._list_tools", return_value=[dummy_tool]):
        tools = list_mcp_tools()
        assert tools[0].description == MESSAGES.mcp.no_description_provided

    # 2. Argument validation error uses localized catalog template
    with pytest.raises(ValidationError) as exc_info:
        _validate_mcp_arg("bad_field", "--flag")
    assert ERRORS.mcp.hyphen_prefixed_argument.format(name="bad_field") in str(exc_info.value)

    # 3. Security error for non-loopback host uses localized catalog template
    with pytest.raises(SecurityError) as sec_info:
        run_mcp_server(transport="sse", host="192.168.1.50")
    assert ERRORS.mcp.security_sse_non_loopback.format(host="192.168.1.50") in str(sec_info.value)


def test_fastmcp_library_tools_and_resource() -> None:
    """Verify library intelligence FastMCP tools and system resource execution."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import (
        ai_ingest_library,
        ai_inspect_symbol,
        ai_query_library,
        get_indexed_libraries_resource,
    )
    from devops_cli.config.defaults import (
        DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
    )

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = '{"status": "ok"}'

        res = ai_ingest_library(package="typer", max_depth=2)
        assert res == '{"status": "ok"}'
        mock_cmd.assert_called_with(
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
            timeout=DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
        )

        res = ai_query_library(query="command", package="typer", exact=True, top_k=3)
        assert res == '{"status": "ok"}'
        mock_cmd.assert_called_with(
            [
                "uv",
                "run",
                "devops",
                "ai",
                "ingest",
                "query-library",
                "command",
                "--top-k",
                "3",
                "--format",
                "json",
                "--package",
                "typer",
                "--exact",
            ],
            timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )

        res = ai_inspect_symbol(symbol="Typer", package="typer")
        assert res == '{"status": "ok"}'
        mock_cmd.assert_called_with(
            [
                "uv",
                "run",
                "devops",
                "ai",
                "ingest",
                "query-library",
                "Typer",
                "--exact",
                "--format",
                "json",
                "--package",
                "typer",
            ],
            timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )

    # Test resource returns valid JSON
    resource_data = get_indexed_libraries_resource()
    assert isinstance(resource_data, str)
    assert resource_data.startswith("[")


def test_fastmcp_ast_tools() -> None:
    """Verify ai_ast_parse and ai_ast_graph FastMCP execution contracts."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import ai_ast_graph, ai_ast_parse
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = '{"status": "ok"}'

        res = ai_ast_parse(file_path="src/main.py", query="(function_definition) @fn")
        assert res == '{"status": "ok"}'
        mock_cmd.assert_called_with(
            [
                "uv",
                "run",
                "devops",
                "ai",
                "ast",
                "parse",
                "src/main.py",
                "--json",
                "--query",
                "(function_definition) @fn",
            ],
            timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )

        res = ai_ast_graph(target_dir="src", max_files=20)
        assert res == '{"status": "ok"}'
        mock_cmd.assert_called_with(
            ["uv", "run", "devops", "ai", "ast", "graph", "--dir", "src", "--max-files", "20"],
            timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )


def test_fastmcp_context_packing_tool() -> None:
    """Verify ai_pack_context FastMCP execution contract."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import ai_pack_context
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = '{"content": "..."}'

        res = ai_pack_context(
            file_path="src/main.py",
            referenced="main,app",
            max_tokens=500,
            strip_private=True,
            skeletonize=False,
        )
        assert res == '{"content": "..."}'
        mock_cmd.assert_called_with(
            [
                "uv",
                "run",
                "devops",
                "ai",
                "pack-context",
                "src/main.py",
                "--max-tokens",
                "500",
                "--json",
                "--referenced",
                "main,app",
                "--no-skeletonize",
            ],
            timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )


def test_fastmcp_ai_read_tool() -> None:
    """Verify ai_read FastMCP execution contract."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import ai_read
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = "# Outline content"

        res = ai_read(
            target_path="src/main.py",
            inspect=True,
            level=0,
            lines="10:50",
            symbol="App",
            format="markdown",
        )
        assert (res, mock_cmd.call_args[0][0]) == (
            "# Outline content",
            [
                "uv",
                "run",
                "devops",
                "ai",
                "read",
                "src/main.py",
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
        assert mock_cmd.call_args[1]["timeout"] == DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS


def test_fastmcp_rag_drift_tool() -> None:
    """Verify rag_drift FastMCP execution contract."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import rag_drift
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = '{"drift_score": 0.0}'

        res = rag_drift(path="src", auto_sync=True)
        assert res == '{"drift_score": 0.0}'
        mock_cmd.assert_called_with(
            [
                "uv",
                "run",
                "devops",
                "ai",
                "rag",
                "drift",
                "src",
                "--json",
                "--auto-sync",
            ],
            timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )


def test_fastmcp_pr_check_readiness_tool() -> None:
    """Verify pr_check_readiness FastMCP execution contract."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import pr_check_readiness
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = "PR #187 satisfies merge readiness"

        res = pr_check_readiness(
            pr_number=187,
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
        assert (res, mock_cmd.call_args[0][0], mock_cmd.call_args[1]["timeout"]) == (
            "PR #187 satisfies merge readiness",
            expected_cmd,
            DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )


def test_fastmcp_pr_thread_resolve_tool() -> None:
    """Verify pr_thread_resolve FastMCP execution contract with without_reply option."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import pr_thread_resolve
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = "Thread resolved"

        # Test default without_reply=False
        res_default = pr_thread_resolve(thread_id="PRRT_1")
        cmd_default = [
            "uv",
            "run",
            "devops",
            "pr",
            "threads",
            "resolve",
            "PRRT_1",
        ]
        assert (res_default, mock_cmd.call_args[0][0], mock_cmd.call_args[1]["timeout"]) == (
            "Thread resolved",
            cmd_default,
            DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )

        # Test without_reply=True
        res_override = pr_thread_resolve(thread_id="PRRT_2", without_reply=True)
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
        assert (res_override, mock_cmd.call_args[0][0], mock_cmd.call_args[1]["timeout"]) == (
            "Thread resolved",
            cmd_override,
            DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )


def test_fastmcp_pr_ready_tool() -> None:
    """Verify pr_ready FastMCP execution contract."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import pr_ready
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = "PR #212 is ready for review"

        res = pr_ready(
            pr_number=212,
            monitor=False,
            force=True,
            repo="owner/repo",
        )
        assert "is ready for review" in res
        mock_cmd.assert_called_with(
            [
                "uv",
                "run",
                "devops",
                "pr",
                "ready",
                "212",
                "--force",
                "--repo",
                "owner/repo",
            ],
            timeout=DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
        )


def test_fastmcp_docker_sign_tool() -> None:
    """Verify docker_sign FastMCP execution contract."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import docker_sign
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = "Image signed successfully"

        res = docker_sign(
            image="example.com/app:1.0.0",
            key="/path/to/key.key",
            keyless=False,
            oidc_token="token123",
            annotations=["env=prod"],
            upload=False,
            dry_run=True,
        )
        assert "Image signed successfully" in res
        mock_cmd.assert_called_with(
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
                "--annotation",
                "env=prod",
                "--no-upload",
                "--dry-run",
            ],
            timeout=DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
            env={"COSIGN_IDENTITY_TOKEN": "token123"},
        )


def test_fastmcp_docker_verify_tool() -> None:
    """Verify docker_verify FastMCP execution contract."""
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import docker_verify
    from devops_cli.config.defaults import DEFAULT_MCP_TOOL_TIMEOUT_SECONDS

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as mock_cmd:
        mock_cmd.return_value = "Image verified successfully"

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
        mock_cmd.assert_called_with(
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
            timeout=DEFAULT_MCP_TOOL_TIMEOUT_SECONDS,
        )


# =============================================================================
# Credential hygiene in dispatcher logs
# =============================================================================


def test_no_dispatch_argument_reaches_a_log_record(caplog) -> None:
    """The dispatcher runs arbitrary `devops` command lines, and some carry a credential.

    `logger.debug("In-process dispatch %s ...", sub_args)` wrote the argument list
    verbatim, so `gh secrets set NAME <token>` put that token in the log in clear text.
    CodeQL reported it as three high-severity `py/clear-text-logging-sensitive-data`
    alerts and they blocked the v0.2.22 release. Masking the values first made it worse --
    the sanitizer is not a barrier CodeQL recognises, so three alerts became six -- so
    nothing derived from the command reaches a record at all.
    """
    import logging

    from devops_cli.ai.mcp.dispatcher import InProcessDispatcher

    secret = "ghp_A1b2C3d4E5f6G7h8I9j0"
    with caplog.at_level(logging.DEBUG):
        InProcessDispatcher().dispatch(["devops", "workspace", "-h", "--token", secret])
    assert secret not in caplog.text


def test_the_dispatch_record_still_reports_its_duration(caplog) -> None:
    """A record stripped of everything is not hygiene; the timing is why it exists."""
    import logging

    from devops_cli.ai.mcp.dispatcher import InProcessDispatcher

    with caplog.at_level(logging.DEBUG):
        InProcessDispatcher().dispatch(["devops", "workspace", "-h"])
    assert "In-process dispatch finished in" in caplog.text


def test_a_handler_failure_reports_its_exception_type(caplog) -> None:
    """Which kind of failure occurred is the diagnostic that survives dropping the data."""
    import logging

    from devops_cli.ai.mcp.dispatcher import InProcessDispatcher

    dispatcher = InProcessDispatcher()

    def explode(*_: str) -> tuple[int, str]:
        raise RuntimeError("holding ghp_A1b2C3d4E5f6G7h8I9j0")

    dispatcher.register_handler(("boom",), explode)
    with caplog.at_level(logging.DEBUG):
        dispatcher._check_functional_handlers(["boom"])
    assert "RuntimeError" in caplog.text and "ghp_A1b2C3d4E5f6G7h8I9j0" not in caplog.text


# =============================================================================
# Lazy domain-gated tool hydration
# =============================================================================


@pytest.fixture(autouse=True)
def reset_domain_gate():
    """Hydration is process-wide state, so a test must not inherit another's."""
    from devops_cli.ai.mcp import server as mcp_server

    mcp_server.reset_hydrated_domains()
    yield
    mcp_server.reset_hydrated_domains()


def test_the_advertised_set_is_a_fraction_of_the_registered_one() -> None:
    """All 155 tools were advertised on every turn.

    Their names and summaries alone cost about 2,700 tokens per request before the
    per-parameter JSON Schema the protocol adds, and a model choosing among 155 tools
    chooses worse than one choosing among a few dozen.
    """
    import asyncio

    from devops_cli.ai.mcp import server as mcp_server

    async def counts() -> tuple[int, int]:
        registered = await mcp_server.mcp._list_tools()
        advertised = [t for t in registered if mcp_server._is_advertised(t.name)]
        return len(registered), len(advertised)

    registered, advertised = asyncio.run(counts())
    assert advertised < registered / 2


def test_filtering_never_removes_a_tool_from_the_server() -> None:
    """An earlier version removed them, which mutated an object every consumer shares.

    The schema exporter, the in-process bridge and every later test then saw whatever the
    last caller had left behind.
    """
    import asyncio

    from devops_cli.ai.mcp import server as mcp_server

    async def registered_count() -> int:
        return len(await mcp_server.mcp._list_tools())

    before = asyncio.run(registered_count())
    mcp_server.hydrate_tool_domain("k8s")
    mcp_server.reset_hydrated_domains()
    assert asyncio.run(registered_count()) == before


def test_an_eager_domain_needs_no_hydration() -> None:
    """The domains this CLI's agent uses constantly must not cost a round trip first."""
    from devops_cli.ai.mcp import server as mcp_server
    from devops_cli.config.constants import CONST_MCP_EAGER_DOMAINS

    eager = sorted(CONST_MCP_EAGER_DOMAINS)[0]
    assert mcp_server._is_advertised(f"{eager}_anything") is True


def test_a_withheld_domain_appears_once_hydrated() -> None:
    """Hydration is the way back; without it the withheld tools are undiscoverable."""
    from devops_cli.ai.mcp import server as mcp_server

    before = mcp_server._is_advertised("k8s_get_pods")
    mcp_server.hydrate_tool_domain("k8s")
    assert (before, mcp_server._is_advertised("k8s_get_pods")) == (False, True)


def test_hydrating_an_eager_domain_is_reported_as_unnecessary() -> None:
    """Asking for something already advertised should not look like it changed anything."""
    from devops_cli.ai.mcp import server as mcp_server
    from devops_cli.config.constants import CONST_MCP_EAGER_DOMAINS

    eager = sorted(CONST_MCP_EAGER_DOMAINS)[0]
    assert mcp_server.hydrate_tool_domain(eager)["hydrated"] is False


def test_the_hydration_tool_is_always_advertised() -> None:
    """Withholding it too would make every other withheld domain unreachable."""
    from devops_cli.ai.mcp import server as mcp_server

    assert mcp_server._is_advertised("hydrate_tool_domain") is True


def test_hydrating_invalid_domain_name_is_rejected() -> None:
    """Invalid characters or empty strings are rejected without mutating hydrated domains."""
    from devops_cli.ai.mcp import server as mcp_server

    assert (
        mcp_server.hydrate_tool_domain("")["hydrated"],
        mcp_server.hydrate_tool_domain("; rm -rf /")["hydrated"],
        mcp_server.hydrate_tool_domain("k8s$bad")["hydrated"],
    ) == (False, False, False)


def test_hydrating_unknown_domain_is_rejected() -> None:
    """Nonexistent domains like 'secrets' are rejected with clear explanation."""
    from devops_cli.ai.mcp import server as mcp_server

    res_secrets = mcp_server.hydrate_tool_domain("secrets")
    res_vault = mcp_server.hydrate_tool_domain("vault")
    assert (
        res_secrets["hydrated"],
        res_secrets["detail"],
        res_vault["hydrated"],
    ) == (
        False,
        "unknown domain: secrets",
        True,
    )


def test_hydrate_tool_domain_notifies_session() -> None:
    """Hydrating a domain dispatches notifications/tools/list_changed if session is active."""
    from unittest.mock import AsyncMock, MagicMock

    from devops_cli.ai.mcp import server as mcp_server

    mock_session = MagicMock()
    mock_session.send_tool_list_changed = AsyncMock()
    mock_ctx = MagicMock(session=mock_session)

    res = mcp_server.hydrate_tool_domain("ssh", ctx=mock_ctx)
    assert (res["hydrated"], mock_session.send_tool_list_changed.called) == (True, True)


# =============================================================================
# Argument contract: a call is checked against its tool's published schema
# =============================================================================

# Values of the wrong JSON type that pydantic's lax mode converted, by the type the parameter
# declares. `true`, `"1"` and `1.0` all became PR 1, so `review_pr` with `post` commented on it.
# JSON Schema counts `1.0` as an integer, so the sweep holds the check to the stricter reading.
_COERCED_VALUES: dict[str, tuple[object, ...]] = {
    "integer": (True, "1", 1.0),
    "number": (True, "1.5"),
    "boolean": ("true",),
}
_SAMPLE_JSON_TYPES: dict[type, str] = {bool: "boolean", str: "string", float: "number"}
# Keywords a published schema may carry: those a refusal is classified and described by, and
# those that only give structure or a default.
_STRUCTURAL_SCHEMA_KEYWORDS = frozenset(
    {"properties", "items", "default", "title", "description", "additionalProperties"}
)
_NUMERIC_BOUND_KEYWORDS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")
_SECRET_SENTINEL = "API_KEY=sentinel-4b1d"


@pytest.fixture
def handler_runner():
    """Stand in for the command runner, failing loudly if any handler gets far enough to run."""
    from unittest.mock import patch

    with patch(
        "devops_cli.ai.mcp.server._run_mcp_cmd", side_effect=AssertionError("a handler ran")
    ) as runner:
        yield runner


@pytest.fixture
def fastmcp_log(caplog):
    """Capture FastMCP's server log, which FastMCP configures not to propagate to the root."""
    import logging

    server_logger = logging.getLogger("fastmcp.server.server")
    server_logger.addHandler(caplog.handler)
    yield caplog
    server_logger.removeHandler(caplog.handler)


async def _call(tool: str, arguments: dict[str, object]) -> tuple[bool, str]:
    """Call a tool the way an MCP client does, returning whether it failed and its reply."""
    from fastmcp import Client

    from devops_cli.ai.mcp.server import mcp

    async with Client(mcp) as client:
        result = await client.call_tool(tool, arguments, raise_on_error=False)
    return result.is_error, "\n".join(getattr(block, "text", "") for block in result.content)


async def _published_schemas() -> dict[str, dict]:
    """Every registered tool's input schema as a client receives it, with all domains hydrated."""
    from fastmcp import Client

    from devops_cli.ai.mcp import server as mcp_server
    from devops_cli.config.constants import CONST_MCP_LAZY_DOMAINS

    for domain in CONST_MCP_LAZY_DOMAINS:
        mcp_server.hydrate_tool_domain(domain)
    async with Client(mcp_server.mcp) as client:
        tools = await client.list_tools()
    return {tool.name: tool.inputSchema for tool in tools}


def _branches(schema: dict) -> list[dict]:
    """The alternatives a property accepts: its `anyOf` branches, or the property itself."""
    return schema.get("anyOf", [schema])


def _coerced_values(schema: dict) -> list[object]:
    """Wrong-typed values for a property, skipping any of a JSON type it also accepts."""
    accepted = {branch.get("type") for branch in _branches(schema)}
    return [
        value
        for declared in sorted(accepted & set(_COERCED_VALUES))
        for value in _COERCED_VALUES[declared]
        if _SAMPLE_JSON_TYPES[type(value)] not in accepted
    ]


def _is_numeric_bounded(schema: dict) -> bool:
    """Report whether a property publishes a numeric bound on any branch."""
    return any(
        keyword in branch for branch in _branches(schema) for keyword in _NUMERIC_BOUND_KEYWORDS
    )


def _schema_keywords(schema: dict) -> set[str]:
    """Every keyword a schema uses, in itself and in each property, item, branch or definition."""
    nested = [
        *schema.get("properties", {}).values(),
        *schema.get("anyOf", []),
        *schema.get("oneOf", []),
        *schema.get("allOf", []),
        *schema.get("$defs", {}).values(),
        *([schema["items"]] if isinstance(schema.get("items"), dict) else []),
    ]
    return set(schema).union(*map(_schema_keywords, nested))


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("review_pr", {"number": True, "post": True}),
        ("review_pr", {"number": "1"}),
        ("review_pr", {"number": 1.0}),
        ("review_pr", {"number": 1, "post": "true"}),
        ("sandbox_stop", {"timeout": True}),
        ("sandbox_stop", {"timeout": "10"}),
        ("sandbox_stop", {"timeout": 10.0}),
        ("sandbox_stop", {"all_instances": "true"}),
        ("ai_vllm_scale", {"replicas": 2.0}),
    ],
)
async def test_a_coerced_argument_is_refused_before_the_handler_runs(
    tool, arguments, handler_runner
) -> None:
    """`review_pr` given `{"number": true, "post": true}` built `devops review pr 1 --post`.

    Pydantic's lax mode turned `true`, `"1"` and `1.0` into PR 1, so a malformed or
    hallucinated call reviewed PR 1 and commented on it. `sandbox_stop` is withheld from the
    listing, which is all the SDK's own strict check ever looks at, so it must refuse too.
    An integral float on an integer that is not a PR number, such as `sandbox_stop`'s
    `timeout` or the advertised `ai_vllm_scale`'s `replicas`, ran its handler the same way.
    """
    is_error, _ = await _call(tool, arguments)
    assert (is_error, handler_runner.call_count) == (True, 0)


@pytest.mark.parametrize(
    ("tool", "arguments", "parameter", "kind"),
    [
        ("review_pr", {}, "number", "MISSING_PARAM"),
        ("review_pr", {"number": 0}, "number", "OUT_OF_RANGE"),
        ("pr_monitor", {"pr_number": 0}, "pr_number", "OUT_OF_RANGE"),
        ("review_pr", {"number": 7, "verbose": True}, "verbose", "HALLUCINATED_PARAM"),
        ("review_pr", {"number": "7"}, "number", "TYPE_MISMATCH"),
        ("review_pr", {"number": 7.0}, "number", "TYPE_MISMATCH"),
        ("ci_run", {"check": "everything"}, "check", "INVALID_CHOICE"),
    ],
)
async def test_each_violation_is_numbered_with_its_parameter_and_kind(
    tool, arguments, parameter, kind, handler_runner
) -> None:
    """The envelope says which parameter broke which rule, one numbered entry each."""
    _, reply = await _call(tool, arguments)
    assert f"1. Parameter: `{parameter}`\n   Kind: {kind}\n" in reply


async def test_a_parameter_that_breaks_two_keywords_is_listed_once(handler_runner) -> None:
    """`5` for `ci_run`'s `check` fails its `enum` and its `type`.

    Each failed keyword became an entry with the same expected value and fix, doubling the
    count and taking a second of the five places a violation on another parameter needs.
    """
    _, reply = await _call("ci_run", {"check": 5})
    assert (
        "1 argument violation(s)" in reply,
        "1. Parameter: `check`" in reply,
        "2. Parameter" in reply,
    ) == (True, True, False)


async def test_a_refusal_names_the_parameter_its_type_and_the_allowed_parameters(
    handler_runner,
) -> None:
    """A model corrects the call in one turn only when told what to send instead.

    Pydantic's own text stopped at the first breach, quoted the value and listed nothing
    the call could have sent.
    """
    _, reply = await _call("review_pr", {"number": "4242", "verbose": True})
    assert (
        "Parameter: `number`" in reply,
        "Expected: integer >= 1" in reply,
        "Parameter: `verbose`" in reply,
        "Allowed parameters: `number`, `persona`, `post`" in reply,
        "Re-issue the call" in reply,
        "4242" in reply,
    ) == (True, True, True, True, True, False)


async def test_a_withheld_tool_refuses_with_the_same_envelope(handler_runner) -> None:
    """Calling a withheld tool still works, so it must be refused the same way."""
    _, reply = await _call("sandbox_stop", {"timeout": "10"})
    assert (
        "Parameter: `timeout`" in reply,
        "Expected: integer" in reply,
        "Allowed parameters: `all_instances`, `instance_id`, `timeout`" in reply,
    ) == (True, True, True)


async def test_a_strict_refusal_is_rendered_like_a_schema_refusal(
    handler_runner, fastmcp_log
) -> None:
    """The strict PR-number alias still refuses `1.0` when the schema check lets it through.

    Pydantic reports that refusal, and FastMCP logs pydantic's errors with the input in each.
    The reply goes through the same envelope, and neither it nor the log holds the value.
    """
    from unittest.mock import patch

    with patch("devops_cli.ai.mcp.server.schema_violations", return_value=[]):
        is_error, reply = await _call("review_pr", {"number": 4242.0})
    assert (
        is_error,
        "Kind: TYPE_MISMATCH" in reply,
        "Allowed parameters:" in reply,
        "4242" in reply,
        "Invalid arguments for tool" in fastmcp_log.text,
        "4242" in fastmcp_log.text,
        handler_runner.call_count,
    ) == (True, True, True, False, True, False, 0)


async def test_a_refused_secret_never_reaches_the_reply(handler_runner) -> None:
    """An invalid `vault_set` returned the secret it was given in its error text."""
    _, reply = await _call("vault_set", {"path": "secret/app", "key_values": _SECRET_SENTINEL})
    assert ("Parameter: `key_values`" in reply, "sentinel-4b1d" in reply) == (True, False)


async def test_an_undeclared_parameter_name_is_masked_and_bounded(handler_runner) -> None:
    """An undeclared name is the caller's text, so it is masked and cut before it is echoed."""
    token = "ghp_A1b2C3d4E5f6G7h8I9j0"
    _, reply = await _call("review_pr", {"number": 7, token: 1, "x" * 500: 1})
    assert ("Kind: HALLUCINATED_PARAM" in reply, token in reply, "x" * 65 in reply) == (
        True,
        False,
        False,
    )


def test_no_rejected_input_reaches_a_log_record(fastmcp_log, handler_runner) -> None:
    """FastMCP logs pydantic's error list for a refused call, and each entry holds the input.

    A malformed `vault_set` wrote its `key_values` to the log. This calls past the middleware,
    as FastMCP itself does once middleware has run, so pydantic refuses and FastMCP logs.
    """
    import asyncio

    from fastmcp.exceptions import ValidationError as FastMCPValidationError

    from devops_cli.ai.mcp.server import mcp

    arguments = {"path": "secret/app", "key_values": _SECRET_SENTINEL}
    with pytest.raises(FastMCPValidationError):
        asyncio.run(mcp.call_tool("vault_set", arguments, run_middleware=False))
    assert (
        "Invalid arguments for tool" in fastmcp_log.text,
        "sentinel-4b1d" in fastmcp_log.text,
    ) == (True, False)


async def test_an_unknown_tool_is_left_to_fastmcp(handler_runner) -> None:
    """The contract checks registered tools; an unknown name keeps FastMCP's own answer."""
    is_error, reply = await _call("no_such_tool", {})
    assert (is_error, "Unknown tool" in reply) == (True, True)


async def test_a_validation_error_without_a_pydantic_cause_is_not_rewritten() -> None:
    """Only pydantic's argument errors become an envelope; anything else passes through."""
    from types import SimpleNamespace

    from fastmcp.exceptions import ValidationError as FastMCPValidationError

    from devops_cli.ai.mcp.server import ArgumentContractMiddleware

    async def call_next(_context: object) -> object:
        raise FastMCPValidationError("not an argument error")

    context = SimpleNamespace(message=SimpleNamespace(name="review_pr", arguments={"number": 7}))
    with pytest.raises(FastMCPValidationError, match="not an argument error"):
        await ArgumentContractMiddleware().on_call_tool(context, call_next)


async def test_every_published_schema_forbids_undeclared_parameters() -> None:
    """`additionalProperties: false` is what makes a hallucinated parameter a refusal.

    It held only through FastMCP's defaults, with nothing asserting it.
    """
    from devops_cli.ai.mcp.server import mcp

    schemas = await _published_schemas()
    registered = await mcp._list_tools()
    open_schemas = sorted(
        name for name, schema in schemas.items() if schema.get("additionalProperties") is not False
    )
    assert (len(schemas), open_schemas) == (len(registered), [])


def test_strict_input_validation_stays_off() -> None:
    """The published-schema middleware is the one argument check.

    The SDK's strict check sees only listed tools, quotes the rejected value instead of
    naming the field, and answers before any middleware, so turning it on would leave
    withheld tools coercing and pre-empt the prescriptive envelope on listed ones.
    """
    from devops_cli.ai.mcp.server import mcp

    assert mcp.strict_input_validation is False


async def test_the_validator_refuses_every_coerced_value_without_running_a_handler(
    record_property, handler_runner
) -> None:
    """Every integer, number and boolean parameter of every tool refuses a coerced value.

    The sweep calls the validator alone, never a handler. How many numeric parameters
    publish a bound is reported, not enforced: bounds per argument class are follow-up work.
    """
    from devops_cli.ai.mcp.argument_contract import schema_violations

    schemas = await _published_schemas()
    swept = [
        (tool, name, value)
        for tool, schema in schemas.items()
        for name, prop in schema["properties"].items()
        for value in _coerced_values(prop)
    ]
    unrefused = [
        (tool, name, value)
        for tool, name, value in swept
        if (name, "TYPE_MISMATCH")
        not in {(v.parameter, v.kind) for v in schema_violations(schemas[tool], {name: value})}
    ]
    numeric = [
        prop
        for schema in schemas.values()
        for prop in schema["properties"].values()
        if {"integer", "number"} & {branch.get("type") for branch in _branches(prop)}
    ]
    record_property(
        "numeric_parameters_with_a_published_bound",
        f"{sum(map(_is_numeric_bounded, numeric))}/{len(numeric)}",
    )
    assert (len(swept) > len(schemas) / 2, unrefused, handler_runner.call_count) == (True, [], 0)


async def test_pr_and_issue_numbers_publish_a_positive_bound() -> None:
    """Every PR and issue number takes the strict alias, whose `ge=1` the schema publishes."""
    schemas = await _published_schemas()
    numbers = {
        (tool, name): prop
        for tool, schema in schemas.items()
        for name, prop in schema["properties"].items()
        if name in {"number", "pr_number", "issue_number"}
    }
    unbounded = sorted(
        key
        for key, prop in numbers.items()
        if not any(
            branch.get("type") == "integer" and branch.get("minimum") == 1
            for branch in _branches(prop)
        )
    )
    assert (len(numbers), unbounded) == (11, [])


async def test_every_published_keyword_is_one_a_refusal_can_describe() -> None:
    """A refusal reads well only for keywords the kind and bound tables know.

    A `pattern` or `multipleOf` failure is a value of the right type, and the refusal would
    name only that type, telling the caller nothing it can fix. A newly published keyword
    fails here first, so its kind and description are added before it can be refused.
    """
    from devops_cli.config.constants import (
        CONST_JSON_SCHEMA_BOUND_PHRASES,
        CONST_JSON_SCHEMA_VIOLATION_KINDS,
    )

    schemas = await _published_schemas()
    published = set().union(*map(_schema_keywords, schemas.values()))
    described = {
        *CONST_JSON_SCHEMA_VIOLATION_KINDS,
        *CONST_JSON_SCHEMA_BOUND_PHRASES,
        *_STRUCTURAL_SCHEMA_KEYWORDS,
    }
    assert (sorted(published - described), {"type", "anyOf", "minimum"} <= published) == (
        [],
        True,
    )


def test_describe_schema_states_what_a_property_accepts() -> None:
    """Expected types are read from the schema's keywords, never from a rejected value."""
    from devops_cli.ai.mcp.argument_contract import describe_schema

    assert [
        describe_schema({"type": "integer", "minimum": 1}),
        describe_schema({"type": "integer", "minimum": 1, "maximum": 10}),
        describe_schema(
            {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]}
        ),
        describe_schema({"enum": ["json", "text"]}),
        describe_schema({"const": "json", "type": "string"}),
        describe_schema({"type": ["string", "null"]}),
        describe_schema({}),
    ] == [
        "integer >= 1",
        "integer >= 1 and <= 10",
        "array of string or null",
        'one of "json", "text"',
        'exactly "json"',
        "string or null",
        "any JSON value",
    ]


# ── Roadmap tools (#739) ──────────────────────────────────────────────────────


def _roadmap_tool_parameters(name: str) -> dict[str, object]:
    import asyncio

    from devops_cli.ai.mcp import server as mcp_server

    tool = asyncio.run(mcp_server.mcp.get_tool(name))
    assert tool is not None
    return dict(tool.parameters["properties"])


def test_the_roadmap_tools_are_registered_and_migrate_only_previews() -> None:
    """`roadmap_migrate` has no confirm parameter: a bulk change is never one tool call away.

    `roadmap_reprioritize` previews unless it is called with `dry_run=False` (#740).
    """
    render = _roadmap_tool_parameters("roadmap_render")
    migrate = _roadmap_tool_parameters("roadmap_migrate")
    reprioritize = _roadmap_tool_parameters("roadmap_reprioritize")
    assert (
        sorted(render),
        render["dry_run"].get("default"),  # type: ignore[attr-defined]
        sorted(migrate),
        sorted(reprioritize),
        reprioritize["dry_run"].get("default"),  # type: ignore[attr-defined]
    ) == (["dry_run", "ref", "repo"], True, ["ref", "repo"], ["dry_run", "ref", "repo"], True)


def test_the_roadmap_tools_resolve_to_the_roadmap_domain_and_hydrate() -> None:
    from devops_cli.ai.mcp import server as mcp_server
    from devops_cli.ai.mcp.dispatcher import resolve_tool_domain

    before = mcp_server._is_advertised("roadmap_render")
    hydrated = mcp_server.hydrate_tool_domain("roadmap")["hydrated"]
    after = (
        mcp_server._is_advertised("roadmap_migrate"),
        mcp_server._is_advertised("roadmap_reprioritize"),
    )
    mcp_server.reset_hydrated_domains()
    assert (
        resolve_tool_domain("roadmap_render"),
        resolve_tool_domain("roadmap_migrate"),
        resolve_tool_domain("roadmap_reprioritize"),
        before,
        hydrated,
        after,
    ) == ("roadmap", "roadmap", "roadmap", False, True, (True, True))


def test_the_roadmap_tools_build_the_commands_argv() -> None:
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import roadmap_migrate, roadmap_render, roadmap_reprioritize

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="ok") as run:
        roadmap_render()
        roadmap_render(repo="dan-petty/devops-cli", ref="release/v0.2.25", dry_run=False)
        roadmap_migrate(repo="dan-petty/devops-cli", ref="release/v0.2.25")
        roadmap_reprioritize()
        roadmap_reprioritize(repo="dan-petty/devops-cli", ref="release/v0.2.25", dry_run=False)
    head = ["uv", "run", "devops", "roadmap"]
    target = ["--repo", "dan-petty/devops-cli", "--ref", "release/v0.2.25"]
    assert [call.args[0] for call in run.call_args_list] == [
        [*head, "render", "--dry-run"],
        [*head, "render", *target],
        [*head, "migrate", "--dry-run", *target],
        [*head, "reprioritize", "--dry-run"],
        [*head, "reprioritize", *target, "--confirm"],
    ]


# =============================================================================
# telemetry_profile names a trace and runs nothing (#980)
# =============================================================================

_PROFILED_TRACE = "0af7651916cd43dd8448eb211c80319c"


async def test_telemetry_profile_publishes_a_trace_id_and_no_command() -> None:
    """`telemetry_profile(command=...)` ran whatever program an MCP caller named.

    `devops telemetry profile` split the string with `shlex` and ran it with the user's whole
    environment, so a prompt-injected agent ran anything with every credential in reach. An
    MCP caller now names a trace already in Jaeger, and the trace ID is all it can send.
    """
    import inspect

    from devops_cli.ai.mcp.server import telemetry_profile

    schema = (await _published_schemas())["telemetry_profile"]
    assert (
        tuple(inspect.signature(telemetry_profile).parameters),
        sorted(schema["properties"]),
        schema.get("required"),
    ) == (("trace_id",), ["trace_id"], ["trace_id"])


async def test_telemetry_profile_refuses_a_command_before_anything_runs(handler_runner) -> None:
    """The call that profiled `bash -c true` is refused as a parameter the tool never had."""
    is_error, reply = await _call(
        "telemetry_profile", {"command": "bash -c true", "trace_id": _PROFILED_TRACE}
    )
    assert (
        is_error,
        "Parameter: `command`" in reply,
        "HALLUCINATED_PARAM" in reply,
        handler_runner.call_count,
    ) == (True, True, True, 0)


def test_telemetry_profile_reads_the_named_trace() -> None:
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import telemetry_profile

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="ok") as run:
        telemetry_profile(trace_id=_PROFILED_TRACE)
    assert run.call_args.args[0] == [
        "uv",
        "run",
        "devops",
        "telemetry",
        "profile",
        "--trace-id",
        _PROFILED_TRACE,
    ]


def test_docker_sandbox_hands_its_command_over_after_the_options_end() -> None:
    """`docker_sandbox` appended `command` straight after its own options (#980).

    `devops docker sandbox` parsed a leading `--root` or `--cpus 64` in that list as its own
    option, so a caller turned off the rootless default the tool never offered. `--` ends the
    options, as `sandbox_deploy` and `sandbox_exec` already did.
    """
    from unittest.mock import patch

    from devops_cli.ai.mcp.server import docker_sandbox

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="ok") as run:
        docker_sandbox(command=["--root", "id"])
    assert run.call_args.args[0][-3:] == ["--", "--root", "id"]


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
