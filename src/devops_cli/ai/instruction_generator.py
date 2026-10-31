"""AI agent instruction generator and scaffolding utilities.

Scaffolds the router AGENTS.md (the rules every task needs, and a table that sends each kind of
task to the document that owns it) with pointer stubs for CLAUDE.md, GEMINI.md and
.github/copilot-instructions.md. The text comes from the Jinja2 templates `AGENTS.md.j2` and
`pointer_stub.md.j2`, so no Markdown lives in this module.
"""

from __future__ import annotations

import logging
import subprocess
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.constants import (
    CONST_AGENTS_MD_FILENAME,
    CONST_AGENTS_MD_ROUTES,
    CONST_PRE_COMMIT_CONFIG_FILENAME,
    CONST_PRE_COMMIT_PRE_PUSH_STAGE,
)
from devops_cli.config.defaults import (
    DEFAULT_AGENTS_MD_CHECK_COMMANDS,
    DEFAULT_PROJECT_VERSION,
    DEFAULT_PYTHON_REQUIRES,
)
from devops_cli.core.templating import render_template

logger = logging.getLogger(__name__)

CONST_CLAUDE_MD_FILENAME = "CLAUDE.md"
CONST_GEMINI_MD_FILENAME = "GEMINI.md"
CONST_COPILOT_INSTRUCTIONS_PATH = ".github/copilot-instructions.md"

DEFAULT_AGENT_FILES: dict[str, str] = {
    CONST_AGENTS_MD_FILENAME: "Canonical agent instructions (single source of truth)",
    CONST_CLAUDE_MD_FILENAME: "Pointer stub redirecting Claude Code to AGENTS.md",
    CONST_GEMINI_MD_FILENAME: "Pointer stub redirecting Gemini CLI to AGENTS.md",
    CONST_COPILOT_INSTRUCTIONS_PATH: "Pointer stub redirecting GitHub Copilot to AGENTS.md",
}


class PointerStub(BaseModel):
    """What differs between the pointer stubs: the tool, the title and the way to AGENTS.md."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title_suffix: str
    tool_name: str
    canonical_relpath: str
    import_line: str | None = None


# The stub of each tool by its file name. A tool that expands an import line (Claude Code and
# Gemini CLI) gets one, in the form that its own documentation shows, so its session carries
# the rules of AGENTS.md.
POINTER_STUBS: dict[str, PointerStub] = {
    CONST_CLAUDE_MD_FILENAME: PointerStub(
        title_suffix="Claude Instructions",
        tool_name="Claude Code",
        canonical_relpath="./AGENTS.md",
        import_line="@AGENTS.md",
    ),
    CONST_GEMINI_MD_FILENAME: PointerStub(
        title_suffix="Gemini CLI Instructions",
        tool_name="Gemini CLI",
        canonical_relpath="./AGENTS.md",
        import_line="@./AGENTS.md",
    ),
    CONST_COPILOT_INSTRUCTIONS_PATH: PointerStub(
        title_suffix="GitHub Copilot Instructions",
        tool_name="GitHub Copilot",
        canonical_relpath="../AGENTS.md",
    ),
}


class ProjectMetadata(BaseModel):
    """Structured metadata parsed from project files for instruction generation."""

    name: str
    description: str = ""
    version: str = DEFAULT_PROJECT_VERSION
    requires_python: str = DEFAULT_PYTHON_REQUIRES
    entry_point: str = ""
    dependencies: list[str] = Field(default_factory=list)
    dev_dependencies: list[str] = Field(default_factory=list)
    # The paths of `CONST_AGENTS_MD_ROUTES` that exist in the project, in the order of its table.
    routed_documents: list[str] = Field(default_factory=list)
    # The commands the project runs before a push: its pre-push hooks, or the uv defaults.
    check_commands: list[str] = Field(
        default_factory=lambda: list(DEFAULT_AGENTS_MD_CHECK_COMMANDS)
    )


def _extract_pyproject_deps(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Extract standard and dev dependencies from parsed pyproject.toml dictionary."""
    deps: list[str] = []
    dev_deps: list[str] = []
    project = data.get("project")
    if isinstance(project, dict):
        raw_deps = project.get("dependencies")
        if isinstance(raw_deps, list):
            deps = [str(d) for d in raw_deps]
    dep_groups = data.get("dependency-groups")
    if isinstance(dep_groups, dict):
        raw_dev = dep_groups.get("dev")
        if isinstance(raw_dev, list):
            dev_deps = [str(d) for d in raw_dev]
    return deps, dev_deps


def _extract_pyproject_meta(
    project: dict[str, Any], default_name: str, default_desc: str
) -> tuple[str, str, str, str, str]:
    """Extract core project naming, description, version, python, and entry points."""
    name = str(project.get("name", default_name))
    desc = str(project.get("description", default_desc))
    ver = str(project.get("version", DEFAULT_PROJECT_VERSION))
    req_py = str(project.get("requires-python", DEFAULT_PYTHON_REQUIRES))
    entry = ""
    scripts = project.get("scripts")
    if isinstance(scripts, dict) and scripts:
        first_script = next(iter(scripts.keys()))
        entry = f"{first_script} ({scripts[first_script]})"
    return name, desc, ver, req_py, entry


def _pre_push_commands(repo_path: Path) -> list[str]:
    """The command of each pre-push hook in the project's `.pre-commit-config.yaml`.

    A local hook runs its `entry`; a hook from another repository is named by its `id`. A file
    that does not parse, or a project without one, has no pre-push commands.
    """
    config_file = repo_path / CONST_PRE_COMMIT_CONFIG_FILENAME
    try:
        config = (
            yaml.safe_load(config_file.read_text(encoding="utf-8"))
            if config_file.is_file()
            else None
        )
    except (yaml.YAMLError, OSError) as exc:
        logger.debug("Failed parsing %s: %s", config_file, exc)
        return []
    if not isinstance(config, dict):
        return []
    default_stages = config.get("default_stages") or []
    return [
        str(hook.get("entry") or hook.get("id"))
        for repo in config.get("repos") or []
        if isinstance(repo, dict)
        for hook in repo.get("hooks") or []
        if isinstance(hook, dict)
        and CONST_PRE_COMMIT_PRE_PUSH_STAGE in (hook.get("stages") or default_stages)
    ]


def parse_project_metadata(repo_path: Path) -> ProjectMetadata:
    """Extract structured metadata from pyproject.toml and repository structure."""
    resolved_path = repo_path.resolve()
    pyproject_file = resolved_path / "pyproject.toml"

    name = resolved_path.name
    description = f"{name} workspace tooling and development environment."
    version = DEFAULT_PROJECT_VERSION
    requires_python = DEFAULT_PYTHON_REQUIRES
    entry_point = ""
    dependencies: list[str] = []
    dev_dependencies: list[str] = []

    if pyproject_file.is_file():
        try:
            with pyproject_file.open("rb") as f:
                data = tomllib.load(f)
            project = data.get("project")
            if isinstance(project, dict):
                name, description, version, requires_python, entry_point = _extract_pyproject_meta(
                    project, name, description
                )
            dependencies, dev_dependencies = _extract_pyproject_deps(data)
        except (tomllib.TOMLDecodeError, OSError) as exc:
            logger.debug("Failed parsing pyproject.toml at %s: %s", pyproject_file, exc)

    return ProjectMetadata(
        name=name,
        description=description,
        version=version,
        requires_python=requires_python,
        entry_point=entry_point,
        dependencies=dependencies,
        dev_dependencies=dev_dependencies,
        routed_documents=[
            path for path, _task in CONST_AGENTS_MD_ROUTES if (resolved_path / path).exists()
        ],
        check_commands=_pre_push_commands(resolved_path) or list(DEFAULT_AGENTS_MD_CHECK_COMMANDS),
    )


def generate_pointer_stub(
    title: str,
    tool_name: str,
    filename: str,
    canonical_relpath: str,
    *,
    import_line: str | None = None,
) -> str:
    """Generate a thin pointer stub that redirects tools to the canonical AGENTS.md.

    With `import_line`, the stub also holds that line, which the tool expands into its context.
    """
    return render_template(
        "pointer_stub.md.j2",
        title=title,
        tool_name=tool_name,
        filename=filename,
        canonical_relpath=canonical_relpath,
        import_line=import_line,
    )


def generate_agents_md(meta: ProjectMetadata) -> str:
    """Generate the router AGENTS.md of a project: its purpose, the rules for every task, and a
    row for each routed document that exists in it."""
    tasks = dict(CONST_AGENTS_MD_ROUTES)
    return render_template(
        "AGENTS.md.j2",
        name=meta.name,
        description=meta.description,
        requires_python=meta.requires_python,
        entry_point=meta.entry_point,
        check_commands=meta.check_commands,
        routes=[(path, tasks[path]) for path in meta.routed_documents if path in tasks],
    )


def generate_instruction_content(target_file: str, meta: ProjectMetadata) -> str:
    """Generate content for a specific instruction file based on project metadata."""
    filename = PurePosixPath(target_file).as_posix()
    stub = POINTER_STUBS.get(filename)
    if stub is not None:
        return generate_pointer_stub(
            title=f"{meta.name} — {stub.title_suffix}",
            tool_name=stub.tool_name,
            filename=filename,
            canonical_relpath=stub.canonical_relpath,
            import_line=stub.import_line,
        )
    return generate_agents_md(meta)


def collect_project_context(repo: Path) -> str:
    """Gather key project files into a single context string."""
    from devops_cli.ai.rag.investigator import investigate_rag_context
    from devops_cli.config.constants import (
        CONST_DEVCONTAINER_JSON_PATH,
        CONST_GIT_DIR_NAME,
    )
    from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
    from devops_cli.core.process import run_subprocess
    from devops_cli.security.sanitizer import sanitize_prompt_boundary_tags

    sections: list[str] = []

    # pyproject.toml
    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        sections.append(f"## pyproject.toml\n```toml\n{pyproject.read_text()}\n```")

    # README
    for name in ("README.md", "README.rst", "README.txt", "README"):
        readme = repo / name
        if readme.exists():
            clean_readme = sanitize_prompt_boundary_tags(readme.read_text()[:4000])
            sections.append(
                f"## {name}\n"
                f'<project_context_file name="{name}">\n'
                f"{clean_readme}\n"
                f"</project_context_file>"
            )
            break

    # Directory tree (2 levels)
    try:
        tree = run_subprocess(
            [
                "find",
                ".",
                "-maxdepth",
                "3",
                "-not",
                "-path",
                f"./{CONST_GIT_DIR_NAME}/*",
                "-not",
                "-path",
                "./.venv/*",
                "-not",
                "-path",
                "./__pycache__/*",
            ],
            capture_output=True,
            text=True,
            cwd=repo,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
        clean_tree = sanitize_prompt_boundary_tags(tree.stdout.strip())
        sections.append(f"## File tree\n```\n{clean_tree}\n```")
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("Failed to read file tree: %s", exc)

    # .editorconfig
    ec = repo / ".editorconfig"
    if ec.exists():
        clean_ec = sanitize_prompt_boundary_tags(ec.read_text()[:4000])
        sections.append(
            "## .editorconfig\n"
            '<project_context_file name=".editorconfig">\n'
            f"{clean_ec}\n"
            "</project_context_file>"
        )

    # devcontainer.json
    dc = repo / CONST_DEVCONTAINER_JSON_PATH
    if dc.exists():
        sections.append(f"## {CONST_DEVCONTAINER_JSON_PATH}\n```json\n{dc.read_text()}\n```")

    # Semantic RAG Architecture Context
    rag = investigate_rag_context(f"{repo.name} architecture CLI commands conventions", top_k=4)
    if rag and rag.has_results:
        sections.append(f"## Indexed Architecture & Subsystem Context\n{rag.formatted_text}")

    return "\n\n".join(sections)


def scaffold_agent_instructions(
    repo_path: Path,
    *,
    force: bool = False,
    template: bool = True,
    use_llm: bool = False,
    files: list[str] | None = None,
) -> list[Path]:
    """Scaffold or regenerate AI agent instruction files in the specified repository.

    Args:
        repo_path: Path to the target repository root.
        force: If True, overwrite existing files. If False, skip existing files.
        template: If True, generate from built-in templates without LLM invocation.
        use_llm: If True and template is False, attempt LLM completion for AGENTS.md.
        files: Optional list of relative file paths to generate. Defaults to
               every file of `DEFAULT_AGENT_FILES`.

    Returns:
        List of Path objects for files that were written or updated.
    """
    resolved_repo = repo_path.resolve()
    target_files = files if files is not None else list(DEFAULT_AGENT_FILES.keys())
    meta = parse_project_metadata(resolved_repo)

    written_paths: list[Path] = []

    for target in target_files:
        dest = (resolved_repo / target).resolve()

        # Guard against path traversal outside target repository root
        if not (dest == resolved_repo or dest.is_relative_to(resolved_repo)):
            logger.warning("Target path '%s' is outside repo root '%s'", dest, resolved_repo)
            continue

        if dest.is_file() and not force:
            logger.debug("Skipping existing instruction file: %s", dest)
            continue

        content = generate_instruction_content(target, meta)

        dest.parent.mkdir(parents=True, exist_ok=True)
        if not content.endswith("\n"):
            content += "\n"
        dest.write_text(content, encoding="utf-8")
        written_paths.append(dest)

    return written_paths
