"""Fast-path help renderer for devops CLI and subcommands."""

from __future__ import annotations

import sys
from typing import Final

from devops_cli import __version__

# Root CLI Help
_ROOT_HELP: Final[str] = """
 Usage: devops [OPTIONS] COMMAND [ARGS]...

 DevOps CLI — manage repos, SSH keys, Kubernetes, and more.

╭─ Options ─────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --version             -v        Show version and exit.                                                    │
│ --dry-run                       Show debug output of commands and AI requests without executing delegated │
│                                 subcommands or external write actions.                                    │
│ --install-completion            Install completion for the current shell.                                 │
│ --show-completion               Show completion for the current shell, to copy it or customize the        │
│                                 installation.                                                             │
│ --help                -h        Show this message and exit.                                               │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ────────────────────────────────────────────────────────────────────────────────────────────────╮
│ repos          Clone and manage repositories.                                                             │
│ ssh            SSH key generation, rotation, and GitHub registration.                                     │
│ branches       Branch management and Jira workflows.                                                     │
│ devcontainer   Manage devcontainer configurations.                                                        │
│ workspace      Manage VS Code workspace files.                                                            │
│ install-tools  Install DevOps tool binaries.                                                             │
│ k8s            Kubernetes resource management.                                                            │
│ kustomize      Kustomize operations.                                                                      │
│ docker         Docker image management.                                                                   │
│ grafana        Grafana dashboard and alert management.                                                    │
│ prometheus     Prometheus query and rule management.                                                      │
│ argo           Argo CD, Workflows, and Rollouts management.                                               │
│ config         Manage devops-cli configuration.                                                           │
│ ci             Run tests, linting, formatting, and type-checks.                                           │
│ uv             Run uv commands through devops.                                                            │
│ scan           Security, vulnerability, secret, and IaC scanner.                                          │
│ ai             Configure and test AI providers.                                                           │
│ review         AI-powered code reviews using expert personas.                                             │
│ mcp            FastMCP server for Model Context Protocol integration.                                     │
│ docs           Generate and validate CLI and API documentation.                                           │
│ release        Manage release cycles, version bumping, changelogs, and release verification.              │
│ pr             Manage GitHub pull requests and base branch targeting.                                     │
│ tf             OpenTofu and Terraform Infrastructure-as-Code operations.                                  │
│ tls            X.509 TLS certificate generation, inspection, verification, and Kubernetes secrets.        │
│ telemetry      OpenTelemetry observability, tracing, and metrics management.                              │
│ serve          FastAPI REST and OpenAPI service engine.                                                   │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────╯
"""

# Subcommand Help Templates
_SUBCOMMAND_HELPS: Final[dict[str, str]] = {
    "ai": """
 Usage: devops ai [OPTIONS] COMMAND [ARGS]...

 Configure and test AI providers (Ollama, Claude, Copilot/OpenAI).

╭─ Options ─────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help  -h        Show this message and exit.                                                             │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ────────────────────────────────────────────────────────────────────────────────────────────────╮
│ config         Show or update AI provider configuration.                                                  │
│ models         List available models for the configured provider.                                         │
│ preload        Preload configured model into VRAM across all configured Ollama servers.                   │
│ test           Send a test prompt to verify AI provider connectivity across configured servers.           │
│ agents         Generate LLM/Agent instruction files (AGENTS.md, CLAUDE.md, copilot-instructions.md).      │
│ chat           Start an interactive chat with a Pydantic AI persona (tools, thinking, streaming, RAG).    │
│ bundle-models  Bundle Ollama model metadata into tarball for air-gapped DevContainers.                    │
│ pipeline       Run a multi-agent Pydantic pipeline with shared DevOps tools and RAG context.              │
│ token-count    Calculate exact BPE tokens for text or files using tiktoken context budgeting.             │
│ route          Evaluate task complexity and determine the optimal LLM provider and model route.           │
│ review         AI-powered multi-persona code review system.                                               │
│ analyze        Analyze codebase metadata and generate structural outlines.                                │
│ rag            Manage RAG vector embeddings, indexing, and semantic search (Qdrant).                      │
│ benchmark      Benchmark, evaluate, and peer-grade candidate AI models across engineering tasks.          │
│ cache          Manage LLM response cache, performance metrics, and warm starting points.                  │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "repos": """
 Usage: devops repos [OPTIONS] COMMAND [ARGS]...

 Clone and manage repositories.

╭─ Options ─────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help  -h        Show this message and exit.                                                             │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ────────────────────────────────────────────────────────────────────────────────────────────────╮
│ clone          Clone a specific repository.                                                               │
│ clone-org      Clone all repositories belonging to a GitHub organization.                                 │
│ list           List cloned repositories and their git status.                                             │
│ sync           Synchronize all cloned repositories with their remotes.                                    │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "scan": """
 Usage: devops scan [OPTIONS] COMMAND [ARGS]...

 Security, vulnerability, secret, and IaC scanner.

╭─ Options ─────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help  -h        Show this message and exit.                                                             │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ────────────────────────────────────────────────────────────────────────────────────────────────╮
│ trivy          Run Aqua Trivy vulnerability, secret, misconfiguration, and IaC scanner.                   │
│ audit          Run pip/uv vulnerability audit on project dependencies.                                    │
│ semgrep        Run Semgrep static AST security and quality scanner.                                       │
│ sast           Alias for semgrep AST security scanning.                                                   │
│ gitleaks       Run Gitleaks sub-millisecond secret and credential pre-filter scanner.                     │
│ secrets        Alias for gitleaks secret scanning.                                                        │
│ checkov        Run Checkov IaC security and compliance scanner on Terraform/Kubernetes manifests.         │
│ iac            Alias for Checkov IaC security and compliance scanner.                                     │
│ all            Run comprehensive security scan suite.                                                     │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "tf": """
 Usage: devops tf [OPTIONS] COMMAND [ARGS]...

 OpenTofu and Terraform Infrastructure-as-Code operations.

╭─ Options ─────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help  -h        Show this message and exit.                                                             │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ────────────────────────────────────────────────────────────────────────────────────────────────╮
│ init           Initialize OpenTofu/Terraform working directory and download providers.                    │
│ plan           Generate and show an execution plan for infrastructure changes.                            │
│ apply          Create or update infrastructure according to configuration.                                │
│ destroy        Destroy managed infrastructure resources.                                                  │
│ output         Read an output variable from the state file.                                               │
│ validate       Validate the configuration files in a directory.                                           │
│ fmt            Format OpenTofu/Terraform configuration files to standard format.                          │
│ lint           Run TFLint static analysis for Terraform and cloud provider best practices.                │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
    "workspace": """
 Usage: devops workspace [OPTIONS] COMMAND [ARGS]...

 Manage VS Code workspace files.

╭─ Options ─────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help  -h        Show this message and exit.                                                             │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ────────────────────────────────────────────────────────────────────────────────────────────────╮
│ sync           Synchronize VS Code workspace file with all cloned repositories.                           │
│ add            Add a repository folder into the VS Code workspace file.                                  │
│ remove         Remove a repository folder from the VS Code workspace file.                              │
│ generate       Regenerate workspace file from all repositories in base directory.                         │
│ open           Open the workspace file in VS Code.                                                        │
│ clean          Prune stale review runs, temporary analysis caches, and traces under .data/.               │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────╯
""",
}


def is_help_requested(args: list[str]) -> bool:
    """Return True if the argument list represents a help query or standalone dry-run."""
    if not args:
        return True
    if len(args) == 1 and args[0] == "--dry-run":
        return True
    return any(a in ("-h", "--help") for a in args)


def is_version_requested(args: list[str]) -> bool:
    """Return True if the argument list represents a version query."""
    return len(args) == 1 and args[0] in ("-v", "--version")


def get_help_text(args: list[str]) -> str | None:
    """Return pre-rendered help text if available for the given CLI arguments."""
    if not args or (len(args) == 1 and args[0] in ("-h", "--help", "--dry-run")):
        return _ROOT_HELP

    # Check for subcommand help (e.g. devops ai --help or devops --help ai)
    non_flags = [a for a in args if not a.startswith("-")]
    if non_flags:
        subcmd = non_flags[0]
        if subcmd in _SUBCOMMAND_HELPS and any(a in ("-h", "--help") for a in args):
            return _SUBCOMMAND_HELPS[subcmd]

    return None


def show_help(args: list[str]) -> bool:
    """Print help text to stdout and return True if handled."""
    text = get_help_text(args)
    if text is not None:
        sys.stdout.write(text + "\n")
        return True
    return False


def show_version() -> None:
    """Print version to stdout."""
    sys.stdout.write(f"devops-cli {__version__}\n")
