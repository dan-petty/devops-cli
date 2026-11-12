"""Who runs devops-cli: a person, or an agent tool, an MCP call or a cluster Job (#5121)."""

from __future__ import annotations

import pytest

from devops_cli.core.caller import is_agent_caller, mcp_call


def test_a_caller_with_no_marker_is_a_person(person_caller: None) -> None:
    assert is_agent_caller() is False


def test_a_caller_that_an_agent_tool_marks_is_an_agent(agent_caller: None) -> None:
    assert is_agent_caller() is True


def test_an_mcp_call_is_an_agent(person_caller: None) -> None:
    with mcp_call():
        assert is_agent_caller() is True


def test_a_cluster_job_is_an_agent(person_caller: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "192.0.2.10")

    assert is_agent_caller() is True
