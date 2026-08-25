"""AI agent instruction generator and scaffolding utilities.

Scaffolds canonical AGENTS.md instructions along with pointer stubs for
CLAUDE.md and .github/copilot-instructions.md across repositories and
project initialization workflows.
"""

from __future__ import annotations

import html
import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from devops_cli.config.constants import CONST_AGENTS_MD_FILENAME

logger = logging.getLogger(__name__)

CONST_CLAUDE_MD_FILENAME = "CLAUDE.md"
CONST_COPILOT_INSTRUCTIONS_PATH = ".github/copilot-instructions.md"

DEFAULT_AGENT_FILES: dict[str, str] = {
    CONST_AGENTS_MD_FILENAME: "Canonical agent instructions (single source of truth)",
    CONST_CLAUDE_MD_FILENAME: "Pointer stub redirecting Claude Code to AGENTS.md",
    CONST_COPILOT_INSTRUCTIONS_PATH: "Pointer stub redirecting GitHub Copilot to AGENTS.md",
}


@dataclass
class ProjectMetadata:
    """Structured metadata parsed from project files for instruction generation."""

    name: str
    description: str = ""
    version: str = "0.1.0"
    requires_python: str = ">=3.14"
    entry_point: str = ""
    dependencies: list[str] = field(default_factory=list)
    dev_dependencies: list[str] = field(default_factory=list)
    has_devcontainer: bool = False
    has_docker: bool = False
    is_devops_cli: bool = False


def parse_project_metadata(repo_path: Path) -> ProjectMetadata:
    """Extract structured metadata from pyproject.toml and repository structure."""
    resolved_path = repo_path.resolve()
    pyproject_file = resolved_path / "pyproject.toml"

    name = resolved_path.name
    description = f"{name} workspace tooling and development environment."
    version = "0.1.0"
    requires_python = ">=3.14"
    entry_point = ""
    dependencies: list[str] = []
    dev_dependencies: list[str] = []

    if pyproject_file.is_file():
        try:
            with pyproject_file.open("rb") as f:
                data = tomllib.load(f)

            project = data.get("project", {})
            if isinstance(project, dict):
                name = str(project.get("name", name))
                description = str(project.get("description", description))
                version = str(project.get("version", version))
                requires_python = str(project.get("requires-python", requires_python))

                scripts = project.get("scripts", {})
                if isinstance(scripts, dict) and scripts:
                    first_script = next(iter(scripts.keys()))
                    entry_point = f"{first_script} ({scripts[first_script]})"

                deps = project.get("dependencies", [])
                if isinstance(deps, list):
                    dependencies = [str(d) for d in deps]

            dep_groups = data.get("dependency-groups", {})
            if isinstance(dep_groups, dict):
                dev_group = dep_groups.get("dev", [])
                if isinstance(dev_group, list):
                    dev_dependencies = [str(d) for d in dev_group]
        except Exception as exc:
            logger.debug("Failed parsing pyproject.toml at %s: %s", pyproject_file, exc)

    has_devcontainer = (resolved_path / ".devcontainer" / "devcontainer.json").is_file() or (
        resolved_path / ".devcontainer.json"
    ).is_file()
    has_docker = (resolved_path / "Dockerfile").is_file() or (
        resolved_path / ".devcontainer" / "Dockerfile"
    ).is_file()
    is_devops_cli = name == "devops-cli" or "devops_cli" in entry_point

    return ProjectMetadata(
        name=name,
        description=description,
        version=version,
        requires_python=requires_python,
        entry_point=entry_point,
        dependencies=dependencies,
        dev_dependencies=dev_dependencies,
        has_devcontainer=has_devcontainer,
        has_docker=has_docker,
        is_devops_cli=is_devops_cli,
    )


def generate_pointer_stub(
    title: str,
    tool_name: str,
    filename: str,
    canonical_relpath: str,
) -> str:
    """Generate a thin pointer stub that redirects tools to the canonical AGENTS.md."""
    return f"""\
# {title}

> **This file is a pointer, not the source.** {tool_name} looks specifically for
> `{filename}`, so this stub exists to redirect it. All actual instructions — project
> overview, build/test commands, code conventions, architecture, AI features,
> environment & modernization policy, and security notes — live in
> [AGENTS.md]({canonical_relpath}). Read that file. Regenerate both via
> `devops ai agents`; do not duplicate content here.
"""


def generate_agents_md(meta: ProjectMetadata) -> str:
    """Generate canonical AGENTS.md document tailored to project metadata."""
    entry_point_line = f"- **Entry Point**: `{meta.entry_point}`\n" if meta.entry_point else ""

    if meta.is_devops_cli:
        build_commands_block = """\
```bash
uv sync                              # Synchronize dependencies with lockfile
uv run pytest                        # Run fast isolated unit tests
uv run ruff check                    # Run fast lint inspection
uv run ruff format                   # Run code formatting
uv run mypy src                      # Run strict typecheck
devops ci                            # Comprehensive quality gate
devops docs generate --sync-readme   # Synchronize CLI docs and README matrix
```"""
    else:
        build_commands_block = """\
```bash
uv sync                              # Synchronize dependencies with lockfile
uv run pytest                        # Run test suite
uv run ruff check                    # Run fast lint inspection
uv run ruff format                   # Run code formatting
uv run mypy src                      # Run strict static type validation
devops --help                        # Access global DevOps automation CLI
```"""

    devcontainer_context = (
        "- **DevContainer Environment**: Configured with pre-baked Python runtime\n"
        "  and DevOps tooling (`uv`, `docker`, `kubectl`, `helm`, `devops`).\n"
        if meta.has_devcontainer
        else ""
    )

    return f"""\
# {meta.name} — AI Agent Instructions & Engineering Best Practices

This document provides foundational context, architectural principles, and operational best
practices for AI coding assistants (GitHub Copilot, Claude, Cursor, Codex) working on this
codebase or reviewing target repositories.

> **Canonical Source**: This file is the single source of truth for AI coding agent
> instructions in this repo. [CLAUDE.md](./CLAUDE.md) and
> [.github/copilot-instructions.md](./.github/copilot-instructions.md) are thin pointers
> to this file.

## 1. Project Overview & Architecture

- **Project Name**: `{meta.name}`
- **Description**: {html.escape(meta.description, quote=True)}
- **Language & Runtime**: Python {meta.requires_python}
{entry_point_line}- **Virtual Environment**: `.venv/` (managed by `uv`)
{devcontainer_context}
## 2. Core Engineering Philosophy & Best Practices

- **High Reliability & Quality First**: Build robust, resilient workstation automation and developer
  tooling with defensive error handling, explicit timeouts, and zero tolerance for flaky tests.
- **Poetic Conciseness & Architectural Elegance**: The codebase is an expressive, poetically concise
  integration of tools, libraries, docs, AI, and automation. Control code complexity by aiming for
  fewer than 6 indentations across all functions and code blocks. Decompose complex tasks, deep
  branching, and nested iterations into dedicated, single-responsibility functions. Prefer clean
  functional pipelines, Pydantic models, and standard library composition over low-level nested
  loops or ad-hoc procedural parsing.
- **Modern Python Ecosystem**: Track modern Python 3.14+ runtime features, typing standards, and
  established open-source libraries (`pydantic v2`, `httpx2`, `pytest`, `ruff`, `mypy`, `uv.lock`).
  Avoid custom workarounds when standard library or robust open-source tools exist.
- **Zero-Trust Security & Egress Safety**:
  - Never store plaintext secrets or tokens in code, configuration files, or logs. Always use OS
    Keyring or secure secret stores.
  - Never leak or extract information from hidden, private, or `.gitignored` files (`.env*`,
    `.ssh/`, `.data/`, `~/.gemini/`, local credentials, private keys) into any documents,
    changelogs, review findings, public commits, or code artifacts.
  - When constructing documentation, reviews, prompt context, or code examples, always redact,
    mask, or generalize any sensitive local environments, file system trees, or user identifiers.
  - Mitigate Server-Side Request Forgery (SSRF) and network egress risks by validating destination
    endpoints.
  - Enforce subprocess safety with explicit command argument lists, bounded timeouts, and error
    handling.
- **Standard Parsers & Dynamic Introspection**: Always use established language-agnostic code
  quality standards, standard library parsers (`ast`, `tokenize`, `json`, `tomllib`, `yaml`,
  `urllib.parse`, `ipaddress`, `mimetypes`, `functools.lru_cache`), and official specifications
  over hardcoded literal subsets.
- **Knowledge Base Consultation**: Always consult project documentation and knowledge base
  guides (`src/devops_cli/ai/knowledge_base/` or `docs/`) before designing, implementing, or
  modifying system components.



## 3. Build, Lint & Test Commands

{build_commands_block}

## 4. Git Hygiene & Branch Management

- **Branch Hierarchy & Isolation**:
  - All feature and fix work must be conducted on dedicated topic branches
    (`feat/<description>`, `fix/<description>`, `docs/<description>`, `refactor/<description>`).
  - Feature, fix, and refactoring PRs target active release branches.
- **Commit Standards**:
  - Follow **Conventional Commits** format (`feat(scope): ...`, `fix(scope): ...`,
    `refactor(scope): ...`, `docs(scope): ...`).
  - Maintain atomic, cohesive commits with clean commit messages.
- **Pull Request Governance**:
  - AI agents prepare clean commits, open/update PRs, monitor remote CI checks, and leave merge
    approval to maintainers.
"""


def generate_instruction_content(target_file: str, meta: ProjectMetadata) -> str:
    """Generate content for a specific instruction file based on project metadata."""
    if target_file == CONST_CLAUDE_MD_FILENAME:
        return generate_pointer_stub(
            title=f"{meta.name} — Claude Instructions",
            tool_name="Claude Code",
            filename="CLAUDE.md",
            canonical_relpath="./AGENTS.md",
        )
    if "copilot" in target_file:
        return generate_pointer_stub(
            title=f"{meta.name} — GitHub Copilot Instructions",
            tool_name="GitHub Copilot",
            filename=".github/copilot-instructions.md",
            canonical_relpath="../AGENTS.md",
        )
    return generate_agents_md(meta)


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
               AGENTS.md, CLAUDE.md, and .github/copilot-instructions.md.

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
