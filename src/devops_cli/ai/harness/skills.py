"""Skills capability for dynamic agent skill loading and execution."""

from __future__ import annotations

import logging
import re
import unicodedata
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.agents.pydantic_agent import AgentTool, BaseCapability, RunContext, Tool
from devops_cli.ai.harness.constants import UNSUPPORTED_BEHAVIORAL_SKILL_FIELDS

logger = logging.getLogger(__name__)


class ParsedSkill(BaseModel):
    """An individual Agent Skill discovered from a SKILL.md package."""

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str
    body: str = ""
    directory: Path
    loaded: bool = False


def normalize_skill_name(name: str) -> str:
    """Normalize and validate an Agent Skill name using Unicode NFKC."""
    norm = unicodedata.normalize("NFKC", str(name)).strip().lower()
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", norm) or len(norm) > 64:
        raise ValueError(
            f"Invalid skill name '{name}': normalized name must be 1-64 lowercase alphanumeric characters separated by hyphens"
        )
    return norm


def _parse_skill_frontmatter_and_body(raw_text: str, skill_md: Path) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter and markdown body from SKILL.md."""
    if not raw_text.startswith("---"):
        return {}, raw_text
    parts = raw_text.split("---", 2)
    if len(parts) < 3:
        return {}, raw_text
    fm_str, body_text = parts[1], parts[2].strip()
    try:
        parsed_fm = yaml.safe_load(fm_str)
        return (parsed_fm if isinstance(parsed_fm, dict) else {}), body_text
    except Exception as e:
        raise ValueError(f"Malformed YAML frontmatter in '{skill_md}': {e}") from e


def _resolve_skill_name(frontmatter_dict: dict[str, Any], dir_name: str) -> str:
    """Validate declared skill name against directory name."""
    dir_norm_name = normalize_skill_name(dir_name)
    declared_name = frontmatter_dict.get("name")
    if not declared_name:
        return dir_norm_name
    norm_decl = normalize_skill_name(str(declared_name))
    if norm_decl != dir_norm_name:
        raise ValueError(f"Skill name '{declared_name}' does not match directory '{dir_name}'")
    return norm_decl


def _validate_and_build_parsed_skill(
    frontmatter_dict: dict[str, Any],
    final_name: str,
    body_text: str,
    child: Path,
    discovered: dict[str, ParsedSkill],
    unsupported_found: set[str],
) -> ParsedSkill:
    """Validate skill frontmatter rules and construct ParsedSkill."""
    if final_name in discovered:
        raise ValueError(f"Duplicate skill name '{final_name}' discovered across libraries")

    desc = str(frontmatter_dict.get("description", "")).strip()
    if not desc:
        raise ValueError(f"Skill '{final_name}' missing required 'description' in frontmatter")
    if len(desc) > 1024:
        warnings.warn(
            f"Skill '{final_name}' description exceeds 1024 character limit ({len(desc)} chars)",
            UserWarning,
            stacklevel=2,
        )

    for k in frontmatter_dict:
        if k in UNSUPPORTED_BEHAVIORAL_SKILL_FIELDS:
            unsupported_found.add(k)

    return ParsedSkill(
        name=final_name,
        description=desc,
        body=body_text,
        directory=child,
    )


class Skills(BaseCapability):
    """Capability loading Agent Skill instructions as on-demand deferred capabilities."""

    id: str = "skills"
    directories: tuple[Path, ...] = Field(default_factory=tuple)
    include: frozenset[str] | None = None
    exclude: frozenset[str] = Field(default_factory=frozenset)
    skills: dict[str, ParsedSkill] = Field(default_factory=dict)
    loaded_skills: set[str] = Field(default_factory=set)

    def __init__(
        self,
        directories: str | Path | Sequence[str | Path],
        *,
        include: Any = None,
        exclude: Any = None,
        id: str | None = None,
    ) -> None:
        if include is not None and exclude is not None:
            raise ValueError("Skills cannot specify both 'include' and 'exclude'")

        # Normalize directories
        dirs_seq = [directories] if isinstance(directories, (str, Path)) else list(directories)
        norm_dirs: list[Path] = []
        for d in dirs_seq:
            p = Path(d)
            if not p.exists() or not p.is_dir():
                raise ValueError(
                    f"Skill library directory does not exist or is not a directory: {d}"
                )
            norm_dirs.append(p)

        norm_include = (
            frozenset(normalize_skill_name(x) for x in include) if include is not None else None
        )
        norm_exclude = (
            frozenset(normalize_skill_name(x) for x in exclude)
            if exclude is not None
            else frozenset()
        )

        super().__init__(
            id=str(id or "skills"),
            directories=tuple(norm_dirs),
            include=norm_include,
            exclude=norm_exclude,
        )

        discovered: dict[str, ParsedSkill] = {}
        unsupported_found: set[str] = set()

        for lib_dir in self.directories:
            for child in sorted(lib_dir.iterdir()):
                if not child.is_dir():
                    continue
                skill_md = child / "SKILL.md"
                if not skill_md.is_file():
                    continue
                raw_text = skill_md.read_text(encoding="utf-8")
                frontmatter_dict, body_text = _parse_skill_frontmatter_and_body(raw_text, skill_md)
                final_name = _resolve_skill_name(frontmatter_dict, child.name)

                # Selection filter
                if self.include is not None and final_name not in self.include:
                    continue
                if final_name in self.exclude:
                    continue

                discovered[final_name] = _validate_and_build_parsed_skill(
                    frontmatter_dict,
                    final_name,
                    body_text,
                    child,
                    discovered,
                    unsupported_found,
                )

        if self.include is not None:
            missing_included = self.include - set(discovered.keys())
            if missing_included:
                raise ValueError(
                    f"Unknown skill(s) specified in 'include': {sorted(missing_included)}"
                )

        if unsupported_found:
            warnings.warn(
                f"Skills library contains unsupported behavioral frontmatter fields: {sorted(unsupported_found)}",
                UserWarning,
                stacklevel=2,
            )

        self.skills = discovered

    def get_system_prompt_additions(self, ctx: RunContext[Any] | None = None) -> list[str]:
        additions: list[str] = []
        if self.skills:
            catalog_lines = [
                "Available specialized skills (load with load_capability when needed):"
            ]
            for name, sk in sorted(self.skills.items()):
                catalog_lines.append(f"- **{name}**: {sk.description}")
            additions.append("\n".join(catalog_lines))

        for name in sorted(self.loaded_skills):
            if name in self.skills:
                sk = self.skills[name]
                additions.append(f"# Skill: {sk.name}\n\n{sk.body}")
        return additions

    def get_tools(self) -> list[AgentTool | Callable[..., Any]]:
        skills_dict = self.skills
        loaded_set = self.loaded_skills

        def load_capability(name: str) -> str:
            """Load the full instructions for a specialized Agent Skill into working memory."""
            clean = name.strip().lower()
            if clean not in skills_dict:
                avail = ", ".join(sorted(skills_dict.keys()))
                return f"Error: Skill '{name}' not found. Available skills: {avail}"

            loaded_set.add(clean)
            sk = skills_dict[clean]
            return f"# Skill: {sk.name}\n\n{sk.body}"

        def list_skills() -> str:
            """List all available and loaded skills in this agent session."""
            if not skills_dict:
                return "No skills configured."
            lines = ["Available Agent Skills:"]
            for s_name, sk in sorted(skills_dict.items()):
                status = "[LOADED]" if s_name in loaded_set else "[AVAILABLE]"
                lines.append(f"- {status} **{s_name}**: {sk.description}")
            return "\n".join(lines)

        return [
            Tool.from_function(
                load_capability,
                name="load_capability",
                description="Load instructions for an Agent Skill by name.",
            ),
            Tool.from_function(
                list_skills,
                name="list_skills",
                description="List all available and currently active Agent Skills.",
            ),
        ]

    def __repr__(self) -> str:
        parts = [f"directories={self.directories!r}"]
        if self.include is not None:
            parts.append(f"include={self.include!r}")
        if self.exclude:
            parts.append(f"exclude={self.exclude!r}")
        return f"Skills({', '.join(parts)})"

    def apply(self, visitor: Callable[[Any], None]) -> None:
        """Expose each selected skill as a deferred leaf capability."""
        for sk in self.skills.values():
            visitor(sk)


DEFAULT_PYAI_DOCS_TOPICS: tuple[str, ...] = (
    "agent",
    "capabilities",
    "hooks",
    "tools",
    "tools-advanced",
    "toolsets",
)
