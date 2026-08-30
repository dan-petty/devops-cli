"""Unit tests for Pydantic AI Harness components and composite stacks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from devops_cli.ai.agents import PydanticAgent
from devops_cli.ai.harness import (
    Coder,
    FileSystem,
    Planning,
    RepoContext,
    Researcher,
    Shell,
    SubAgent,
    SubAgents,
)


def test_file_system_safe_operations(tmp_path: Path) -> None:
    test_file = tmp_path / "sample.txt"
    test_file.write_text("Hello from harness file system")

    fs = FileSystem(root=tmp_path)
    tools = {t.name: t for t in fs.get_tools() if hasattr(t, "name")}

    assert "read_file" in tools
    assert "write_file" in tools
    assert "list_directory" in tools

    read_res = tools["read_file"].execute(path="sample.txt")
    assert "Hello from harness file system" in read_res
    assert "sha256:" in read_res

    write_res = tools["write_file"].execute(
        path="nested/output.txt", content="New data\nSecond line"
    )
    assert "successfully written" in write_res
    assert (tmp_path / "nested" / "output.txt").read_text() == "New data\nSecond line"

    # Edit file
    edit_res = tools["edit_file"].execute(
        path="nested/output.txt", old_text="Second line", new_text="Edited line"
    )
    assert "successfully edited" in edit_res
    assert "Edited line" in (tmp_path / "nested" / "output.txt").read_text()

    # Search & Find
    search_res = tools["search_files"].execute(query="Edited", path=".")
    assert "nested/output.txt" in search_res

    find_res = tools["find_files"].execute(pattern="*.txt", path=".")
    assert "sample.txt" in find_res
    assert "nested/output.txt" in find_res

    # File info
    info_res = tools["file_info"].execute(path="nested/output.txt")
    assert "Size:" in info_res
    assert "sha256:" in info_res

    list_res = tools["list_directory"].execute(path=".")
    assert "sample.txt" in list_res
    assert "nested" in list_res


def test_file_system_protected_and_denied_patterns(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET=123")

    fs = FileSystem(root_dir=tmp_path)
    tools = {t.name: t for t in fs.get_tools() if hasattr(t, "name")}

    # Protected file (.env) is read-only
    write_res = tools["write_file"].execute(path=".env", content="NEW_SECRET=456")
    assert "Access denied" in write_res or "is protected" in write_res


def test_file_system_path_traversal_blocked(tmp_path: Path) -> None:
    fs = FileSystem(root=tmp_path)
    tools = {t.name: t for t in fs.get_tools() if hasattr(t, "name")}

    with pytest.raises(PermissionError):
        tools["read_file"].execute(path="../../../etc/passwd")


def test_shell_allowed_commands(tmp_path: Path) -> None:
    sh = Shell(cwd=tmp_path, allowed_commands=["echo", "ls"])
    tools = {t.name: t for t in sh.get_tools() if hasattr(t, "name")}

    res = tools["run_command"].execute(command="echo hello_devops")
    assert "hello_devops" in res
    assert "[stdout]" in res

    blocked_res = tools["run_command"].execute(command="rm -rf /")
    assert "blocked by security allowlist" in blocked_res


def test_shell_background_and_interactive(tmp_path: Path) -> None:
    sh = Shell(cwd=tmp_path, allowed_commands=["echo", "sleep"])
    tools = {t.name: t for t in sh.get_tools() if hasattr(t, "name")}

    # Background start, check, stop
    start_res = tools["start_command"].execute(command="sleep 10")
    assert "Background command started with ID: " in start_res
    cmd_id = start_res.split("ID: ")[1].strip()

    check_res = tools["check_command"].execute(command_id=cmd_id)
    assert "status:" in check_res

    stop_res = tools["stop_command"].execute(command_id=cmd_id)
    assert "terminated" in stop_res


def test_shell_denied_and_interactive_blocks(tmp_path: Path) -> None:
    sh = Shell(cwd=tmp_path, allow_interactive=False)
    tools = {t.name: t for t in sh.get_tools() if hasattr(t, "name")}

    interactive_res = tools["run_command"].execute(command="vi file.txt")
    assert "Interactive command 'vi' is blocked" in interactive_res

    denied_res = tools["run_command"].execute(command="rm -rf /tmp/foo")
    assert "blocked by security denylist" in denied_res

    with pytest.raises(ValueError):
        Shell(allowed_commands=["ls"], denied_commands=["rm"])


def test_planning_capability() -> None:
    plan = Planning()
    tools = {t.name: t for t in plan.get_tools() if hasattr(t, "name")}

    assert "update_plan" in tools
    update_res = tools["update_plan"].execute(steps=["Step 1: Discover", "Step 2: Execute"])
    assert "2 steps" in update_res

    prompt_additions = plan.get_system_prompt_additions()
    assert "1. Step 1: Discover" in prompt_additions[0]
    assert "2. Step 2: Execute" in prompt_additions[0]


def test_repo_context_injection(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("# Core Philosophy\nHigh Reliability First.")

    repo = RepoContext(workspace_dir=tmp_path)
    additions = repo.get_system_prompt_additions()
    assert len(additions) == 1
    assert "High Reliability First" in additions[0]


def test_sub_agents_delegation() -> None:
    mock_client = MagicMock()
    mock_client.model = "test-model"

    child_agent = PydanticAgent(
        client=mock_client,
        name="ExplorerAgent",
        system_prompt="Explore files.",
    )
    mock_client.chat_messages.return_value = "Found 3 services in k8s/."

    sub_agent_wrap = SubAgent(
        child_agent, name="explorer", description="Explores repository structure"
    )
    sub_agents_cap = SubAgents(agents=[sub_agent_wrap])
    tools = {t.name: t for t in sub_agents_cap.get_tools() if hasattr(t, "name")}

    assert "delegate_to_explorer" in tools
    res = tools["delegate_to_explorer"].execute(prompt="Check k8s directory")
    assert "Found 3 services in k8s/." in res


def test_coder_and_researcher_harness_stacks(tmp_path: Path) -> None:
    coder = Coder(workspace_dir=tmp_path)
    coder_tools = coder.get_tools()
    coder_tool_names = {t.name for t in coder_tools if hasattr(t, "name")}
    assert "read_file" in coder_tool_names
    assert "run_shell" in coder_tool_names
    assert "update_plan" in coder_tool_names

    researcher = Researcher()
    researcher_tools = researcher.get_tools()
    researcher_tool_names = {t.name for t in researcher_tools if hasattr(t, "name")}
    assert "web_fetch" in researcher_tool_names
    assert "duckduckgo_search" in researcher_tool_names


def test_coder_agent_factory(tmp_path: Path) -> None:
    from devops_cli.ai.harness import coder_agent

    mock_client = MagicMock()
    mock_client.model = "test-model"

    agent = coder_agent(client=mock_client, workspace_dir=tmp_path)
    assert agent.name == "coder"
    assert "read_file" in agent._tools
    assert "run_shell" in agent._tools
    assert "update_plan" in agent._tools


def test_researcher_agent_factory() -> None:
    from devops_cli.ai.harness import researcher_agent

    mock_client = MagicMock()
    mock_client.model = "test-model"

    agent = researcher_agent(client=mock_client)
    assert agent.name == "researcher"
    assert "web_fetch" in agent._tools
    assert "duckduckgo_search" in agent._tools
    assert "Search broadly before drawing conclusions" in agent.system_prompt


def test_macroscope_capability_missing_cli(tmp_path: Path) -> None:
    from devops_cli.ai.harness import Macroscope

    cap = Macroscope(command="nonexistent_macroscope_bin", cwd=tmp_path)
    tools = cap.get_tools()
    assert len(tools) == 1
    tool_func = tools[0].func  # type: ignore[union-attr]
    result = tool_func()
    assert "not found" in result
    assert "curl -sSL https://raw.githubusercontent.com/prassoai/macroscope-local" in result


def test_macroscope_capability_streaming_findings(tmp_path: Path) -> None:
    import json
    from unittest.mock import patch

    from devops_cli.ai.harness import Macroscope

    mock_output = "\n".join(
        [
            json.dumps({"type": "review_id", "id": "rev-12345"}),
            json.dumps(
                {
                    "type": "issue_event",
                    "issue": {
                        "issue_id": "iss-1",
                        "sequence": 1,
                        "path": "src/app.py",
                        "line": 42,
                        "severity": "high",
                        "category": "security",
                        "body": "Unsanitized user input leading to SQL injection",
                    },
                }
            ),
            json.dumps({"type": "issue_status", "status": "completed"}),
        ]
    )

    cap = Macroscope(base="main", cwd=tmp_path)
    sys_prompt = cap.get_system_prompt_additions()
    assert "Macroscope Code Review Capability enabled." in sys_prompt[0]

    with (
        patch("shutil.which", return_value="/usr/local/bin/macroscope"),
        patch("subprocess.run") as mock_run,
    ):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = mock_output
        mock_run.return_value = mock_proc

        tool = cap.get_tools()[0]
        res = tool.func()  # type: ignore[union-attr]
        assert "Macroscope Review (rev-12345)" in res
        assert "[HIGH] src/app.py:42 (security)" in res
        assert "Unsanitized user input" in res


def test_playwright_browser_capability() -> None:
    from devops_cli.ai.harness import PlaywrightBrowser

    browser_cap = PlaywrightBrowser(
        headless=True,
        block_private_addresses=True,
        allowed_domains=["example.com"],
    )

    prompt_additions = browser_cap.get_system_prompt_additions()
    assert "Playwright Browser Capability enabled." in prompt_additions[0]

    tools = {t.name: t for t in browser_cap.get_tools()}
    assert "navigate" in tools
    assert "snapshot" in tools
    assert "click" in tools
    assert "type_text" in tools
    assert "press_key" in tools
    assert "select_option" in tools
    assert "hover" in tools
    assert "wait_for" in tools
    assert "screenshot" in tools
    assert "get_text" in tools
    assert "scroll" in tools
    assert "go_back" in tools
    assert "go_forward" in tools
    assert "execute_js" in tools
    assert "console_messages" in tools
    assert "tabs" in tools
    assert "handle_next_dialog" in tools
    assert "network_requests" in tools

    # Navigate
    assert "Egress blocked" in tools["navigate"].func("http://127.0.0.1:8080/admin")  # type: ignore[union-attr]
    assert "Navigated to https://example.com" in tools["navigate"].func("https://example.com")  # type: ignore[union-attr]

    # Inspect other tools
    assert "RootWebArea" in tools["snapshot"].func()  # type: ignore[union-attr]
    assert "Clicked element '#btn'" in tools["click"].func(selector="#btn")  # type: ignore[union-attr]
    assert "Typed 'hello'" in tools["type_text"].func(selector="#input", text="hello")  # type: ignore[union-attr]
    assert "Pressed key 'Enter'" in tools["press_key"].func(key="Enter")  # type: ignore[union-attr]
    assert "Selected options" in tools["select_option"].func(selector="#dropdown", values=["val1"])  # type: ignore[union-attr]
    assert "Hovered over" in tools["hover"].func(selector="#item")  # type: ignore[union-attr]
    assert "Waited until #modal appeared" in tools["wait_for"].func(selector="#modal")  # type: ignore[union-attr]
    assert "Waited until #loader disappeared" in tools["wait_for"].func(
        selector="#loader", gone=True
    )  # type: ignore[union-attr]
    assert "Screenshot captured" in tools["screenshot"].func()  # type: ignore[union-attr]
    assert "Page text content" in tools["get_text"].func()  # type: ignore[union-attr]
    assert "Scrolled page down" in tools["scroll"].func(direction="down")  # type: ignore[union-attr]
    assert "Navigated back" in tools["go_back"].func()  # type: ignore[union-attr]
    assert "Navigated forward" in tools["go_forward"].func()  # type: ignore[union-attr]
    assert "Script executed" in tools["execute_js"].func(script="console.log('hi')")  # type: ignore[union-attr]
    assert "Console logs:" in tools["console_messages"].func()  # type: ignore[union-attr]
    assert "Tabs action 'list'" in tools["tabs"].func(action="list")  # type: ignore[union-attr]
    assert "Next dialog configured" in tools["handle_next_dialog"].func(accept=True)  # type: ignore[union-attr]
    assert "Network requests:" in tools["network_requests"].func()  # type: ignore[union-attr]


def test_file_system_edge_cases(tmp_path: Path) -> None:
    from devops_cli.ai.harness import FileSystem

    fs = FileSystem(root=tmp_path)
    tools = {t.name: t for t in fs.get_tools() if hasattr(t, "name")}

    # Non-existent file read
    assert "file not found" in tools["read_file"].execute(path="nonexistent.txt")

    # Binary file read
    bin_file = tmp_path / "data.bin"
    bin_file.write_bytes(b"\x00\x01\x02\x03\x04")
    assert "Binary file" in tools["read_file"].execute(path="data.bin")

    # Stale edit conflict on write
    text_file = tmp_path / "test.txt"
    text_file.write_text("v1 content")
    res_stale = tools["write_file"].execute(
        path="test.txt", content="v2 content", expected_hash="wrong_hash"
    )
    assert "stale edit conflict" in res_stale

    # Edit file not found
    assert "file not found" in tools["edit_file"].execute(
        path="missing.txt", old_text="a", new_text="b"
    )

    # Edit file old text not found
    assert "target old_text not found" in tools["edit_file"].execute(
        path="test.txt", old_text="nonexistent text", new_text="b"
    )

    # Edit file duplicate match
    text_file.write_text("word word word")
    assert "matches 3 times" in tools["edit_file"].execute(
        path="test.txt", old_text="word", new_text="replacement"
    )

    # Edit file stale hash
    assert "stale edit conflict" in tools["edit_file"].execute(
        path="test.txt", old_text="word", new_text="replacement", expected_hash="bad_hash"
    )

    # List directory not a dir
    assert "not a directory" in tools["list_directory"].execute(path="test.txt")

    # Find files not a dir
    assert "not a directory" in tools["find_files"].execute(pattern="*", path="test.txt")


def test_macroscope_empty_and_exceptions(tmp_path: Path) -> None:
    import subprocess
    from unittest.mock import patch

    from devops_cli.ai.harness import Macroscope

    cap = Macroscope(base="main", cwd=tmp_path, timeout=5)
    tools = cap.get_tools()
    tool = tools[0]

    # Empty review
    with (
        patch("shutil.which", return_value="/usr/local/bin/macroscope"),
        patch("subprocess.run") as mock_run,
    ):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = '{"type": "review_id", "id": "rev-999"}\n{"type": "issue_status", "status": "completed"}'
        mock_run.return_value = mock_proc

        res = tool.func()  # type: ignore[union-attr]
        assert "0 issues found" in res

    # TimeoutExpired exception
    with (
        patch("shutil.which", return_value="/usr/local/bin/macroscope"),
        patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="macroscope", timeout=5)),
    ):
        res = tool.func()  # type: ignore[union-attr]
        assert "timed out after" in res

    # General Exception
    with (
        patch("shutil.which", return_value="/usr/local/bin/macroscope"),
        patch("subprocess.run", side_effect=OSError("Process failed")),
    ):
        res = tool.func()  # type: ignore[union-attr]
        assert "Macroscope review error:" in res


def test_tool_output_limits_and_hooks() -> None:
    from devops_cli.ai.harness import ClearToolResults, ToolOutputLimits, WarnNearLimits

    # Limits capability
    lim = ToolOutputLimits(max_chars=1000)
    assert lim.max_chars == 1000

    # ClearToolResults
    clearer = ClearToolResults(max_fraction=0.8)
    assert clearer.max_fraction == 0.8
    assert clearer.get_tools() == []

    # WarnNearLimits
    warner = WarnNearLimits(max_context_fraction=0.85)
    assert warner.max_context_fraction == 0.85
    assert warner.get_tools() == []
