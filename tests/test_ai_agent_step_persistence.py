"""Unit tests for Pydantic AI Step Persistence capability, durable runs, and branching."""

from __future__ import annotations

from devops_cli.ai.agents import (
    InMemoryStepStore,
    RunContext,
    SqliteStepStore,
    StepPersistence,
    StepRecord,
)


def test_in_memory_step_store_lifecycle() -> None:
    """Verify InMemoryStepStore saving, sequential retrieval, and forking."""
    store = InMemoryStepStore()

    # 1. Save steps
    s1 = StepRecord(run_id="run_1", kind="model_request", payload={"prompt": "list pods"})
    s2 = StepRecord(run_id="run_1", kind="tool_call", payload={"tool_name": "k8s_pods"})
    s3 = StepRecord(run_id="run_1", kind="tool_result", payload={"pods": ["pod-a", "pod-b"]})
    store.save_step(s1)
    store.save_step(s2)
    store.save_step(s3)

    steps = store.get_steps("run_1")
    assert len(steps) == 3
    assert [s.step_number for s in steps] == [1, 2, 3]
    assert store.get_latest_step("run_1") == s3

    # 2. Fork run up to step 2
    forked = store.fork_run(source_run_id="run_1", new_run_id="run_1_fork", up_to_step=2)
    assert len(forked) == 2
    assert forked[0].run_id == "run_1_fork"
    assert forked[0].kind == "model_request"
    assert forked[1].kind == "tool_call"


def test_sqlite_step_store_lifecycle() -> None:
    """Verify SqliteStepStore database operations, queries, and forking."""
    store = SqliteStepStore(db_path=":memory:")

    s1 = StepRecord(run_id="run_sql", kind="model_request", payload={"prompt": "show config"})
    s2 = StepRecord(run_id="run_sql", kind="tool_call", payload={"tool": "config_show"})
    store.save_step(s1)
    store.save_step(s2)

    steps = store.get_steps("run_sql")
    assert len(steps) == 2
    assert steps[0].payload == {"prompt": "show config"}
    assert steps[1].step_number == 2

    # Fork
    forked = store.fork_run(source_run_id="run_sql", new_run_id="run_sql_fork", up_to_step=1)
    assert len(forked) == 1
    assert forked[0].run_id == "run_sql_fork"
    assert forked[0].payload == {"prompt": "show config"}


def test_step_persistence_capability() -> None:
    """Verify StepPersistence capability integration with agent lifecycle hooks."""
    cap = StepPersistence(store=InMemoryStepStore())

    # 1. Direct step saving
    step1 = cap.save_step(kind="checkpoint", payload={"state": "init"})
    assert step1.kind == "checkpoint"
    assert step1.run_id == cap.current_run_id

    # 2. Lifecycle hooks
    hooks = cap.get_hooks()
    assert hooks is not None
    assert len(hooks.before_tool_execute) > 0
    assert len(hooks.after_tool_execute) > 0

    ctx = RunContext()
    hooks.before_tool_execute[0](
        ctx, "k8s_pods", {"namespace": "default", "api_token": "super-secret-key"}
    )
    hooks.after_tool_execute[0](ctx, "k8s_pods", {"password": "admin-password", "status": "ok"})

    history = cap.continue_run(cap.current_run_id)
    assert len(history) == 3
    assert history[1].kind == "tool_call"
    assert history[1].payload["args"]["api_token"] == "***REDACTED***"
    assert history[2].kind == "tool_result"
    assert history[2].payload["result"]["password"] == "***REDACTED***"

    # 3. Fork run
    fork_id, forked_steps = cap.fork_run(up_to_step=2)
    assert fork_id != history[0].run_id
    assert len(forked_steps) == 2
    assert cap.current_run_id == fork_id


def test_sqlite_step_store_path_traversal() -> None:
    """Verify SqliteStepStore rejects relative path traversal."""
    import pytest

    with pytest.raises(ValueError, match="Directory traversal not permitted"):
        SqliteStepStore(db_path="../escaped.db")
