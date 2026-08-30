"""RepoContext capability for inspecting workspace repositories and assets."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.agents.pydantic_agent import AgentTool, BaseCapability, RunContext, Tool

logger = logging.getLogger(__name__)


class AssetRoot(BaseModel):
    """Where context engineering assets live under a single root directory (e.g. .claude, .agents)."""

    model_config = ConfigDict(extra="ignore")

    root: str
    exists: bool = False
    path: Path
    skills: list[str] = Field(default_factory=list)
    agents: list[str] = Field(default_factory=list)
    hooks: list[str] = Field(default_factory=list)


class AgentContextInventory(BaseModel):
    """A structured map of where a repository's context engineering assets live."""

    model_config = ConfigDict(extra="ignore")

    workspace_dir: Path
    roots: dict[str, AssetRoot] = Field(default_factory=dict)
    discovered_instruction_files: list[Path] = Field(default_factory=list)


def _format_nested_candidate_note(
    candidate: Path, fname: str, target_dir: Path, nested_inject: str
) -> str:
    """Format note for nested candidate instruction file."""
    if nested_inject == "pointer":
        return f"\n\n[RepoContext: Note that {fname} is present in {target_dir.name}/]"
    try:
        c = candidate.read_text(encoding="utf-8").strip()
        return f"\n\n# Context from {candidate.name}:\n{c}"
    except Exception:
        return f"\n\n[RepoContext: {fname} present]"


def _format_root_inventory_lines(r_name: str, r: Any) -> list[str]:
    """Format single inventory root lines."""
    if not r.exists:
        return [f"  - {r_name}: (not present)"]
    res = [f"  - **{r_name}** ({r.path}):"]
    if r.skills:
        res.append(f"      skills: {', '.join(r.skills)}")
    if r.agents:
        res.append(f"      agents: {', '.join(r.agents)}")
    if r.hooks:
        res.append(f"      hooks: {', '.join(r.hooks)}")
    return res


class RepoContext(BaseCapability):
    """Capability that discovers and loads a repository's accumulated coding-assistant context engineering."""

    id: str = "repo_context"
    workspace_dir: Path = Field(default_factory=lambda: Path("."))
    home_dir: Path | None = None
    filenames: tuple[str, ...] = ("CLAUDE.md", "AGENTS.md")
    autoload_instructions: bool = True
    expose_inventory_tool: bool = True
    inventory_tool_name: str = "inventory_agent_context"
    nested_traversal: bool = False
    nested_inject: Literal["pointer", "contents"] = "pointer"
    traversal_tool_names: frozenset[str] = Field(
        default_factory=lambda: frozenset({"list_directory", "read_file", "list_dir", "view_file"})
    )
    traversal_path_arg: str = "path"
    asset_roots: tuple[str, ...] = (".claude", ".agents", ".codex", ".grok")
    surfaced_directories: set[str] = Field(default_factory=set)

    def __init__(
        self,
        workspace_dir: str | Path = Path("."),
        *,
        home_dir: str | Path | None = None,
        filenames: Sequence[str] = ("CLAUDE.md", "AGENTS.md"),
        autoload_instructions: bool = True,
        expose_inventory_tool: bool = True,
        inventory_tool_name: str = "inventory_agent_context",
        nested_traversal: bool = False,
        nested_inject: Literal["pointer", "contents"] = "pointer",
        traversal_tool_names: frozenset[str] | Sequence[str] | None = None,
        traversal_path_arg: str = "path",
        asset_roots: Sequence[str] = (".claude", ".agents", ".codex", ".grok"),
        id: str = "repo_context",
    ) -> None:
        ws_path = Path(workspace_dir).resolve()
        h_path = Path(home_dir).resolve() if home_dir is not None else None
        t_names = (
            frozenset(traversal_tool_names)
            if traversal_tool_names is not None
            else frozenset({"list_directory", "read_file", "list_dir", "view_file"})
        )
        super().__init__(
            id=str(id or "repo_context"),
            workspace_dir=ws_path,
            home_dir=h_path,
            filenames=tuple(filenames),
            autoload_instructions=autoload_instructions,
            expose_inventory_tool=expose_inventory_tool,
            inventory_tool_name=inventory_tool_name,
            nested_traversal=nested_traversal,
            nested_inject=nested_inject,
            traversal_tool_names=t_names,
            traversal_path_arg=traversal_path_arg,
            asset_roots=tuple(asset_roots),
        )

    def for_run(self, ctx: RunContext[Any] | None = None) -> RepoContext:
        """Return a fresh per-run instance with isolated traversal/cache state."""
        return RepoContext(
            workspace_dir=self.workspace_dir,
            home_dir=self.home_dir,
            filenames=self.filenames,
            autoload_instructions=self.autoload_instructions,
            expose_inventory_tool=self.expose_inventory_tool,
            inventory_tool_name=self.inventory_tool_name,
            nested_traversal=self.nested_traversal,
            nested_inject=self.nested_inject,
            traversal_tool_names=self.traversal_tool_names,
            traversal_path_arg=self.traversal_path_arg,
            asset_roots=self.asset_roots,
            id=self.id,
        )

    def _resolve_ancestor_chain(self) -> list[Path]:
        """Resolve ancestor directory chain from home_dir down to workspace_dir (ancestor-first)."""
        chain: list[Path] = [self.workspace_dir]
        if self.home_dir is not None:
            curr = self.workspace_dir.parent
            while True:
                chain.append(curr)
                if curr == self.home_dir or curr.parent == curr:
                    break
                curr = curr.parent
        chain.reverse()
        return chain

    def _try_add_discovered_file(
        self, fpath: Path, seen_resolved: set[Path], seen_hashes: set[str], discovered: list[Path]
    ) -> None:
        """Attempt to add a resolved unique instruction file."""
        if not fpath.is_file():
            return
        resolved = fpath.resolve()
        if resolved in seen_resolved:
            return
        try:
            content = resolved.read_text(encoding="utf-8")
            chash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if chash in seen_hashes:
                return
            seen_resolved.add(resolved)
            seen_hashes.add(chash)
            discovered.append(resolved)
        except Exception:
            pass

    def discover(self) -> list[Path]:
        """Discover instruction files traversing ancestors up to stop_at root."""
        chain = self._resolve_ancestor_chain()
        discovered: list[Path] = []
        seen_resolved: set[Path] = set()
        seen_hashes: set[str] = set()

        for d in chain:
            if not d.exists() or not d.is_dir():
                continue
            for fname in self.filenames:
                self._try_add_discovered_file(d / fname, seen_resolved, seen_hashes, discovered)
        return discovered

    def _scan_skills_dir(self, skills_dir: Path) -> list[str]:
        """Scan skills directory for subdirectories containing SKILL.md."""
        if not skills_dir.is_dir():
            return []
        return [
            s.name
            for s in sorted(skills_dir.iterdir())
            if s.is_dir() and (s / "SKILL.md").is_file()
        ]

    def _scan_agents_dir(self, agents_dir: Path) -> list[str]:
        """Scan agents directory for agent specification files and directories."""
        if not agents_dir.is_dir():
            return []
        agents: list[str] = []
        for a in sorted(agents_dir.iterdir()):
            if a.is_file() and a.suffix == ".md":
                agents.append(a.stem)
            elif a.is_dir() and (a / "AGENT.md").is_file():
                agents.append(a.name)
        return agents

    def _scan_hooks(self, r_path: Path) -> list[str]:
        """Scan hook configuration files in asset root."""
        hooks: list[str] = []
        for h_candidate in [r_path / "settings.json", r_path / "hooks.json"]:
            if not h_candidate.is_file():
                continue
            try:
                parsed = json.loads(h_candidate.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    hooks.extend(list(parsed.keys()))
            except Exception:
                pass
        return hooks

    def inventory(self) -> AgentContextInventory:
        """Collect structured inventory of context engineering roots, skills, agents, and hooks."""
        roots_map: dict[str, AssetRoot] = {}
        for r_name in self.asset_roots:
            r_path = self.workspace_dir / r_name
            if not r_path.exists() or not r_path.is_dir():
                roots_map[r_name] = AssetRoot(root=r_name, exists=False, path=r_path)
                continue

            roots_map[r_name] = AssetRoot(
                root=r_name,
                exists=True,
                path=r_path,
                skills=self._scan_skills_dir(r_path / "skills"),
                agents=self._scan_agents_dir(r_path / "agents"),
                hooks=self._scan_hooks(r_path),
            )

        inst_files = self.discover()
        return AgentContextInventory(
            workspace_dir=self.workspace_dir,
            roots=roots_map,
            discovered_instruction_files=inst_files,
        )

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        additions: list[str] = []
        if self.autoload_instructions:
            files = self.discover()
            for f in files:
                try:
                    rel = f.relative_to(self.workspace_dir)
                except ValueError:
                    rel = f
                content = f.read_text(encoding="utf-8").strip()
                if content:
                    additions.append(f"# Repository Instructions ({rel}):\n{content}")

        if self.expose_inventory_tool:
            additions.append(
                f"You have access to the '{self.inventory_tool_name}' tool to inspect context engineering assets (.claude, .agents, skills, sub-agents)."
            )
        return additions

    def after_tool_execute(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: Any,
    ) -> Any:
        """Strategy 3: append a directory's instruction file to a list/read result."""
        if not self.nested_traversal or tool_name not in self.traversal_tool_names:
            return result

        path_val = (
            args.get(self.traversal_path_arg)
            or args.get("path")
            or args.get("dir")
            or args.get("directory")
        )
        if not path_val:
            return result

        target_path = Path(path_val)
        if not target_path.is_absolute():
            target_path = self.workspace_dir / target_path
        if target_path.is_file() or target_path.suffix:
            target_dir = target_path.parent
        else:
            target_dir = target_path

        dir_key = str(target_dir.resolve())
        if dir_key in self.surfaced_directories:
            return result

        for fname in self.filenames:
            candidate = target_dir / fname
            if candidate.is_file():
                self.surfaced_directories.add(dir_key)
                note = _format_nested_candidate_note(
                    candidate, fname, target_dir, self.nested_inject
                )
                return f"{result}{note}"
        return result

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        if not self.expose_inventory_tool:
            return []

        inv_fn = self.inventory

        def inventory_agent_context() -> str:
            """Inspect where context engineering assets live across .claude, .agents, .codex, and .grok."""
            inv = inv_fn()
            lines = [f"Repository Context Inventory ({inv.workspace_dir}):"]
            if inv.discovered_instruction_files:
                lines.append("Instruction files:")
                lines.extend(f"  - {inst}" for inst in inv.discovered_instruction_files)
            lines.append("Asset roots:")
            for r_name, r in sorted(inv.roots.items()):
                lines.extend(_format_root_inventory_lines(r_name, r))
            return "\n".join(lines)

        return [
            Tool.from_function(
                inventory_agent_context,
                name=self.inventory_tool_name,
                description="Report where the repository's context engineering assets (skills, agents, hooks) live.",
            )
        ]
