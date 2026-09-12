"""AI agent instruction generator and scaffolding utilities.

Scaffolds canonical AGENTS.md instructions along with pointer stubs for
CLAUDE.md and .github/copilot-instructions.md across repositories and
project initialization workflows.
"""

from __future__ import annotations

import html
import logging
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

from devops_cli.config.constants import CONST_AGENTS_MD_FILENAME

logger = logging.getLogger(__name__)

CONST_CLAUDE_MD_FILENAME = "CLAUDE.md"
CONST_COPILOT_INSTRUCTIONS_PATH = ".github/copilot-instructions.md"

DEFAULT_AGENT_FILES: dict[str, str] = {
    CONST_AGENTS_MD_FILENAME: "Canonical agent instructions (single source of truth)",
    CONST_CLAUDE_MD_FILENAME: "Pointer stub redirecting Claude Code to AGENTS.md",
    CONST_COPILOT_INSTRUCTIONS_PATH: "Pointer stub redirecting GitHub Copilot to AGENTS.md",
}


class ProjectMetadata(BaseModel):
    """Structured metadata parsed from project files for instruction generation."""

    name: str
    description: str = ""
    version: str = "0.1.0"
    requires_python: str = ">=3.14"
    entry_point: str = ""
    dependencies: list[str] = Field(default_factory=list)
    dev_dependencies: list[str] = Field(default_factory=list)
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
    *,
    is_devops_cli: bool = False,
) -> str:
    """Generate a thin pointer stub that redirects tools to the canonical AGENTS.md."""
    alpha_notice = (
        "\n>\n"
        "> **Pre-1.0 Alpha Notice**: This codebase is active alpha software prior to release `1.0.0`\n"
        "> with no backwards compatibility guarantees. The codebase must remain clean of legacy\n"
        "> references and obsolete shims at all times. Post-1.0 releases adhere strictly to\n"
        "> Semantic Versioning and enterprise change management (feature flags, deprecations, migrations)."
        if is_devops_cli
        else ""
    )
    return f"""\
# {title}

> **This file is a pointer, not the source.** {tool_name} looks specifically for
> `{filename}`, so this stub exists to redirect it. All actual instructions — project
> overview, build/test commands, code conventions, architecture, AI features,
> environment & modernization policy, and security notes — live in
> [AGENTS.md]({canonical_relpath}). Read that file. Regenerate both via
> `devops ai agents`; do not duplicate content here.{alpha_notice}
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

    alpha_lifecycle_block = (
        "- **Pre-1.0 Alpha Lifecycle & Zero Backwards Compatibility Guarantee**: Prior to release 1.0.0,\n"
        "  this codebase is active alpha software with no intention of maintaining backwards compatibility.\n"
        "  The codebase must remain clean of legacy references, obsolete shims, and compatibility remnants\n"
        "  at all times so that it can reach maturity at a reasonable rate. Releases after 1.0.0 will strictly\n"
        "  follow Semantic Versioning conventions with feature flags, formal deprecations, and migration tooling.\n"
        if meta.is_devops_cli
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
  - **Comprehensive Sanitization of Internal Systems & Homelab Data**: Never record or expose concrete
    internal hostnames (`*.lan`, `*.local`, physical machine names), private RFC 1918 IP addresses
    (`192.168.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`), private container registries, non-standard local
    NodePort endpoints, physical storage devices/mount paths (`/mnt/nvme*`, `/dev/sd*`), or private cluster
    topology details in task tracking (`docs/agent/tasks/`), documentation, roadmaps, tests, manifests (`k8s/`),
    or configuration templates (`config.yaml`). Always use abstract roles (`<storage-node>`, `<gpu-node>`,
    `<worker-node>`, `<host>`), RFC 5737 documentation IPs (`192.0.2.0/24`), and standard localhost endpoints.
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
- **Never Lower Security Standards or Quality Thresholds**: AI agents and assistants must never
  lower, relax, disable, bypass, or weaken security standards, quality thresholds (such as minimum
  code coverage requirements like 90%, strict static type checks, or lint rules), or compliance
  validations unless explicitly instructed to do so by the user.
- **Continuous Standards Compliance & Solution Refinement**: AI agents and assistants must always check
  that any proposed solution, design, code change, or architecture meets all project standards and
  conventions, updating and refining the solution whenever necessary until every project standard
  is met or exceeded.
- **Mandatory Documentation Synchronization After Every Change**: AI agents and assistants must always
  update project documents, architecture references, command documentation, and README files
  (`devops docs generate --sync-readme`, `docs/`, `AGENTS.md`, and relevant knowledge base task manuals)
  after every change to maintain 100% documentation integrity and prevent documentation drift.
- **Dedicated Agent Workspace Data Isolation**: The workspace data directory is configured via `DEVOPS_CLI_DATA_DIR` (or configuration setting `data.dir`, defaulting to `./.data`). AI agents executing CLI review sessions, background benchmarks, analysis scans, test executions, or temporary operational tasks must isolate agent work products under the dedicated `agent/` subfolder (`<data_dir>/agent`, e.g. `./.data/agent`) to separate agent artifacts from the user workspace data tier.
- **Mandatory Backup for Files Outside Workspace (`.bak-<YYYYMMDD-HHMMSS>`)**: Whenever modifying, overwriting, editing, or truncating any file located anywhere outside of the project workspace directory (such as files in user home directories, global configuration files, `~/.ssh/`, `~/.bashrc`, `~/.zshrc`, `/etc/`, or system files), AI agents and assistants **MUST ALWAYS** create a timestamped backup of the target file named `<original-filepath>.bak-<YYYYMMDD-HHMMSS>` prior to making any edits.
- **Iterative CI Quality Gate & Zero Tooling Redundancy**: AI agents must always make all planned
  code changes, run `devops ci`, fix all reported issues, and run `devops ci` again, iteratively
  fixing issues and running `devops ci` until passing. Agents should not run any other tooling
  that is already covered and automatically executed by `devops ci`.
- **API Rate Limit Honor, Resilient Backoff & Quota Budgeting**: AI agents and automated workflows MUST
  actively respect API rate limits, complexity budgets, and resource quotas across all external services
  (GitHub REST/GraphQL APIs, AI LLM/embedding inference endpoints, package registries, and cloud APIs).
  Proactively monitor rate limits (`gh api rate_limit`, `x-ratelimit-remaining`, `Retry-After`), gracefully
  fall back from complexity-constrained or rate-limited GraphQL queries to targeted REST endpoints, apply
  exponential backoff with random jitter, and avoid aggressive polling loops.
- **AI Inference Rate Limit & Token Budget Management**: Review pipelines and AI agent stages calling
  local or remote LLMs (Ollama, Anthropic, Gemini, OpenAI) must budget token consumption and honor
  provider quotas (Tokens-Per-Minute / TPM and Requests-Per-Minute / RPM). Bound concurrency with
  semaphores (`asyncio.Semaphore(5)` for 4–8 concurrent workers) to prevent overloading inference endpoints. On HTTP 429 or
  provider overload errors, implement exponential backoff with jitter and retry reflection rather than
  unthrottled burst retries.
{alpha_lifecycle_block}- **Clean Solutions Over Legacy Remnants (Zero Zombie Code)**: When modifying, refactoring, or
  replacing features, schemas, configurations, or interfaces, implement clean, complete solutions
  and ruthlessly remove obsolete code, variables, aliases, fallback shims, and legacy workarounds.
  Never leave remnants or vestigial fallback paths.



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
  - **Concise, Effect-Driven Commit Messages**: Commit messages MUST be concise and simply state the direct effect of the specific change. Avoid overly verbose summaries, compound multi-clause sentences, redundant narrative preambles, or sprawling lists in commit subjects. State clearly and directly what the change accomplishes.
  - Maintain atomic, cohesive commits with clean commit messages.
  - **No Internal References or Numeric IDs**: Commit messages and PR titles must describe technical changes using descriptive engineering terminology, never internal session timestamps, review numbers, subagent IDs, or prompt phase numbers.
- **Pull Request Governance & Two-Stage Review Lifecycle**:
  - AI agents prepare clean commits, open/update PRs, monitor remote CI checks (`devops pr monitor`), and leave merge approval to maintainers.
  - **Stage 1: Draft Pull Requests for In-Progress Work**:
    - Whenever opening any pull request that is not yet fully implemented, tested, and ready for review, AI agents MUST create the pull request as a draft (`gh pr create --draft` or passing `draft: true` via API). A draft pull request signals active work in progress, prevents premature review cycles, avoids false merge-readiness assumptions, while satisfying the requirement that every remote topic branch have an open pull request.
    - Actively monitor remote CI checks (`devops pr monitor <pr_number>` or `gh pr checks <pr_number>`) on every push. Remediate any failures immediately with test-first commits.
  - **Stage 2: Transition to Ready for Review & Post-Ready Review Remediation**:
    - **Marking Ready for Review**: Once all implementation logic, test-first coverage (>= 90%), documentation synchronization (`devops docs generate --sync-readme`), and all local/remote CI quality gates pass cleanly, and any initial review comments are addressed, AI agents MUST convert the pull request to ready for review (`gh pr ready <pr_number>`).
    - **Post-Ready Secondary Review & Copilot Monitoring Gate**:
      - Marking a pull request as ready for review triggers automated GitHub Copilot review sessions, CodeQL scans, and reviewer notifications.
      - AI agents are STRICTLY PROHIBITED from concluding a task immediately after marking a PR ready.
      - **5-Minute Completion Allowance & 60-Second Polling Interval**:
        - Allow at least 5 minutes (300 seconds) for pull request checks or reviews to complete.
        - Wait at least a full minute (60 seconds) between request cycles when monitoring pull request status. Never poll in rapid or sub-minute intervals.
      - Actively check for newly posted review comments/threads (`devops pr threads list <pr_number> --unresolved-only`), and address all findings.
      - If Copilot or reviewers submit review comments:
        1. Remediate all feedback iteratively using Test-First Development (author/update tests first).
        2. Reply directly within each specific review thread on the exact comment addressed (`devops pr threads reply <thread_id> "<body>"`). Never rely solely on top-level PR summary comments.
        3. Programmatically resolve review threads (`devops pr threads resolve <thread_id>`).
      - Re-verify that all remote CI checks remain 100% green (`devops pr monitor <pr_number>`).
    - **Task Completion Guarantee**: A task is ONLY complete when the PR is marked ready, all remote CI checks pass, Copilot post-ready review sessions have settled, and 0 unresolved review threads remain.
  - **Mandatory PR Monitoring Gate (`devops pr monitor`) (Zero Premature Completions & Unmonitored PRs)**:
    - AI agents **MUST ALWAYS** actively monitor pull requests by running `devops pr monitor <pr_number>` (or FastMCP `pr_monitor`) immediately after opening a PR (`gh pr create`) or pushing commits to any branch with an active PR (`git push`).
    - **Strict Prohibition of Premature Completion**: Never conclude a turn, declare a task done, switch branches, or ask the user to review or merge while CI checks are pending, failing, or while automated code review sessions (such as GitHub Copilot code review) are in progress or unresolved.
    - **Wait for Copilot Review Sessions to Settle**: Automated code review bots submit reviews asynchronously. `devops pr monitor` automatically enforces settling windows and checks timeline activity. Agents must wait for this review session to complete.
    - **Remediate Check Failures Immediately**: If any CI check fails (exit code 1), immediately inspect failed logs (`gh run view --log-failed`), diagnose root causes, apply test-first fixes with concise effect-driven commit messages, push, and re-run `devops pr monitor <pr_number>`.
    - **Remediate Review Feedback In-Thread & Resolve**: If Copilot or reviewers leave review comments (exit code 2):
      1. Inspect all open threads: `devops pr threads list <pr_number> --unresolved-only`.
      2. Author test-first fixes in `src/` and `tests/`.
      3. Commit with concise message stating the direct effect and push.
      4. Post direct in-thread replies: `devops pr threads reply <thread_id> "<body>"`. Never rely solely on top-level PR summary comments.
      5. Resolve threads: `devops pr threads resolve <thread_id>`.
      6. Re-run `devops pr monitor <pr_number>` until exit code 0 is achieved.
    - **Merge Readiness Guarantee**: A PR is ONLY ready for merging when `devops pr monitor` exits with code 0: all CI checks are 100% green, Copilot review session is settled, and 0 unresolved review discussion threads remain.
- **GitHub Projects, Issues & Views Governance**:
  - Proactively author and populate tracking issues for all scheduled roadmap deliverables upon milestone activation; the open issues queue (`issues?q=is:issue+state:open`), projects tab (`projects`), and issue views (`issues/views`) must never be left empty.
  - Link project boards conforming to `.github/project-template.json` to the repository (`devops gh project link <number>`) and synchronize items and custom fields via `devops gh project sync`.
  - Enforce strict remote branch lifecycle: every remote topic branch on `origin` must have an associated open PR, and merged or superseded branches must be deleted immediately.
  - Respect GitHub API rate limits: monitor `gh api rate_limit`, adaptively fall back to REST when GraphQL complexity limits are reached, avoid unthrottled polling, and honor `Retry-After` reset windows.
"""


def generate_instruction_content(target_file: str, meta: ProjectMetadata) -> str:
    """Generate content for a specific instruction file based on project metadata."""
    if target_file == CONST_CLAUDE_MD_FILENAME:
        return generate_pointer_stub(
            title=f"{meta.name} — Claude Instructions",
            tool_name="Claude Code",
            filename="CLAUDE.md",
            canonical_relpath="./AGENTS.md",
            is_devops_cli=meta.is_devops_cli,
        )
    if "copilot" in target_file:
        return generate_pointer_stub(
            title=f"{meta.name} — GitHub Copilot Instructions",
            tool_name="GitHub Copilot",
            filename=".github/copilot-instructions.md",
            canonical_relpath="../AGENTS.md",
            is_devops_cli=meta.is_devops_cli,
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
