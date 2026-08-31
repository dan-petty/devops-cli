"""Planning capability and plan stores for multi-step task tracking."""

from __future__ import annotations

import contextlib
import json
import logging
import sqlite3
import uuid
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, Field

from devops_cli.ai.agents.pydantic_agent import (
    AgentHooks,
    AgentTool,
    BaseCapability,
    RunContext,
    Tool,
)
from devops_cli.models.ai import ChatMessage

logger = logging.getLogger(__name__)

PlanStatus = Literal["pending", "in_progress", "completed", "cancelled", "blocked"]


class PlanItem(BaseModel):
    """Structured plan task item."""

    id: str = Field(default_factory=lambda: f"task-{uuid.uuid4().hex}")
    content: str
    active_form: str | None = None
    status: PlanStatus = "pending"
    parent_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)


class PlanEvent(BaseModel):
    """Event emitted upon plan mutations."""

    event_type: str
    item: PlanItem
    old_status: str | None = None
    new_status: str | None = None


class PlanEventEmitter:
    """Event emitter managing lifecycle callbacks for plan task state changes."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[[PlanEvent], Any]]] = defaultdict(list)

    def on(
        self, event_type: str, handler: Callable[[PlanEvent], Any]
    ) -> Callable[[PlanEvent], Any]:
        self._listeners[event_type].append(handler)
        return handler

    def on_completed(self, handler: Callable[[PlanEvent], Any]) -> Callable[[PlanEvent], Any]:
        return self.on("completed", handler)

    def on_status_changed(self, handler: Callable[[PlanEvent], Any]) -> Callable[[PlanEvent], Any]:
        return self.on("status_changed", handler)

    def on_task_added(self, handler: Callable[[PlanEvent], Any]) -> Callable[[PlanEvent], Any]:
        return self.on("task_added", handler)

    def emit(self, event: PlanEvent) -> None:
        for handler in self._listeners.get(event.event_type, []):
            try:
                handler(event)
            except Exception:
                pass


class PlanStore:
    """Abstract interface for plan storage backends."""

    def __init__(self, event_emitter: PlanEventEmitter | None = None) -> None:
        self.event_emitter = event_emitter

    def get_items(self) -> list[PlanItem]:
        raise NotImplementedError

    def set_items(self, items: list[PlanItem]) -> None:
        raise NotImplementedError

    def add_item(self, item: PlanItem) -> PlanItem:
        raise NotImplementedError

    def update_item_status(self, item_id: str, status: PlanStatus) -> bool:
        raise NotImplementedError

    def remove_item(self, item_id: str) -> bool:
        raise NotImplementedError


def _make_status_event(item: PlanItem, old: str, new_status: str) -> PlanEvent:
    """Construct a PlanEvent for status transitions."""
    ev_type = "completed" if new_status == "completed" else "status_changed"
    return PlanEvent(event_type=ev_type, item=item, old_status=old, new_status=new_status)


_STATUS_ICONS: dict[str, str] = {
    "completed": "[✓]",
    "in_progress": "[>]",
    "cancelled": "[x]",
    "blocked": "[!]",
}


def _status_icon(status: str) -> str:
    """Return progress box icon for a step status."""
    return _STATUS_ICONS.get(status, "[ ]")


class InMemoryPlanStore(PlanStore):
    """In-memory plan storage backend."""

    def __init__(
        self,
        items: list[PlanItem] | None = None,
        event_emitter: PlanEventEmitter | None = None,
    ) -> None:
        super().__init__(event_emitter=event_emitter)
        self._items: list[PlanItem] = list(items or [])

    def get_items(self) -> list[PlanItem]:
        return list(self._items)

    def set_items(self, items: list[PlanItem]) -> None:
        self._items = list(items)

    def add_item(self, item: PlanItem) -> PlanItem:
        self._items.append(item)
        if self.event_emitter:
            self.event_emitter.emit(PlanEvent(event_type="task_added", item=item))
        return item

    def update_item_status(self, item_id: str, status: PlanStatus) -> bool:
        for item in self._items:
            if item.id == item_id:
                old = item.status
                item.status = status
                if self.event_emitter:
                    self.event_emitter.emit(_make_status_event(item, old, status))
                return True
        return False

    def remove_item(self, item_id: str) -> bool:
        initial_len = len(self._items)
        self._items = [it for it in self._items if it.id != item_id]
        return len(self._items) < initial_len


class SqlitePlanStore(PlanStore):
    """SQLite-backed plan storage backend persisted across sessions."""

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        session: str = "default",
        event_emitter: PlanEventEmitter | None = None,
    ) -> None:
        super().__init__(event_emitter=event_emitter)
        self.db_path = str(db_path)
        self.session = session
        self._init_db()

    def _init_db(self) -> None:
        with contextlib.closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS plan_items (
                    session TEXT NOT NULL,
                    id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    active_form TEXT,
                    status TEXT NOT NULL,
                    parent_id TEXT,
                    depends_on TEXT,
                    sequence_num INTEGER NOT NULL,
                    PRIMARY KEY (session, id)
                )
                """
            )
            conn.commit()

    def get_items(self) -> list[PlanItem]:
        with contextlib.closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.execute(
                "SELECT id, content, active_form, status, parent_id, depends_on FROM plan_items WHERE session = ? ORDER BY sequence_num ASC",
                (self.session,),
            )
            return [
                PlanItem(
                    id=r[0],
                    content=r[1],
                    active_form=r[2],
                    status=r[3],
                    parent_id=r[4],
                    depends_on=json.loads(r[5]) if r[5] else [],
                )
                for r in cur.fetchall()
            ]

    def set_items(self, items: list[PlanItem]) -> None:
        params = [
            (
                self.session,
                it.id,
                it.content,
                it.active_form,
                it.status,
                it.parent_id,
                json.dumps(it.depends_on),
                idx,
            )
            for idx, it in enumerate(items)
        ]
        with contextlib.closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("DELETE FROM plan_items WHERE session = ?", (self.session,))
            conn.executemany(
                "INSERT INTO plan_items (session, id, content, active_form, status, parent_id, depends_on, sequence_num) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                params,
            )
            conn.commit()

    def add_item(self, item: PlanItem) -> PlanItem:
        with contextlib.closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence_num), -1) FROM plan_items WHERE session = ?",
                (self.session,),
            ).fetchone()
            max_seq = row[0] if row else -1
            conn.execute(
                "INSERT OR REPLACE INTO plan_items (session, id, content, active_form, status, parent_id, depends_on, sequence_num) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.session,
                    item.id,
                    item.content,
                    item.active_form,
                    item.status,
                    item.parent_id,
                    json.dumps(item.depends_on),
                    max_seq + 1,
                ),
            )
            conn.commit()
        if self.event_emitter:
            self.event_emitter.emit(PlanEvent(event_type="task_added", item=item))
        return item

    def update_item_status(self, item_id: str, status: PlanStatus) -> bool:
        with contextlib.closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.execute(
                "UPDATE plan_items SET status = ? WHERE session = ? AND id = ?",
                (status, self.session, item_id),
            )
            conn.commit()
            updated = cur.rowcount > 0

        if updated and self.event_emitter:
            items = [it for it in self.get_items() if it.id == item_id]
            if items:
                self.event_emitter.emit(_make_status_event(items[0], items[0].status, status))
        return updated

    def remove_item(self, item_id: str) -> bool:
        with contextlib.closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.execute(
                "DELETE FROM plan_items WHERE session = ? AND id = ?",
                (self.session, item_id),
            )
            conn.commit()
            return cur.rowcount > 0


DEFAULT_PLANNING_GUIDANCE: str = (
    "You have access to a structured planning toolset (write_plan, read_plan, add_task, update_task_status, remove_task). "
    "Keep a concise, structured plan to track progress on multi-step tasks. "
    "Ensure exactly one step is marked as 'in_progress' at any given time while working. "
    "Mark steps 'completed' promptly when finished."
)


class Planning(BaseCapability):
    """Structured task planning capability that maintains state and injects cache-safe tail reminders."""

    id: str = "planning"
    guidance: str | None = None
    cache_ttl: Literal["5m", "1h"] = "5m"
    store: Any = None
    store_resolver: Any = None
    enable_subtasks: bool = False
    inject: bool = True
    tools: Sequence[str] | None = None
    descriptions: dict[str, str] | None = None
    plans: list[str] = Field(default_factory=list)

    def __init__(
        self,
        *,
        guidance: str | None = None,
        cache_ttl: Literal["5m", "1h"] = "5m",
        store: PlanStore | None = None,
        store_resolver: Callable[[RunContext[Any]], PlanStore] | None = None,
        enable_subtasks: bool = False,
        inject: bool = True,
        tools: Sequence[str] | None = None,
        descriptions: dict[str, str] | None = None,
        plans: list[str] | None = None,
    ) -> None:
        super().__init__(
            guidance=guidance,
            cache_ttl=cache_ttl,
            store=store,
            store_resolver=store_resolver,
            enable_subtasks=enable_subtasks,
            inject=inject,
            tools=list(tools) if tools is not None else None,
            descriptions=descriptions,
            plans=plans or [],
        )

    def resolve_store(self, ctx: RunContext[Any] | None = None) -> PlanStore:
        """Resolve active PlanStore from resolver, configured store, or in-memory default."""
        if ctx is not None and self.store_resolver is not None:
            return cast(PlanStore, self.store_resolver(ctx))
        if self.store is not None:
            return cast(PlanStore, self.store)
        mem = InMemoryPlanStore()
        if self.plans:
            mem.set_items([PlanItem(content=p, status="pending") for p in self.plans])
        self.store = mem
        return mem

    def _unblock_dependent_items(self, store: PlanStore, task_id: str) -> None:
        """Unblock items whose dependencies are all satisfied."""
        items = store.get_items()
        unresolved = {x.id for x in items if x.status not in ("completed", "cancelled")}
        for it in items:
            if task_id in it.depends_on and it.status == "blocked":
                if not any(d in unresolved for d in it.depends_on):
                    store.update_item_status(it.id, "pending")

    def _build_tool(
        self, fn: Callable[..., Any], name: str, default_desc: str
    ) -> AgentTool | Callable[..., Any]:
        """Construct a tool instance using configured override descriptions if present."""
        desc = self.descriptions.get(name, default_desc) if self.descriptions else default_desc
        return Tool.from_function(fn, name=name, description=desc)

    def _parse_input_plan_item(self, item: dict[str, Any] | PlanItem | str) -> PlanItem:
        """Parse raw dictionary, string, or PlanItem into a canonical PlanItem."""
        if isinstance(item, PlanItem):
            if not self.enable_subtasks and (
                item.status == "blocked" or item.parent_id or item.depends_on
            ):
                raise ValueError("Subtasks and dependency blocking require enable_subtasks=True")
            return item
        if isinstance(item, str):
            return PlanItem(content=item, status="pending")

        status = cast(PlanStatus, item.get("status") or "pending")
        parent_id = item.get("parent_id")
        depends_on = list(item.get("depends_on") or [])
        if not self.enable_subtasks and (status == "blocked" or parent_id or depends_on):
            raise ValueError("Subtasks and dependency blocking require enable_subtasks=True")

        return PlanItem(
            id=str(item.get("id") or f"task-{uuid.uuid4().hex[:6]}"),
            content=str(item.get("content") or item.get("task") or ""),
            active_form=item.get("active_form"),
            status=status,
            parent_id=parent_id,
            depends_on=depends_on,
        )

    def _render_hierarchical_plan(self, items: list[PlanItem], summary: str) -> str:
        """Render plan as indented hierarchical tree."""
        lines = [summary]
        parent_map: dict[str | None, list[PlanItem]] = defaultdict(list)
        for it in items:
            parent_map[it.parent_id].append(it)

        def _render_node(pid: str | None, indent: int = 0) -> None:
            for child in parent_map.get(pid, []):
                icon = _status_icon(child.status)
                lines.append(f"{'  ' * indent}{icon} {child.id}: {child.content}")
                _render_node(child.id, indent + 1)

        _render_node(None)
        return "\n".join(lines)

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        all_tools: list[AgentTool | Callable[..., Any]] = []

        def write_plan(items: list[dict[str, Any] | PlanItem | str]) -> str:
            """Create or replace the full plan (whole-list replacement)."""
            store = self.resolve_store()
            parsed = [self._parse_input_plan_item(it) for it in items]
            store.set_items(parsed)
            self.plans = [it.content for it in parsed]
            return f"Plan successfully written with {len(parsed)} steps."

        def read_plan(view: str = "flat") -> str:
            """Read the current plan with step ids and progress summary."""
            store = self.resolve_store()
            items = store.get_items()
            if not items:
                return "Plan is currently empty. Use write_plan or add_task to create steps."

            done = sum(1 for it in items if it.status == "completed")
            summary = f"Plan Progress: {done}/{len(items)} completed ({round(done / len(items) * 100)}%)\n"

            if view == "hierarchical" and self.enable_subtasks:
                return self._render_hierarchical_plan(items, summary)

            lines = [summary]
            for it in items:
                icon = _status_icon(it.status)
                label = (
                    f" ({it.active_form})" if it.active_form and it.status == "in_progress" else ""
                )
                dep_info = f" [depends on: {', '.join(it.depends_on)}]" if it.depends_on else ""
                lines.append(f"{icon} {it.id}: {it.content}{label}{dep_info}")
            return "\n".join(lines)

        def add_task(content: str, active_form: str | None = None) -> str:
            """Append a single pending step to the plan."""
            store = self.resolve_store()
            item = PlanItem(content=content, active_form=active_form, status="pending")
            created = store.add_item(item)
            self.plans.append(content)
            return f"Task '{created.id}' added to plan: {content}"

        def update_task_status(task_id: str, status: PlanStatus) -> str:
            """Move one step between statuses by id."""
            store = self.resolve_store()
            valid_statuses = ("pending", "in_progress", "completed", "cancelled", "blocked")
            if status not in valid_statuses:
                return f"Error: invalid status '{status}'. Must be one of {valid_statuses}."

            updated = store.update_item_status(task_id, status)
            if not updated:
                return f"Error: task id '{task_id}' not found in plan."

            if status in ("completed", "cancelled") and self.enable_subtasks:
                self._unblock_dependent_items(store, task_id)

            return f"Task '{task_id}' status updated to '{status}'."

        def update_task_statuses(updates: list[dict[str, str]]) -> str:
            """Apply several status changes in one call, validated all-or-nothing."""
            store = self.resolve_store()
            items = {it.id: it for it in store.get_items()}
            for u in updates:
                tid = u.get("id") or u.get("task_id")
                st = u.get("status")
                if not tid or tid not in items:
                    return f"Error: task id '{tid}' not found. No updates applied."
                if st not in ("pending", "in_progress", "completed", "cancelled", "blocked"):
                    return f"Error: invalid status '{st}'. No updates applied."

            for u in updates:
                tid = str(u.get("id") or u.get("task_id"))
                st = cast(PlanStatus, u.get("status"))
                store.update_item_status(tid, st)

            return f"Successfully updated statuses for {len(updates)} tasks."

        def remove_task(task_id: str) -> str:
            """Delete a step from the plan by id."""
            store = self.resolve_store()
            removed = store.remove_item(task_id)
            if not removed:
                return f"Error: task id '{task_id}' not found."
            return f"Task '{task_id}' removed from plan."

        def update_plan(steps: list[str]) -> str:
            """Update the execution plan with structured checklist items."""
            return write_plan([{"content": s, "status": "pending"} for s in steps])

        all_tools.extend(
            [
                self._build_tool(write_plan, "write_plan", "Create or replace the full plan."),
                self._build_tool(
                    read_plan, "read_plan", "Read the current plan with step ids and status."
                ),
                self._build_tool(add_task, "add_task", "Append a single pending step to the plan."),
                self._build_tool(
                    update_task_status,
                    "update_task_status",
                    "Move one step between statuses by id.",
                ),
                self._build_tool(
                    update_task_statuses,
                    "update_task_statuses",
                    "Apply several status changes in one batch call.",
                ),
                self._build_tool(remove_task, "remove_task", "Delete a step from the plan by id."),
                self._build_tool(
                    update_plan,
                    "update_plan",
                    "Update the current multi-step execution plan (string list).",
                ),
            ]
        )

        if self.enable_subtasks:

            def add_subtask(parent_id: str, content: str, active_form: str | None = None) -> str:
                """Add a child step under a parent step."""
                store = self.resolve_store()
                items = {it.id: it for it in store.get_items()}
                if parent_id not in items:
                    return f"Error: parent task id '{parent_id}' not found."
                sub = PlanItem(
                    content=content, active_form=active_form, status="pending", parent_id=parent_id
                )
                created = store.add_item(sub)
                return f"Subtask '{created.id}' added under parent '{parent_id}': {content}"

            def set_dependency(task_id: str, depends_on_id: str) -> str:
                """Make one step wait for another prerequisite step."""
                if task_id == depends_on_id:
                    return "Error: self-dependency not allowed."
                store = self.resolve_store()
                items = {it.id: it for it in store.get_items()}
                if task_id not in items:
                    return f"Error: task id '{task_id}' not found."
                if depends_on_id not in items:
                    return f"Error: prerequisite task id '{depends_on_id}' not found."

                target = items[task_id]
                prereq = items[depends_on_id]
                if task_id in prereq.depends_on:
                    return "Error: circular dependency detected."

                if depends_on_id in target.depends_on:
                    return f"Task '{task_id}' already depends on '{depends_on_id}' (status: {target.status})."

                target.depends_on.append(depends_on_id)
                if prereq.status not in ("completed", "cancelled"):
                    target.status = "blocked"
                store.set_items(list(items.values()))
                return (
                    f"Task '{task_id}' now depends on '{depends_on_id}' (status: {target.status})."
                )

            def get_available_tasks() -> str:
                """List steps with no incomplete dependencies that can start now."""
                store = self.resolve_store()
                items = store.get_items()
                resolved = {it.id for it in items if it.status in ("completed", "cancelled")}
                available = [
                    it
                    for it in items
                    if it.status in ("pending", "in_progress")
                    and all(dep in resolved for dep in it.depends_on)
                ]
                if not available:
                    return "No tasks currently available to start."
                return f"Available tasks ({len(available)}):\n" + "\n".join(
                    f"- {it.id}: {it.content} [{it.status}]" for it in available
                )

            all_tools.extend(
                [
                    self._build_tool(
                        add_subtask, "add_subtask", "Add a child step under a parent."
                    ),
                    self._build_tool(
                        set_dependency,
                        "set_dependency",
                        "Make one step wait for another prerequisite step.",
                    ),
                    self._build_tool(
                        get_available_tasks,
                        "get_available_tasks",
                        "List steps with no incomplete dependencies.",
                    ),
                ]
            )

        if self.tools is not None:
            tool_set = set(self.tools)
            registered_names = {getattr(t, "name", "") for t in all_tools}
            unknown = tool_set - registered_names
            if unknown:
                raise ValueError(f"Unknown tool(s) requested for Planning capability: {unknown}")
            return [t for t in all_tools if getattr(t, "name", "") in tool_set]

        return all_tools

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        if self.guidance == "":
            return []
        return [self.guidance or DEFAULT_PLANNING_GUIDANCE]

    def get_hooks(self) -> AgentHooks | None:
        if not self.inject:
            return None

        def _inject_plan_reminder(ctx: RunContext[Any], messages: list[ChatMessage]) -> None:
            store = self.resolve_store(ctx)
            items = store.get_items()
            if not items:
                return

            done = sum(1 for it in items if it.status == "completed")
            in_prog = [it for it in items if it.status == "in_progress"]
            prog_str = f"[{done}/{len(items)} completed"
            if in_prog:
                prog_str += f", in progress: '{in_prog[0].content}'"
            prog_str += "]"

            rendered_lines = [f"<plan-reminder {prog_str}>"]
            for it in items:
                st_icon = (
                    "[✓]"
                    if it.status == "completed"
                    else "[>]"
                    if it.status == "in_progress"
                    else "[x]"
                    if it.status == "cancelled"
                    else "[!]"
                    if it.status == "blocked"
                    else "[ ]"
                )
                label = (
                    f" ({it.active_form})" if it.active_form and it.status == "in_progress" else ""
                )
                rendered_lines.append(f"{st_icon} {it.id}: {it.content}{label}")
            rendered_lines.append("</plan-reminder>")
            reminder_text = "\n".join(rendered_lines)

            if messages and messages[-1].role == "user":
                messages[-1] = messages[-1].model_copy(
                    update={"content": f"{messages[-1].content}\n\n{reminder_text}"}
                )

        return AgentHooks(before_model_request=[_inject_plan_reminder])


MINIMUM_EFFORT_FLOOR: str = "low"

_EFFORT_RANKS: dict[str, int] = {
    "minimal": 1,
    "low": 2,
    "medium": 3,
    "high": 4,
    "xhigh": 5,
    "max": 6,
}


def clamp_effort(level: str | bool | None, floor: str = MINIMUM_EFFORT_FLOOR) -> str | bool | None:
    """Clamp thinking effort level to a minimum floor.

    Maps None/False to the floor, leaves True (provider default) unchanged,
    and raises concrete effort levels below the floor up to the floor.
    """
    if level is None or level is False:
        return floor
    if level is True:
        return True
    if isinstance(level, str):
        level_lower = level.lower()
        floor_lower = floor.lower()
        rank = _EFFORT_RANKS.get(level_lower, 2)
        floor_rank = _EFFORT_RANKS.get(floor_lower, 2)
        return floor if rank < floor_rank else level
    return floor
