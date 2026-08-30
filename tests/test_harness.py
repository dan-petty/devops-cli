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

    items = plan.resolve_store().get_items()
    assert len(items) == 2
    assert items[0].content == "Step 1: Discover"
    assert items[1].content == "Step 2: Execute"

    prompt_additions = plan.get_system_prompt_additions()
    assert "You have access to a structured planning toolset" in prompt_additions[0]


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


def test_planning_in_memory_store_and_events() -> None:
    from devops_cli.ai.harness import (
        InMemoryPlanStore,
        PlanEvent,
        PlanEventEmitter,
        PlanItem,
    )

    events: list[str] = []
    emitter = PlanEventEmitter()

    @emitter.on_task_added
    def on_add(evt: PlanEvent) -> None:
        events.append(f"added:{evt.item.content}")

    @emitter.on_status_changed
    def on_status(evt: PlanEvent) -> None:
        events.append(f"status:{evt.item.content}->{evt.new_status}")

    @emitter.on_completed
    def on_done(evt: PlanEvent) -> None:
        events.append(f"done:{evt.item.content}")

    store = InMemoryPlanStore(event_emitter=emitter)
    item = store.add_item(PlanItem(content="First Task"))
    assert len(store.get_items()) == 1

    store.update_item_status(item.id, "in_progress")
    store.update_item_status(item.id, "completed")
    store.remove_item(item.id)
    assert len(store.get_items()) == 0

    assert "added:First Task" in events
    assert "status:First Task->in_progress" in events
    assert "done:First Task" in events


def test_planning_sqlite_store(tmp_path: Path) -> None:
    from devops_cli.ai.harness import PlanItem, SqlitePlanStore

    db_path = tmp_path / "test_plan.db"
    store = SqlitePlanStore(db_path=db_path, session="session-1")

    item1 = store.add_item(
        PlanItem(content="Step 1", active_form="Doing Step 1", status="in_progress")
    )
    item2 = store.add_item(PlanItem(content="Step 2", status="pending", depends_on=[item1.id]))

    items = store.get_items()
    assert len(items) == 2
    assert items[0].content == "Step 1"
    assert items[1].depends_on == [item1.id]

    store.update_item_status(item1.id, "completed")
    assert store.get_items()[0].status == "completed"

    store.remove_item(item2.id)
    assert len(store.get_items()) == 1

    # Overwrite whole items list
    store.set_items([PlanItem(content="Fresh Step")])
    assert len(store.get_items()) == 1
    assert store.get_items()[0].content == "Fresh Step"


def test_planning_capability_tools() -> None:
    from devops_cli.ai.harness import Planning

    planning = Planning()
    tools = {t.name: t for t in planning.get_tools()}

    assert "write_plan" in tools
    assert "read_plan" in tools
    assert "add_task" in tools
    assert "update_task_status" in tools
    assert "update_task_statuses" in tools
    assert "remove_task" in tools
    assert "update_plan" in tools

    # Test write_plan and read_plan
    write_res = tools["write_plan"].func([{"content": "Step 1"}, {"content": "Step 2"}])  # type: ignore[union-attr]
    assert "2 steps" in write_res

    read_res = tools["read_plan"].func()  # type: ignore[union-attr]
    assert "Plan Progress: 0/2 completed" in read_res

    # Test add_task
    add_res = tools["add_task"].func(content="Step 3", active_form="Implementing Step 3")  # type: ignore[union-attr]
    assert "Step 3" in add_res

    store_items = planning.resolve_store().get_items()
    assert len(store_items) == 3
    t1_id = store_items[0].id

    # Test update_task_status
    up_res = tools["update_task_status"].func(task_id=t1_id, status="in_progress")  # type: ignore[union-attr]
    assert "updated to 'in_progress'" in up_res

    invalid_st_res = tools["update_task_status"].func(task_id=t1_id, status="invalid_status")  # type: ignore[union-attr]
    assert "Error: invalid status" in invalid_st_res

    not_found_res = tools["update_task_status"].func(task_id="unknown-999", status="completed")  # type: ignore[union-attr]
    assert "not found" in not_found_res

    # Test update_task_statuses batch
    batch_res = tools["update_task_statuses"].func(updates=[{"id": t1_id, "status": "completed"}])  # type: ignore[union-attr]
    assert "Successfully updated" in batch_res

    batch_err = tools["update_task_statuses"].func(
        updates=[{"id": "unknown-id", "status": "completed"}]
    )  # type: ignore[union-attr]
    assert "Error: task id 'unknown-id' not found" in batch_err

    # Test remove_task
    rem_res = tools["remove_task"].func(task_id=t1_id)  # type: ignore[union-attr]
    assert "removed from plan" in rem_res


def test_planning_subtasks_and_dependencies() -> None:
    from devops_cli.ai.harness import Planning

    planning = Planning(enable_subtasks=True)
    tools = {t.name: t for t in planning.get_tools()}

    assert "add_subtask" in tools
    assert "set_dependency" in tools
    assert "get_available_tasks" in tools

    tools["write_plan"].func([{"content": "Parent Task"}])  # type: ignore[union-attr]
    parent_id = planning.resolve_store().get_items()[0].id

    # Add subtask
    sub_res = tools["add_subtask"].func(parent_id=parent_id, content="Child Task")  # type: ignore[union-attr]
    assert "Child Task" in sub_res
    child_id = planning.resolve_store().get_items()[1].id

    # Set dependency (child depends on parent)
    dep_res = tools["set_dependency"].func(task_id=child_id, depends_on_id=parent_id)  # type: ignore[union-attr]
    assert "status: blocked" in dep_res

    # Self-dependency error
    self_dep = tools["set_dependency"].func(task_id=child_id, depends_on_id=child_id)  # type: ignore[union-attr]
    assert "self-dependency not allowed" in self_dep

    # Hierarchical read
    h_read = tools["read_plan"].func(view="hierarchical")  # type: ignore[union-attr]
    assert "Parent Task" in h_read
    assert "Child Task" in h_read

    # Complete parent -> child auto unblocks
    tools["update_task_status"].func(task_id=parent_id, status="completed")  # type: ignore[union-attr]
    assert planning.resolve_store().get_items()[1].status == "pending"

    # Get available tasks
    avail = tools["get_available_tasks"].func()  # type: ignore[union-attr]
    assert "Child Task" in avail


def test_planning_hooks_and_options() -> None:
    import pytest

    from devops_cli.ai.agents.pydantic_agent import RunContext
    from devops_cli.ai.harness import InMemoryPlanStore, PlanItem, Planning
    from devops_cli.models.ai import ChatMessage

    # Allowlist filtering
    filtered = Planning(tools=["write_plan", "read_plan"])
    f_tool_names = [t.name for t in filtered.get_tools()]
    assert f_tool_names == ["write_plan", "read_plan"]

    with pytest.raises(ValueError, match="Unknown tool"):
        Planning(tools=["nonexistent_tool"]).get_tools()

    # Reject subtasks when enable_subtasks=False
    plain_plan = Planning(enable_subtasks=False)
    plain_tools = {t.name: t for t in plain_plan.get_tools()}
    with pytest.raises(ValueError, match="require enable_subtasks=True"):
        plain_tools["write_plan"].func([{"content": "Step", "status": "blocked"}])  # type: ignore[union-attr]

    # Custom store resolver
    custom_store = InMemoryPlanStore()
    custom_store.add_item(PlanItem(content="Custom Store Task", status="in_progress"))
    resolved_plan = Planning(store_resolver=lambda ctx: custom_store)
    ctx = RunContext(deps=None)
    assert resolved_plan.resolve_store(ctx).get_items()[0].content == "Custom Store Task"

    # Guidance omission
    assert Planning(guidance="").get_system_prompt_additions() == []
    assert len(Planning(guidance="Custom Guidance").get_system_prompt_additions()) == 1

    # Injection hook
    hook_plan = Planning(inject=True)
    hook_plan.resolve_store().add_item(
        PlanItem(content="Hook Task", status="in_progress", active_form="Hooking")
    )
    hooks = hook_plan.get_hooks()
    assert hooks is not None and len(hooks.before_model_request) == 1

    msgs = [ChatMessage(role="user", content="Hello agent")]
    hooks.before_model_request[0](ctx, msgs)
    assert "<plan-reminder" in msgs[-1].content
    assert "Hook Task (Hooking)" in msgs[-1].content


def test_clamp_effort_and_options() -> None:
    from devops_cli.ai.harness import (
        MINIMUM_EFFORT_FLOOR,
        ModelOption,
        clamp_effort,
    )

    assert clamp_effort(None) == MINIMUM_EFFORT_FLOOR
    assert clamp_effort(False) == MINIMUM_EFFORT_FLOOR
    assert clamp_effort(True) is True
    assert clamp_effort("minimal") == "low"
    assert clamp_effort("high") == "high"
    assert clamp_effort("max") == "max"

    opt = ModelOption(
        model="test-model", description="Reasoning model", settings={"thinking": "high"}
    )
    assert opt.model == "test-model"
    assert opt.description == "Reasoning model"


def test_subagent_run_controls_and_budget() -> None:
    from devops_cli.ai.harness import SubAgent, SubAgents

    call_history: list[str] = []

    def dummy_worker(prompt: str) -> str:
        call_history.append(prompt)
        if "fail" in prompt:
            raise ValueError("Execution failed")
        return f"Processed: {prompt}"

    sub = SubAgent(
        agent=dummy_worker,
        name="worker",
        description="Worker subagent",
        max_calls=2,
        on_failure="Fallback message for failure",
        contain_errors=True,
    )

    subagents = SubAgents(agents=[sub], contain_errors=True)
    tools = {t.name: t for t in subagents.get_tools()}

    assert "delegate_task" in tools
    assert "delegate_to_worker" in tools

    # First call succeeds
    res1 = tools["delegate_task"].func(agent_name="worker", task="Task 1")  # type: ignore[union-attr]
    assert res1 == "Processed: Task 1"

    # Second call succeeds
    res2 = tools["delegate_to_worker"].func(prompt="Task 2")  # type: ignore[union-attr]
    assert res2 == "Processed: Task 2"

    # Third call exhausts budget
    res3 = tools["delegate_task"].func(agent_name="worker", task="Task 3")  # type: ignore[union-attr]
    assert "Fallback message for failure" in res3

    # Test unknown agent
    unknown_res = tools["delegate_task"].func(agent_name="unknown", task="Task")  # type: ignore[union-attr]
    assert "Error: unknown sub-agent 'unknown'" in unknown_res

    # Test error containment and fallback
    failing_sub = SubAgent(
        agent=dummy_worker,
        name="failing_worker",
        contain_errors=True,
    )
    subagents_err = SubAgents(agents=[failing_sub])
    err_tools = {t.name: t for t in subagents_err.get_tools()}
    crashed_res = err_tools["delegate_task"].func(agent_name="failing_worker", task="fail now")  # type: ignore[union-attr]
    assert "Sub-agent 'failing_worker' crashed" in crashed_res


def test_subagent_model_routing() -> None:
    from devops_cli.ai.harness import ModelOption, SubAgent, SubAgents

    def mock_agent(prompt: str) -> str:
        return f"OK: {prompt}"

    sub1 = SubAgent(agent=mock_agent, name="fast_bot", models=["fast"])
    sub2 = SubAgent(agent=mock_agent, name="general_bot")

    subagents = SubAgents(
        agents=[sub1, sub2],
        models={
            "fast": "anthropic:claude-haiku",
            "deep": ModelOption(model="anthropic:claude-opus", description="deep reasoning"),
        },
    )

    tools = {t.name: t for t in subagents.get_tools()}

    # Call with allowed model
    ok_res = tools["delegate_task"].func(agent_name="fast_bot", task="fast task", model="fast")  # type: ignore[union-attr]
    assert ok_res == "OK: fast task"

    # Call with disallowed model for pinned subagent
    disallowed_res = tools["delegate_task"].func(
        agent_name="fast_bot", task="fast task", model="deep"
    )  # type: ignore[union-attr]
    assert "Error: model 'deep' not allowed for sub-agent 'fast_bot'" in disallowed_res

    # Call with unknown model
    unknown_model_res = tools["delegate_task"].func(
        agent_name="general_bot", task="gen task", model="unknown_model"
    )  # type: ignore[union-attr]
    assert "Error: model 'unknown_model' not in model menu" in unknown_model_res

    # System prompt additions check
    prompt_add = subagents.get_system_prompt_additions()[0]
    assert "Available Sub-Agents for delegation:" in prompt_add
    assert "fast_bot" in prompt_add
    assert "Model Menu:" in prompt_add


def test_subagents_markdown_disk_loading(tmp_path: Path) -> None:
    from devops_cli.ai.harness import SubAgents

    agent_dir = tmp_path / "agents"
    agent_dir.mkdir(parents=True)

    agent_file = agent_dir / "analyst.md"
    agent_file.write_text(
        "---\nname: analyst\ndescription: Data Analyst Agent\ntools: read_file, run_query\n---\nYou analyze system metrics and logs.",
        encoding="utf-8",
    )

    subagents = SubAgents(agent_folders=[agent_dir])
    loaded = subagents.load_disk_agents()

    assert len(loaded) == 1
    assert loaded[0].name == "analyst"
    assert loaded[0].description == "Data Analyst Agent"

    tools = {t.name: t for t in subagents.get_tools()}
    assert "delegate_to_analyst" in tools
