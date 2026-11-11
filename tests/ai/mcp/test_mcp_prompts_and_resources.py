"""The server registers its prompts and resources, a prompt fills in its parameters, and a
resource dispatches its command with its bound."""

from __future__ import annotations

import asyncio
from typing import Final

from devops_cli.ai.mcp.server import mcp
from devops_cli.config.defaults import DEFAULT_MCP_TOOL_TIMEOUT_SECONDS
from tests.support.fakes.mcp_dispatcher import DispatcherFake

# The resources of the MCP server that run a `devops gh` command.
_GH_RESOURCES: Final = (
    "resource://gh/issues/status",
    "resource://gh/pages/status",
    "resource://gh/project/status",
    "resource://gh/views/status",
)


def test_fastmcp_prompts_and_resources_registration() -> None:
    """Verify FastMCP prompt templates and dynamic system resources are registered."""
    import asyncio

    from devops_cli.ai.mcp.server import mcp

    # Check prompts
    prompts = asyncio.run(mcp.list_prompts())
    prompt_names = {p.name for p in prompts}
    expected_prompts = {
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


def test_fastmcp_prompts_rendering() -> None:
    """Verify that FastMCP prompt templates correctly interpolate parameters from task markdown files."""
    from devops_cli.ai.mcp.server import (
        architecture_analysis_prompt,
        k8s_diagnostics_prompt,
        security_audit_prompt,
    )

    arch = architecture_analysis_prompt(target="src/core")
    assert "src/core" in arch

    sa = security_audit_prompt(target="src/security")
    assert "src/security" in sa
    assert "CVEs" in sa

    k8s = k8s_diagnostics_prompt(namespace="kube-system")
    assert "kube-system" in k8s
    assert "pod status" in k8s

    arch = architecture_analysis_prompt(target="src/devops_cli")
    assert "src/devops_cli" in arch
    assert "cyclic imports" in arch


def test_mcp_prompts_execution() -> None:
    """Verify architecture analysis and security audit prompt templates return populated markdown."""
    from devops_cli.ai.mcp.server import architecture_analysis_prompt, security_audit_prompt

    arch_p = architecture_analysis_prompt(target="src/devops_cli")
    sec_p = security_audit_prompt(target="src")
    assert (
        "src/devops_cli" in arch_p,
        "security audit" in sec_p.lower(),
        "src" in sec_p,
    ) == (True, True, True)


def test_each_gh_resource_waits_longer_than_a_github_read(mcp_dispatcher: DispatcherFake) -> None:
    """Each `resource://gh/` resource dispatches its command with `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS`,
    which the chain test of `tests/github/test_github_session_timeouts.py` holds above the GitHub
    session read bound. A GitHub read in the command then stops first, and the resource gets its
    error, not the timeout of the dispatch (#4678)."""
    uris = sorted(
        str(resource.uri)
        for resource in asyncio.run(mcp.list_resources())
        if str(resource.uri).startswith("resource://gh/")
    )
    for uri in uris:
        asyncio.run(mcp.read_resource(uri))

    assert dict(zip(uris, (call.timeout for call in mcp_dispatcher.calls), strict=True)) == (
        dict.fromkeys(_GH_RESOURCES, DEFAULT_MCP_TOOL_TIMEOUT_SECONDS)
    )
