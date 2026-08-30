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


def test_dynamic_workflow_script_execution() -> None:
    import asyncio

    from devops_cli.ai.harness import DynamicWorkflow, WorkflowAgent

    def reviewer_func(prompt: str) -> str:
        return f"Review findings for: {prompt}"

    def summarizer_func(prompt: str) -> str:
        return f"Summary of: {prompt}"

    reviewer = WorkflowAgent(agent=reviewer_func, name="reviewer", description="Reviews code")
    summarizer = WorkflowAgent(
        agent=summarizer_func, name="summarizer", description="Summarizes reports"
    )

    workflow = DynamicWorkflow(agents=[reviewer, summarizer])
    tools = {t.name: t for t in workflow.get_tools()}
    assert "run_workflow" in tools

    run_wf = tools["run_workflow"].func

    # Test sequential chaining and last expression value
    script1 = """
import asyncio
rep1 = await reviewer(task="auth.py")
rep2 = await reviewer(task="parser.py")
await summarizer(task=rep1 + " and " + rep2)
"""
    res1 = asyncio.run(run_wf(code=script1))  # type: ignore[union-attr]
    assert "Summary of: Review findings for: auth.py and Review findings for: parser.py" in res1

    # Test concurrent fan-out with asyncio.gather
    script2 = """
import asyncio
reports = await asyncio.gather(
    reviewer(task="file_a.py"),
    reviewer(task="file_b.py")
)
reports
"""
    res2 = asyncio.run(run_wf(code=script2))  # type: ignore[union-attr]
    assert isinstance(res2, list)
    assert len(res2) == 2
    assert "Review findings for: file_a.py" in res2[0]


def test_dynamic_workflow_structured_outputs_and_prints() -> None:
    import asyncio

    from pydantic import BaseModel

    from devops_cli.ai.harness import DynamicWorkflow, WorkflowAgent

    class ReviewScore(BaseModel):
        score: int
        comment: str

    def critic_func(prompt: str) -> ReviewScore:
        return ReviewScore(score=9, comment="Great code")

    critic = WorkflowAgent(agent=critic_func, name="critic", output_type=ReviewScore)
    workflow = DynamicWorkflow(agents=[critic])
    run_wf = {t.name: t for t in workflow.get_tools()}["run_workflow"].func

    # Test subscript access to Pydantic model outputs and print capture
    script = """
print("Starting criticism...")
res = await critic(task="Check quality")
print("Criticism complete")
{"final_score": res["score"], "reason": res["comment"]}
"""
    output_res = asyncio.run(run_wf(code=script))  # type: ignore[union-attr]
    assert isinstance(output_res, dict)
    assert "output" in output_res
    assert "Starting criticism...\nCriticism complete" in output_res["output"]
    assert output_res["result"] == {"final_score": 9, "reason": "Great code"}


def test_dynamic_workflow_budget_and_reveal() -> None:
    import asyncio

    import pytest

    from devops_cli.ai.harness import DynamicWorkflow, WorkflowAgent

    def worker(prompt: str) -> str:
        return f"Done: {prompt}"

    workflow = DynamicWorkflow(
        agents=[WorkflowAgent(agent=worker, name="w1")],
        max_agent_calls=2,
        defer_loading=True,
    )

    # Prompt additions when deferred
    prompts = workflow.get_system_prompt_additions()
    assert "DynamicWorkflow [dynamic_workflow]" in prompts[0]

    # Test reveal() validation
    with pytest.raises(ValueError, match="Invalid agent name"):
        workflow.reveal(WorkflowAgent(agent=worker, name="123invalid"))

    with pytest.raises(ValueError, match="Agent name collision"):
        workflow.reveal(WorkflowAgent(agent=worker, name="w1"))

    workflow.reveal(WorkflowAgent(agent=worker, name="w2"))
    assert len(workflow.agents) == 2

    # Test positional task error
    run_wf = {t.name: t for t in workflow.get_tools()}["run_workflow"].func
    err_pos = asyncio.run(run_wf(code='await w1("positional")'))  # type: ignore[union-attr]
    assert "must be called with keyword argument task=" in err_pos

    # Test max_agent_calls budget limit
    budget_script = """
await w1(task="call 1")
await w2(task="call 2")
await w1(task="call 3")
"""
    err_budget = asyncio.run(run_wf(code=budget_script))  # type: ignore[union-attr]
    assert "Workflow budget exhausted: reached maximum agent calls (2)" in err_budget


def test_dynamic_workflow_edge_cases_and_syntax() -> None:
    import asyncio

    from devops_cli.ai.harness import DynamicWorkflow, WorkflowAgent

    class NonPydanticResult:
        def __init__(self, val: str) -> None:
            self.val = val

    class AsyncAgent:
        async def run_async(self, prompt: str) -> NonPydanticResult:
            return NonPydanticResult(val=f"async_{prompt}")

    workflow = DynamicWorkflow(
        agents=[
            WorkflowAgent(agent=AsyncAgent(), name="async_bot"),
            WorkflowAgent(agent="static_string_agent", name="str_bot"),
        ]
    )
    run_wf = {t.name: t for t in workflow.get_tools()}["run_workflow"].func

    # Test syntax error handling
    err_syntax = asyncio.run(run_wf(code="def invalid syntax here: : :"))  # type: ignore[union-attr]
    assert "SyntaxError in workflow script" in err_syntax

    # Test async runner execution and custom object dict unpacking
    script_async = """
res = await async_bot(task="test_async")
res["val"]
"""
    res_async = asyncio.run(run_wf(code=script_async))  # type: ignore[union-attr]
    assert res_async == "async_test_async"

    # Test static string agent call
    res_str = asyncio.run(run_wf(code='await str_bot(task="ping")'))  # type: ignore[union-attr]
    assert res_str == "static_string_agent"

    # Test script with only prints and None return
    script_print_only = """
print("Only printing")
"""
    res_print = asyncio.run(run_wf(code=script_print_only))  # type: ignore[union-attr]
    assert res_print == {"output": "Only printing"}

    # Test script with empty return and no print
    script_empty = """
pass
"""
    res_empty = asyncio.run(run_wf(code=script_empty))  # type: ignore[union-attr]
    assert res_empty == {}


def test_subagents_edge_cases() -> None:
    from devops_cli.ai.harness import AgentOverride, SubAgent, SubAgents

    def sync_worker(prompt: str) -> str:
        return f"Echo: {prompt}"

    sa = SubAgents(
        agents=[SubAgent(agent=sync_worker, name="echoer")],
        models={"default": "anthropic:claude-3-5-sonnet"},
        agent_folders=None,
        agent_overrides={"analyst": AgentOverride(model="gpt-4o", effort="high")},
    )

    # load_disk_agents returns empty when agent_folders is None
    assert sa.load_disk_agents() == []

    # get_system_prompt_additions when empty
    empty_sa = SubAgents(agent_folders=None)
    assert "No sub-agents currently registered" in empty_sa.get_system_prompt_additions()[0]

    # Tool invocation
    tools = {t.name: t for t in sa.get_tools()}
    res = tools["delegate_task"].func(agent_name="echoer", task="hello")  # type: ignore[union-attr]
    assert res == "Echo: hello"


def test_advisor_capability_initialization_and_validation() -> None:
    import pytest

    from devops_cli.ai.harness import Advisor

    # Valid initialization
    adv = Advisor("anthropic:claude-3-5-sonnet", mode="auto", max_uses=3, max_tokens=2048)
    assert adv.model == "anthropic:claude-3-5-sonnet"
    assert adv.max_uses == 3
    assert adv.max_tokens == 2048

    # Validation errors
    with pytest.raises(ValueError, match="max_uses must be at least 1"):
        Advisor("openai:gpt-4o", max_uses=0)

    with pytest.raises(ValueError, match="max_tokens must be at least 1024"):
        Advisor("openai:gpt-4o", max_tokens=500)

    with pytest.raises(ValueError, match="OpenRouter native advisor does not support max_uses"):
        Advisor("openrouter:anthropic/claude-3.5-sonnet", mode="native", max_uses=2)

    with pytest.raises(ValueError, match="caching is only supported on Anthropic native advisor"):
        Advisor("openai:gpt-4o", mode="native", caching="5m")


def test_advisor_consultation_execution_and_limits() -> None:
    import asyncio

    from devops_cli.ai.harness import Advisor

    def mock_advisor_sync(prompt: str) -> str:
        return f"Advice: {prompt}"

    class AsyncMockAdvisor:
        async def run_async(self, prompt: str) -> str:
            return f"Async advice: {prompt}"

    adv_sync = Advisor(model=mock_advisor_sync, max_uses=2)
    tools = {t.name: t for t in adv_sync.get_tools()}
    assert "advisor" in tools
    adv_fn = tools["advisor"].func

    # First call
    res1 = asyncio.run(adv_fn(prompt="How to refactor?"))  # type: ignore[union-attr]
    assert res1 == "Advice: How to refactor?"

    # Second call
    res2 = asyncio.run(adv_fn(prompt="Check security"))  # type: ignore[union-attr]
    assert res2 == "Advice: Check security"

    # Third call exceeds max_uses
    res3 = asyncio.run(adv_fn(prompt="Another question"))  # type: ignore[union-attr]
    assert "Maximum advisor consultations (2) reached" in res3

    # Test for_run isolation
    adv_fresh = adv_sync.for_run()
    assert adv_fresh.current_uses == 0
    fresh_tools = {t.name: t for t in adv_fresh.get_tools()}
    fresh_res = asyncio.run(fresh_tools["advisor"].func(prompt="Fresh start"))  # type: ignore[union-attr]
    assert fresh_res == "Advice: Fresh start"

    # Test async runner model
    adv_async = Advisor(model=AsyncMockAdvisor())
    async_tool = {t.name: t for t in adv_async.get_tools()}["advisor"].func
    res_async = asyncio.run(async_tool(prompt="Async check"))  # type: ignore[union-attr]
    assert res_async == "Async advice: Async check"

    # Test deferred prompts
    adv_def = Advisor("openai:gpt-4o", defer_loading=True)
    assert "Advisor [advisor]:" in adv_def.get_system_prompt_additions()[0]


def test_code_mode_execution_and_tool_wrapping() -> None:
    import asyncio
    from typing import Any

    from devops_cli.ai.agents.pydantic_agent import Tool
    from devops_cli.ai.harness import CodeMode, MountDir, OSAccess

    def get_weather(city: str) -> dict[str, Any]:
        temp = 72 if city == "Paris" else 65
        return {"city": city, "temp_f": temp, "condition": "sunny"}

    async def get_traffic(city: str) -> str:
        return f"Light traffic in {city}"

    weather_tool = Tool.from_function(get_weather, name="get_weather")
    traffic_tool = Tool.from_function(get_traffic, name="get_traffic")

    cm = CodeMode(
        sandboxed_tools=[weather_tool, traffic_tool],
        mount=MountDir(virtual_path="/work", host_path="/tmp/agent-work", mode="read-write"),
        os_access=OSAccess(environ={"API_KEY": "secret-123"}),
        max_tool_calls=5,
    )
    tools = {t.name: t for t in cm.get_tools()}
    assert "run_code" in tools
    run_fn = tools["run_code"].func

    # Test concurrent fan-out and last expression return
    script1 = """
import asyncio
paris, tokyo = await asyncio.gather(
    get_weather(city="Paris"),
    get_weather(city="Tokyo")
)
traf = await get_traffic(city="Paris")
summary = f"{paris['city']}: {paris['temp_f']}F, {tokyo['city']}: {tokyo['temp_f']}F - {traf}"
summary
"""
    res1 = asyncio.run(run_fn(code=script1))  # type: ignore[union-attr]
    assert "Paris: 72F, Tokyo: 65F - Light traffic in Paris" in res1

    # Test REPL state persistence across calls
    script2 = """
var_from_call1 = summary.upper()
var_from_call1
"""
    res2 = asyncio.run(run_fn(code=script2))  # type: ignore[union-attr]
    assert "PARIS: 72F, TOKYO: 65F - LIGHT TRAFFIC IN PARIS" in res2

    # Test print capturing with result
    script3 = """
print("Logging metric...")
{"status": "ok", "prev": var_from_call1[:5]}
"""
    res3 = asyncio.run(run_fn(code=script3))  # type: ignore[union-attr]
    assert isinstance(res3, dict)
    assert res3["output"] == "Logging metric..."
    assert res3["result"] == {"status": "ok", "prev": "PARIS"}

    # Test restart=True resets REPL state
    res4 = asyncio.run(run_fn(code="print('restart done')", restart=True))  # type: ignore[union-attr]
    assert res4 == {"output": "restart done"}
    assert cm.repl_state == {}

    # Test syntax error handling
    err_syntax = asyncio.run(run_fn(code="def broken syntax :::"))  # type: ignore[union-attr]
    assert "SyntaxError in code mode snippet" in err_syntax

    # Test max_tool_calls limit
    budget_script = """
for i in range(10):
    await get_weather(city=f"City_{i}")
"""
    err_budget = asyncio.run(run_fn(code=budget_script))  # type: ignore[union-attr]
    assert "Nested tool call limit exceeded: maximum 5" in err_budget

    # Test for_run isolation
    fresh_cm = cm.for_run()
    assert fresh_cm.tool_call_count == 0
    assert fresh_cm.repl_state == {}

    # Test deferred prompts
    cm_def = CodeMode(defer_loading=True)
    assert "CodeMode [code_mode]:" in cm_def.get_system_prompt_additions()[0]


def test_tool_search_discovery_and_strategies() -> None:
    import asyncio
    from typing import Any

    from devops_cli.ai.agents.pydantic_agent import Tool
    from devops_cli.ai.harness import ToolSearch

    def calculate_mortgage(principal: float, rate: float) -> float:
        """Calculate monthly mortgage payment for a home loan."""
        return principal * (rate / 12)

    def calculate_compound_interest(principal: float, rate: float, time: int) -> float:
        """Calculate compound interest over investment timeline."""
        return principal * ((1 + rate) ** time)

    def weather_lookup(city: str) -> str:
        """Check weather forecast and rain condition for a given city."""
        return f"Sunny in {city}"

    t_mortgage = Tool.from_function(calculate_mortgage, name="calculate_mortgage")
    t_interest = Tool.from_function(calculate_compound_interest, name="calculate_compound_interest")
    t_weather = Tool.from_function(weather_lookup, name="weather_lookup")

    # 1. Test Default Keyword search
    ts = ToolSearch(
        searchable_tools=[t_mortgage, t_interest, t_weather],
        max_results=2,
    )
    tools = {t.name: t for t in ts.get_tools()}
    assert "search_tools" in tools
    search_fn = tools["search_tools"].func

    # First search for finance loans
    res1 = asyncio.run(search_fn(queries=["mortgage loan"]))  # type: ignore[union-attr]
    assert res1["count"] == 1
    assert res1["matched_tools"][0]["name"] == "calculate_mortgage"
    assert "calculate_mortgage" in ts.discovered_tools

    # Second search matches compound interest and mortgage (undiscovered ranks first)
    res2 = asyncio.run(search_fn(queries=["calculate interest payment"]))  # type: ignore[union-attr]
    assert res2["count"] == 2
    assert res2["matched_tools"][0]["name"] == "calculate_compound_interest"

    # 2. Test Regex strategy
    ts_regex = ToolSearch(
        strategy="regex",
        searchable_tools=[t_mortgage, t_interest, t_weather],
    )
    search_regex_fn = {t.name: t for t in ts_regex.get_tools()}["search_tools"].func
    res_regex = asyncio.run(search_regex_fn(queries=[r"weather_.*"]))  # type: ignore[union-attr]
    assert res_regex["count"] == 1
    assert res_regex["matched_tools"][0]["name"] == "weather_lookup"

    # 3. Test BM25 strategy
    ts_bm25 = ToolSearch(
        strategy="bm25",
        searchable_tools=[t_mortgage, t_interest, t_weather],
    )
    search_bm25_fn = {t.name: t for t in ts_bm25.get_tools()}["search_tools"].func
    res_bm25 = asyncio.run(search_bm25_fn(queries=["forecast rain sunny"]))  # type: ignore[union-attr]
    assert res_bm25["count"] == 1
    assert res_bm25["matched_tools"][0]["name"] == "weather_lookup"

    # 4. Test Custom callable strategy
    def custom_filter(ctx: Any, queries: list[str], tools_list: list[Any]) -> list[str]:
        return ["calculate_compound_interest"]

    ts_custom = ToolSearch(
        strategy=custom_filter,
        searchable_tools=[t_mortgage, t_interest, t_weather],
    )
    search_custom_fn = {t.name: t for t in ts_custom.get_tools()}["search_tools"].func
    res_custom = asyncio.run(search_custom_fn(queries=["custom query"]))  # type: ignore[union-attr]
    assert res_custom["count"] == 1
    assert res_custom["matched_tools"][0]["name"] == "calculate_compound_interest"

    # 5. Test empty queries / no tools
    ts_empty = ToolSearch(searchable_tools=[])
    search_empty_fn = {t.name: t for t in ts_empty.get_tools()}["search_tools"].func
    res_empty = asyncio.run(search_empty_fn(queries=[]))  # type: ignore[union-attr]
    assert res_empty["count"] == 0

    # 6. Test for_run isolation
    fresh_ts = ts.for_run()
    assert fresh_ts.discovered_tools == set()

    # 7. Test deferred system prompt
    ts_def = ToolSearch(defer_loading=True)
    assert "ToolSearch [tool_search]:" in ts_def.get_system_prompt_additions()[0]


def test_compaction_suite() -> None:
    from devops_cli.ai.harness import (
        ClampOversizedMessages,
        ClearToolResults,
        DeduplicateFileReads,
        FallbackCompaction,
        ReportContextUsage,
        SlidingWindowCompaction,
        SummarizingCompaction,
        TieredCompaction,
        WarnNearLimits,
        compact_now,
        is_pinned,
        pin,
        reinject_pinned,
    )
    from devops_cli.models.ai import ChatMessage

    # 1. Test pin, is_pinned, reinject_pinned
    msg1 = ChatMessage(role="system", content="System instruction")
    msg2 = ChatMessage(role="user", content="User prompt")
    pin(msg1)
    assert is_pinned(msg1) is True
    assert is_pinned(msg2) is False

    reinj = reinject_pinned([msg2], [msg1])
    assert reinj[0] == msg1
    assert reinj[1] == msg2

    # 2. Test ClampOversizedMessages
    huge_msg = ChatMessage(role="user", content="A" * 30000)
    clamp = ClampOversizedMessages(max_chars=1000)
    clamped = clamp.compact_messages([huge_msg])
    assert len(clamped[0].content) < 2000
    assert "Truncated content:" in clamped[0].content

    # Pinned message is preserved
    pin(huge_msg)
    preserved = clamp.compact_messages([huge_msg])
    assert len(preserved[0].content) == 30000

    # 3. Test ClearToolResults
    tool_msg1 = ChatMessage(role="user", content="[Tool Result: grep] Output 1")
    tool_msg2 = ChatMessage(role="user", content="[Tool Result: grep] Output 2")
    tool_msg3 = ChatMessage(role="user", content="[Tool Result: grep] Output 3")
    clear_cap = ClearToolResults(keep_pairs=1)
    cleared = clear_cap.compact_messages([msg1, tool_msg1, tool_msg2, tool_msg3])
    assert "[Cleared tool result:" in cleared[1].content
    assert "[Cleared tool result:" in cleared[2].content
    assert cleared[3].content == "[Tool Result: grep] Output 3"

    # Also test dict-based tool results
    dict_tools = [
        {"role": "tool", "content": "Out 1", "name": "grep", "tool_call_id": "c1"},
        {"role": "tool", "content": "Out 2", "name": "grep", "tool_call_id": "c2"},
    ]
    cleared_dicts = clear_cap.compact_messages(dict_tools)
    assert "[Cleared tool result: grep]" in cleared_dicts[0]["content"]

    # 4. Test DeduplicateFileReads
    read_msg1 = {
        "role": "tool",
        "content": "v1 contents",
        "name": "read_file",
        "tool_call_id": "call_a",
    }
    read_msg2 = {
        "role": "tool",
        "content": "v2 contents",
        "name": "read_file",
        "tool_call_id": "call_b",
    }
    dedupe = DeduplicateFileReads()
    deduped = dedupe.compact_messages([read_msg1, read_msg2])
    assert "[Superseded file read: read_file]" in deduped[0]["content"]
    assert deduped[1]["content"] == "v2 contents"

    # 5. Test SlidingWindowCompaction
    # 5. Test SlidingWindowCompaction with receipts
    msgs = [ChatMessage(role="system", content="Prompt")] + [
        ChatMessage(role="user", content=f"Turn {i}") for i in range(10)
    ]
    sw = SlidingWindowCompaction(max_messages=3)
    sw_compacted = sw.compact_messages(msgs)
    assert len(sw_compacted) == 4  # System + last 3
    assert sw_compacted[0].content == "Prompt"
    assert sw_compacted[-1].content == "Turn 9"

    class DummyHandleProvider:
        def compaction_transcript_handle(self) -> str:
            return "run-12345"

    sw_receipts = SlidingWindowCompaction(
        max_messages=3, receipts=True, transcript_handle_provider=DummyHandleProvider()
    )
    sw_receipts_res = sw_receipts.compact_messages(msgs)
    assert "Compaction Receipt:" in sw_receipts_res[1].content
    assert "handle=run-12345" in sw_receipts_res[1].content

    # 6. Test SummarizingCompaction with incremental & bridge_prefix
    sum_cap = SummarizingCompaction(
        keep_tail=2,
        bridge_prefix=True,
        receipts=True,
        transcript_handle_provider=DummyHandleProvider(),
    )
    sum_compacted = sum_cap.compact_messages(msgs)
    assert "Compaction Receipt:" in sum_compacted[1].content
    assert "Conversation Summary:" in sum_compacted[2].content
    assert "Cross-model bridge:" in sum_compacted[2].content

    # Incremental update on already summarized turn
    incremental_res = sum_cap.compact_messages(
        sum_compacted + [ChatMessage(role="user", content="Turn 11")]
    )
    assert "<previous-summary>" in incremental_res[2].content

    # 7. Test FallbackCompaction & TieredCompaction
    tiered = TieredCompaction(
        tiers=[ClearToolResults(keep_pairs=1), SlidingWindowCompaction(max_messages=2)]
    )
    res_tiered = tiered.compact_messages([msg1, tool_msg1, tool_msg2, tool_msg3])
    assert len(res_tiered) <= 3

    fallback = FallbackCompaction(strategies=[tiered])
    res_fallback = fallback.compact_messages([msg1, msg2])
    assert len(res_fallback) == 2

    # 8. Test WarnNearLimits
    warn_cap = WarnNearLimits(max_context_fraction=0.85)
    assert "85%" in warn_cap.get_system_prompt_additions()[0]

    # 9. Test ReportContextUsage & compact_now
    reporter = ReportContextUsage()
    usage = reporter.get_usage([msg1, msg2], context_limit=10000)
    assert usage.message_count == 2
    assert usage.context_fraction >= 0.0

    compacted_direct = compact_now([msg1, msg2], strategy=sw)
    assert len(compacted_direct) == 2


def test_tool_output_limits_suite(tmp_path: Path) -> None:
    from devops_cli.ai.harness import (
        Band,
        LocalFileStore,
        Passthrough,
        Spill,
        Summarize,
        ToolOutputLimits,
        Truncate,
        TruncationStrategy,
        indented_json,
        json_lines,
    )

    # 1. Test Truncation strategies
    t_head = Truncate(max_chars=20, strategy=TruncationStrategy.head)
    assert (
        t_head.reduce("12345678901234567890EXTRA")
        == "12345678901234567890\n\n[... 5 characters truncated ...]"
    )

    t_tail = Truncate(max_chars=20, strategy=TruncationStrategy.tail)
    assert (
        t_tail.reduce("EXTRA12345678901234567890")
        == "[... 5 characters truncated ...]\n\n12345678901234567890"
    )

    t_head_tail = Truncate(max_chars=10, strategy=TruncationStrategy.head_tail)
    assert "truncated" in t_head_tail.reduce("12345678901234567890")

    # 2. Test LocalFileStore and slicing
    store = LocalFileStore(base_dir=tmp_path / "spills")
    handle = store.write("sample", b"line1\nline2\nline3\nline4\nline5")
    assert "spill_sample_" in handle
    assert store.read(handle) == b"line1\nline2\nline3\nline4\nline5"

    slice_head = store.read_slice(handle, offset=0, limit=2)
    assert slice_head == "line1\nline2"

    slice_tail = store.read_slice(handle, limit=2, from_end=True)
    assert slice_tail == "line4\nline5"

    slice_filter = store.read_slice(handle, pattern="line3")
    assert slice_filter == "line3"

    # 3. Test Serializers
    struct_val = {"key": "value", "count": 42}
    ind_res = indented_json(struct_val)
    assert '"key": "value"' in ind_res
    assert "\n" in ind_res

    jl_res = json_lines([{"a": 1}, {"b": 2}])
    assert '{"a": 1}\n{"b": 2}' == jl_res

    # 4. Test ToolOutputLimits with Bands
    tol = ToolOutputLimits(
        bands=[
            Band(over=1000, action=Spill(store=store, then=Truncate(max_chars=50))),
            Band(over=500, action=Summarize()),
            Band(over=100, action=Truncate(max_chars=50)),
            Band(over=50, action=Passthrough()),
        ],
        per_tool={"custom_tool": [Band(over=20, action=Truncate(max_chars=10))]},
        tool_filter=["test_tool", "custom_tool", "structured_tool"],
        over_tokens=True,
        tokenizer=lambda s: len(s) // 2,
        serializer=indented_json,
        strip_ansi=True,
        store=store,
    )

    # Tool exemption: read_tool_result
    res_exempt, red_exempt = tol.reduce_output("read_tool_result", "X" * 5000)
    assert not red_exempt

    # Tool filter: unlisted tool passes through
    res_unlisted, red_unlisted = tol.reduce_output("other_tool", "X" * 5000)
    assert not red_unlisted

    # Bytes pass through
    res_bytes, red_bytes = tol.reduce_output("test_tool", b"raw bytes")
    assert not red_bytes
    assert res_bytes == b"raw bytes"

    # Structured object with serializer
    res_struct, red_struct = tol.reduce_output("structured_tool", {"large": "data" * 100})
    assert red_struct

    # per_tool override
    res_per_tool, red_per_tool = tol.reduce_output("custom_tool", "a" * 50)
    assert red_per_tool
    assert "truncated" in res_per_tool

    # Below 50: passthrough
    res, reduced = tol.reduce_output("test_tool", "Short output")
    assert not reduced
    assert res == "Short output"

    # 60 chars (Passthrough band)
    res_pass, red_pass = tol.reduce_output("test_tool", "X" * 120)
    assert not red_pass
    assert len(res_pass) == 120

    # 200 tokens (Truncate band)
    res_trunc, red_trunc = tol.reduce_output("test_tool", "T" * 300)
    assert red_trunc
    assert "truncated" in res_trunc

    # 600 tokens (Summarize band)
    res_sum, red_sum = tol.reduce_output("test_tool", ("line\n" * 300))
    assert red_sum
    assert "[Summary of test_tool" in res_sum

    # 2000 tokens (Spill band)
    res_spill, red_spill = tol.reduce_output("test_tool", "S" * 3000, tool_call_id="call1")
    assert red_spill
    assert "[Tool output spilled:" in res_spill
    assert "Handle:" in res_spill

    # Test Spill fallback when store errors
    class FailingStore:
        def write(self, key: str, data: bytes) -> str:
            raise RuntimeError("Disk full")

    spill_fail = Spill(store=FailingStore(), then=Truncate(max_chars=20))
    res_spill_fail = spill_fail.reduce("Long text that cannot be spilled to disk")
    assert "truncated" in res_spill_fail

    # Test tool registration
    tools = tol.get_tools()
    assert len(tools) == 1
    assert tools[0].name == "read_tool_result"
    assert "line1" in tools[0].execute(handle=handle, offset=0, limit=2)
    assert "Error" in tools[0].execute(handle="nonexistent_handle")


def test_warn_on_cache_busts_suite() -> None:
    import pytest

    from devops_cli.ai.harness import CacheBustWarning, WarnOnCacheBusts

    # 1. Test validation error on zero/negative collapse_ratio
    with pytest.raises(ValueError, match="collapse_ratio must be greater than 0.0"):
        WarnOnCacheBusts(collapse_ratio=0.0)

    # 2. Test normal operation and warnings
    monitor = WarnOnCacheBusts(
        collapse_ratio=0.5,
        min_prefix_tokens=1000,
        cache_ttl_seconds=300.0,
    )

    # First request establishes prefix of 2000 tokens (read=0, write=2000)
    w1 = monitor.record_usage(
        "anthropic",
        "claude-3-5-sonnet",
        cache_read_tokens=0,
        cache_write_tokens=2000,
        current_time=100.0,
    )
    assert w1 is None
    mark = monitor.marks[("anthropic", "claude-3-5-sonnet")]
    assert mark.established_prefix == 2000

    # Second request hits cache with 2000 tokens -> healthy
    w2 = monitor.record_usage(
        "anthropic",
        "claude-3-5-sonnet",
        cache_read_tokens=2000,
        cache_write_tokens=500,
        current_time=110.0,
    )
    assert w2 is None
    assert mark.established_prefix == 2500

    # Third request collapses cache to 500 tokens (< 0.5 * 2500) -> emits warning
    with pytest.warns(
        CacheBustWarning, match="Prompt cache collapsed for anthropic:claude-3-5-sonnet"
    ):
        w3 = monitor.record_usage(
            "anthropic",
            "claude-3-5-sonnet",
            cache_read_tokens=500,
            cache_write_tokens=100,
            current_time=120.0,
        )
        assert w3 is not None
        assert "read 500 cached tokens" in w3

    # Fourth request in sustained collapse -> stays latched and silent
    w4 = monitor.record_usage(
        "anthropic",
        "claude-3-5-sonnet",
        cache_read_tokens=400,
        cache_write_tokens=0,
        current_time=130.0,
    )
    assert w4 is None

    # Fifth request with cache expiry gap (> 300s)
    mark.latched_warning = False
    with pytest.warns(CacheBustWarning, match="exceeds assumed cache TTL"):
        w5 = monitor.record_usage(
            "anthropic",
            "claude-3-5-sonnet",
            cache_read_tokens=100,
            cache_write_tokens=0,
            current_time=500.0,
        )
        assert w5 is not None
        assert "exceeds assumed cache TTL" in w5

    # 3. Test for_run produces isolated instance
    run_monitor = monitor.for_run()
    assert run_monitor.marks == {}
    assert run_monitor.collapse_ratio == monitor.collapse_ratio

    # 4. Test after_model_request hook integration
    class DummyUsage:
        cache_read_tokens = 2000
        cache_write_tokens = 500

    class DummyResponse:
        usage = DummyUsage()

    class DummyContext:
        provider_name = "anthropic"
        model_name = "claude-3-5-sonnet"

    resp = run_monitor.after_model_request(request_context=DummyContext(), response=DummyResponse())
    assert resp is not None
    assert ("anthropic", "claude-3-5-sonnet") in run_monitor.marks
