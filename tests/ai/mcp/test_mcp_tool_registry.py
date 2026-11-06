"""The server registers the tools clients expect, each with documented parameters and honest annotations."""

from __future__ import annotations

import asyncio

from devops_cli.ai.mcp.server import (
    list_mcp_tools,
    mcp,
)


def test_server_name() -> None:
    """FastMCP server must be named 'devops-cli'."""
    assert mcp.name == "devops-cli"


def test_tools_registered() -> None:
    """All expected MCP tools must be registered on the server."""
    from devops_cli.config.constants import CONST_MCP_EXPOSURE_TABLE

    tools = asyncio.run(mcp._list_tools())
    tool_names = {t.name for t in tools}

    expected_exposure = {"_".join(e[0]).replace("-", "_") for e in CONST_MCP_EXPOSURE_TABLE}
    expected_hand_written = {
        "hydrate_tool_domain",
        "security_intel_package",
        "security_intel_network",
        "scan_uv_audit",
        "k8s_tempo_info",
    }
    assert tool_names == (expected_exposure | expected_hand_written)


def test_list_mcp_tools_returns_list_of_dicts() -> None:
    """list_mcp_tools() must return a list of dicts with name and description keys."""
    tools = list_mcp_tools()
    assert isinstance(tools, list)
    assert len(tools) > 0
    for t in tools:
        assert "name" in t
        assert "description" in t


def test_all_tools_have_descriptions() -> None:
    """All registered tools must have non-empty docstrings used as descriptions."""
    tools = asyncio.run(mcp._list_tools())
    missing_desc = [t.name for t in tools if not t.description]
    assert missing_desc == [], f"Tools missing descriptions: {missing_desc}"


def test_ai_architecture_tool_is_removed() -> None:
    """Verify the tool that ran the never-existing `devops analyze architecture` is gone,
    with no shim left behind."""
    from devops_cli.ai.mcp import server

    tool_names = {tool.name for tool in asyncio.run(mcp._list_tools())}

    assert "ai_architecture" not in tool_names
    assert "ai_architecture" not in dir(server)


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
        "review_stats",
        "review_export_feedback",
        # Repositories & Workspace
        "repos_list",
        "repos_sync",
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
        "k8s_doctor",
        "k8s_bootstrap",
        "k8s_deploy_stack",
        "k8s_teardown_stack",
        "k8s_tempo_info",
        "k8s_create_tls_secret",
        "k8s_enable_tls",
        "k8s_chaos",
        "k8s_audit",
        "k8s_lint",
        "k8s_validate",
        "k8s_diff_helm",
        "argo_cd_apps_list",
        "argo_cd_apps_status",
        # Monitoring & Tracing
        "grafana_dashboards_list",
        "prometheus_query",
        "telemetry_status",
        "telemetry_test",
        "telemetry_profile",
        "telemetry_logfire",
        # Docker & Isolation
        "docker_images",
        "docker_sandbox",
        "docker_sign",
        "docker_verify",
        # CI & Quality
        "ci",
        # Terraform / OpenTofu
        "tf_plan",
        "tf_apply",
        "tf_output",
        "tf_notify_plan",
        # RAG & Embeddings
        "ai_rag_query",
        "ai_rag_index",
        "ai_rag_drift",
        "ai_benchmark",
        # Security Intel & Scanners
        "security_intel_package",
        "security_intel_network",
        "scan_uv_audit",
        "scan_fix",
        "scan_trivy",
        "scan_secrets",
        "scan_sast",
        "scan_complexity",
        "scan_aibom",
        "scan_sbom",
        # TLS & Certificates
        "tls_inspect",
        # AI Architecture & AST
        "ai_repomap",
        "ai_diagram",
        "ai_test_gen",
        "ai_harness_status",
        "ai_harness_offload",
        "ai_chaos_model",
        "ai_quiesce",
        "ai_failover",
        "ai_resume",
        "ai_constellation",
        "ai_ingest_library",
        "ai_ingest_query_library",
        "ai_ast_parse",
        "ai_ast_graph",
        "ai_pack_context",
        "ai_read",
        "ai_cost_report",
        # HashiCorp Vault
        "vault_status",
        "vault_get",
        "vault_sync",
        # GitHub Projects, Pages, Issues & Views
        "gh_views_sync",
        "gh_pages_status",
        "gh_pages_build",
        "gh_pages_verify",
        "gh_issues_list",
        "gh_issues_view",
        "gh_issues_create",
        "gh_issues_triage",
        "gh_issues_status",
        "gh_issues_edit",
        "gh_project_list",
        "gh_project_audit",
        "gh_views_audit",
        "gh_rate_limit",
        "gh_runs_list",
        "gh_runs_view",
        "roadmap_intake",
        "roadmap_refine",
        "roadmap_run",
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


def test_no_tool_text_names_a_flag_that_the_tool_does_not_publish() -> None:
    """A description of a tool or a parameter names no `--flag` that the tool leaves out.

    The text of a tool is the help text of its command. A person reads the flag at the command
    line, but a model that reads it calls a parameter that the schema lacks, and the call fails
    (#2704).
    """
    import asyncio
    import re

    from devops_cli.ai.mcp.generator import resolve_click_command
    from devops_cli.ai.mcp.server import mcp
    from devops_cli.config.constants import CONST_MCP_EXPOSURE_TABLE

    paths = {"_".join(path).replace("-", "_"): path for path, *_ in CONST_MCP_EXPOSURE_TABLE}
    flags_by_name = {
        name: {
            opt: param.name
            for param in resolve_click_command(path).params
            for opt in getattr(param, "opts", [])
            if opt.startswith("--")
        }
        for name, path in paths.items()
    }
    unpublished: list[str] = []
    for tool in asyncio.run(mcp._list_tools()):
        if tool.name not in flags_by_name:
            continue
        published = set(tool.parameters["properties"])
        texts = [tool.description or ""] + [
            str(prop.get("description", "")) for prop in tool.parameters["properties"].values()
        ]
        for flag in set(re.findall(r"(?<![\w-])--[a-z][a-z-]*", " ".join(texts))):
            name = flags_by_name[tool.name].get(flag)
            if name is not None and name not in published:
                unpublished.append(f"{tool.name}: {flag}")
    assert unpublished == []


def test_fastmcp_tool_annotations_and_mutating_floor() -> None:
    """Every registered FastMCP tool sets readOnlyHint, and argument-mutating tools carry False (#857)."""
    import asyncio

    from devops_cli.ai.mcp.server import mcp
    from devops_cli.docs.generator import DocGenerator

    mutating_tools_floor: frozenset[str] = frozenset(
        {
            "argo_rollouts_analyze",
            "docker_sign",
            "gh_project_reconcile",
            "ai_rag_drift",
        }
    )

    registered = asyncio.run(mcp._list_tools())
    missing_hint = [
        t.name
        for t in registered
        if t.annotations is None or not isinstance(t.annotations.read_only_hint, bool)
    ]
    hints_by_name = {
        t.name: t.annotations.read_only_hint for t in registered if t.annotations is not None
    }
    floor_expected_false = mutating_tools_floor | {
        "gh_labels_sync",
        "k8s_teardown_stack",
        "pr_close",
        "review_pr",
        "tf_apply",
        "valkey_flush",
        "valkey_set",
    }
    wrong_floor = sorted(
        name for name in floor_expected_false if hints_by_name.get(name) is not False
    )
    info_by_name = {info.name: info for info in list_mcp_tools()}
    info_mismatches = [
        name
        for name, expected in hints_by_name.items()
        if (
            info_by_name[name].read_only_hint,
            info_by_name[name]["readOnlyHint"],
            "readOnlyHint" in info_by_name[name],
        )
        != (expected, expected, True)
    ]
    doc_generator = DocGenerator()
    mcp_docs = doc_generator.introspect_mcp_tools()
    rendered_md = doc_generator.render_mcp_tools_markdown(mcp_docs)
    assert (
        missing_hint,
        wrong_floor,
        info_mismatches,
        hints_by_name.get("repos_list"),
        "**Annotations:** `readOnlyHint: false`" in rendered_md,
        "**Annotations:** `readOnlyHint: true`" in rendered_md,
    ) == ([], [], [], True, True, True)


def test_the_vault_tools_take_no_address() -> None:
    """A client must never choose which Vault a tool asks: `vault_get` and `vault_sync`
    send the user's Vault token there, and `vault_status` sends a request to it."""
    import inspect

    from devops_cli.ai.mcp import server

    parameters = {
        name: set(inspect.signature(getattr(server, name)).parameters)
        for name in ("vault_get", "vault_sync", "vault_status")
    }
    assert (
        "vault_addr" not in parameters["vault_get"],
        "vault_addr" not in parameters["vault_sync"],
        "vault_addr" not in parameters["vault_status"],
    ) == (True, True, True)
