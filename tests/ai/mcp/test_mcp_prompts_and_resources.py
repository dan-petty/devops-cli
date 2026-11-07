"""The server registers its prompts and resources, and a prompt fills in its parameters."""

from __future__ import annotations


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
