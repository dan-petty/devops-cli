"""Modular Agent Harness Slots, Sub-Agent Local Offloading, and Tiered Synthesis.

Partitions multi-agent execution into swappable slots (ModelSlot, SkillSlot, ToolSlot,
SubAgentSlot) and offloads token-intensive code exploration and AST symbol searching
to local open-weight models (Granite, Qwen2.5-Coder) under the "Big decides, small
types, big checks" synthesis protocol toward an unmeasured token savings target.
"""

from __future__ import annotations

import fnmatch
import logging
import time
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.capability import TaskComplexity
from devops_cli.ai.harness.skills import ParsedSkill, normalize_skill_name
from devops_cli.ai.repomap import SymbolNode, parse_file_symbols
from devops_cli.config.defaults import DEFAULT_AI_FALLBACK_MODEL, DEFAULT_AI_FALLBACK_PROVIDER
from devops_cli.config.settings import AIConfig, load_settings
from devops_cli.core.repo import is_ignored_by_git
from devops_cli.exceptions.ai import HarnessValidationError

logger = logging.getLogger(__name__)


class SlotState(StrEnum):
    """Lifecycle state of an individual harness slot."""

    EMPTY = "empty"
    # Set from configuration; nothing has checked the model or tool is reachable.
    CONFIGURED = "configured"
    ATTACHED = "attached"
    ACTIVE = "active"
    FAILED = "failed"
    DETACHED = "detached"


class SlotType(StrEnum):
    """Categorical classification of harness slots."""

    MODEL = "model"
    SKILL = "skill"
    TOOL = "tool"
    SUBAGENT = "subagent"


class SynthesisTier(StrEnum):
    """Tiers in the 'Big decides, small types, big checks' synthesis protocol."""

    DECIDE = "decide"
    TYPE = "type"
    CHECK = "check"


class BaseSlot(BaseModel):
    """Foundational base slot with lifecycle tracking and validation hooks."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    slot_type: SlotType
    state: SlotState = SlotState.EMPTY
    metadata: dict[str, Any] = Field(default_factory=dict)

    def attach(self) -> None:
        """Transition slot to attached state."""
        self.state = SlotState.ATTACHED

    def detach(self) -> None:
        """Transition slot to detached state."""
        self.state = SlotState.DETACHED

    def is_ready(self) -> bool:
        """Check if slot is attached or active and ready for execution."""
        return self.state in (SlotState.ATTACHED, SlotState.ACTIVE)

    def validate_slot(self) -> bool:
        """Validate internal slot invariants."""
        return bool(self.name)

    def to_dict(self) -> dict[str, Any]:
        """Convert slot model to dictionary."""
        return {
            "name": self.name,
            "slot_type": self.slot_type.value,
            "state": self.state.value,
            "metadata": self.metadata,
        }


class ModelSlot(BaseSlot):
    """Slot managing frontier and local LLM runtime bindings."""

    slot_type: SlotType = SlotType.MODEL
    provider: str = "ollama"
    model_name: str = "qwen2.5-coder:7b"
    tier: TaskComplexity = TaskComplexity.LOW
    is_local: bool = True
    temperature: float = 0.0
    max_tokens: int | None = None
    client: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Convert ModelSlot to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "provider": self.provider,
                "model_name": self.model_name,
                "tier": self.tier.value,
                "is_local": self.is_local,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
        )
        return data

    def swap_model(
        self,
        provider: str,
        model_name: str,
        tier: TaskComplexity,
        is_local: bool | None = None,
    ) -> None:
        """Hot-swap the bound model and routing tier."""
        self.provider = provider
        self.model_name = model_name
        self.tier = tier
        self.is_local = (provider == "ollama") if is_local is None else is_local
        self.state = SlotState.ATTACHED

    def ensure_local(self) -> None:
        """Enforce that model is configured for local sovereign execution."""
        if not self.is_local or self.provider != "ollama":
            raise HarnessValidationError(
                f"ModelSlot '{self.name}' must be local (ollama) for sovereign offloading, got {self.provider}:{self.model_name}"
            )


class SkillSlot(BaseSlot):
    """Slot dynamically attaching and detaching SKILL.md capability packages."""

    slot_type: SlotType = SlotType.SKILL
    active_skills: dict[str, ParsedSkill] = Field(default_factory=dict)
    max_skills: int = 20

    @property
    def skills(self) -> dict[str, ParsedSkill]:
        """Return active skills mapping."""
        return self.active_skills

    def attach_skill(self, skill: ParsedSkill) -> None:
        """Attach a parsed skill package."""
        if len(self.active_skills) >= self.max_skills:
            raise HarnessValidationError(
                f"SkillSlot capacity limit reached (max {self.max_skills} skills)"
            )
        norm_name = normalize_skill_name(skill.name)
        self.active_skills[norm_name] = skill
        self.state = SlotState.ATTACHED

    def detach_skill(self, skill_name: str) -> bool:
        """Detach a skill by name."""
        try:
            norm_name = normalize_skill_name(skill_name)
        except HarnessValidationError:
            norm_name = skill_name.strip().lower()
        if norm_name in self.active_skills:
            del self.active_skills[norm_name]
            if not self.active_skills:
                self.state = SlotState.EMPTY
            return True
        return False

    def has_skill(self, skill_name: str) -> bool:
        """Check whether a skill is currently attached."""
        try:
            norm_name = normalize_skill_name(skill_name)
        except HarnessValidationError:
            norm_name = skill_name.strip().lower()
        return norm_name in self.active_skills

    def get_skill_prompts(self) -> list[str]:
        """Format attached skills for prompt context injection."""
        return [
            f"### Skill: {skill.name}\n{skill.description}\n\n{skill.body}".strip()
            for skill in self.active_skills.values()
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert SkillSlot to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "skills": [s.name for s in self.active_skills.values()],
                "count": len(self.active_skills),
            }
        )
        return data


def _get_tool_name(tool: Any) -> str:
    """Extract canonical name from callable tool."""
    return str(getattr(tool, "__name__", getattr(tool, "name", str(tool))))


def mark_tool_mutating(tool: Any, is_mutating: bool = True) -> Any:
    """Explicitly mark a callable tool with mutating metadata."""
    try:
        setattr(tool, "is_mutating", is_mutating)
    except AttributeError, TypeError:
        pass
    return tool


def mark_tool_read_only(tool: Any) -> Any:
    """Explicitly mark a callable tool as read-only safe."""
    return mark_tool_mutating(tool, is_mutating=False)


def _is_mutating_tool(tool: Any) -> bool:
    """Predicate evaluating whether a tool performs mutating operations based on metadata."""
    if hasattr(tool, "is_mutating"):
        return bool(getattr(tool, "is_mutating"))
    if hasattr(tool, "read_only"):
        return not bool(getattr(tool, "read_only"))
    return True


class ToolSlot(BaseSlot):
    """Slot managing sandboxed and read-only tools."""

    slot_type: SlotType = SlotType.TOOL
    tools: list[Any] = Field(default_factory=list)
    read_only: bool = False
    denied_tools: set[str] = Field(default_factory=set)
    read_only_allowlist: set[str] = Field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        """Convert ToolSlot to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "tools": [_get_tool_name(t) for t in self.tools],
                "read_only": self.read_only,
                "read_only_allowlist": sorted(self.read_only_allowlist),
                "count": len(self.tools),
            }
        )
        return data

    def attach_tool(self, tool: Any, *, is_mutating: bool | None = None) -> None:
        """Register a tool callable with optional explicit mutating metadata."""
        if is_mutating is not None:
            mark_tool_mutating(tool, is_mutating=is_mutating)
        self.tools.append(tool)
        self.state = SlotState.ATTACHED

    def detach_tool(self, tool_name: str) -> bool:
        """Remove a tool by function or identifier name."""
        target = tool_name.lower()
        original_len = len(self.tools)
        self.tools = [t for t in self.tools if _get_tool_name(t).lower() != target]
        return len(self.tools) < original_len

    def set_read_only(self, enabled: bool) -> None:
        """Enable or disable read-only sandboxing mode."""
        self.read_only = enabled

    def allow_read_only_tools(self, *tool_names: str) -> None:
        """Register tool names in the safe read-only allowlist."""
        self.read_only_allowlist.update(name.strip().lower() for name in tool_names if name.strip())

    def is_tool_mutating(self, tool: Any) -> bool:
        """Evaluate if a tool is mutating using explicit metadata or default-deny policy."""
        if hasattr(tool, "is_mutating"):
            return bool(getattr(tool, "is_mutating"))
        if hasattr(tool, "read_only"):
            return not bool(getattr(tool, "read_only"))
        name = _get_tool_name(tool).lower()
        if name in self.read_only_allowlist:
            return False
        # Default-deny when sandboxed: tools lacking explicit read-only status are treated as mutating
        return True

    def get_active_tools(self) -> list[Any]:
        """Return executable tools applying read-only and denied-list filters."""
        if not self.read_only:
            return [t for t in self.tools if _get_tool_name(t).lower() not in self.denied_tools]
        return [
            t
            for t in self.tools
            if _get_tool_name(t).lower() not in self.denied_tools and not self.is_tool_mutating(t)
        ]


class SubAgentResult(BaseModel):
    """Output payload from sub-agent exploration or code offloading."""

    subagent_id: str
    role: str
    status: str = "success"
    output: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    duration_seconds: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize SubAgentResult to dictionary."""
        return {
            "subagent_id": self.subagent_id,
            "role": self.role,
            "status": self.status,
            "output": self.output,
            "data": self.data,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
        }


def _walk_python_files(repo_path: Path, max_files: int = 100) -> list[Path]:
    """Discover Python source files while pruning excluded directories."""
    matched: list[Path] = []
    if not repo_path.is_dir():
        return matched

    for item in repo_path.rglob("*.py"):
        if is_ignored_by_git(repo_path, item):
            continue
        matched.append(item)
        if len(matched) >= max_files:
            break
    return matched


def _collect_matching_symbols(
    nodes: list[SymbolNode], rel_path: str, query_lower: str, matches: list[dict[str, Any]]
) -> None:
    """Recursively collect matching AST symbols within indentation limits."""
    for node in nodes:
        if query_lower in node.name.lower():
            matches.append(
                {
                    "file": rel_path,
                    "name": node.name,
                    "kind": node.kind,
                    "line_number": node.line_number,
                    "signature": node.signature,
                    "docstring": node.docstring,
                }
            )
        if node.children:
            _collect_matching_symbols(node.children, rel_path, query_lower, matches)


class SubAgentSlot(BaseSlot):
    """Slot managing sub-agent exploration and offloading engines."""

    slot_type: SlotType = SlotType.SUBAGENT
    subagent_id: str = "subagent-1"
    role: str = "ast_explorer"
    model_slot: ModelSlot = Field(
        default_factory=lambda: ModelSlot(
            name="subagent_model",
            slot_type=SlotType.MODEL,
            provider="ollama",
            model_name="qwen2.5-coder:7b",
            is_local=True,
            state=SlotState.ATTACHED,
        )
    )
    tool_slot: ToolSlot = Field(
        default_factory=lambda: ToolSlot(
            name="subagent_tools",
            slot_type=SlotType.TOOL,
            read_only=True,
            state=SlotState.ATTACHED,
        )
    )
    skill_slot: SkillSlot = Field(
        default_factory=lambda: SkillSlot(
            name="subagent_skills",
            slot_type=SlotType.SKILL,
            state=SlotState.ATTACHED,
        )
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert SubAgentSlot to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "subagent_id": self.subagent_id,
                "role": self.role,
                "model_slot": self.model_slot.to_dict(),
                "tool_slot": self.tool_slot.to_dict(),
                "skill_slot": self.skill_slot.to_dict(),
            }
        )
        return data

    timeout_seconds: float = 60.0

    def offload_ast_search(
        self,
        repo_path: Path | str,
        symbol_name: str,
        max_files: int = 100,
    ) -> SubAgentResult:
        """Offload Python AST symbol searching to local sub-agent."""
        start_time = time.perf_counter()
        root = Path(repo_path).resolve()
        query_lower = symbol_name.strip().lower()
        matches: list[dict[str, Any]] = []

        try:
            if not root.is_dir():
                elapsed = time.perf_counter() - start_time
                return SubAgentResult(
                    subagent_id=self.subagent_id,
                    role=self.role,
                    status="failed",
                    output=f"Target repository path '{repo_path}' is not a directory.",
                    error=f"NotADirectoryError: {repo_path}",
                    duration_seconds=round(elapsed, 4),
                )
            py_files = _walk_python_files(root, max_files=max_files)
            for file_path in py_files:
                file_node = parse_file_symbols(file_path, root)
                if file_node and file_node.symbols:
                    rel = str(file_path.relative_to(root))
                    _collect_matching_symbols(file_node.symbols, rel, query_lower, matches)

            output_lines = [
                f"Found {len(matches)} match(es) for symbol '{symbol_name}' across {len(py_files)} files:"
            ]
            for m in matches:
                output_lines.append(
                    f"- {m['kind']} {m['name']}{m['signature']} ({m['file']}:{m['line_number']})"
                )
            output_text = "\n".join(output_lines)
            elapsed = time.perf_counter() - start_time

            return SubAgentResult(
                subagent_id=self.subagent_id,
                role=self.role,
                status="success",
                output=output_text,
                data={"symbol": symbol_name, "matches": matches, "files_scanned": len(py_files)},
                duration_seconds=round(elapsed, 4),
            )
        except Exception as exc:
            logger.warning("SubAgentSlot AST search failure: %s", exc)
            elapsed = time.perf_counter() - start_time
            return SubAgentResult(
                subagent_id=self.subagent_id,
                role=self.role,
                status="failed",
                output=f"Error searching AST: {exc}",
                error=str(exc),
                duration_seconds=round(elapsed, 4),
            )

    def offload_file_scout(
        self,
        repo_path: Path | str,
        pattern: str,
        max_results: int = 50,
    ) -> SubAgentResult:
        """Offload directory mapping and file pattern scouting."""
        start_time = time.perf_counter()
        root = Path(repo_path).resolve()
        matched_files: list[str] = []

        try:
            if not root.is_dir():
                elapsed = time.perf_counter() - start_time
                return SubAgentResult(
                    subagent_id=self.subagent_id,
                    role=self.role,
                    status="failed",
                    output=f"Target repository path '{repo_path}' is not a directory.",
                    error=f"NotADirectoryError: {repo_path}",
                    duration_seconds=round(elapsed, 4),
                )
            files_scanned = 0
            for item in root.rglob("*"):
                if is_ignored_by_git(root, item):
                    continue
                if item.is_file():
                    files_scanned += 1
                    if fnmatch.fnmatch(item.name, pattern):
                        matched_files.append(str(item.relative_to(root)))
                        if len(matched_files) >= max_results:
                            break

            output_text = f"Scouted {len(matched_files)} files matching '{pattern}':\n" + "\n".join(
                f"- {f}" for f in matched_files
            )
            elapsed = time.perf_counter() - start_time

            return SubAgentResult(
                subagent_id=self.subagent_id,
                role=self.role,
                status="success",
                output=output_text,
                data={"pattern": pattern, "files": matched_files, "files_scanned": files_scanned},
                duration_seconds=round(elapsed, 4),
            )
        except Exception as exc:
            elapsed = time.perf_counter() - start_time
            return SubAgentResult(
                subagent_id=self.subagent_id,
                role=self.role,
                status="failed",
                output=f"Error scouting files: {exc}",
                error=str(exc),
                duration_seconds=round(elapsed, 4),
            )

    def offload_symbol_catalog(
        self,
        repo_path: Path | str,
        max_files: int = 30,
    ) -> SubAgentResult:
        """Offload whole-module symbol catalog generation."""
        start_time = time.perf_counter()
        root = Path(repo_path).resolve()
        catalog: list[dict[str, Any]] = []

        try:
            if not root.is_dir():
                elapsed = time.perf_counter() - start_time
                return SubAgentResult(
                    subagent_id=self.subagent_id,
                    role=self.role,
                    status="failed",
                    output=f"Target repository path '{repo_path}' is not a directory.",
                    error=f"NotADirectoryError: {repo_path}",
                    duration_seconds=round(elapsed, 4),
                )
            py_files = _walk_python_files(root, max_files=max_files)
            for file_path in py_files:
                file_node = parse_file_symbols(file_path, root)
                if not file_node:
                    continue
                rel = str(file_path.relative_to(root))
                for sym in file_node.symbols:
                    catalog.append(
                        {
                            "file": rel,
                            "name": sym.name,
                            "kind": sym.kind,
                            "signature": sym.signature,
                        }
                    )

            output_text = f"Cataloged {len(catalog)} symbols across {len(py_files)} files."
            elapsed = time.perf_counter() - start_time

            return SubAgentResult(
                subagent_id=self.subagent_id,
                role=self.role,
                status="success",
                output=output_text,
                data={"symbols": catalog, "file_count": len(py_files)},
                duration_seconds=round(elapsed, 4),
            )
        except Exception as exc:
            elapsed = time.perf_counter() - start_time
            return SubAgentResult(
                subagent_id=self.subagent_id,
                role=self.role,
                status="failed",
                output=f"Error cataloging symbols: {exc}",
                error=str(exc),
                duration_seconds=round(elapsed, 4),
            )


def _extract_subagent_metrics(sub_results: list[SubAgentResult]) -> tuple[int, int]:
    """Calculate aggregated files scanned and match counts across sub-agent results."""
    files_scanned = 0
    matches = 0
    for r in sub_results:
        files_scanned += int(
            r.data.get("files_scanned", r.data.get("file_count", len(r.data.get("files", []))))
        )
        for key in ("matches", "symbols", "files"):
            if key in r.data:
                matches += len(r.data[key])
                break
    return files_scanned, matches


class TieredExecutionResult(BaseModel):
    """What a harness run searched for and found; no model is called."""

    task: str
    search: str
    subagent_results: list[SubAgentResult] = Field(default_factory=list)
    summary: str = ""
    status: str = "completed"
    files_scanned: int = 0
    matches: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize TieredExecutionResult to dictionary."""
        return {
            "task": self.task,
            "status": self.status,
            "search": self.search,
            "subagent_results": [r.to_dict() for r in self.subagent_results],
            "summary": self.summary,
            "files_scanned": self.files_scanned,
            "matches": self.matches,
        }


def _evaluate_tiered_status(sub_results: list[SubAgentResult]) -> str:
    """Determine tiered execution status from sub-agent outcome statuses."""
    if not sub_results:
        return "completed"
    successes = sum(1 for r in sub_results if r.status == "success")
    if successes == len(sub_results):
        return "completed"
    if successes > 0:
        return "partial"
    return "failed"


def _summarize_search(task: str, status: str, sub_results: list[SubAgentResult]) -> str:
    """Summarize what the searches found, or why they failed."""
    if status == "failed":
        errors = [r.error or r.output for r in sub_results if r.error or r.output]
        detail = f": {'; '.join(errors)}" if errors else "."
        return f"Search failed for task '{task}'{detail}"

    matched_symbols = sum(len(r.data.get("matches", [])) for r in sub_results)
    cataloged_symbols = sum(len(r.data.get("symbols", [])) for r in sub_results)
    total_symbols = matched_symbols + cataloged_symbols
    scouted_files = sum(len(r.data.get("files", [])) for r in sub_results)

    finding_clauses: list[str] = []
    if total_symbols > 0:
        finding_clauses.append(f"{total_symbols} discovered symbol(s)")
    if scouted_files > 0:
        finding_clauses.append(f"{scouted_files} matched file(s)")

    findings_text = " and ".join(finding_clauses) if finding_clauses else "nothing"
    prefix = "Some searches failed; found" if status == "partial" else "Found"
    return f"{prefix} {findings_text} for task '{task}'."


def _describe_search(symbol_query: str | None, file_pattern: str | None) -> str:
    """Describe the searches a run performs."""
    searches: list[str] = []
    if symbol_query:
        searches.append(f"AST search for symbol '{symbol_query}'")
    if file_pattern:
        searches.append(f"glob search for '{file_pattern}'")
    return "; ".join(searches) or "symbol catalog of every Python file"


class AgentHarness(BaseModel):
    """Integrated harness managing swappable slots and tiered execution."""

    name: str = "default_harness"
    model_slot: ModelSlot
    skill_slot: SkillSlot
    tool_slot: ToolSlot
    subagent_slot: SubAgentSlot

    def to_dict(self) -> dict[str, Any]:
        """Serialize AgentHarness to dictionary."""
        return {
            "name": self.name,
            "model_slot": self.model_slot.to_dict(),
            "skill_slot": self.skill_slot.to_dict(),
            "tool_slot": self.tool_slot.to_dict(),
            "subagent_slot": self.subagent_slot.to_dict(),
        }

    @classmethod
    def from_config(cls, ai: AIConfig | None = None) -> AgentHarness:
        """Build the harness from configuration, with every slot marked configured, not checked.

        The model slot holds the configured provider and model. The sub-agent runs local AST
        and glob searches and calls no model; its model slot holds the local fallback model.
        """
        ai = ai or load_settings().ai
        m_slot = ModelSlot(
            name="frontier_model",
            slot_type=SlotType.MODEL,
            provider=ai.provider,
            model_name=ai.model,
            tier=TaskComplexity.FRONTIER,
            is_local=ai.provider == "ollama",
            state=SlotState.CONFIGURED,
        )
        sk_slot = SkillSlot(name="skills", slot_type=SlotType.SKILL, state=SlotState.CONFIGURED)
        t_slot = ToolSlot(name="tools", slot_type=SlotType.TOOL, state=SlotState.CONFIGURED)

        sub_model = ModelSlot(
            name="subagent_model",
            slot_type=SlotType.MODEL,
            provider=DEFAULT_AI_FALLBACK_PROVIDER,
            model_name=DEFAULT_AI_FALLBACK_MODEL,
            tier=TaskComplexity.LOW,
            is_local=True,
            state=SlotState.CONFIGURED,
        )
        sub_tools = ToolSlot(
            name="subagent_tools",
            slot_type=SlotType.TOOL,
            read_only=True,
            state=SlotState.CONFIGURED,
        )
        sub_skills = SkillSlot(
            name="subagent_skills",
            slot_type=SlotType.SKILL,
            state=SlotState.CONFIGURED,
        )
        sub_slot = SubAgentSlot(
            name="subagent_slot",
            slot_type=SlotType.SUBAGENT,
            subagent_id="local_scout",
            role="ast_explorer",
            model_slot=sub_model,
            tool_slot=sub_tools,
            skill_slot=sub_skills,
            state=SlotState.CONFIGURED,
        )

        return cls(
            name="default_harness",
            model_slot=m_slot,
            skill_slot=sk_slot,
            tool_slot=t_slot,
            subagent_slot=sub_slot,
        )

    def validate_invariants(self) -> bool:
        """Verify that all 4 slots are properly attached and operational."""
        return (
            self.model_slot.is_ready()
            and self.skill_slot.is_ready()
            and self.tool_slot.is_ready()
            and self.subagent_slot.is_ready()
        )

    def execute_tiered(
        self,
        task: str,
        repo_path: Path | str,
        symbol_query: str | None = None,
        file_pattern: str | None = None,
    ) -> TieredExecutionResult:
        """Run the sub-agent's local searches for a task and report what they found.

        No model is called: the result names the searches run and their match counts.
        """
        sub_results: list[SubAgentResult] = []
        if symbol_query:
            sub_results.append(self.subagent_slot.offload_ast_search(repo_path, symbol_query))
        if file_pattern:
            sub_results.append(self.subagent_slot.offload_file_scout(repo_path, file_pattern))
        if not symbol_query and not file_pattern:
            sub_results.append(self.subagent_slot.offload_symbol_catalog(repo_path))

        status = _evaluate_tiered_status(sub_results)
        files_scanned, matches = _extract_subagent_metrics(sub_results)
        return TieredExecutionResult(
            task=task,
            search=_describe_search(symbol_query, file_pattern),
            subagent_results=sub_results,
            summary=_summarize_search(task, status, sub_results),
            status=status,
            files_scanned=files_scanned,
            matches=matches,
        )
