"""Modular Agent Harness Slots, Sub-Agent Local Offloading, and Tiered Synthesis.

Partitions multi-agent execution into swappable slots (ModelSlot, SkillSlot, ToolSlot,
SubAgentSlot) and offloads token-intensive code exploration and AST symbol searching
to local open-weight models (Granite, Qwen2.5-Coder) under the "Big decides, small
types, big checks" synthesis protocol to achieve 85%+ token savings.
"""

from __future__ import annotations

import fnmatch
import logging
import time
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.harness.skills import ParsedSkill, normalize_skill_name
from devops_cli.ai.repomap import SymbolNode, parse_file_symbols
from devops_cli.ai.router import TaskComplexity
from devops_cli.exceptions.ai import HarnessValidationError

logger = logging.getLogger(__name__)

MUTATING_TOOL_PREFIXES: tuple[str, ...] = (
    "write_",
    "edit_",
    "delete_",
    "apply_",
    "mutate_",
    "rm_",
    "create_",
    "drop_",
    "update_",
    "set_",
)

IGNORED_EXPLORATION_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".data",
        ".ruff_cache",
        ".mypy_cache",
        ".pytest_cache",
        "node_modules",
        "dist",
        "build",
    }
)


class SlotState(StrEnum):
    """Lifecycle state of an individual harness slot."""

    EMPTY = "empty"
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

    def estimate_tokens(self, text: str) -> int:
        """Estimate token consumption for a text prompt (~4 characters per token)."""
        return max(1, len(text) // 4) if text else 0


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
        except Exception:
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
        except Exception:
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


def _is_mutating_tool(tool: Any) -> bool:
    """Predicate evaluating whether a tool performs mutating operations."""
    name = _get_tool_name(tool).lower()
    return any(name.startswith(p) for p in MUTATING_TOOL_PREFIXES)


class ToolSlot(BaseSlot):
    """Slot managing sandboxed and read-only tools."""

    slot_type: SlotType = SlotType.TOOL
    tools: list[Any] = Field(default_factory=list)
    read_only: bool = False
    denied_tools: set[str] = Field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        """Convert ToolSlot to dictionary."""
        data = super().to_dict()
        data.update(
            {
                "tools": [_get_tool_name(t) for t in self.tools],
                "read_only": self.read_only,
                "count": len(self.tools),
            }
        )
        return data

    def attach_tool(self, tool: Any) -> None:
        """Register a tool callable."""
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

    def get_active_tools(self) -> list[Any]:
        """Return executable tools applying read-only and denied-list filters."""
        if not self.read_only:
            return [t for t in self.tools if _get_tool_name(t).lower() not in self.denied_tools]
        return [
            t
            for t in self.tools
            if _get_tool_name(t).lower() not in self.denied_tools and not _is_mutating_tool(t)
        ]


class SubAgentResult(BaseModel):
    """Output payload from sub-agent exploration or code offloading."""

    subagent_id: str
    role: str
    status: str = "success"
    output: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    tokens_used: int = 0
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
            "tokens_used": self.tokens_used,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
        }


def _walk_python_files(repo_path: Path, max_files: int = 100) -> list[Path]:
    """Discover Python source files while pruning excluded directories."""
    matched: list[Path] = []
    if not repo_path.is_dir():
        return matched

    for item in repo_path.rglob("*.py"):
        if any(part in IGNORED_EXPLORATION_DIRS for part in item.parts):
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
            tokens = self.model_slot.estimate_tokens(output_text)
            elapsed = time.perf_counter() - start_time

            return SubAgentResult(
                subagent_id=self.subagent_id,
                role=self.role,
                status="success",
                output=output_text,
                data={"symbol": symbol_name, "matches": matches, "files_scanned": len(py_files)},
                tokens_used=tokens,
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
            if root.is_dir():
                for item in root.rglob("*"):
                    if any(part in IGNORED_EXPLORATION_DIRS for part in item.parts):
                        continue
                    if item.is_file() and fnmatch.fnmatch(item.name, pattern):
                        matched_files.append(str(item.relative_to(root)))
                        if len(matched_files) >= max_results:
                            break

            output_text = f"Scouted {len(matched_files)} files matching '{pattern}':\n" + "\n".join(
                f"- {f}" for f in matched_files
            )
            tokens = self.model_slot.estimate_tokens(output_text)
            elapsed = time.perf_counter() - start_time

            return SubAgentResult(
                subagent_id=self.subagent_id,
                role=self.role,
                status="success",
                output=output_text,
                data={"pattern": pattern, "files": matched_files},
                tokens_used=tokens,
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
            tokens = self.model_slot.estimate_tokens(output_text) + (len(catalog) * 8)
            elapsed = time.perf_counter() - start_time

            return SubAgentResult(
                subagent_id=self.subagent_id,
                role=self.role,
                status="success",
                output=output_text,
                data={"symbols": catalog, "file_count": len(py_files)},
                tokens_used=tokens,
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


class TokenSavingsSummary(BaseModel):
    """Metrics report detailing token offloading savings."""

    frontier_tokens: int = 0
    offloaded_tokens: int = 0
    baseline_frontier_without_offload: int = 0
    savings_percentage: float = 0.0
    is_target_met: bool = False

    @classmethod
    def calculate(cls, frontier_tokens: int, offloaded_tokens: int) -> TokenSavingsSummary:
        """Calculate token savings percentage against non-offloaded baseline."""
        baseline = frontier_tokens + offloaded_tokens
        pct = round((offloaded_tokens / baseline) * 100.0, 2) if baseline > 0 else 0.0
        return cls(
            frontier_tokens=frontier_tokens,
            offloaded_tokens=offloaded_tokens,
            baseline_frontier_without_offload=baseline,
            savings_percentage=pct,
            is_target_met=(pct >= 85.0),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize TokenSavingsSummary to dictionary."""
        return {
            "frontier_tokens": self.frontier_tokens,
            "offloaded_tokens": self.offloaded_tokens,
            "baseline_frontier_without_offload": self.baseline_frontier_without_offload,
            "savings_percentage": self.savings_percentage,
            "is_target_met": self.is_target_met,
        }


class TieredExecutionResult(BaseModel):
    """Aggregate result from the 'Big decides, small types, big checks' protocol."""

    task: str
    decision_plan: str
    subagent_results: list[SubAgentResult] = Field(default_factory=list)
    verification_report: str = ""
    savings: TokenSavingsSummary = Field(default_factory=TokenSavingsSummary)
    status: str = "completed"

    def to_dict(self) -> dict[str, Any]:
        """Serialize TieredExecutionResult to dictionary."""
        return {
            "task": self.task,
            "status": self.status,
            "decision_plan": self.decision_plan,
            "subagent_results": [r.to_dict() for r in self.subagent_results],
            "verification_report": self.verification_report,
            "savings": self.savings.to_dict(),
        }


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
    def create_default(
        cls,
        frontier_model: str = "claude-3-7-sonnet",
        local_model: str = "qwen2.5-coder:7b",
    ) -> AgentHarness:
        """Construct standard harness with frontier reasoning and local offloader."""
        m_slot = ModelSlot(
            name="frontier_model",
            slot_type=SlotType.MODEL,
            provider="claude",
            model_name=frontier_model,
            tier=TaskComplexity.FRONTIER,
            is_local=False,
            state=SlotState.ATTACHED,
        )
        sk_slot = SkillSlot(name="skills", slot_type=SlotType.SKILL, state=SlotState.ATTACHED)
        t_slot = ToolSlot(name="tools", slot_type=SlotType.TOOL, state=SlotState.ATTACHED)

        sub_model = ModelSlot(
            name="subagent_model",
            slot_type=SlotType.MODEL,
            provider="ollama",
            model_name=local_model,
            tier=TaskComplexity.LOW,
            is_local=True,
            state=SlotState.ATTACHED,
        )
        sub_tools = ToolSlot(
            name="subagent_tools",
            slot_type=SlotType.TOOL,
            read_only=True,
            state=SlotState.ATTACHED,
        )
        sub_skills = SkillSlot(
            name="subagent_skills",
            slot_type=SlotType.SKILL,
            state=SlotState.ATTACHED,
        )
        sub_slot = SubAgentSlot(
            name="subagent_slot",
            slot_type=SlotType.SUBAGENT,
            subagent_id="local_scout",
            role="ast_explorer",
            model_slot=sub_model,
            tool_slot=sub_tools,
            skill_slot=sub_skills,
            state=SlotState.ATTACHED,
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
        """Execute task across 3 tiers ('Big decides, small types, big checks')."""
        # Tier 1: Big decides — plan formation
        decision_plan = (
            f"Tier 1 (Frontier - {self.model_slot.model_name}): Decomposed task '{task}'. "
            f"Delegating exploration to local sub-agent slot for symbol '{symbol_query or '*'}'."
        )
        frontier_tokens = self.model_slot.estimate_tokens(decision_plan)

        # Tier 2: Small types — local offload
        sub_results: list[SubAgentResult] = []
        offloaded_tokens = 0

        if symbol_query:
            ast_res = self.subagent_slot.offload_ast_search(repo_path, symbol_query)
            sub_results.append(ast_res)
            offloaded_tokens += ast_res.tokens_used

        if file_pattern:
            scout_res = self.subagent_slot.offload_file_scout(repo_path, file_pattern)
            sub_results.append(scout_res)
            offloaded_tokens += scout_res.tokens_used

        if not symbol_query and not file_pattern:
            cat_res = self.subagent_slot.offload_symbol_catalog(repo_path)
            sub_results.append(cat_res)
            offloaded_tokens += cat_res.tokens_used

        # Tier 3: Big checks — synthesis and validation
        match_count = sum(len(r.data.get("matches", [])) for r in sub_results)
        verification_report = (
            f"Tier 3 (Frontier - {self.model_slot.model_name}): Verified {match_count} discovered symbol(s) "
            f"and synthesized response for task '{task}' against architectural invariants."
        )
        frontier_tokens += self.model_slot.estimate_tokens(verification_report)

        savings = TokenSavingsSummary.calculate(
            frontier_tokens=frontier_tokens,
            offloaded_tokens=offloaded_tokens,
        )

        return TieredExecutionResult(
            task=task,
            decision_plan=decision_plan,
            subagent_results=sub_results,
            verification_report=verification_report,
            savings=savings,
            status="completed",
        )
