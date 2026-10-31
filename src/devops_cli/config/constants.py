"""Non-configurable constants used across the CLI."""

from __future__ import annotations

import ipaddress
import json
import re
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from pydantic_ai.messages import FinishReason

# ── Application & Configuration ───────────────────────────────────────────────
CONST_APP_NAME = "devops-cli"
CONST_HELP_OPTION_NAMES = ("-h", "--help")
CONST_CONFIG_DIR = Path.home() / ".config" / CONST_APP_NAME
CONST_CONFIG_PATH = CONST_CONFIG_DIR / "config.yaml"
# Where a relative data path resolves while a command reads a tree it does not own, such as a
# review, in place of the main worktree of the repository it starts in, unless that is
# devops-cli's own repository (#972); and where review data resolves for every command started
# outside that repository. The default data directory is then `~/.local/share/devops-cli/.data`.
CONST_USER_DATA_ROOT = Path.home() / ".local" / "share" / CONST_APP_NAME
CONST_KEYRING_SERVICE = CONST_APP_NAME
# An entry never stored: looking it up tells a locked keyring from an unlocked one, reading no
# secret (`require_persistent_keyring`).
CONST_KEYRING_UNLOCK_PROBE_KEY = "keyring-unlock-probe"
# The most `devops config set <key> --from-file` reads into the keyring. A 4096-bit RSA private key
# in PEM is about 3.3 KiB, so a key with its certificate chain fits; a wrong path to a large file
# is refused after this many bytes, not read whole (#1649).
CONST_SECRET_FILE_MAX_BYTES: Final[int] = 64 * 1024
CONST_PROJECT_CONFIG_FILENAME = "config.yaml"
CONST_PROJECT_CONFIG_CANDIDATES: Final[tuple[str, ...]] = (
    CONST_PROJECT_CONFIG_FILENAME,
    f".devcontainer/{CONST_PROJECT_CONFIG_FILENAME}",
    f".devops/{CONST_PROJECT_CONFIG_FILENAME}",
    ".devops.yaml",
    ".devcontainer/.devops.yaml",
)
# A write that changes a config file first copies it beside itself as `<name>.bak-<UTC stamp>`,
# and keeps the newest of these copies, so a person can restore what a write replaced (#1921).
CONST_CONFIG_BACKUP_INFIX: Final[str] = ".bak-"
CONST_CONFIG_BACKUP_STAMP_FORMAT: Final[str] = "%Y%m%d-%H%M%S"
CONST_CONFIG_BACKUPS_KEPT: Final[int] = 10
# The value that a copy of a config file shows for a credential that a removal took out of the file
# (#2645). A person sees that a value was there, and the copy does not hold it.
CONST_CONFIG_REDACTED_VALUE: Final[str] = "***REDACTED***"
# The `action` of the audit record that each write of a config file appends (#1921).
CONST_AUDIT_ACTION_CONFIG_WRITE: Final[str] = "config_write"
# The command that removes a key from the active config file without a load of the settings, and
# that the error of a key a settings section refuses names (#2201).
CONST_CONFIG_UNSET_COMMAND: Final[str] = "devops config unset"
# The type of the pydantic error for a key that a section with `extra="forbid"` does not declare.
CONST_PYDANTIC_EXTRA_FORBIDDEN: Final[str] = "extra_forbidden"
# The release that removed each settings key, by its dotted key, so the error of a config file that
# still holds the key names the release. A key goes here only when the changelog of the release
# names its removal (#2201).
CONST_REMOVED_CONFIG_KEYS: Final[dict[str, str]] = {"ai.vllm_url": "0.2.34"}
# The per-model sampling and serving settings. They belong in a gateway deployment's
# `litellm_params` or in the Ollama tag, not in a section of the settings (#1070).
CONST_AI_SERVING_SETTINGS: Final[frozenset[str]] = frozenset(
    {"top_k", "min_p", "presence_penalty", "repeat_penalty", "think", "keep_alive"}
)
CONST_SETTINGS_SECTION_METADATA: Final[dict[str, tuple[str, str]]] = {
    "github": (
        "GitHub Configuration (`github`)",
        "GitHub authentication, default owner, and repository settings.",
    ),
    "ssh": (
        "SSH Configuration (`ssh`)",
        "SSH key generation, rotation, signing, and GitHub registration settings.",
    ),
    "repos": (
        "Repositories Configuration (`repos`)",
        "Multi-repository workspace discovery, cloning, and sync settings.",
    ),
    "workspace": (
        "Workspace Configuration (`workspace`)",
        "Multi-root VS Code workspace file management and data tier settings.",
    ),
    "grafana": (
        "Grafana Configuration (`grafana`)",
        "Grafana endpoint, authentication, and service addressing settings.",
    ),
    "prometheus": (
        "Prometheus Configuration (`prometheus`)",
        "Prometheus query endpoint, authentication, and service addressing settings.",
    ),
    "argocd": (
        "Argo CD Configuration (`argocd`)",
        "Argo CD server endpoint, authentication, TLS, and service addressing settings.",
    ),
    "qdrant": (
        "Qdrant Vector Store (`qdrant`)",
        "The vector store that RAG searches query and indexing writes to.",
    ),
    "valkey": (
        "Valkey Configuration (`valkey`)",
        "Valkey caching endpoint, authentication, TLS, and service addressing settings.",
    ),
    "runs": (
        "Shared Run Index (`runs`)",
        "PostgreSQL connection settings for the shared AI run index.",
    ),
    "tempo": (
        "Tempo Configuration (`tempo`)",
        "Grafana Tempo distributed tracing query endpoint and service addressing settings.",
    ),
    "pyroscope": (
        "Pyroscope Configuration (`pyroscope`)",
        "Grafana Pyroscope continuous profiling endpoint and service addressing settings.",
    ),
    "telemetry": (
        "Telemetry & Metrics (`telemetry`)",
        "OpenTelemetry export and Logfire settings.",
    ),
    "k8s": (
        "Kubernetes Configuration (`k8s`)",
        "Kubernetes context, ingress domain, and service addressing settings.",
    ),
    "cloudflare": (
        "Cloudflare Configuration (`cloudflare`)",
        "Cloudflare API token and zone settings.",
    ),
    "sandbox": (
        "Sandbox Configuration (`sandbox`)",
        "Isolated container sandbox runtime, resource limits, and network policy settings.",
    ),
    "ci": (
        "CI Gate Configuration (`ci`)",
        "Limit on how many CPU-heavy `devops ci` gates run at once on one host.",
    ),
    "ai": (
        "AI & LLM Configuration (`ai`)",
        "AI code review, multi-agent pipelines, RAG semantic search, and embeddings.",
    ),
    "open_webui": (
        "Open WebUI Configuration (`open_webui`)",
        "Open WebUI endpoint, authentication, and service addressing settings.",
    ),
    "data": (
        "Data Storage Tier (`data`)",
        "Local artifact caches, review findings, session histories, and log paths.",
    ),
    "service": (
        "Service Configuration (`service`)",
        "In-cluster webhook receiver and background job runner settings.",
    ),
    "firecrawl": (
        "Firecrawl Configuration (`firecrawl`)",
        "Firecrawl web search API authentication settings.",
    ),
}
CONST_DOMAIN_EXCEPTION_MODULES: Final[tuple[str, ...]] = (
    "devops_cli.ai.agents.testing",
    "devops_cli.ai.client.models",
    "devops_cli.ai.gateway_tune",
    "devops_cli.ai.pool_load",
    "devops_cli.ai.rag.embeddings",
    "devops_cli.ai.rag.qdrant",
    "devops_cli.ai.run_store",
    "devops_cli.core.templating",
    "devops_cli.github.ssh",
    "devops_cli.http.client",
    "devops_cli.k8s.node_port",
    "devops_cli.k8s.service_proxy",
    "devops_cli.review.state",
    "devops_cli.telemetry.context",
    "devops_cli.telemetry.memory_profiler",
)
CONST_PROJECT_CONFIG_ENV = "DEVOPS_CLI_CONFIG"  # absolute path overrides CWD lookup
# A configuration file is only eligible for caching once it has been still for this
# long. The kernel stamps files from a coarse clock, so a file rewritten moments after
# it was parsed can carry the identical modification time and size as the copy already
# held, and a cache trusting that stamp would keep serving the superseded values.
CONST_SETTINGS_CACHE_SETTLE_SECONDS: Final[float] = 2.0
CONST_VSCODE_WORKSPACE_FILE = Path(".code-workspace")
CONST_VSCODE_CLI = "code"
CONST_AGENTS_MD_FILENAME = "AGENTS.md"
# AGENTS.md is a router: the rules every task needs and a table of the documents that own the
# rest (#1961). Every agent reads it in full at the start of each session, so it stays short.
CONST_AGENTS_MD_MAX_CHARS: Final[int] = 6_500
# The documents a generated AGENTS.md can route to, each with the kind of task it owns, in the
# order of its table. `devops ai agents` writes a row only for a path that exists in the target.
CONST_AGENTS_MD_ROUTES: Final[tuple[tuple[str, str], ...]] = (
    ("README.md", "learn what the project does and how to run it"),
    ("CONTRIBUTING.md", "set up, name a branch, write a pull request title, run one check"),
    ("docs/TESTING.md", "write or change a test"),
    ("ARCHITECTURE.md", "change the structure of the code"),
    ("SECURITY.md", "handle secrets, network egress or a vulnerability report"),
    ("CONTEXT.md", "use a project term"),
    ("docs/adr/", "need the reason for a decision"),
    ("openspec/config.yaml", "plan and record each item as an OpenSpec change"),
    (".github/ISSUE_TEMPLATE/", "file an issue"),
    (".github/pull_request_template.md", "write a pull request body"),
    (".devops/review.toml", "suppress a review finding"),
    ("k8s/README.md", "change a manifest or the cluster"),
)
CONST_PYPROJECT_FILENAME = "pyproject.toml"
CONST_UV_LOCK_FILENAME = "uv.lock"
# The two files `npm ci` installs a Node tool from: the manifest naming its one dependency at an
# exact version, and the lockfile that records the sha512 of every package that version needs.
CONST_NPM_PROJECT_FILES: Final[tuple[str, ...]] = ("package.json", "package-lock.json")
# Where the tools lock and its Node tools' directories sit in a checkout, from its root.
CONST_TOOLS_LOCK_REPO_DIR: Final[str] = "src/devops_cli/tools_lock"
CONST_PRE_COMMIT_CONFIG_FILENAME = ".pre-commit-config.yaml"
# The pre-commit stage of the hooks that run on `git push`.
CONST_PRE_COMMIT_PRE_PUSH_STAGE: Final[str] = "pre-push"
CONST_CHANGELOG_FILENAME = "CHANGELOG.md"
CONST_CURRENT_DIR = Path(".")
CONST_ROOT_DIR = Path("/")
CONST_DOCS_DIR_NAME = "docs"
CONST_DOCS_DIR_PATH = Path(CONST_DOCS_DIR_NAME)
CONST_VSCODE_DIR_NAME = ".vscode"
CONST_MCP_JSON_NAME = "mcp.json"
# Claude Code reads project-scoped MCP servers from `.mcp.json` at the repository root.
# VS Code's own MCP support reads `.vscode/mcp.json`, and the two are not interchangeable:
# `${workspaceFolder}` is a VS Code substitution that Claude Code does not expand, so a
# copy of the VS Code file would hand the server a literal `${workspaceFolder}` on PATH.
CONST_CLAUDE_MCP_JSON_NAME = ".mcp.json"
# Kilo Code reads project-scoped MCP servers from `kilo.jsonc` at the repository root. It reads
# neither `.mcp.json` nor `.vscode/mcp.json`, and `.kilo/kilo.jsonc` is left out of git.
CONST_KILO_CONFIG_NAME = "kilo.jsonc"
CONST_MCP_EAGER_DOMAINS: Final[frozenset[str]] = frozenset({"ai", "review", "config", "workspace"})
CONST_MCP_LAZY_DOMAINS: Final[frozenset[str]] = frozenset(
    {
        "argo",
        "benchmark",
        "branches",
        "ci",
        "docker",
        "docs",
        "gh",
        "grafana",
        "k8s",
        "pr",
        "prometheus",
        "rag",
        "repos",
        "roadmap",
        "sandbox",
        "scan",
        "security",
        "ssh",
        "telemetry",
        "tf",
        "tls",
        "valkey",
        "vault",
        "verify",
    }
)
CONST_MCP_DOMAINS: Final[frozenset[str]] = frozenset(
    CONST_MCP_EAGER_DOMAINS | CONST_MCP_LAZY_DOMAINS | {"github", "secrets", "benchmarks"}
)
# Command exposure table: (command_path, timeout_seconds, read_only, format_json)
CONST_MCP_EXPOSURE_TABLE: Final[tuple[tuple[tuple[str, ...], float, bool, bool], ...]] = (
    (("ai", "ast", "graph"), 60.0, True, False),
    (("ai", "ast", "parse"), 60.0, True, True),
    (("ai", "benchmark"), 300.0, True, False),
    (("ai", "chaos-model"), 300.0, False, False),
    (("ai", "constellation"), 30.0, True, True),
    (("ai", "cost", "report"), 30.0, True, True),
    (("ai", "diagram"), 60.0, True, False),
    (("ai", "failover"), 60.0, True, False),
    (("ai", "gateway", "failover"), 30.0, True, True),
    (("ai", "gateway", "probe-backend"), 30.0, True, True),
    (("ai", "gateway", "routes"), 30.0, True, True),
    (("ai", "gateway", "status"), 30.0, True, True),
    (("ai", "harness", "offload"), 60.0, True, False),
    (("ai", "harness", "status"), 30.0, True, False),
    (("ai", "ingest", "library"), 300.0, True, True),
    (("ai", "ingest", "query-library"), 60.0, True, True),
    (("ai", "pack-context"), 60.0, True, True),
    (("ai", "prewarm"), 600.0, False, False),
    (("ai", "quiesce"), 60.0, True, False),
    (("ai", "rag", "drift"), 60.0, False, True),
    (("ai", "rag", "index"), 300.0, False, False),
    (("ai", "rag", "query"), 60.0, True, False),
    (("ai", "read"), 60.0, True, False),
    (("ai", "repomap"), 60.0, True, False),
    (("ai", "resume"), 60.0, True, False),
    (("ai", "test-gen"), 300.0, True, False),
    (("argo", "cd", "apps", "list"), 30.0, True, False),
    (("argo", "cd", "apps", "status"), 30.0, True, False),
    (("argo", "fleet", "sync"), 300.0, False, True),
    (("argo", "rollouts", "analyze"), 300.0, False, True),
    (("branches", "list"), 60.0, True, False),
    (("ci",), 360.0, True, False),
    (("config", "audit-keys"), 30.0, True, False),
    (("config", "output"), 30.0, True, True),
    (("config", "show"), 30.0, True, False),
    (("docker", "images"), 30.0, True, False),
    (("docker", "sandbox"), 300.0, False, False),
    (("docker", "sign"), 300.0, False, False),
    (("docker", "verify"), 300.0, True, False),
    (("gh", "issues", "close"), 60.0, False, False),
    (("gh", "issues", "create"), 60.0, False, False),
    (("gh", "issues", "edit"), 60.0, False, False),
    (("gh", "issues", "list"), 60.0, True, False),
    (("gh", "issues", "status"), 60.0, True, False),
    (("gh", "issues", "triage"), 60.0, True, False),
    (("gh", "issues", "view"), 60.0, True, False),
    (("gh", "labels", "list"), 60.0, True, False),
    (("gh", "labels", "sync"), 300.0, False, False),
    (("gh", "milestones", "close"), 60.0, False, False),
    (("gh", "milestones", "edit"), 60.0, False, False),
    (("gh", "milestones", "list"), 60.0, True, False),
    (("gh", "pages", "build"), 60.0, False, False),
    (("gh", "pages", "status"), 60.0, True, False),
    (("gh", "pages", "verify"), 30.0, True, False),
    (("gh", "project", "audit"), 60.0, True, False),
    (("gh", "project", "list"), 60.0, True, False),
    (("gh", "project", "reconcile"), 60.0, False, False),
    (("gh", "project", "status"), 30.0, True, False),
    (("gh", "project", "sync"), 300.0, False, False),
    (("gh", "rate-limit"), 60.0, True, False),
    (("gh", "runs", "list"), 60.0, True, False),
    (("gh", "runs", "view"), 60.0, True, False),
    (("gh", "views", "audit"), 60.0, True, False),
    (("gh", "views", "spec"), 30.0, True, False),
    (("gh", "views", "sync"), 300.0, False, False),
    (("grafana", "dashboards", "list"), 30.0, True, False),
    (("k8s", "audit"), 60.0, True, False),
    (("k8s", "bootstrap"), 360.0, False, False),
    (("k8s", "chaos"), 300.0, False, False),
    (("k8s", "create-tls-secret"), 60.0, False, False),
    (("k8s", "deploy-stack"), 360.0, False, False),
    (("k8s", "diff-helm"), 60.0, True, False),
    # `--stack gitea` makes a temporary repository in Gitea and deletes it (#2187).
    (("k8s", "doctor"), 60.0, False, True),
    (("k8s", "enable-tls"), 60.0, False, False),
    (("k8s", "lint"), 60.0, True, False),
    (("k8s", "logs"), 300.0, True, True),
    (("k8s", "pods"), 30.0, True, False),
    (("k8s", "security-stream"), 60.0, True, True),
    (("k8s", "status"), 60.0, True, False),
    (("k8s", "teardown-stack"), 180.0, False, False),
    (("k8s", "validate"), 60.0, True, False),
    (("pr", "check-readiness"), 60.0, True, False),
    (("pr", "checks"), 60.0, True, False),
    (("pr", "close"), 60.0, False, False),
    (("pr", "diff"), 60.0, True, False),
    (("pr", "edit"), 60.0, False, False),
    (("pr", "list"), 60.0, True, False),
    (("pr", "monitor"), 210.0, True, False),
    (("pr", "ready"), 180.0, False, False),
    (("pr", "threads", "list"), 60.0, True, False),
    (("pr", "threads", "reply"), 60.0, False, False),
    (("pr", "threads", "resolve"), 60.0, False, False),
    (("pr", "update"), 60.0, False, False),
    (("prometheus", "query"), 30.0, True, False),
    (("repos", "list"), 30.0, True, False),
    (("repos", "sync"), 120.0, False, False),
    (("review", "branch"), 300.0, True, False),
    (("review", "export-feedback"), 60.0, True, False),
    (("review", "findings"), 60.0, True, False),
    (("review", "path"), 300.0, True, False),
    (("review", "pr"), 300.0, False, False),
    (("review", "stats"), 60.0, True, False),
    (("roadmap", "intake"), 300.0, False, False),
    (("roadmap", "refine"), 300.0, True, False),
    (("roadmap", "run"), 300.0, True, False),
    (("sandbox", "deploy"), 300.0, False, False),
    (("sandbox", "exec"), 300.0, False, False),
    (("sandbox", "network-policy"), 300.0, True, False),
    (("sandbox", "status"), 30.0, True, True),
    (("sandbox", "stop"), 60.0, False, False),
    (("scan", "aibom"), 60.0, True, False),
    (("scan", "complexity"), 60.0, True, False),
    (("scan", "fix"), 300.0, False, False),
    (("scan", "injection"), 60.0, True, False),
    (("scan", "sast"), 300.0, True, False),
    (("scan", "sbom"), 60.0, True, False),
    (("scan", "secrets"), 300.0, True, False),
    (("scan", "trivy"), 300.0, True, False),
    (("ssh", "audit"), 30.0, True, False),
    (("ssh", "status"), 30.0, True, False),
    (("telemetry", "logfire"), 30.0, True, False),
    (("telemetry", "profile"), 60.0, True, False),
    (("telemetry", "status"), 30.0, True, False),
    (("telemetry", "test"), 30.0, False, False),
    (("tf", "apply"), 600.0, False, False),
    (("tf", "cost", "breakdown"), 300.0, True, True),
    (("tf", "notify-plan"), 60.0, True, False),
    (("tf", "output"), 30.0, True, False),
    (("tf", "plan"), 300.0, True, False),
    (("tls", "ca"), 30.0, False, False),
    (("tls", "cert"), 30.0, False, False),
    (("tls", "inspect"), 30.0, True, False),
    (("valkey", "flush"), 30.0, False, False),
    (("valkey", "get"), 30.0, True, False),
    (("valkey", "info"), 30.0, True, False),
    (("valkey", "ping"), 30.0, True, False),
    (("valkey", "set"), 30.0, False, False),
    (("valkey", "stats"), 30.0, True, False),
    (("vault", "get"), 60.0, True, False),
    (("vault", "set"), 60.0, False, False),
    (("vault", "status"), 30.0, True, False),
    (("vault", "sync"), 60.0, False, False),
)

# The argv heads that run the devops CLI, directly or through `uv run`. `devops docs check`
# resolves every list literal under src/devops_cli that starts with one (#868). Such a list
# spells the command word as a quoted literal in one of Python's two quote characters, so a
# module holding neither spelling is not parsed.
CONST_DEVOPS_ARGV_PREFIXES: Final[tuple[tuple[str, ...], ...]] = (
    ("devops",),
    ("uv", "run", "devops"),
)
CONST_DEVOPS_ARGV_QUOTED_COMMAND: Final[tuple[str, ...]] = ('"devops"', "'devops'")
# Well-known placeholder tokens in the documented command lines checked for argv resolution (#921).
CONST_DOCS_ARGV_KNOWN_PLACEHOLDERS: Final[frozenset[str]] = frozenset(
    {"...", "COMMAND", "ARGS", "OPTIONS", "SUBCOMMAND", "PARAMS"}
)
# The documentation inventory (#1103): every Markdown file in the repository matches the globs of
# exactly one class, so a new document is classified in the pull request that adds it. The classes
# differ in how a document stays true:
# - generated: written by `DocGenerator` or the instruction generator and checked against them.
# - tool-owned: written only by one tool's own step, release-please for `CHANGELOG.md` in its
#   release pull request and `openspec archive` for the specs in the pull request that closes a
#   change, and by no other pull request.
# - record: history, never rewritten to match later code, so no command name in it is checked.
# - prompt: loaded by code at run time.
# - tool-generated: written by a pinned tool, `devops openspec regenerate` for OpenSpec's skills, and
#   checked by regenerating them, never named-checked.
# - hand-written: everything else, listed by path (README.md also holds a generated command matrix).
# An entry with a glob wildcard is a pattern and may match no file (`openspec/specs/**/*.md`
# matches none until the first change is archived); an entry without one names a document and
# must match its file.
CONST_DOCS_CLASS_GENERATED: Final[str] = "generated"
CONST_DOCS_CLASS_TOOL_OWNED: Final[str] = "tool-owned"
CONST_DOCS_CLASS_RECORD: Final[str] = "record"
CONST_DOCS_CLASS_PROMPT: Final[str] = "prompt"
CONST_DOCS_CLASS_TOOL_GENERATED: Final[str] = "tool-generated"
CONST_DOCS_CLASS_HAND_WRITTEN: Final[str] = "hand-written"
CONST_DOCS_INVENTORY: Final[dict[str, tuple[str, ...]]] = {
    CONST_DOCS_CLASS_GENERATED: (
        "CLAUDE.md",
        "GEMINI.md",
        ".github/copilot-instructions.md",
        "docs/CLI_REFERENCE.md",
        "docs/CONFIGURATION.md",
        "docs/ENV_VARS.md",
        "docs/ERRORS.md",
        "docs/KNOWLEDGE_BASE.md",
        "docs/MCP_TOOLS.md",
        "docs/TELEMETRY.md",
        "docs/commands/*.md",
    ),
    CONST_DOCS_CLASS_TOOL_OWNED: (
        "CHANGELOG.md",
        "openspec/specs/**/*.md",
    ),
    CONST_DOCS_CLASS_RECORD: (
        "docs/adr/*.md",
        "docs/agent/archive/**/*.md",
        "openspec/changes/**/*.md",
    ),
    CONST_DOCS_CLASS_PROMPT: (
        "src/devops_cli/ai/personas/**/*.md",
        "src/devops_cli/ai/prompts/**/*.md",
        "src/devops_cli/ai/tasks/**/*.md",
    ),
    CONST_DOCS_CLASS_TOOL_GENERATED: (
        ".claude/skills/openspec-*/SKILL.md",
        ".agents/skills/openspec-*/SKILL.md",
        ".kilocode/skills/openspec-*/SKILL.md",
    ),
    CONST_DOCS_CLASS_HAND_WRITTEN: (
        ".github/pull_request_template.md",
        "AGENTS.md",
        "ARCHITECTURE.md",
        "CONTEXT.md",
        "CONTRIBUTING.md",
        "README.md",
        "RELEASE_CYCLE.md",
        "SECURITY.md",
        "docs/DEVCONTAINER_USAGE.md",
        "docs/KNOWN_ISSUES.md",
        "docs/ROADMAP_WORKFLOW.md",
        "docs/ROUTINE_TASKS.md",
        "docs/SDLC.md",
        "docs/SELF_IMPROVEMENT.md",
        "docs/TESTING.md",
        "docs/VISION.md",
        "docs/agent/README.md",
        "docs/index.md",
        "k8s/**/README.md",
        "src/devops_cli/ai/knowledge_base/**/*.md",
        "tf/README.md",
    ),
}
# The classes whose `devops` command lines `devops docs check` resolves against the live command
# tree: the documents a reader or a model follows, which must name commands that exist.
CONST_DOCS_NAME_CHECKED_CLASSES: Final[tuple[str, ...]] = (
    CONST_DOCS_CLASS_PROMPT,
    CONST_DOCS_CLASS_HAND_WRITTEN,
)
# The list methods that add tokens to a `devops` argv built up in a variable.
CONST_ARGV_EXTENDING_METHODS: Final[frozenset[str]] = frozenset({"append", "extend"})
# Bound on the length of command output returned to an MCP client.
CONST_MCP_MAX_COMMAND_OUTPUT_CHARS: Final[int] = 4000
# Name of the thread that runs an in-process MCP command. A command that passes its timeout
# leaves this thread running, and the test floor waits for it by name (#2277).
CONST_MCP_DISPATCH_THREAD_NAME: Final[str] = "devops-mcp-dispatch"
# The class of mistake a refused MCP tool argument is reported as, so a model can correct the
# call in one turn (#862).
CONST_ARGUMENT_HALLUCINATED: Final[str] = "HALLUCINATED_PARAM"
CONST_ARGUMENT_MISSING: Final[str] = "MISSING_PARAM"
CONST_ARGUMENT_TYPE_MISMATCH: Final[str] = "TYPE_MISMATCH"
CONST_ARGUMENT_INVALID_CHOICE: Final[str] = "INVALID_CHOICE"
CONST_ARGUMENT_OUT_OF_RANGE: Final[str] = "OUT_OF_RANGE"
CONST_ARGUMENT_CONSTRAINT_VIOLATION: Final[str] = "CONSTRAINT_VIOLATION"
# The JSON Schema keyword that refused an argument, by the class of mistake it signals. It
# covers every keyword the current tool registry publishes, which a test holds it to; a
# keyword outside it is still a refusal, reported as a constraint violation.
CONST_JSON_SCHEMA_VIOLATION_KINDS: Final[dict[str, str]] = {
    "additionalProperties": CONST_ARGUMENT_HALLUCINATED,
    "required": CONST_ARGUMENT_MISSING,
    "type": CONST_ARGUMENT_TYPE_MISMATCH,
    "anyOf": CONST_ARGUMENT_TYPE_MISMATCH,
    "oneOf": CONST_ARGUMENT_TYPE_MISMATCH,
    "enum": CONST_ARGUMENT_INVALID_CHOICE,
    "const": CONST_ARGUMENT_INVALID_CHOICE,
    "minimum": CONST_ARGUMENT_OUT_OF_RANGE,
    "maximum": CONST_ARGUMENT_OUT_OF_RANGE,
    "exclusiveMinimum": CONST_ARGUMENT_OUT_OF_RANGE,
    "exclusiveMaximum": CONST_ARGUMENT_OUT_OF_RANGE,
    "minLength": CONST_ARGUMENT_OUT_OF_RANGE,
    "maxLength": CONST_ARGUMENT_OUT_OF_RANGE,
    "minItems": CONST_ARGUMENT_OUT_OF_RANGE,
    "maxItems": CONST_ARGUMENT_OUT_OF_RANGE,
}
# The pydantic error type that refused an argument the published schema allowed, such as a
# strict PR number's `1.0` were the schema check bypassed. Its type errors cover the six JSON
# value types.
CONST_PYDANTIC_VIOLATION_KINDS: Final[dict[str, str]] = {
    "unexpected_keyword_argument": CONST_ARGUMENT_HALLUCINATED,
    "missing_argument": CONST_ARGUMENT_MISSING,
    "dict_type": CONST_ARGUMENT_TYPE_MISMATCH,
    "list_type": CONST_ARGUMENT_TYPE_MISMATCH,
    "string_type": CONST_ARGUMENT_TYPE_MISMATCH,
    "int_type": CONST_ARGUMENT_TYPE_MISMATCH,
    "float_type": CONST_ARGUMENT_TYPE_MISMATCH,
    "bool_type": CONST_ARGUMENT_TYPE_MISMATCH,
    "none_required": CONST_ARGUMENT_TYPE_MISMATCH,
}
# How each bound a JSON Schema can publish reads after the type it bounds: "integer >= 1".
CONST_JSON_SCHEMA_BOUND_PHRASES: Final[dict[str, str]] = {
    "minimum": ">= {}",
    "maximum": "<= {}",
    "exclusiveMinimum": "> {}",
    "exclusiveMaximum": "< {}",
    "minLength": "of length >= {}",
    "maxLength": "of length <= {}",
    "minItems": "of size >= {}",
    "maxItems": "of size <= {}",
}
# An undeclared parameter's name is the caller's own text, so a refusal echoes only a masked
# prefix of it this long.
CONST_MCP_UNDECLARED_PARAMETER_ECHO_LENGTH: Final[int] = 64
# FastMCP logs each tool call's and prompt request's arguments at DEBUG on this logger, and the
# log keeps CONST_REDACTED_LOG_VALUE in their place (#899).
CONST_FASTMCP_OPERATIONS_LOGGER: Final[str] = "fastmcp.server.mixins.mcp_operations"
CONST_REDACTED_LOG_VALUE: Final[str] = "<redacted>"
# Root commands whose module app takes the command's own name as its first argument:
CONST_CLI_ROOT_LEVEL_COMMANDS: Final[frozenset[str]] = frozenset({"format", "lint"})
# The command words that run a `devops review` command, which reads a tree devops-cli does not
# own: the root command enters that rule before it opens the command's span and so builds the
# process's tracer, whose endpoint a project config could otherwise name (#972).
CONST_REVIEW_COMMAND_WORDS: Final[frozenset[tuple[str, ...]]] = frozenset(
    {("review",), ("ai", "review")}
)
# The word a devops-cli command line starts with, and the module behind it: the `devops`
# script calls `devops_cli.entry:main`. `telemetry profile` runs only a command line starting
# with that word, as `python -P -m` that module under the running interpreter; `-P` keeps the
# working directory off `sys.path`, which plain `-m` puts first (#980).
CONST_DEVOPS_CLI_COMMAND: Final[str] = "devops"
CONST_DEVOPS_CLI_ENTRY_MODULE: Final[str] = "devops_cli.entry"
CONST_SYSTEM_TEMP_DIRS: tuple[Path, ...] = (Path("/tmp"), Path("/var/tmp"))  # nosec B108 # names the shared temp directories to refuse them; nothing writes here
CONST_FORBIDDEN_SYSTEM_DIRS: tuple[Path, ...] = (
    Path("/etc"),
    Path("/usr"),
    Path("/bin"),
    Path("/sbin"),
    Path("/var"),
    Path("/sys"),
    Path("/proc"),
)

# ── Data Directories & Artifact Paths ─────────────────────────────────────────
CONST_ANALYSIS_DIR_NAME = "analysis"
CONST_REVIEWS_DIR_NAME = "reviews"
CONST_LOGS_DIR_NAME = "logs"
CONST_MODELS_DIR_NAME = "models"
CONST_CACHE_DIR_NAME = "cache"
CONST_CI_CACHE_FILENAME = "ci_cache.json"
CONST_COVERAGE_INDEX_FILENAME = "coverage_index.json"
# Library contracts, under the data directory: the only place they are written and read (#972).
CONST_LIBRARIES_DIR_NAME = "libraries"
# The config and ignore files a review's static scanners are handed in place of any in their
# working directory or the scanned tree (#972). Each keeps the scanner's defaults: Trivy's
# defaults, Gitleaks' default rules, and Bandit's defaults with no `[bandit]` option. The ignore
# files they are handed are empty. kube-linter's config is in `devops_cli.security.kubelinter`.
CONST_REVIEW_SCAN_TRIVY_CONFIG = "{}\n"
CONST_REVIEW_SCAN_GITLEAKS_CONFIG = "[extend]\nuseDefault = true\n"
CONST_REVIEW_SCAN_BANDIT_INI = "[bandit]\n"
# The `group` that Popeye 0.22 writes for an issue of the resource itself, not of one of its
# containers: `__root__`, or empty for an issue that it measured (#1434).
CONST_POPEYE_RESOURCE_GROUPS: Final[frozenset[str]] = frozenset({"", "__root__"})
# The prefix of the empty directory that a Popeye scan starts in (#2132).
CONST_POPEYE_SCAN_DIR_PREFIX: Final[str] = "devops-scan-popeye-"
CONST_REVIEW_SCAN_GOLANGCI_LINT_CONFIG: Final[str] = (
    "linters:\n"
    "  disable-all: true\n"
    "  enable:\n"
    "    - errcheck\n"
    "    - govet\n"
    "    - staticcheck\n"
    "linters-settings:\n"
    "  govet:\n"
    "    enable:\n"
    "      - lostcancel\n"
)
# Bandit's project file. This repository's names the targets `devops ci security` and an
# unisolated `devops scan report` of the tree both scan; a review hands Bandit an empty one in
# its place (#972).
CONST_BANDIT_INI_NAME: Final[str] = ".bandit"
# Every status a scan outcome can have, most severe first: outcomes merged into one, such as a
# scanner's per-file or per-batch runs, report the worst status any of them had.
CONST_SCAN_STATUS_PRECEDENCE: Final[tuple[str, ...]] = (
    "failed",
    "coverage_gap",
    "unavailable",
    "not installed",
    "dry-run",
    "built-in patterns",
    "ran",
    "not_applicable",
)
# The statuses of a scan that gave no result: its tool is not installed, it failed, or it does not
# apply to the target. Such a scan says nothing about the target, so no reply or report of one
# calls the target clean (#1435).
CONST_SCAN_NO_RESULT_STATUSES: Final[frozenset[str]] = frozenset(
    {"unavailable", "not installed", "failed", "not_applicable"}
)
# The word that the reply of an agent scan tool gives a scan status (#1435). A scan that ran is
# `ok`, and a tool that no directory of PATH holds is `not installed`, whichever adapter found it
# missing. Every other status, such as `failed`, `not_applicable` or `coverage_gap`, keeps its name.
CONST_AGENT_SCAN_STATUS_WORDS: Final[dict[str, str]] = {
    "ran": "ok",
    "clean": "ok",
    "unavailable": "not installed",
}
# Click context meta key the `devops ci` group sets when a subcommand only prints its help,
# so the gate does not announce the root it would check.
CONST_CI_SUBCOMMAND_SHOWS_HELP_META_KEY: Final[str] = "devops_cli.ci.subcommand_shows_help"
# A check that averages more than 5 minutes is a P0 bug (AGENTS.md rule 5), so the test step must
# stay inside this budget; past it, the gate names the slowest tests from a pytest durations report
# of this many entries.
CONST_CI_TEST_BUDGET_SECONDS: Final[float] = 300.0
CONST_CI_SLOWEST_TESTS_SHOWN: Final[int] = 10
# The job of `ci.yml` that runs the test row: `devops ci job-time` reads the time of this job from
# its last runs (#2699), so the budget above is checked on the runs of the runner and not on the
# one run of a pull request.
CONST_CI_TEST_JOB_NAME: Final[str] = "Tests & Coverage"
# `devops ci` gate slots (#2336): a directory directly under the data directory, outside the
# subdirectories that `devops workspace clean` prunes, holds one lock file for each slot.
CONST_CI_GATE_SLOTS_DIRNAME: Final[str] = "ci-gate-slots"
CONST_CI_GATE_SLOT_FILENAME: Final[str] = "slot-{index}.lock"
# The branch form `<type>/<issue>-<slug>` (CONTRIBUTING.md, Naming). The types are those of
# `release-please-config.json`, and the form is the one the `branch-name` pre-commit hook accepts;
# `tests/test_branch_form.py` fails when either disagrees with these (#2337).
CONST_BRANCH_TYPES: Final[tuple[str, ...]] = (
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "docs",
    "test",
    "build",
    "ci",
    "style",
    "chore",
)
CONST_BRANCH_SLUG_PATTERN: Final[str] = "[a-z0-9]+(?:-[a-z0-9]+)*"
# `devops repos worktrees add` (#2337) puts the worktree of an issue at `w-<issue>` under this path
# of the data directory (CONTRIBUTING.md: agent files and worktrees live under `.data/agent/`).
CONST_AGENT_WORKTREES_SUBPATH: Final[str] = "agent/worktrees"
CONST_AGENT_WORKTREE_PREFIX: Final[str] = "w-"
CONST_GIT_REMOTE_ORIGIN: Final[str] = "origin"
# Host-folder shares (WSL's drvfs over 9p) answer each file check hundreds of times slower than
# a Linux filesystem, which multiplies the gate's time for a workspace checked out on them.
CONST_SLOW_WORKSPACE_FSTYPES: Final[frozenset[str]] = frozenset({"9p", "drvfs"})
CONST_LLM_CACHE_DIR_NAME = "llm"
# The prefix of an LLM response cache key.
CONST_LLM_CACHE_KEY_PREFIX: Final[str] = "llm_"
# The length of the SHA-256 digest in hexadecimal format.
CONST_SHA256_HEX_LENGTH: Final[int] = 64
# The valid hexadecimal characters for cache key verification.
CONST_HEX_CHARACTERS: Final[frozenset[str]] = frozenset("0123456789abcdefABCDEF")
# The incremental mypy caches of reviews, below the data cache directory, one for each reviewed
# tree, Python version and environment lock (#2034).
CONST_MYPY_CACHE_DIR_NAME: Final[str] = "mypy"
# The variable that names the cache directory of mypy. A review sets it in place of `--cache-dir`,
# so the command of a mypy run names no path of the host but its config file and its targets.
CONST_MYPY_CACHE_DIR_ENV: Final[str] = "MYPY_CACHE_DIR"
# The directory of a canary scratch directory where the mypy canary writes its cache.
CONST_MYPY_CANARY_CACHE_DIR_NAME: Final[str] = "mypy_cache"
# The directory of the data cache that holds the Ruff cache of each reviewed tree, and the variable
# that names the cache directory to Ruff. The variable wins over a `cache-dir` of the config of the
# tree, and Ruff keys its entries by the package of each file, not by the directory it starts in
# (Ruff 0.16.8, measured 2026-10-24, #2096).
CONST_RUFF_CACHE_DIR_NAME: Final[str] = "ruff"
CONST_RUFF_CACHE_DIR_ENV: Final[str] = "RUFF_CACHE_DIR"
# golangci-lint loads packages through the `go` command (#2129). In the sandbox it has no network,
# so the `go` command reads modules only from the module cache of the host and runs only the
# toolchain that the sandbox binds. `go env` names both, from the Go variables of the host here.
CONST_GO_ENV_ARGS: Final[tuple[str, ...]] = ("env", "-json", "GOROOT", "GOMODCACHE")
CONST_GO_ENV_TIMEOUT_SECONDS: Final[float] = 30.0
CONST_GO_HOST_ENV_VARIABLES: Final[frozenset[str]] = frozenset(
    {"GOROOT", "GOPATH", "GOMODCACHE", "GOENV", "XDG_CONFIG_HOME"}
)
CONST_GO_NO_FETCH_ENV: Final[tuple[tuple[str, str], ...]] = (
    ("GOPROXY", "off"),
    ("GOTOOLCHAIN", "local"),
)
CONST_GOROOT_ENV: Final[str] = "GOROOT"
CONST_GOMODCACHE_ENV: Final[str] = "GOMODCACHE"
# The Go build cache and the golangci-lint cache of each reviewed tree, in the data cache directory.
CONST_GOLANGCI_LINT_CACHE_DIR_NAME: Final[str] = "golangci-lint"
CONST_GO_BUILD_CACHE_ENV: Final[str] = "GOCACHE"
CONST_GOLANGCI_LINT_CACHE_ENV: Final[str] = "GOLANGCI_LINT_CACHE"
# The error of the `go` command for a module that is in no module cache when GOPROXY=off
# (`errProxyOff`, cmd/go/internal/modfetch/proxy.go).
CONST_GO_PROXY_OFF_ERROR: Final[str] = "module lookup disabled by GOPROXY=off"
CONST_BENCHMARKS_DIR_NAME = "benchmarks"
# The kinds of run `devops ai benchmark --type` takes: `auto` picks embedding when a model's name
# says it embeds and chat otherwise. Any other value is refused rather than run as chat (#950).
CONST_BENCHMARK_TYPES: Final[tuple[str, ...]] = ("auto", "chat", "embedding")

CONST_AUDIT_LOG_NAME = "audit.jsonl"
CONST_FEEDBACK_DATASET_NAME = "feedback_dataset.jsonl"
CONST_EMBEDDING_REPORT_FILENAME = "embedding_report.json"
CONST_TLS_DIR_NAME = "tls"
CONST_RAG_DIR_NAME = "rag"
CONST_SAMPLES_DIR_NAME = "samples"
CONST_RUNS_DIR_NAME = "runs"
CONST_INDEX_CACHE_FILENAME = "index_cache.json"
CONST_INDEX_COUNTS_FILENAME: Final[str] = "index_counts.json"
# ── Memory & Byte Sizing Constants ────────────────────────────────────────────
CONST_FP32_BYTES_PER_ELEMENT: int = 4
CONST_KILOBYTE_BYTES: int = 1024

# ── TLS & Cryptographic Certificates ──────────────────────────────────────────
CONST_CA_CERT_NAME = "ca.crt"
CONST_CA_KEY_NAME = "ca.key"
CONST_SERVER_CERT_NAME = "tls.crt"
CONST_SERVER_KEY_NAME = "tls.key"
CONST_FULLCHAIN_CERT_NAME = "fullchain.crt"

# ── DevContainer ──────────────────────────────────────────────────────────────
CONST_DEVCONTAINER_DIR_NAME = ".devcontainer"
CONST_DEVCONTAINER_JSON_NAME = "devcontainer.json"
CONST_DEVCONTAINER_JSON_PATH = Path(CONST_DEVCONTAINER_DIR_NAME) / CONST_DEVCONTAINER_JSON_NAME
CONST_DEVCONTAINER_IMAGE_PREFIX = "mcr.microsoft.com/devcontainers/python:"
CONST_DEVCONTAINER_PUBLISHED_IMAGE = "ghcr.io/dan-petty/devops-cli/devcontainer:latest"
CONST_CANONICAL_OCI_SOURCE: Final[str] = "https://github.com/dan-petty/devops-cli"
# The Secret Service gh, git and Python keyring use; dbus-x11 satisfies gnome-keyring's
# session-bus dependency without pulling in systemd. Mirrors .devcontainer/Dockerfile.
CONST_KEYRING_PACKAGES: Final[tuple[str, ...]] = ("gnome-keyring", "dbus-x11")
# How long post-start waits for the keyring password before leaving it to the first
# interactive terminal, so an unwatched prompt never stalls the container start.
CONST_KEYRING_PROMPT_TIMEOUT_SECONDS: Final[int] = 60

# ── Specifications, Load Testing & Chaos ──────────────────────────────────────
CONST_SPECS_DIR_NAME = ".devops/specs"
# Review-specific conventions a project keeps for devops ai review: read in full, beside the
# general conventions file, by the personas and the verifier.
# Declarative path classes configuration file for review routing and tool scoping (#1047).
CONST_REVIEW_CONFIG_FILE = ".devops/review.toml"
CONST_DEFAULT_PATH_CLASSES: Final[dict[str, tuple[str, ...]]] = {
    "src": ("src/**", "lib/**", "app/**"),
    "test": ("tests/**", "test/**", "*_test.py", "test_*.py"),
    "fixture": (
        "tests/fixtures/**",
        "tests/golden/**",
        "fixtures/**",
        "golden/**",
        "**/fixtures/**",
        "**/golden/**",
    ),
    "iac": ("k8s/**", "helm/**", "Dockerfile*", "Containerfile*", "*.tf", "*.tfvars"),
    "docs": ("docs/**", "*.md", "*.rst", "LICENSE*", "NOTICE*"),
}
CONST_SPECS_DIR_PATH = Path(CONST_SPECS_DIR_NAME)
# ── OpenTofu & Infrastructure ──────────────────────────────────────────────────
CONST_TF_DIR_NAME = "tf"
CONST_TF_DIR_PATH = Path(CONST_TF_DIR_NAME)
CONST_TF_AWS_DIR = CONST_TF_DIR_PATH / "aws"
CONST_TF_AZURE_DIR = CONST_TF_DIR_PATH / "azure"
CONST_TF_GCP_DIR = CONST_TF_DIR_PATH / "gcp"
CONST_TF_ENVIRONMENTS_DIR = CONST_TF_DIR_PATH / "environments"
CONST_OPENTOFU_BINARIES: tuple[str, ...] = ("tofu", "terraform")


# ── Git & Workspace ───────────────────────────────────────────────────────────
CONST_GIT_DIR_NAME = ".git"
CONST_BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pyc",
        ".pyo",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".db",
        ".sqlite",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".tgz",
        ".7z",
        ".rar",
        ".log",
    }
)
# ── Network & Remote Services ─────────────────────────────────────────────────
CONST_GITHUB_HOST = "github.com"
CONST_URL_SCHEME_HTTP = "http://"
CONST_URL_SCHEME_HTTPS = "https://"
CONST_GITHUB_SSH_PREFIX = "git@github.com:"
CONST_GITHUB_SSH_URL_PREFIX = "ssh://git@github.com/"
CONST_GITHUB_HTTP_PREFIX = "http://github.com/"
CONST_GITHUB_HTTPS_PREFIX = "https://github.com/"
CONST_GITHUB_REPO_SUFFIX = ".git"
# ── What a failed gh command wrote (#983) ─────────────────────────────────────
# gh reports a failure only as text on stderr and an exit status. This table, matched
# lower-cased against gh's stderr and read only by `devops_cli.github.error_classifier`, is the
# one place gh's failures are classified by its text. stdout holds GitHub's answer, which for a
# failed GraphQL read may carry partial data such as item titles, and is never matched.
# `_is_branch_unprotected_error` (github/branch_protection.py), `create_repository_issue`
# (github/issues.py), `_report_create_failure` (commands/pr.py) and `extract_retry_after`
# (github/rate_limiter.py) still match gh's text of their own. An HTTP answer the session
# receives is classified by its status and headers instead.
#
# gh project's owner lookup (`OwnerIDAndType`, gh 2.102.0) writes this for any failed owner
# lookup that is not a "not found" for both a user and an organization (a 401, a 403, a 5xx, a
# network error or a rate limit), and drops the cause. `run_gh` does not retry it, and
# `_run_project_cli` resends the command as `--owner @me` at once. A lookup that is not recovered
# is classified as a rate limit, as the board lookup read it before #983.
CONST_GH_UNKNOWN_OWNER_TYPE: Final[str] = "unknown owner type"
# A primary or secondary rate limit, in GitHub's words as gh writes them.
CONST_GITHUB_RATE_LIMIT_PATTERNS: tuple[str, ...] = (
    "rate limit exceeded",
    "rate limit already exceeded",
    "secondary rate limit",
    "too many requests",
    "http 429",
    "wait a few minutes before you try again",
)
CONST_GITHUB_SECONDARY_RATE_LIMIT_PATTERNS: tuple[str, ...] = (
    "secondary rate limit",
    "wait a few minutes before you try again",
    "please retry your request again later",
    "exceeded a secondary rate limit",
)
# A token without a scope the command needs: gh project's GraphQL message ("your authentication
# token is missing required scopes"), gh api's scope suggestion ("This API operation needs the
# ... scope"), GitHub's GraphQL refusal of a project field ("requires one of the following
# scopes: ['read:project']") and gh gpg-key's "insufficient OAuth scopes".
CONST_GITHUB_SCOPE_PATTERNS: tuple[str, ...] = (
    "missing required scopes",
    "this api operation needs the",
    "read:project",
    "oauth scope",
)
# What GitHub answers (HTTP 403) when the permissions of an installation token do not cover the
# path: "Resource not accessible by integration" (#2752).
CONST_GITHUB_TOKEN_NOT_COVERED_PATTERN: Final[str] = "resource not accessible by integration"
# No login, one GitHub refused (HTTP 401), an account GitHub suspended (HTTP 403, #2161), or a
# GitHub App installation that its owner suspended (HTTP 403, #2474): GitHub refuses the request
# for a token with "This installation has been suspended", and a request with a token minted
# before with "This installation owned by <owner> suspended your access at <time>".
CONST_GITHUB_UNAUTHENTICATED_PATTERNS: tuple[str, ...] = (
    "not logged in",
    "http 401",
    "bad credentials",
    "account was suspended",
    "installation has been suspended",
    "suspended your access",
)
# gh's exit status for a command that requires authentication (`gh help exit-codes`).
CONST_GH_AUTH_REQUIRED_EXIT_CODE: Final[int] = 4
# The HTTP status gh names on stderr: `gh api` writes `<message> (HTTP <status>)` or
# `HTTP <status>`, and its other commands go-gh's `HTTP <status>: <message> (<url>)`.
CONST_GH_HTTP_STATUS_RE: Final[re.Pattern[str]] = re.compile(r"\bHTTP (?P<status>\d{3})\b")
# The scope gh project's commands need to create and edit boards; it includes read:project.
CONST_GH_PROJECT_SCOPE: Final[str] = "project"
# The OAuth scope GitHub's REST documentation requires to add a key at each SSH key endpoint, in
# the order `devops ssh register` posts to them.
CONST_GITHUB_SSH_KEY_ENDPOINT_SCOPES: Final[dict[str, str]] = {
    "/user/keys": "admin:public_key",
    "/user/ssh_signing_keys": "write:ssh_signing_key",
}
# The scopes registering a key needs, as `gh auth refresh -s` takes them.
CONST_GITHUB_SSH_KEY_REFRESH_SCOPES: Final[str] = ",".join(
    CONST_GITHUB_SSH_KEY_ENDPOINT_SCOPES.values()
)

CONST_URL_ANTHROPIC_API_BASE = "https://api.anthropic.com"
CONST_URL_GITHUB_COPILOT_API_BASE = "https://api.githubcopilot.com"
# The API a hosted provider's requests, and the AI key, go to when no api_base_url is set.
CONST_AI_PROVIDER_API_BASES: Final[dict[str, str]] = {
    "claude": CONST_URL_ANTHROPIC_API_BASE,
    "copilot": CONST_URL_GITHUB_COPILOT_API_BASE,
}
# What `backend_host` reports for a provider with no configured or default endpoint, or for an
# endpoint URL with no httpx2 origin, and what a served_by display shows for a value that names no
# server. It is never the text of the URL, so it never holds userinfo.
CONST_AI_BACKEND_HOST_UNKNOWN = "unknown"
# The longest value, and the characters outside the allowed set, of a metric label that a caller
# of a command sets, such as the model of `devops ai prewarm` (#2676). The set holds the letters
# and marks of an Ollama model reference: `hf.co/org/repo:Q4_K_M`.
CONST_METRIC_LABEL_MAX_LENGTH: Final[int] = 128
CONST_METRIC_LABEL_UNSAFE_RE: Final[re.Pattern[str]] = re.compile(r"[^A-Za-z0-9._:/-]")
# The `backend_info` of a reply the response cache answered, and the server its spend-ledger row
# names: no backend served it, so spend reports leave it out of their server counts (#816).
CONST_RESPONSE_CACHE_SERVER: Final[str] = "cache"
# The `request_type` of a spend-ledger row that records one embedding request. Its tokens are
# all input tokens, and its local savings use the embedding reference model (#1623).
CONST_SPEND_REQUEST_TYPE_EMBEDDING: Final[str] = "embedding"
# The pricing source of a call that ran on local hardware and costs nothing, and of a hosted
# model that neither genai-prices nor a price override prices. A spend-ledger row stores it in
# `pricing_source` (#1672).
CONST_PRICING_SOURCE_LOCAL: Final[str] = "local"
CONST_PRICING_SOURCE_UNKNOWN: Final[str] = "unknown"
# The genai-prices provider ID that reads a LiteLLM model reference, such as `openai/gpt-4o`:
# genai-prices takes the provider from the prefix and the model from the rest (#2031).
CONST_GENAI_PRICES_LITELLM_PROVIDER: Final[str] = "litellm"
CONST_URL_GITHUB_API_BASE = "https://api.github.com"
# What the GitHub session sends with every REST request (#983): GitHub requires a User-Agent
# naming the project or user, and the API version pins the REST contract the session reads.
CONST_GITHUB_USER_AGENT: Final[str] = CONST_APP_NAME
CONST_GITHUB_API_VERSION: Final[str] = "2022-11-28"
CONST_GITHUB_HEADER_API_VERSION: Final[str] = "x-github-api-version"
# The media type GitHub serves a pull request's unified diff as.
CONST_GITHUB_DIFF_MEDIA_TYPE: Final[str] = "application/vnd.github.diff"
# The `repo` and `row` of a GitHub request that no Service worker and no job row sent (#2475).
CONST_GITHUB_REQUEST_SCOPE_OTHER: Final[str] = "other"
# The characters that open and close an expression in a URI template (RFC 6570, section 2.2).
# gidgethub expands every path as a template, so the session sends them percent-encoded.
CONST_URI_TEMPLATE_EXPRESSION_DELIMITERS: Final[str] = "{}"
# Response headers the session's error classifier and quota ledger read, named as GitHub's REST
# documentation names them ("Rate limits for the REST API", "Scopes for OAuth apps").
CONST_GITHUB_HEADER_RATE_LIMIT_RESOURCE: Final[str] = "x-ratelimit-resource"
# What every rate-limit header's name starts with: GitHub sends them with each answer it counts
# against an identity's quota.
CONST_GITHUB_HEADER_RATE_LIMIT_PREFIX: Final[str] = "x-ratelimit-"
CONST_GITHUB_HEADER_RETRY_AFTER: Final[str] = "retry-after"
CONST_GITHUB_HEADER_OAUTH_SCOPES: Final[str] = "x-oauth-scopes"
CONST_GITHUB_HEADER_ACCEPTED_OAUTH_SCOPES: Final[str] = "x-accepted-oauth-scopes"
CONST_URL_CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"
CONST_CLOUDFLARE_CFARGOTUNNEL_SUFFIX = ".cfargotunnel.com"
CONST_CLOUDFLARE_DEFAULT_SERVICE = "http://traefik.kube-system.svc.cluster.local:80"
CONST_CLOUDFLARE_CATCHALL_SERVICE = "http_status:404"
CONST_CLOUDFLARE_DEFAULT_SUBDOMAINS: tuple[str, ...] = ("*", "@")
# The only wildcard a tunnel ingress hostname takes: a leading `*.` (cloudflared ingress/rule.go).
CONST_CLOUDFLARE_WILDCARD_PREFIX = "*."
CONST_CLOUDFLARE_RECORD_COMMENT: Final[str] = "Managed by devops-cli"
CONST_CLOUDFLARE_BYPASS_POLICY_NAME: Final[str] = "homelab-public-ip-bypass"
CONST_CLOUDFLARE_ALLOW_POLICY_NAME: Final[str] = "Allow homelab authorized emails"
CONST_CLOUDFLARE_DEFAULT_SESSION_DURATION: Final[str] = "24h"
CONST_URL_GITHUB_STATUS_SUMMARY: Final[str] = "https://www.githubstatus.com/api/v2/summary.json"
CONST_URL_CLOUDFLARE_STATUS_SUMMARY: Final[str] = (
    "https://www.cloudflarestatus.com/api/v2/summary.json"
)
CONST_STATUSPAGE_HTTP_TIMEOUT_SECONDS: Final[float] = 5.0
CONST_STATUSPAGE_INDICATOR_VALUES: Final[dict[str, int]] = {
    "none": 0,
    "minor": 1,
    "major": 2,
    "critical": 3,
}
CONST_STATUSPAGE_COMPONENT_STATUS_VALUES: Final[dict[str, int]] = {
    "operational": 0,
    "degraded_performance": 1,
    "partial_outage": 2,
    "major_outage": 3,
    "under_maintenance": 1,
}
CONST_GITHUB_STATUS_KEY_COMPONENTS: Final[tuple[str, ...]] = (
    "Git Operations",
    "API Requests",
    "Actions",
    "Pull Requests",
    "Issues",
    "Copilot",
    "Pages",
    "Packages",
)
CONST_CLOUDFLARE_STATUS_KEY_COMPONENTS: Final[tuple[str, ...]] = (
    "Tunnel",
    "Authoritative DNS",
    "Access",
    "Zero Trust",
    "Dashboard",
    "API",
    "CDN/Cache",
    "Workers",
)
CONST_STATUS_COMMAND_SERVICES: Final[tuple[str, ...]] = ("all", "github", "cloudflare")


# ── Kubernetes & RFC 1123 Patterns ────────────────────────────────────────────
CONST_K8S_LABEL_RE: re.Pattern[str] = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
CONST_K8S_SUBDOMAIN_RE: re.Pattern[str] = re.compile(r"^[a-z0-9]([a-z0-9.\-]{0,251}[a-z0-9])?$")
CONST_K8S_NODE_ROLE_LABEL_PREFIX = "node-role.kubernetes.io/"
# What the llm stack's Ollama tiers select GPU nodes by (#1367): the extended resource and labels
# the node-provisioning automation and GPU Feature Discovery set, and the label every tier's
# DaemonSet carries, read from `ollama-profiles.yaml`, whose required matchExpressions say which
# values each tier accepts.
CONST_K8S_GPU_RESOURCE: Final[str] = "nvidia.com/gpu"
CONST_K8S_GPU_PRESENT_LABEL: Final[str] = "nvidia.com/gpu.present"
CONST_K8S_GPU_TOTAL_VRAM_LABEL: Final[str] = "nvidia.com/gpu.total-vram-gib"
CONST_K8S_GPU_ARCHITECTURE_LABEL: Final[str] = "nvidia.com/gpu.architecture"
CONST_K8S_OLLAMA_PROVIDER_LABEL: Final[tuple[str, str]] = ("llm.devops.io/provider", "ollama")
CONST_K8S_OLLAMA_PROFILES_PATH: Final[str] = "llm/profiles/ollama-profiles.yaml"
CONST_K8S_TEMPLATE_DOMAIN_PLACEHOLDER: Final[str] = "example.com"
CONST_K8S_TEMPLATE_DOMAIN_VARS: Final[tuple[str, ...]] = ("DOMAIN", "K8S_DOMAIN")
CONST_INLINE_SUPPRESSION_MARKERS: Final[dict[str, tuple[str, ...]]] = {
    "bandit": ("nosec",),
    "semgrep": ("nosemgrep", "no-semgrep"),
    "ruff": ("noqa",),
}
"""The inline markers each review tool honours; a tool not listed has none (#1341)."""
CONST_RAG_INCOMPLETE_FILE_MARKER: Final[str] = "incomplete"
"""The RAG cache entry of a file only some of whose chunks are stored; it matches no content hash."""
CONST_K8S_DEVOPS_CONFIGMAP: Final[str] = "devops-cli-config"
"""The ConfigMap `devops k8s deploy-stack` renders from config.yaml; no Argo CD Application owns it."""
CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS: Final[tuple[str, ...]] = (
    "devops",
    "ingress",
    "mattermost",
)
"""The Argo CD Applications whose hosts deploy-stack sets from the configured domain (#1290)."""
CONST_K8S_KUSTOMIZATION_NAMES: Final[tuple[str, ...]] = (
    "kustomization.yaml",
    "kustomization.yml",
    "Kustomization",
)
"""The standard file names Kustomize recognizes for a directory overlay."""
CONST_K8S_STACKS: Final[tuple[str, ...]] = ("infra", "llm", "logging", "devops", "gitea", "chat")
"""The stacks of the Kubernetes stack commands, in deploy order: the one declaration of a stack
name. `_resolve_stacks` and every help text that lists stacks read it (#2008)."""
CONST_K8S_ALL_STACKS: Final[str] = "all"
"""The `--stack` value that selects every stack of `CONST_K8S_STACKS`."""
CONST_K8S_VALID_STACKS: Final[tuple[str, ...]] = (*CONST_K8S_STACKS, CONST_K8S_ALL_STACKS)
"""Every `--stack` value the Kubernetes stack commands accept (#2157)."""
CONST_K8S_MATTERMOST_URL: Final[str] = "http://mattermost.mattermost.svc.cluster.local:8065"
"""Mattermost's base URL inside the cluster, which the derived hook URLs of the push table start
with (#1391, #1392, #1393)."""
CONST_K8S_ARGOCD_APPLICATION_DIRS: Final[tuple[Path, ...]] = (
    Path("k8s/argocd/apps"),
    Path("k8s/argocd/bootstrap"),
)
"""Directories scanned for Argo CD Applications (#1343)."""
CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS_BY_STACK: Final[dict[str, tuple[str, ...]]] = {
    "infra": ("ingress",),
    "devops": ("devops", "ingress"),
    # Application `ingress` renders the Ingress of the git host (k8s/ingress/ingress-routes.yaml).
    "gitea": ("ingress",),
    "chat": ("mattermost",),
}
"""The homelab Applications whose hosts a stack's deploy sets."""
CONST_K8S_ARGOCD_FETCH_TIMEOUT_SECONDS: Final[float] = 300.0
"""How long fetching an Application's revision may take before deploy-stack gives up."""
"""JQ expression in cluster.yaml ignoreDifferences matching Argo CD PreDelete/PostDelete finalizers (#1674)."""
CONST_GIT_NONINTERACTIVE_ENV: Final[dict[str, str]] = {"GIT_TERMINAL_PROMPT": "0"}
"""Environment that makes git fail instead of prompting for credentials."""
CONST_GIT_NONINTERACTIVE_SSH_CONFIG: Final[str] = "core.sshCommand=ssh -o BatchMode=yes"
"""The `git -c` value that makes git fail instead of asking for a passphrase or a host key. It is
an argument, because the guard of `build_subprocess_env` refuses `GIT_SSH_COMMAND` (#2483)."""
CONST_GIT_ACCEPTED_ENV: Final[frozenset[str]] = frozenset(
    {
        "GIT_TERMINAL_PROMPT",
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_AUTHOR_DATE",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "GIT_COMMITTER_DATE",
    }
)
"""The git keys that `build_subprocess_env` accepts from a caller (#2483). devops-cli sets
`GIT_TERMINAL_PROMPT`, a tool request sets the author and the committer, and `commit_snapshot`
sets their dates (git(1), #2146). None runs a program or writes a file. The guard refuses each
other `GIT_` key, also one that git adds later."""

# Keys that send data egress to an arbitrary network destination, which should be refused.
CONST_DATA_EGRESS_ENV_VARS: Final[frozenset[str]] = frozenset({"GH_TELEMETRY_ENDPOINT_URL"})
"""Environment variables that send data egress to a network destination. These are refused
from caller overrides because they can redirect telemetry to arbitrary destinations."""
CONST_GIT_GLOBAL_CONFIG_ENV: Final[frozenset[str]] = frozenset({"GIT_CONFIG_GLOBAL"})
"""The ambient key that a `git config --global` call names in `extra_allowed_env`, so that it
writes the global file that the environment names, as it does in a shell (#2483)."""
CONST_K8S_TEMPLATE_EXTENSIONS: Final[tuple[str, ...]] = (".yaml", ".yml")

# ── Kubernetes RBAC Audit ─────────────────────────────────────────────────────
# The built-in ClusterRoles that grant everything (cluster-admin) or write access to most of
# a namespace (admin, edit).
CONST_K8S_RBAC_PRIVILEGED_CLUSTER_ROLES: Final[frozenset[str]] = frozenset(
    {"cluster-admin", "admin", "edit"}
)
# In a PolicyRule's verbs, resources or apiGroups, grants every value.
CONST_K8S_RBAC_WILDCARD: Final[str] = "*"
CONST_K8S_SYSTEM_NAMESPACE: Final[str] = "kube-system"
CONST_K8S_SYSTEM_SUBJECT_PREFIX: Final[str] = "system:"
# The username of one ServiceAccount, `system:serviceaccount:<namespace>:<name>`, and the group of
# every ServiceAccount in a namespace, `system:serviceaccounts:<namespace>`. A User or Group
# subject with either name is a ServiceAccount, judged by its namespace like one.
CONST_K8S_SERVICE_ACCOUNT_SUBJECT_PREFIXES: Final[tuple[str, ...]] = (
    "system:serviceaccount:",
    "system:serviceaccounts:",
)
# The control-plane identities without a `system:` prefix that a distribution binds to a broad
# or wildcard role on every cluster it installs: k3s's kube-apiserver kubelet client and cloud
# controller manager (k3s manifests/rolebindings.yaml and manifests/ccm.yaml), and the kubeadm
# 1.29+ admin.conf group that took over from system:masters.
CONST_K8S_RBAC_DISTRIBUTION_SUBJECTS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("User", "kube-apiserver"),
        ("User", "k3s-cloud-controller-manager"),
        ("Group", "kubeadm:cluster-admins"),
    }
)
# The built-in groups and user that stand for every client or every service account. Their
# `system:` prefix marks them as built in, not as cluster components, so it excuses nothing.
CONST_K8S_RBAC_BROAD_SUBJECTS: Final[frozenset[str]] = frozenset(
    {
        "system:anonymous",
        "system:unauthenticated",
        "system:authenticated",
        "system:serviceaccounts",
    }
)

# ── File Permissions ──────────────────────────────────────────────────────────
CONST_PERM_DIR = 0o700
CONST_PERM_PRIVATE_KEY = 0o600
CONST_PERM_PUBLIC_KEY = 0o644
CONST_PERM_EXEC = 0o755
# A file the repository commits, such as a generated table under src/.
CONST_PERM_REPO_FILE = 0o644

CONST_MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024
# ── Code Review & Analysis ────────────────────────────────────────────────────
# Characters per token for sizing review pages from a context window (source code averages
# slightly under four; the lower figure leaves margin).
CONST_REVIEW_CHARS_PER_TOKEN: Final[float] = 3.5
# Memory bandwidth (GB/s) by GPU model, matched against `nvidia-smi` names (longest key first).
# Token generation reads every active weight once per token, so it is bandwidth-bound; this is
# the hardware input to `devops ai gateway tune`'s capacity estimates.
CONST_GPU_MEMORY_BANDWIDTH_GBPS: Final[dict[str, float]] = {
    "h100 sxm": 3350.0,
    "h100": 2000.0,
    "a100 80gb": 2039.0,
    "a100": 1555.0,
    "l40s": 864.0,
    "l4": 300.0,
    "a10g": 600.0,
    "a10": 600.0,
    "t4": 320.0,
    "v100": 900.0,
    "pg500-216": 900.0,  # V100 SXM2 32 GB board
    "titan v": 653.0,
    "p100": 732.0,
    "p40": 346.0,
    "p6000": 432.0,
    "rtx a6000": 768.0,
    "rtx a5000": 768.0,
    "rtx a4000": 448.0,
    "rtx 5090": 1792.0,
    "rtx 5080": 960.0,
    "rtx 5070 ti": 896.0,
    "rtx 5070": 672.0,
    "rtx 4090": 1008.0,
    "rtx 4080": 717.0,
    "rtx 4070 ti": 504.0,
    "rtx 4060 ti": 288.0,
    "rtx 3090 ti": 1008.0,
    "rtx 3090": 936.0,
    "rtx 3080": 760.0,
    "rtx 3070": 448.0,
    "rtx 3060": 360.0,
    "titan rtx": 672.0,
    "gtx 1080 ti": 484.0,
    "gtx 1080": 320.0,
    "gtx 1070": 256.0,
    "gtx 1050 ti": 112.0,
}
# A review session's reported findings; a session directory holding one is a completed session.
CONST_REVIEW_FINDINGS_FILENAME = "findings.json"
# Every finding a review session produced, each with its verification status; findings.json keeps
# only those still reported.
CONST_REVIEW_CANDIDATES_FILENAME = "candidates.json"
# Held while `devops review verify` reads and writes a session's files, so verdicts given on one
# session at once, as an MCP client's parallel calls give them, wait their turn (#949).
CONST_REVIEW_VERDICT_LOCK_FILENAME = ".verify.lock"
# The admitted tool findings of a review session, with their fingerprint_v2 (#871).
CONST_REVIEW_SARIF_FILENAME = "findings.sarif"
# A review session's per-page records: the file each page read and the findings it raised there.
CONST_REVIEW_PAGES_DIRNAME = "files"
# A review session's Markdown report, and where its time went (#771).
CONST_REVIEW_REPORT_FILENAME = "review.md"
CONST_REVIEW_PROFILE_FILENAME = "profile.json"
# The phrase of the marker that an issue filed from a review finding carries in its body, with
# the finding's fingerprint_v2; the issue search for it finds the findings already filed (#2419).
CONST_REVIEW_FILED_FINDING_MARKER: Final[str] = "devops-review-finding"
# GitHub's `state_reason` of a closed issue that still settles the review finding it carries, so
# the review does not file the finding again: a person rejected it, or another issue tracks it. A
# finding whose issue was closed as completed is filed again, because the defect came back.
CONST_REVIEW_FILED_FINDING_SETTLING_CLOSE_REASONS: Final[frozenset[str]] = frozenset(
    {"not_planned", "duplicate"}
)
# Where a review writes its session until it is whole: inside the sessions directory, so that
# publishing it is one rename, and a dot-directory, so that it is not a session (#771).
CONST_REVIEW_STAGING_DIRNAME = ".staging"
# `devops review score` (#1138): the labels a person gives a distinct finding, the two that count
# as valid, the producer of a model's finding, and the severities its HIGH/CRITICAL figure reads.
CONST_REVIEW_LABEL_VALID_STRICT = "valid-strict"
CONST_REVIEW_LABEL_VALID_LENIENT = "valid-lenient"
CONST_REVIEW_LABEL_FALSE = "false"
CONST_REVIEW_LABELS_VALID: Final[frozenset[str]] = frozenset(
    {CONST_REVIEW_LABEL_VALID_STRICT, CONST_REVIEW_LABEL_VALID_LENIENT}
)
CONST_REVIEW_PRODUCER_PERSONA = "persona"
CONST_REVIEW_SCORE_HIGH_SEVERITIES: Final[frozenset[str]] = frozenset({"CRITICAL", "HIGH"})
# A model's finding matches a label of its path and origin page when their lines lie this close,
# the window the loop study clustered persona findings with.
CONST_REVIEW_SCORE_PERSONA_LINE_WINDOW = 5
CONST_REVIEW_GENERATED_FILES = frozenset(
    {
        "uv.lock",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Pipfile.lock",
        "poetry.lock",
        "Gemfile.lock",
        "composer.lock",
        "go.sum",
        "Cargo.lock",
    }
)
CONST_SSH_GRACE_DAYS = 7

CONST_STATUS_VERIFIED = "VERIFIED"
CONST_STATUS_UNVERIFIED = "UNVERIFIED"
CONST_STATUS_INVALIDATED = "INVALIDATED"
CONST_STATUS_MITIGATED = "MITIGATED"
CONST_STATUS_SUCCESS = "SUCCESS"

CONST_GIT_MAIN_BRANCH = "main"
CONST_SAFE_GIT_REF_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z0-9_\-/.^~@]+$")
# The mode `git ls-tree` gives a link, whose blob is the path it points to.
CONST_GIT_SYMLINK_MODE: Final[str] = "120000"
# How a file changed, by the status letter `git diff --name-status` prints (every letter
# git-diff(1) documents for --diff-filter). Copies and renames print the old path, then the new.
CONST_GIT_NAME_STATUS_CHANGE_TYPES: Final[dict[str, str]] = {
    "A": "added",
    "B": "broken",
    "C": "copied",
    "D": "deleted",
    "M": "modified",
    "R": "renamed",
    "T": "type-changed",
    "U": "unmerged",
    "X": "unknown",
}
CONST_GIT_NAME_STATUS_TWO_PATH_LETTERS: Final[frozenset[str]] = frozenset({"C", "R"})
CONST_GIT_WORKTREE_PREFIX: Final[str] = "worktree "
CONST_GIT_HEAD_PREFIX: Final[str] = "HEAD "
CONST_GIT_BRANCH_PREFIX: Final[str] = "branch "
CONST_GIT_LOCKED_TOKEN: Final[str] = "locked"
CONST_GIT_PRUNABLE_TOKEN: Final[str] = "prunable"
CONST_GIT_DETACHED_TOKEN: Final[str] = "detached"
CONST_GIT_BARE_TOKEN: Final[str] = "bare"
# `git worktree remove` fails with this when a run in parallel already removed the worktree.
CONST_GIT_NOT_A_WORKTREE_TOKEN: Final[str] = "is not a working tree"
# The same, from a pull request file's `status` in the GitHub REST API (its documented enum).
CONST_GITHUB_PR_FILE_CHANGE_TYPES: Final[dict[str, str]] = {
    "added": "added",
    "changed": "modified",
    "copied": "copied",
    "modified": "modified",
    "removed": "deleted",
    "renamed": "renamed",
    "unchanged": "unchanged",
}
# Changes whose symbol delta compares the file with its text at the base revision.
CONST_SYMBOL_DELTA_BASE_CHANGE_TYPES: Final[frozenset[str]] = frozenset(
    {"deleted", "modified", "renamed"}
)
# Changes a review records a symbol delta for: those whose file exists at head.
CONST_REVIEW_SYMBOL_DELTA_CHANGE_TYPES: Final[frozenset[str]] = frozenset(
    {"added", "modified", "renamed"}
)
CONST_DEFAULT_LINE_NUMBER = 1
CONST_MARKDOWN_HEADING_LEVEL = 3

CONST_STANDARD_HTML_TAGS: Final[frozenset[str]] = frozenset(
    {
        "a",
        "b",
        "blockquote",
        "br",
        "code",
        "details",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "img",
        "kbd",
        "li",
        "ol",
        "p",
        "pre",
        "span",
        "sub",
        "summary",
        "sup",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
    }
)

# The generated CLI reference masks a text default when the parameter's name or envvar names a
# credential. The name is split on "_" and "-" and matched word by word, so TOKENS (a count),
# VALKEY and a bare KEY (a key size, a config key, a field key) name none (#956).
CONST_DOC_CREDENTIAL_NAME_WORDS: Final[frozenset[str]] = frozenset(
    {"APIKEY", "AUTH", "CREDENTIAL", "PASSPHRASE", "PASSWORD", "SECRET", "TOKEN"}
)
# Adjacent words that name a credential where neither does alone.
CONST_DOC_CREDENTIAL_NAME_WORD_PAIRS: Final[frozenset[tuple[str, str]]] = frozenset(
    {("API", "KEY")}
)
# A name ending in this word holds what a credential is called, such as a Kubernetes Secret's
# name, not the credential.
CONST_DOC_CREDENTIAL_NAMING_WORD: Final[str] = "NAME"

# ── GitHub CLI & Pull Requests ────────────────────────────────────────────────
CONST_GH_CLI = "gh"
CONST_CI_WORKFLOW_FILE = "ci.yml"
CONST_GIT_CLI = "git"
CONST_GH_AUTH_SUBCOMMAND = "auth"
# The variable gh reads its token from first; the session pins it on every gh and git child
# (#767).
CONST_GH_AUTH_ENV_VAR = "GH_TOKEN"
# Every variable gh reads a token from, so a pinned child is given none but the session's.
CONST_GH_TOKEN_ENV_VARS: Final[tuple[str, ...]] = (CONST_GH_AUTH_ENV_VAR, "GITHUB_TOKEN")
# Where `gh auth token` finds a stored login: its config directory and the keyring's session bus.
CONST_GH_LOGIN_ENV_VARS: Final[frozenset[str]] = frozenset(
    {"GH_CONFIG_DIR", "XDG_CONFIG_HOME", "DBUS_SESSION_BUS_ADDRESS"}
)
# The variable that holds a GitHub App's private key. A process whose environment holds it acts
# as the App (ADR 0015), as Secret devops/devops-cli gives it to the cluster's pods.
CONST_GITHUB_APP_PRIVATE_KEY_ENV: Final[str] = "DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY"
# How an App installation names its quota ledger: one ledger for every token of the installation.
CONST_GITHUB_APP_LEDGER_KEY: Final[str] = "app-installation-{installation_id}"
# The permissions that each installation token of the App asks for: those the roadmap jobs use
# (ADR 0015). The token carries only these, whatever the installation grants. GitHub refuses a
# token with HTTP 422 when the installation does not grant one of them (#2473).
# The setting that limits an installation token to one repository (#2667).
CONST_GITHUB_APP_TOKEN_REPOSITORY_SETTING: Final[str] = "service.github_app.token_repository"
CONST_GITHUB_APP_TOKEN_PERMISSIONS: Final[dict[str, str]] = {
    "issues": "write",
    "pull_requests": "write",
    "contents": "write",
    "checks": "read",
    "actions": "read",
    "metadata": "read",
}
# GitHub's commit email of an account, `<id>+<login>@users.noreply.github.com`, for a bot too.
CONST_GITHUB_NOREPLY_EMAIL: Final[str] = "{account_id}+{login}@users.noreply.github.com"
# Hex characters of the identity key's SHA-256 that name an identity's cache directory.
CONST_GITHUB_IDENTITY_DIGEST_CHARS: Final[int] = 16
# Identities whose rate limiters a process keeps in memory at once; a process acts as one, and a
# second session with another token adds one more. Older ones are read from disk again.
CONST_GITHUB_IDENTITY_LIMITERS_KEPT: Final[int] = 4
# Copilot code review is the GitHub App `copilot-pull-request-reviewer`, and GitHub names an app's
# bot account `<slug>[bot]` (#1345). The reviews endpoint names the bot
# `copilot-pull-request-reviewer[bot]`, and GraphQL names it `copilot-pull-request-reviewer`, gh's
# `CopilotReviewerLogin` (gh 2.102.0, api/queries_repo.go): a review record is Copilot's only when
# its author's login is exactly one of them. The issue timeline names the same account (id
# 175728472) `Copilot`, type Bot, a login the Copilot coding agent shares, so a timeline `reviewed`
# event is matched by the id of one of Copilot's reviews, never by login (read on #1283's
# timeline).
CONST_COPILOT_REVIEWER_APP_SLUG: Final[str] = "copilot-pull-request-reviewer"
CONST_COPILOT_REVIEWER_LOGINS: Final[frozenset[str]] = frozenset(
    {f"{CONST_COPILOT_REVIEWER_APP_SLUG}[bot]", CONST_COPILOT_REVIEWER_APP_SLUG}
)
# The keys a review record names its author under: `user` in a REST review, `author` in a
# GraphQL one.
CONST_GITHUB_REVIEW_AUTHOR_KEYS: Final[tuple[str, ...]] = ("user", "author")
# The login GitHub shows for a deleted account, whose GraphQL `author` is null.
CONST_GITHUB_GHOST_LOGIN: Final[str] = "ghost"
CONST_GH_QUOTA_CACHE_FILENAME = "gh_quota.json"
# GitHub's rate limit `reset` is whole epoch seconds, so a window can still be reported within the
# second after it. A call at a reset that has passed waits until this long past it, because it is
# not clear when in that second the reset occurs (#1364).
CONST_GH_RATE_LIMIT_RESET_MARGIN_SECONDS: Final[float] = 1.0
# How far the local clock may run past the reset GitHub has just reported before the clocks count
# as disagreeing. The Service measured GitHub reporting an ended window 0.72 s to 2.07 s past its
# reset (#1364); a larger gap is a clock for a person to correct, not something to pace around.
CONST_GH_RATE_LIMIT_CLOCK_SKEW_BOUND_SECONDS: Final[float] = 5.0
# The details key of a roadmap GraphQL budget refusal's reset, ISO 8601, which the Service reads
# to hold every repository's rounds until then (#1400). The rate limiter's own errors carry
# `reset_epoch`, `reported_reset`, `local_clock`, `gap_seconds` or `reported_resources` instead,
# so none of them reads as a refusal.
CONST_GRAPHQL_REFUSAL_RESET_KEY: Final[str] = "reset_at"
CONST_GH_WEBHOOK_SIGNATURE_HEADER = "X-Hub-Signature-256"
# What GitHub writes before the hex digest in that header.
CONST_GH_WEBHOOK_SIGNATURE_PREFIX: Final[str] = "sha256="
CONST_GH_WEBHOOK_EVENT_HEADER: Final[str] = "X-GitHub-Event"
CONST_GH_WEBHOOK_DELIVERY_HEADER: Final[str] = "X-GitHub-Delivery"
CONST_SERVICE_MAX_BODY_BYTES: Final[int] = 25 * 1024 * 1024
CONST_SERVICE_DELIVERY_LRU_CAPACITY: Final[int] = 10_000
CONST_SERVICE_SOURCE_WEBHOOK: Final[str] = "webhook"
CONST_SERVICE_SOURCE_POLL: Final[str] = "poll"
CONST_SERVICE_PING_EVENT: Final[str] = "ping"
# The status of a delivery the GitHub App's own bot sent: the roadmap does not answer its own write.
CONST_SERVICE_STATUS_OWN_WRITE: Final[str] = "ignored_own_write"


class WebhookProviderName(StrEnum):
    """The providers whose webhooks the Service receives, each at `POST /webhooks/<provider>`
    (#1386). A sender gets a member once a consumer or a responder acts on its events."""

    GITHUB = "github"
    MATTERMOST = "mattermost"


class WebhookExposure(StrEnum):
    """How a webhook provider is reached: `TUNNEL` through the public Ingress, `CLUSTER` only at
    the Service's cluster DNS name (#1386)."""

    TUNNEL = "tunnel"
    CLUSTER = "cluster"


# What a delivery came to, the `outcome` of its log record and of the deliveries counter (#1386).
CONST_SERVICE_OUTCOME_ACCEPTED: Final[str] = "accepted"
CONST_SERVICE_OUTCOME_IGNORED: Final[str] = "ignored"
CONST_SERVICE_OUTCOME_REJECTED: Final[str] = "rejected"
CONST_SERVICE_OUTCOME_NO_SUBSCRIBER: Final[str] = "no_subscriber"
# The outcome of a delivery the GitHub App's own bot sent, which the roadmap consumer refuses: apart
# from the other ignored deliveries, so an echo loop with another bot or workflow shows (#2475).
CONST_SERVICE_OUTCOME_SELF: Final[str] = "self"
# The deliveries counter's `event` for an event no consumer subscribes to, so a sender's choice of
# event name can't grow the series (#1386).
CONST_SERVICE_EVENT_OTHER: Final[str] = "other"
CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES: Final[str] = "devops_cli_service_webhook_deliveries_total"
CONST_SERVICE_METRIC_TRIGGERS: Final[str] = "devops_cli_service_triggers_total"
CONST_SERVICE_METRIC_JOBS: Final[str] = "devops_cli_service_jobs_total"
CONST_SERVICE_METRIC_JOB_SECONDS: Final[str] = "devops_cli_service_job_seconds_total"
# The time the last job of a lane started, or the time its worker started before its first job
# (#2505).
CONST_SERVICE_METRIC_JOB_START_TIMESTAMP: Final[str] = (
    "devops_cli_service_job_start_timestamp_seconds"
)
CONST_SERVICE_METRIC_QUEUE_DEPTH: Final[str] = "devops_cli_service_queue_depth"
# Counts each time GitHub refused the Service's identity and every round stopped (#2161), and
# each start that finds the halt kept from before, so the count stays above 0 while the Service
# is halted (#2474). The `identity` label names the account, as the refusal does.
CONST_SERVICE_METRIC_IDENTITY_REFUSED: Final[str] = "devops_cli_service_identity_refused_total"
# The Service's hourly GitHub request budget (#2475): its limit, the requests of the window as of
# the last round or check, and a count of each hold when it begins.
CONST_SERVICE_METRIC_BUDGET_LIMIT: Final[str] = "devops_cli_service_budget_limit_requests"
CONST_SERVICE_METRIC_BUDGET_SPENT: Final[str] = "devops_cli_service_budget_spent_requests"
CONST_SERVICE_METRIC_BUDGET_HOLDS: Final[str] = "devops_cli_service_budget_holds_total"
# 1 while a job of a repository failed its limit of rounds in a row and waits for new input, else
# 0, by `repo` and `row` (#2475). The label is `row`, not `job`, which is the scrape's label.
CONST_SERVICE_METRIC_JOB_SUSPENDED: Final[str] = "devops_cli_service_job_suspended"
# Counts chat commands handled through the webhook router by `command` and `result` (#1395).
CONST_SERVICE_METRIC_CHAT_COMMANDS: Final[str] = "devops_cli_service_chat_commands_total"
# The Service's window for its GitHub request budget (#2161).
CONST_SERVICE_BUDGET_WINDOW_SECONDS: Final[int] = 3600
# What the Service keeps on its volume so that a restart does not clear it (#2474), each a file in
# the `roadmap` directory of the data directory, beside each repository's `schedule.json`: the
# halt after GitHub refused the identity, the requests of the budget window, and the ledger of
# failed rounds. A GitHub login has no dot, so no file name is a repository owner's directory.
CONST_SERVICE_HALT_FILENAME: Final[str] = "service-halt.json"
CONST_SERVICE_BUDGET_FILENAME: Final[str] = "service-budget.json"
CONST_SERVICE_FAILURES_FILENAME: Final[str] = "service-failures.json"
# The cause the log line that suspends a job gives for a failed round that an earlier process
# counted: the file keeps the count and not the cause (#2753).
CONST_SERVICE_CAUSE_UNKNOWN: Final[str] = "unknown"
# The Service's lanes (#1532): each repository has one worker per lane. The status lane runs the
# jobs that call no model (the metrics and the submission of the implement Job, #2757). The model
# lane runs the jobs that call the model, so a status-lane round never waits for a model-lane
# round. A service app given no jobs runs its logging job in the default lane.
CONST_SERVICE_LANE_STATUS: Final[str] = "status"
CONST_SERVICE_LANE_TRIAGE: Final[str] = "triage"
CONST_SERVICE_LANE_MODEL: Final[str] = "model"
CONST_SERVICE_LANE_DEFAULT: Final[str] = "default"
CONST_SERVICE_PROBE_PATHS: Final[frozenset[str]] = frozenset(
    {
        "/healthz",
        "/readyz",
        "/metrics",
    }
)
CONST_GH_NON_API_COMMANDS: Final[frozenset[str]] = frozenset(
    {
        "auth",
        "version",
        "--version",
        "help",
        "--help",
    }
)
CONST_GH_CHECK_BUCKET_PASS: Final[str] = "pass"
CONST_GH_CHECK_BUCKET_FAIL: Final[str] = "fail"
CONST_GH_CHECK_BUCKET_PENDING: Final[str] = "pending"
CONST_GH_CHECK_BUCKET_SKIPPING: Final[str] = "skipping"
CONST_GH_CHECK_BUCKET_CANCEL: Final[str] = "cancel"
CONST_GH_CHECK_BUCKET_UNREAD: Final[str] = "unread"

CONST_PR_API_STATE_MAP: Final[dict[str, str]] = {
    "all": "all",
    "closed": "closed",
    "merged": "closed",
}
CONST_GH_ISSUE_EVENT_CHANGE_KINDS: Final[dict[str, str]] = {
    "labeled": "labeled",
    "unlabeled": "unlabeled",
    "closed": "closed",
    "reopened": "reopened",
}
CONST_GH_ISSUE_STATE_REASON_REOPENED: Final[str] = "reopened"
"""GitHub's `state_reason` on an issue someone reopened, which it keeps while the issue is open.
No roadmap job reopens an issue, so it marks a person's reopen (ADR 0002)."""

# ── Exception Details ─────────────────────────────────────────────────────────
CONST_MAX_ERROR_DETAIL_LENGTH = 256

# ── AI Client Structured Output Metric Invariants ─────────────────────────────
CONST_JSON_REPAIR_SOURCE_REPAIR_JSON_STRING: Final[str] = "repair_json_string"
CONST_JSON_REPAIR_SOURCE_EXTRACT_JSON_BLOCK: Final[str] = "extract_json_block"
CONST_JSON_REPAIR_SOURCE_CHAT_STRUCTURED: Final[str] = "chat_structured"


CONST_EXIT_SUCCESS: int = 0
CONST_EXIT_FAILURE: int = 1
CONST_EXIT_USAGE: int = 2
CONST_EXIT_ERROR_INFERENCE: int = 10
# The status the subprocess runners report when the program is not on PATH, as POSIX shells do.
CONST_EXIT_COMMAND_NOT_FOUND: int = 127
# `fnmatch` patterns of the upper-case keys that `build_subprocess_env` refuses from a caller
# (#2205, #2429). Sources: the page above each family, and the sudo env_delete list.
CONST_CODE_LOADING_ENV_PATTERNS: Final[tuple[str, ...]] = (
    # ld.so(8), iconv(1), dyld(1). Each LD_ key, as the sudo env_delete list has it (#2674): the
    # loader keys load a library, and LD_DEBUG_OUTPUT and LD_PROFILE_OUTPUT make it write a file
    "LD_*",
    "GCONV_PATH",
    "DYLD_*",
    # bash(1)
    "BASH_ENV",
    "ENV",
    "BASH_FUNC_*",
    "SHELLOPTS",
    "BASHOPTS",
    "PS4",
    # zsh(1), zshparam(1)
    "ZDOTDIR",
    "FPATH",
    "NULLCMD",
    "READNULLCMD",
    # git(1), git-config(1), git-init(1): each GIT_ key but the ones of CONST_GIT_ACCEPTED_ENV
    "GIT_*",
    # git-var(1), the fall-back keys of GIT_EDITOR and GIT_PAGER
    "VISUAL",
    "EDITOR",
    "PAGER",
    # less(1), the filter that a pager runs
    "LESSOPEN",
    "LESSCLOSE",
    "LESS",
    # the git-mergetool--lib script, which reads a shell file from this directory
    "MERGE_TOOLS_DIR",
    # ssh(1), ssh-add(1), ssh-keygen(1), ssh-agent(1) and the OpenSSH source (#2633): each SSH_ key
    "SSH_*",
    # ssh_config(5): ssh starts this program to run a ProxyCommand, a LocalCommand or a Match exec
    "SHELL",
    # gh and kubectl (#2672). gh help environment: gh starts the program of GH_BROWSER, of its
    # fall-back BROWSER, of GH_EDITOR and of GH_PAGER. GH_PATH is the path that gh auth setup-git
    # writes as the git credential helper, and git starts it. kubectl starts the program of
    # KUBE_EDITOR (kubectl edit) and KUBECTL_EXTERNAL_DIFF (kubectl diff). GH_CONFIG_DIR and
    # KUBECONFIG stay accepted: callers set both, and a caller names a file that it controls.
    "GH_BROWSER",
    "BROWSER",
    "GH_EDITOR",
    "GH_PAGER",
    "GH_PATH",
    "KUBE_EDITOR",
    "KUBECTL_EXTERNAL_DIFF",
    # uv and npm (#2673). Each key names a program, or a directory of programs, that the tool
    # starts: uv starts the interpreter of UV_PYTHON, the bin/python of the environment of
    # VIRTUAL_ENV and UV_PROJECT_ENVIRONMENT, and an interpreter below UV_PYTHON_INSTALL_DIR when
    # it prefers its own Python builds. npm starts the shell of script-shell for each script, passes
    # node-options as NODE_OPTIONS to each script, starts the program of git for a git dependency
    # and of editor for `npm config edit`, starts the shell of `npm explore`, and loads the module
    # of init-module for `npm init`. node-gyp, which `npm install` runs for a package with a
    # binding.gyp, starts the interpreter of npm_config_python and of PYTHON.
    # npm reads `npm_config_script-shell` as `npm_config_script_shell`, so `[_-]` matches both.
    # npm_config_userconfig, npm_config_globalconfig and UV_CONFIG_FILE stay accepted: callers set
    # them, and a caller names a file that it controls.
    "UV_PYTHON",
    "UV_PYTHON_INSTALL_DIR",
    "UV_PROJECT_ENVIRONMENT",
    "VIRTUAL_ENV",
    "NPM_CONFIG_SCRIPT[_-]SHELL",
    "NPM_CONFIG_NODE[_-]OPTIONS",
    "NPM_CONFIG_GIT",
    "NPM_CONFIG_EDITOR",
    "NPM_CONFIG_INIT[_-]MODULE",
    "NPM_CONFIG_SHELL",
    "NPM_CONFIG_PYTHON",
    "PYTHON",
    # The keys that make a child write a file that the caller names (#2674). They load no code.
    # curl(1): curl, git over HTTPS and the ssl module of Python write the TLS secrets of each
    # connection to SSLKEYLOGFILE, and curl writes a QUIC log to the directory of QLOGDIR.
    # node(1): Node.js writes coverage data to the directory of NODE_V8_COVERAGE and its warnings
    # to the file of NODE_REDIRECT_WARNINGS. The LD_ keys of the loader are the pattern above.
    "SSLKEYLOGFILE",
    "QLOGDIR",
    "NODE_V8_COVERAGE",
    "NODE_REDIRECT_WARNINGS",
    # python(1)
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
    "PYTHONPLATLIBDIR",
    "PYTHONPYCACHEPREFIX",
    # node(1)
    "NODE_OPTIONS",
    "NODE_PATH",
    "NODE_COMPILE_CACHE",
    "NODE_REPL_EXTERNAL_MODULE",
    # perlrun(1)
    "PERL5OPT",
    "PERL5LIB",
    "PERLLIB",
    "PERL5DB",
    # ruby(1)
    "RUBYOPT",
    "RUBYLIB",
    # java(1), the JVM TI specification
    "JAVA_TOOL_OPTIONS",
    "JDK_JAVA_OPTIONS",
    "_JAVA_OPTIONS",
    "CLASSPATH",
    # The keys that make a library or Python load a module of the caller (#2503)
    # openssl-env(7): each key. OPENSSL_CONF, OPENSSL_CONF_INCLUDE, OPENSSL_MODULES and
    # OPENSSL_ENGINES name a configuration, a provider directory or an engine directory
    "OPENSSL*",
    # kerberos(7), krb5.conf(5): each key. KRB5_CONFIG names the file with the plug-in modules
    "KRB5*",
    # kerberos(7): the file that lists the GSS-API mechanism libraries
    "GSS_MECH_CONFIG",
    # lib/common.c of Cyrus SASL (_sasl_get_default_path): the plug-in directory
    "SASL_PATH",
    # Modules/getpath.py of CPython: the virtual environment that Python starts from
    "PYTHONEXECUTABLE",
    "__PYVENV_LAUNCHER__",
)
# uv's exit status for a check that ran and failed; it exits 2 when it could not run.
CONST_UV_EXIT_FAILURE: int = 1
# zizmor audits whose findings fail `devops scan workflows` and the `devops ci` gate (#861).
# Every other audit's findings are shown and do not fail it.
CONST_ZIZMOR_BLOCKING_RULES: frozenset[str] = frozenset(
    {"template-injection", "unpinned-uses", "excessive-permissions"}
)
# zizmor's severities (its `Severity` enum, `Unknown` aside), as the scan table names them.
# The GitHub Actions files zizmor audits: `.github/workflows/*.y(a)ml` and `action.y(a)ml`.
CONST_GITHUB_ACTIONS_ROOT: Final[str] = ".github"
CONST_GITHUB_WORKFLOWS_DIRNAME: Final[str] = "workflows"
CONST_GITHUB_ACTION_FILE_STEM: Final[str] = "action"
CONST_YAML_SUFFIXES: Final[tuple[str, ...]] = (".yaml", ".yml")
# The configuration an isolated zizmor scan is handed in place of the scanned tree's: no rules
# changed (#972).
CONST_REVIEW_SCAN_ZIZMOR_CONFIG: Final[str] = "rules: {}\n"
CONST_ZIZMOR_SEVERITIES: Final[dict[str, str]] = {
    "High": "HIGH",
    "Medium": "MEDIUM",
    "Low": "LOW",
    "Informational": "INFO",
}
CONST_EXIT_CANCELLED: int = 130
# The signals that cancel a `devops ci test` run, whose pytest runs in a session of its own that
# no Ctrl-C, terminal hangup or supervisor's SIGTERM reaches (#1669). The run takes over Ctrl-C's
# SIGINT too: `asyncio.run`'s own handler raised KeyboardInterrupt at a second Ctrl-C wherever the
# run was, which could skip the SIGKILL of the stop (#2069).
CONST_CI_RUN_STOP_SIGNAL_NAMES: Final[tuple[str, ...]] = ("SIGINT", "SIGTERM", "SIGHUP")

CONST_MSG_KEYRING_UNAVAILABLE = "OS Keyring service is unavailable; run in headless CI mode"
CONST_MSG_BRANCH_INVALID = "Branch name is invalid"
CONST_MSG_URL_INVALID = "Invalid URL format or scheme"
CONST_MSG_SSRF_RESOLVES_PRIVATE = "Target resolves to a private or loopback network endpoint"

# ── Telemetry Invariants ──────────────────────────────────────────────────────
CONST_OTEL_SCOPE_NAME = "devops-cli.telemetry"
CONST_OTEL_SPAN_KIND_INTERNAL = "internal"
CONST_OTEL_SPAN_KIND_CLIENT = "client"
CONST_OTEL_METRIC_UNIT_ONE = "1"
CONST_OTEL_SERVICE_NAME = "devops-cli"
CONST_OTEL_OTLP_HTTP_PORT = 4318
CONST_OTEL_OTLP_GRPC_PORT = 4317
# The GenAI semantic conventions, which have no tagged release, are pinned to a commit and
# resolved by weaver (the version the conventions repository pins in its versions.env).
CONST_SEMCONV_GENAI_REPO: Final[str] = "open-telemetry/semantic-conventions-genai"
CONST_SEMCONV_GENAI_GIT_URL: Final[str] = (
    "https://github.com/open-telemetry/semantic-conventions-genai.git"
)
CONST_SEMCONV_GENAI_MODEL_DIR: Final[str] = "model"
CONST_SEMCONV_RESOLVED_REGISTRY_FILE: Final[str] = "resolved.yaml"
CONST_SEMCONV_WEAVER_BIN: Final[str] = "weaver"
CONST_SEMCONV_WEAVER_VERSION: Final[str] = "0.26.1"
CONST_URL_WEAVER_RELEASES: Final[str] = "https://github.com/open-telemetry/weaver/releases"
CONST_GIT_COMMIT_SHA_PATTERN: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{40}")
# A quoted string in Python source whose text starts with the GenAI attribute namespace.
CONST_SEMCONV_GENAI_LITERAL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"""(?P<quote>['"])(?P<text>gen_ai\.[^\n]*?)(?P=quote)"""
)
# Python string prefixes are at most two letters (`rb`, `fr`, `tr`). An `f` or `t` among them
# makes the string a template filled in at run time.
CONST_PYTHON_STRING_PREFIX_MAX_LENGTH: Final[int] = 2
CONST_PYTHON_TEMPLATE_STRING_PREFIXES: Final[frozenset[str]] = frozenset({"f", "t"})
# Provider ids whose GenAI `gen_ai.provider.name` well-known value differs from the id.
# Every other id is a custom value the conventions allow, and is written unchanged.
CONST_GENAI_PROVIDER_NAMES: Final[dict[str, str]] = {"claude": "anthropic"}
# The cluster's collector, as k8s/otel deploys it.
CONST_OTEL_COLLECTOR_NAMESPACE = "otel"
# The labels the opentelemetry-collector chart gives the `otel-collector` release's pods. Both
# are needed: Tempo runs in the same namespace and listens on the same OTLP ports.
CONST_OTEL_COLLECTOR_POD_LABELS: Final[dict[str, str]] = {
    "app.kubernetes.io/name": "opentelemetry-collector",
    "app.kubernetes.io/instance": "otel-collector",
}
CONST_OTEL_COLLECTOR_SERVICE = "otel-collector-opentelemetry-collector"
# The Valkey holding the shared run index (k8s/llm/valkey-runs.yaml), and the Kubernetes object
# that holds its password.
CONST_RUNS_INDEX_NAMESPACE = "llm"
CONST_RUNS_INDEX_SERVICE = "valkey-runs"
CONST_RUNS_INDEX_AUTH_OBJECT = "valkey-runs-auth"

# ── Network Reference & Egress Security Invariants ────────────────────────────
# httpx2 request extension carrying a caller's egress policy, a callable the HTTP broker's request
# hook calls with each hop's URL before that hop is sent
CONST_HTTP_EGRESS_POLICY_EXTENSION: Final[str] = "egress_policy"
# RFC 2606 Reserved Top-Level Domains for testing & documentation
CONST_RFC2606_RESERVED_TLDS: frozenset[str] = frozenset(
    {
        "test",
        "example",
        "invalid",
    }
)

# RFC 2606 and RFC 6761 Reserved Second-Level Domains
CONST_RFC2606_RESERVED_DOMAINS: frozenset[str] = frozenset(
    {
        "example.com",
        "example.org",
        "example.net",
        "example.edu",
    }
)

# Special-use and private infrastructure TLDs / suffixes (RFC 6762, RFC 8375, Kubernetes)
CONST_SPECIAL_USE_TLDS: frozenset[str] = frozenset(
    {
        "local",
        "internal",
        "lan",
        "corp",
        "home.arpa",
        "onion",
        "arpa",
        "cluster.local",
        "localdomain",
        "svc",
    }
)

# Authoritative public registries and documentation schemas excluded from external egress audits
CONST_EXCLUDED_PUBLIC_REGISTRIES: frozenset[str] = frozenset(
    {
        "schema.org",
        "w3.org",
        "json-schema.org",
        "opencontainers.org",
        "github.com",
        "gitlab.com",
        "bitbucket.org",
        "pypi.org",
        "pypi.python.org",
        "pythonhosted.org",
        "files.pythonhosted.org",
        "npmjs.com",
        "npmjs.org",
        "registry.npmjs.org",
        "yarnpkg.com",
        "registry.yarnpkg.com",
        "crates.io",
        "static.crates.io",
        "golang.org",
        "pkg.go.dev",
        "proxy.golang.org",
        "sum.golang.org",
        "rubygems.org",
        "maven.org",
        "apache.org",
        "gradle.org",
        "packagist.org",
        "nuget.org",
        "google.com",
        "osv.dev",
        "nist.gov",
        "shodan.io",
        "cloudflare.com",
    }
)


# ── Review Finding Consolidation Signals ─────────────────────────────────────
# Identifiers too generic to prove two findings describe the same defect. Kept here
# (never inline) so the list stays auditable for over-matching, per the brittle-subset
# prohibition: it only ever *weakens* a duplicate signal, never invalidates a finding.
REVIEW_GENERIC_SYMBOL_STOPWORDS: Final[frozenset[str]] = frozenset(
    {
        "the",
        "and",
        "not",
        "for",
        "with",
        "this",
        "that",
        "from",
        "into",
        "when",
        "self",
        "none",
        "true",
        "false",
        "str",
        "int",
        "dict",
        "list",
        "set",
        "any",
        "type",
        "class",
        "def",
        "return",
        "value",
        "values",
        "name",
        "names",
        "data",
        "path",
        "paths",
        "file",
        "files",
        "line",
        "lines",
        "code",
        "test",
        "tests",
        "error",
        "errors",
        "exception",
        "result",
        "results",
        "config",
        "settings",
        "method",
        "function",
        "module",
        "object",
        "param",
        "params",
        "arg",
        "args",
        "kwargs",
        "input",
        "output",
        "call",
        "calls",
        "user",
        "users",
        "http",
        "https",
        "api",
        "url",
        "urls",
        "time",
        "size",
        "count",
        "index",
        "key",
        "keys",
        "item",
        "items",
        "state",
        "status",
        "message",
        "messages",
        "log",
        "logs",
        "logger",
    }
)

# ── Executable Verification Criteria Constants ──────────────────────────────
# Closed, read-only allowlist of executable binaries for finding verification criteria. Each one
# resolves inside the host sandbox: the system's under `/usr`, and python, python3 and ruff from
# the reviewed repository's `.venv/bin`. pytest is not offered (see `CONST_PYTEST_MODULES`): a
# passing existing test demonstrates no defect.
CONST_ALLOWED_CRITERIA_BINARIES: Final[frozenset[str]] = frozenset(
    {
        "cat",
        "find",
        "git",
        "grep",
        "head",
        "jq",
        "python",
        "python3",
        "ruff",
        "tail",
        "test",
        "wc",
        "[",
    }
)

# The allowlisted criteria binaries that run Python, which take a `-c` or `-m` argument and
# run under the Python criteria time limit.
CONST_PYTHON_CRITERIA_BINARIES: Final[frozenset[str]] = frozenset({"python", "python3"})

# Read-only git subcommands permitted in verification criteria.
CONST_ALLOWED_GIT_SUBCOMMANDS: Final[frozenset[str]] = frozenset(
    {
        "check-ignore",
        "diff",
        "grep",
        "log",
        "ls-files",
        "show",
        "status",
    }
)

# Shell metacharacters and operators disallowed in executable criteria commands.
CONST_DISALLOWED_SHELL_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "|",
        "||",
        "&",
        "&&",
        ";",
        ">",
        ">>",
        "<",
        "<<",
        "`",
        "$(",
        "${",
    }
)

# pytest and its implementation package, and the functions that start its test runner. A python
# criterion may import pytest, for `pytest.raises` or a test module that imports it, but may not
# run tests, either as `python -m pytest` or by calling `pytest.main` in `python -c`, whose exit
# status that call does not even set: a passing existing test demonstrates no defect.
CONST_PYTEST_MODULES: Final[frozenset[str]] = frozenset({"_pytest", "pytest"})
CONST_PYTEST_RUNNER_FUNCTIONS: Final[frozenset[str]] = frozenset({"console_main", "main"})
# Calls that import a module by its name as a string (`__import__('pytest')`).
CONST_IMPORT_BY_NAME_CALLS: Final[frozenset[str]] = frozenset({"__import__", "import_module"})

# `find` actions that run a command, which may be any binary rather than an allowlisted one, or
# that write or delete files. A `find` criterion may only search.
CONST_FORBIDDEN_FIND_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "-delete",
        "-exec",
        "-execdir",
        "-fls",
        "-fprint",
        "-fprint0",
        "-fprintf",
        "-ok",
        "-okdir",
    }
)

# Forbidden module names in Python AST for python -c criteria commands to prevent side effects.
CONST_FORBIDDEN_PYTHON_CRITERIA_MODULES: Final[frozenset[str]] = frozenset(
    {
        "ftplib",
        "http",
        "posix",
        "pty",
        "requests",
        "shutil",
        "socket",
        "subprocess",
        "telnetlib",
        "urllib",
    }
)


# ── Review Schemas ──────────────────────────────────────────────────────────────
CONST_REVIEW_PROMPT_PLACEHOLDER_BASENAMES: Final[frozenset[str]] = frozenset(
    {"file.ext", "filename.ext", "path/to/file.ext", "src/file.py", "path/to/file.py", "example.py"}
)

CONST_REVIEW_TITLE_FILLER_WORDS: Final[frozenset[str]] = frozenset(
    {
        "missing",
        "lack",
        "lacks",
        "lacking",
        "absent",
        "potential",
        "possible",
        "possibly",
        "insecure",
        "unsafe",
        "improper",
        "improperly",
        "incorrect",
        "inadequate",
        "insufficient",
        "weak",
        "issue",
        "issues",
        "risk",
        "risks",
        "vulnerability",
        "vulnerable",
        "problem",
        "use",
        "uses",
        "using",
        "usage",
        "without",
        "not",
        "the",
        "and",
        "for",
        "with",
        "from",
        "via",
        "into",
        "when",
        "may",
        "can",
        "could",
        "due",
        "are",
        "has",
        "have",
        "does",
        "should",
    }
)


# ── Unified Secret Resolution & Vault Lease Lifecycle ────────────────────────
# Provider identifiers recorded in the credential access audit trail.
CONST_SECRET_PROVIDER_KEYRING: Final[str] = "keyring"
CONST_SECRET_PROVIDER_VAULT: Final[str] = "vault"
CONST_SECRET_PROVIDER_ENVIRONMENT: Final[str] = "environment"
CONST_SECRET_PROVIDER_SETTINGS: Final[str] = "settings"

# Upper bound on retained credential access records, preventing unbounded growth in
CONST_SECRET_AUDIT_MAX_ENTRIES: Final[int] = 1000

# Vault API paths. Fixed by the Vault HTTP API, so this set is closed and exhaustive.
CONST_VAULT_API_PREFIX: Final[str] = "/v1"
# Conventional KV-v2 mount and folder holding this project's managed credentials.
CONST_VAULT_SECRET_MOUNT: Final[str] = "secret/data/devops-cli"
CONST_VAULT_PATH_APPROLE_LOGIN: Final[str] = "auth/approle/login"
CONST_VAULT_PATH_KUBERNETES_LOGIN: Final[str] = "auth/kubernetes/login"

# Supported Vault authentication methods, closed by what this CLI implements.
CONST_VAULT_AUTH_METHODS: Final[frozenset[str]] = frozenset({"approle", "kubernetes"})
CONST_VAULT_PATH_TOKEN_RENEW_SELF: Final[str] = "auth/token/renew-self"
CONST_VAULT_PATH_TOKEN_REVOKE_SELF: Final[str] = "auth/token/revoke-self"
CONST_VAULT_PATH_HEALTH: Final[str] = "sys/health"
CONST_VAULT_PATH_LEASE_RENEW: Final[str] = "sys/leases/renew"
CONST_VAULT_PATH_LEASE_REVOKE: Final[str] = "sys/leases/revoke"

# The keyring entry `devops vault login` writes: one record holding the token and the address
# and namespace that issued it. It keeps the name a bare token was stored under before the
# record existed, so such an entry is found and reported as unusable rather than ignored.
CONST_VAULT_LOGIN_KEYRING_KEY: Final[str] = "vault_token"
# Environment variables a Vault token is read from, in order, after the stored login.
CONST_VAULT_TOKEN_ENV_VARS: Final[tuple[str, ...]] = ("VAULT_TOKEN", "DEVOPS_CLI_VAULT_TOKEN")
# Credential ids the broker's two token lookups are audited under.
CONST_VAULT_LOGIN_CREDENTIAL_ID: Final[str] = "vault.login"
CONST_VAULT_TOKEN_CREDENTIAL_ID: Final[str] = "vault.token"
# Where the broker's token came from, beside the keyring and environment provider names. The
# set is closed: a token is passed in, read from one of the two providers, or absent.
CONST_VAULT_TOKEN_SOURCE_ARGUMENT: Final[str] = "argument"
CONST_VAULT_TOKEN_SOURCE_NONE: Final[str] = "none"
# Statuses with which Vault refuses the token a request carried: missing, expired, revoked, or
# without a policy for the path. Fixed by the Vault HTTP API.
CONST_VAULT_TOKEN_REJECTED_STATUSES: Final[frozenset[int]] = frozenset({401, 403})

# Default in-cluster ServiceAccount token projected into every Kubernetes pod.
CONST_KUBERNETES_SA_TOKEN_PATH: Final[str] = "/var/run/secrets/kubernetes.io/serviceaccount/token"

# ── Grafana Dashboard Schema ─────────────────────────────────────────────────
# Grafana lays dashboards out on a fixed 24-column grid; a panel extending past it is
# clipped rather than wrapped.
CONST_GRAFANA_DASHBOARD_GRID_WIDTH: Final[int] = 24
# Dashboard JSON schema version targeted by the generated models (Grafana 10+).
CONST_GRAFANA_SCHEMA_VERSION: Final[int] = 39
CONST_GRAFANA_DEFAULT_DATASOURCE_TYPE: Final[str] = "prometheus"

# Panel types emitted by the builder library.
CONST_GRAFANA_PANEL_TYPE_TIMESERIES: Final[str] = "timeseries"
CONST_GRAFANA_PANEL_TYPE_STAT: Final[str] = "stat"
CONST_GRAFANA_PANEL_TYPE_ROW: Final[str] = "row"

# ── PromQL Structural Validation ─────────────────────────────────────────────
# Bracket pairs used by the PromQL grammar. Closed and exhaustive: these are the only
# grouping delimiters the language defines.
CONST_PROMQL_BRACKET_PAIRS: Final[dict[str, str]] = {"(": ")", "[": "]", "{": "}"}

# Quote characters that open a PromQL string literal.
CONST_PROMQL_QUOTE_CHARS: Final[frozenset[str]] = frozenset({'"', "'", "`"})

# Duration units defined by the PromQL time-duration grammar. Closed and exhaustive per
# the Prometheus query language specification.
CONST_PROMQL_DURATION_UNITS: Final[frozenset[str]] = frozenset({"ms", "s", "m", "h", "d", "w", "y"})

# Keywords that open a parenthesised list of label names: aggregation modifiers and
# vector-matching modifiers. Closed and exhaustive per the PromQL grammar.
CONST_PROMQL_GROUPING_KEYWORDS: Final[frozenset[str]] = frozenset(
    {"by", "without", "on", "ignoring", "group_left", "group_right"}
)

# The modifiers that may follow an aggregation operator's name, as in `sum by (job) (x)`.
CONST_PROMQL_AGGREGATION_MODIFIERS: Final[frozenset[str]] = frozenset({"by", "without"})

# Every word the PromQL lexer reads as a keyword or a number rather than a metric name:
# the grouping keywords, the set and arithmetic operators spelled as words, the `bool` and
# `offset` modifiers, and the `Inf` and `NaN` number literals. Matched case-insensitively,
# as the lexer does.
CONST_PROMQL_KEYWORDS: Final[frozenset[str]] = CONST_PROMQL_GROUPING_KEYWORDS | frozenset(
    {"and", "or", "unless", "atan2", "bool", "offset", "inf", "nan"}
)

# ── Cache Key Namespacing ────────────────────────────────────────────────────
# Root prefix for every cache key this project writes, so a shared Valkey instance can
# be swept per-project and keys never collide with another tenant's.
CONST_CACHE_NAMESPACE_ROOT: Final[str] = "devops-cli"

# ── Source & Test Tree Layout ────────────────────────────────────────────────
# Repository layout conventions used to map changed sources onto covering tests.
CONST_SOURCE_ROOT_DIR: Final[str] = "src"
CONST_TESTS_ROOT_DIR: Final[str] = "tests"
CONST_TEST_FILE_PREFIX: Final[str] = "test_"
CONST_PYTHON_FILE_SUFFIX: Final[str] = ".py"
CONST_PYTHON_SOURCE_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyi"})
# A pytest fixture file: a change to one reaches every test beside and below it.
CONST_CONFTEST_FILENAME: Final[str] = "conftest.py"
# The prefix of every name pytest reads from a conftest as a hook, `pytest_plugins` included:
# its plugin manager registers a module's `pytest_*` attributes and nothing else, and calls such a
# hook for every test, so a conftest binding one reaches tests outside its directory (#1312).
CONST_PYTEST_HOOK_PREFIX: Final[str] = "pytest_"
# The name of pytest's fixture decorator, `pytest.fixture` or `from pytest import fixture`, and of
# the plugins' that wrap it (`pytest_asyncio.fixture`): a test module's helper that names it may
# register a fixture, which reaches tests that never import the helper (#1312).
CONST_PYTEST_FIXTURE_NAME: Final[str] = "fixture"
# Files whose change can alter the outcome of tests that never import them, so a change to one
# defeats the coverage index and forces a full `devops ci` run.
CONST_FULL_RUN_TRIGGER_NAMES: Final[frozenset[str]] = frozenset(
    {CONST_CONFTEST_FILENAME, "pyproject.toml", "uv.lock", ".python-version"}
)

# ── Mutation Testing (mutmut 3.8, `devops ci mutate`) ────────────────────────
# How mutmut names what it mutates, a closed domain it defines (`mangle_function_name`): a
# module-level function is `<module>.x_<function>`, a method of a module-level class
# `<module>.xǁ<Class>ǁ<method>`, and each of their mutants that name, `__mutmut_` and a number.
CONST_MUTMUT_FUNCTION_PREFIX: Final[str] = "x_"
CONST_MUTMUT_CLASS_SEPARATOR: Final[str] = "ǁ"
CONST_MUTMUT_METHOD_PREFIX: Final[str] = f"x{CONST_MUTMUT_CLASS_SEPARATOR}"
CONST_MUTMUT_MUTANT_INFIX: Final[str] = "__mutmut_"
# mutmut leaves a decorated function alone unless this is its one, bare, decorator.
CONST_MUTMUT_MUTABLE_DECORATORS: Final[frozenset[str]] = frozenset({"staticmethod", "classmethod"})
# The function names mutmut never mutates (`NEVER_MUTATE_FUNCTION_NAMES`).
CONST_MUTMUT_NEVER_MUTATED_NAMES: Final[frozenset[str]] = frozenset(
    {"__getattribute__", "__setattr__", "__new__"}
)
# `mutmut results` statuses: those the report counts, and those of a mutant no test killed.
CONST_MUTMUT_COUNTED_STATUSES: Final[tuple[str, ...]] = (
    "killed",
    "survived",
    "timeout",
    "no tests",
)
CONST_MUTMUT_SURVIVING_STATUSES: Final[tuple[str, ...]] = ("survived", "no tests")

# ── Fail-to-Pass Test Replay (`devops ci fail-to-pass`, #844) ────────────────
# A changed test file that imports a module the fix adds cannot be collected on base; without
# `--continue-on-collection-errors` pytest then runs none of the other changed files (#861).
CONST_FAIL_TO_PASS_PYTEST_FLAGS: Final[tuple[str, ...]] = (
    "-o",
    "addopts=",
    "-p",
    "no:cacheprovider",
    "--continue-on-collection-errors",
)
CONST_FAIL_TO_PASS_JUNIT_TAG_STATUS: Final[dict[str, str]] = {
    "failure": "failed",
    "error": "errored",
    "skipped": "skipped",
}
# The root element pytest's `--junitxml` report closes last; a report that never closes it is
# empty or was cut short, and holds no complete replay (#1669).
CONST_FAIL_TO_PASS_JUNIT_ROOT_TAG: Final[str] = "testsuites"
# pytest's exit statuses (`pytest.ExitCode`) for a run that stopped before reporting the tests it
# was given: interrupted (2), internal error (3) and usage error (4). A replay ending so could not
# run on base; exit 5, no tests collected, is an empty replay (#1669).
CONST_FAIL_TO_PASS_COULD_NOT_RUN_EXIT_STATUSES: Final[frozenset[int]] = frozenset({2, 3, 4})

# ── Terraform / OpenTofu HCL AST Analysis ────────────────────────────────────
# HCL configuration file extensions recognised by Terraform and OpenTofu.
CONST_HCL_FILE_EXTENSIONS: Final[tuple[str, ...]] = (".tf",)
# Candidate state file names, in the order Terraform and OpenTofu resolve them.
CONST_TF_STATE_FILE_NAMES: Final[tuple[str, ...]] = (
    "terraform.tfstate",
    ".terraform/terraform.tfstate",
)
# Top-level key of the file `init` writes to `.terraform/terraform.tfstate` to cache a configured
# backend: that file records where state lives, not the resources it tracks.
CONST_TF_BACKEND_CACHE_KEY: Final[str] = "backend"

# Top-level HCL block types. This set is closed and exhaustive: it is fixed by the
# Terraform and OpenTofu configuration language grammar, not inferred from samples.
CONST_HCL_BLOCK_RESOURCE: Final[str] = "resource"
CONST_HCL_BLOCK_DATA: Final[str] = "data"
CONST_HCL_BLOCK_MODULE: Final[str] = "module"
CONST_HCL_BLOCK_VARIABLE: Final[str] = "variable"
CONST_HCL_BLOCK_OUTPUT: Final[str] = "output"
# Marker key `python-hcl2` injects to distinguish blocks from plain attribute maps.
CONST_HCL_BLOCK_MARKER: Final[str] = "__is_block__"

# Traversal prefixes that do NOT address another resource, so they create no dependency
# edge. Closed and exhaustive: these are the named values defined by the configuration
# language's expression grammar, not an inferred subset.
CONST_HCL_NON_RESOURCE_NAMESPACES: Final[frozenset[str]] = frozenset(
    {"var", "local", "each", "count", "path", "self", "terraform"}
)

# ── Argo CRD Group, Version & Resource Plurals ───────────────────────────────
# The Argo project serves Applications, ApplicationSets, Rollouts, AnalysisRuns,
# and Workflows from a single API group. These identifiers are fixed by the
# published Argo CRD manifests, so the set is closed and exhaustive.
CONST_ARGO_API_GROUP: Final[str] = "argoproj.io"
CONST_ARGO_API_VERSION: Final[str] = "v1alpha1"

CONST_ARGO_PLURAL_APPLICATIONS: Final[str] = "applications"
CONST_ARGO_PLURAL_APPLICATION_SETS: Final[str] = "applicationsets"
CONST_ARGO_PLURAL_ROLLOUTS: Final[str] = "rollouts"
CONST_ARGO_PLURAL_ANALYSIS_RUNS: Final[str] = "analysisruns"
CONST_ARGO_PLURAL_WORKFLOWS: Final[str] = "workflows"

# Argo Rollouts control-plane fields. The rollouts controller watches these
# exact fields to drive promotion, abort, and restart, which is what the
# `kubectl argo rollouts` plugin patches on the user's behalf.
CONST_ROLLOUT_FIELD_ABORT: Final[str] = "abort"
CONST_ROLLOUT_FIELD_PROMOTE_FULL: Final[str] = "promoteFull"
CONST_ROLLOUT_FIELD_PAUSE_CONDITIONS: Final[str] = "pauseConditions"
CONST_ROLLOUT_FIELD_CONTROLLER_PAUSE: Final[str] = "controllerPause"
CONST_ROLLOUT_FIELD_RESTART_AT: Final[str] = "restartAt"

# Terminal Argo Workflow phases. Closed set defined by the Argo Workflows
# controller's `status.phase` enumeration.
CONST_ARGO_WORKFLOW_PHASE_SUCCEEDED: Final[str] = "Succeeded"
CONST_ARGO_WORKFLOW_PHASE_FAILED: Final[str] = "Failed"
CONST_ARGO_WORKFLOW_PHASE_ERROR: Final[str] = "Error"

CONST_ARGO_WORKFLOW_FAILURE_PHASES: Final[frozenset[str]] = frozenset(
    {CONST_ARGO_WORKFLOW_PHASE_FAILED, CONST_ARGO_WORKFLOW_PHASE_ERROR}
)
CONST_ARGO_WORKFLOW_TERMINAL_PHASES: Final[frozenset[str]] = (
    CONST_ARGO_WORKFLOW_FAILURE_PHASES | frozenset({CONST_ARGO_WORKFLOW_PHASE_SUCCEEDED})
)

# Argo Workflows pod naming conventions and defaults.
CONST_ARGO_ANNOTATION_POD_NAME_FORMAT: Final[str] = "workflows.argoproj.io/pod-name-format"
CONST_ARGO_POD_NAME_V1: Final[str] = "v1"
CONST_ARGO_POD_NAME_V2: Final[str] = "v2"
CONST_ARGO_SKIPPED_PHASES: Final[frozenset[str]] = frozenset({"Skipped", "Omitted"})
CONST_ARGO_DEFAULT_LOG_CONTAINER: Final[str] = "main"

CONST_FNV_OFFSET_BASIS_32: Final[int] = 2166136261
CONST_FNV_PRIME_32: Final[int] = 16777619
CONST_MAX_K8S_RESOURCE_NAME_LENGTH: Final[int] = 253
CONST_K8S_NAMING_HASH_LENGTH: Final[int] = 10
CONST_MAX_POD_NAME_PREFIX_LENGTH: Final[int] = (
    CONST_MAX_K8S_RESOURCE_NAME_LENGTH - CONST_K8S_NAMING_HASH_LENGTH
)

# ── Docker Engine Socket API & BuildKit Cache Introspection ──────────────────
# Container CPU utilisation severity thresholds for live stats rendering.
CONST_DOCKER_CPU_WARNING_PERCENT: Final[float] = 50.0
CONST_DOCKER_CPU_CRITICAL_PERCENT: Final[float] = 80.0

# The scheme docker-py's `parse_host` gives a unix socket endpoint; its client then speaks over
# the socket its `UnixHTTPAdapter` derives from that URL.
CONST_DOCKER_UNIX_ADAPTER_SCHEME: Final[str] = "http+unix"

# `GET /system/df` object types returned by the Engine API disk-usage endpoint.
CONST_DOCKER_DF_BUILD_CACHE_KEY: Final[str] = "BuildCache"
# BuildKit build-cache record types emitted by `GET /system/df` (buildkit solver
# vertex classes). Exhaustive per the BuildKit cache record schema.
CONST_DOCKER_BUILD_CACHE_TYPES: Final[frozenset[str]] = frozenset(
    {
        "internal",
        "frontend",
        "source.local",
        "source.git.checkout",
        "exec.cachemount",
        "regular",
    }
)

# Podman socket paths and engine discovery constants
CONST_PODMAN_ROOTFUL_SOCKET_PATH: Final[Path] = Path("/run/podman/podman.sock")
CONST_RUN_USER_BASE: Final[Path] = Path("/run/user")
CONST_PODMAN_SOCKET_RELATIVE_PATH: Final[Path] = Path("podman/podman.sock")
CONST_DOCKER_DEFAULT_UNIX_SOCKET: Final[str] = "/var/run/docker.sock"
CONST_PODMAN_ENGINE_COMPONENT_NAME: Final[str] = "Podman Engine"
CONST_SECURITY_OPT_ROOTLESS: Final[str] = "name=rootless"

# Sensitive host configuration and credential directories forbidden from container sandbox mounts
CONST_SANDBOX_SENSITIVE_SUBPATHS: Final[frozenset[str]] = frozenset(
    {
        ".ssh",
        ".aws",
        ".kube",
        ".git",
    }
)
# The system runtime root, where rootful engine sockets and each user's runtime directory
# (`/run/user/<uid>`, with its session bus) live. A sandbox workspace never overlaps it, nor
# $XDG_RUNTIME_DIR, nor the engine socket's directory (#1115). Only the sandbox check refuses it:
# subprocess working directories and every other `CONST_FORBIDDEN_SYSTEM_DIRS` caller do not.
CONST_SANDBOX_RUNTIME_ROOT: Final[Path] = Path("/run")
CONST_XDG_RUNTIME_DIR_ENV_VAR: Final[str] = "XDG_RUNTIME_DIR"
# The user's SSH agent socket directory and the X11 socket directory. A sandbox workspace never
# is or holds either (#1384); a workspace under one is still mounted.
CONST_SSH_AUTH_SOCK_ENV_VAR: Final[str] = "SSH_AUTH_SOCK"
CONST_X11_SOCKET_DIR: Final[Path] = Path("/tmp/.X11-unix")  # nosec B108 # the fixed X11 socket directory that X servers create; read, not written

# Multi-tier sandbox networking mode constants
CONST_SANDBOX_NETWORK_ISOLATED: Final[str] = "isolated"
CONST_SANDBOX_NETWORK_NAMESPACE: Final[str] = "sandbox_namespace"
CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST: Final[str] = "public_whitelist"
CONST_SANDBOX_NETWORK_LOCAL_WHITELIST: Final[str] = "local_whitelist"
CONST_SANDBOX_NETWORK_BRIDGE: Final[str] = "bridge"

# The TCP port a whitelist entry that names none opens, by URL scheme ("" for no scheme). Any
# other scheme has no default, so its entry must name a port.
CONST_SANDBOX_WHITELIST_DEFAULT_PORTS: Final[dict[str, int]] = {"": 443, "https": 443, "http": 80}
# The network modes whose NetworkPolicy can take the opt-in egress rule to the OTel collector:
# isolated has no egress to add it to, and bridge already allows all of it.
CONST_SANDBOX_COLLECTOR_LANE_MODES: Final[tuple[str, ...]] = (
    CONST_SANDBOX_NETWORK_NAMESPACE,
    CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST,
    CONST_SANDBOX_NETWORK_LOCAL_WHITELIST,
)
CONST_SANDBOX_DOCKER_INTERNAL_NET: Final[str] = "devops-sandbox-net"
# The Docker network each network mode runs on: none, the egress-denied internal bridge, or the
# default bridge. The whitelist modes run on the internal bridge, behind the egress proxy.
CONST_SANDBOX_DOCKER_NETWORK_BY_MODE: Final[dict[str, str]] = {
    CONST_SANDBOX_NETWORK_ISOLATED: "none",
    CONST_SANDBOX_NETWORK_NAMESPACE: CONST_SANDBOX_DOCKER_INTERNAL_NET,
    CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST: CONST_SANDBOX_DOCKER_INTERNAL_NET,
    CONST_SANDBOX_NETWORK_LOCAL_WHITELIST: CONST_SANDBOX_DOCKER_INTERNAL_NET,
    CONST_SANDBOX_NETWORK_BRIDGE: "bridge",
}

# Exit status reported when a sandbox workload exceeds its wall-clock budget,
# matching the conventional GNU coreutils `timeout` termination code.
CONST_SANDBOX_TIMEOUT_EXIT_CODE: Final[int] = 124

CONST_SANDBOX_NETWORK_MODES: Final[frozenset[str]] = frozenset(
    {
        CONST_SANDBOX_NETWORK_ISOLATED,
        CONST_SANDBOX_NETWORK_NAMESPACE,
        CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST,
        CONST_SANDBOX_NETWORK_LOCAL_WHITELIST,
        CONST_SANDBOX_NETWORK_BRIDGE,
    }
)

CONST_SANDBOX_NETWORK_MODE_ALIASES: Final[dict[str, str]] = {
    "isolated": CONST_SANDBOX_NETWORK_ISOLATED,
    "none": CONST_SANDBOX_NETWORK_ISOLATED,
    "isolated_pod": CONST_SANDBOX_NETWORK_ISOLATED,
    "isolated-pod": CONST_SANDBOX_NETWORK_ISOLATED,
    "sandbox_namespace": CONST_SANDBOX_NETWORK_NAMESPACE,
    "sandbox-namespace": CONST_SANDBOX_NETWORK_NAMESPACE,
    "namespace": CONST_SANDBOX_NETWORK_NAMESPACE,
    "internal": CONST_SANDBOX_NETWORK_NAMESPACE,
    "public_whitelist": CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST,
    "public-whitelist": CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST,
    "public": CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST,
    "local_whitelist": CONST_SANDBOX_NETWORK_LOCAL_WHITELIST,
    "local-whitelist": CONST_SANDBOX_NETWORK_LOCAL_WHITELIST,
    "local": CONST_SANDBOX_NETWORK_LOCAL_WHITELIST,
    "bridge": CONST_SANDBOX_NETWORK_BRIDGE,
}

# Falco runtime security severity hierarchy
CONST_FALCO_SEVERITY_LEVELS: Final[dict[str, int]] = {
    "DEBUG": 0,
    "INFO": 1,
    "INFORMATIONAL": 1,
    "NOTICE": 2,
    "WARNING": 3,
    "ERROR": 4,
    "CRITICAL": 5,
    "ALERT": 6,
    "EMERGENCY": 7,
}

CONST_MIN_SECURITY_STREAM_DURATION: Final[int] = 1
CONST_MAX_SECURITY_STREAM_DURATION: Final[int] = 3600
CONST_MIN_SECURITY_STREAM_TAIL_LINES: Final[int] = 1
CONST_MAX_SECURITY_STREAM_TAIL_LINES: Final[int] = 10000

# Characters of a failed scanner's non-JSON stdout quoted in its reason; `ScanOutcome` caps the
# whole reason at CONST_MAX_ERROR_DETAIL_LENGTH
CONST_SCANNER_STDOUT_EXCERPT_CHARS: Final[int] = 100

# Threat intelligence distributed caching
CONST_THREAT_INTEL_CACHE_PREFIX: Final[str] = "valkey:threat_intel:domain"

# RAG embedding distributed caching
CONST_VALKEY_EMBEDDING_PREFIX: Final[str] = "valkey:rag:embedding"

# The schemes of a Valkey URL. Every other scheme is refused, also those that valkey-py reads.
CONST_VALKEY_SCHEMES: Final[frozenset[str]] = frozenset({"valkey", "valkeys"})

# The scheme of a Valkey URL that connects over TLS
CONST_VALKEY_TLS_SCHEME: Final[str] = "valkeys"

# The one query key that a Valkey URL can hold: the database, as in `valkey://example.com/?db=2`
CONST_VALKEY_URL_QUERY_KEYS: Final[frozenset[str]] = frozenset({"db"})

# Characters of a failed embedding reply's body quoted in its EmbeddingsError
CONST_EMBEDDING_REPLY_EXCERPT_CHARS: Final[int] = 500

# Canonical embedding dimensions for widely used embedding models, used to size a collection when
# the model cannot be probed
CONST_KNOWN_EMBEDDING_DIMENSIONS: Final[dict[str, int]] = {
    "bge-m3": 1024,
    "bge-large": 1024,
    "bge-base": 768,
    "bge-small": 384,
    "nomic-embed-text": 768,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "all-minilm": 384,
    "qwen3-embedding": 1024,
    "embeddinggemma": 768,
}

# Asymmetric task prefix for Qwen3-Embedding queries
CONST_QWEN3_EMBEDDING_QUERY_PREFIX: Final[str] = (
    "Instruct: Given a code search query, retrieve relevant code or documentation\nQuery:"
)

# Known lockfile basenames skipped by RAG indexer
CONST_RAG_SKIPPED_LOCKFILES: Final[frozenset[str]] = frozenset(
    {"package-lock.json", "pnpm-lock.yaml", "go.sum"}
)

# Safety limit for maximum chunk size in estimated tokens sent to embedding models
CONST_RAG_MAX_CHUNK_TOKENS: Final[int] = 8192

# How many of a file's symbol names follow its path in a lookup in the code index: the context
# `ai/analyze/outlines.py` asks the index for and the query the embedding benchmark makes of a
# code chunk.
CONST_INDEX_LOOKUP_SYMBOLS: Final[int] = 5

# The only symbol of the chunk holding a Python file's imports and docstring, ahead of its first
# definition: a marker the chunker puts there, not a name the file defines.
CONST_CHUNK_MODULE_PREAMBLE_SYMBOL: Final[str] = "<module>"

# Consecutive transient embedding failures before pausing RAG lookups
CONST_RAG_CIRCUIT_BREAKER_FAILURES: Final[int] = 3

# Duration in seconds to pause RAG lookups when circuit breaker opens
CONST_RAG_CIRCUIT_BREAKER_PAUSE_SECONDS: Final[float] = 60.0

# Project identifier used for bundled DevOps CLI Knowledge Base chunks in Qdrant
CONST_RAG_KB_PROJECT: Final[str] = "devops-cli-kb"

# Payload fields indexed when ensuring collections in Qdrant (#1388, #1389)
CONST_RAG_PAYLOAD_INDEXES: Final[tuple[dict[str, Any], ...]] = (
    {"field_name": "project_name", "field_schema": "keyword", "is_tenant": True},
    {"field_name": "file_path", "field_schema": "keyword"},
)

# Helm releases that deploy DaemonSets across all cluster nodes
CONST_HELM_DAEMONSET_RELEASES: Final[frozenset[str]] = frozenset(
    {"k8s-monitoring", "dcgm-exporter"}
)

# Helm releases teardown-stack leaves installed: deleting a CRD deletes every object of its kind
# in the cluster, so uninstalling the Prometheus Operator CRDs would delete every ServiceMonitor
CONST_HELM_TEARDOWN_RETAINED_RELEASES: Final[frozenset[str]] = frozenset(
    {"prometheus-operator-crds"}
)

# The minimum supported Helm CLI version for Kubernetes stack deployments (#1438)
CONST_HELM_MIN_VERSION: Final[str] = "3.17.0"

# What a gh request writes (#1125, `github/request_classifier.py`). Uncertain requests count as
# writes, so a high-level command reads only when its verb is a read verb or its group only reads.
CONST_GH_READ_VERBS: Final[frozenset[str]] = frozenset(
    {
        "view",
        "list",
        "status",
        "checks",
        "diff",
        "show",
        "item-list",
        "field-list",
    }
)
CONST_GH_READ_GROUPS: Final[frozenset[str]] = frozenset({"search"})
# The value flags gh takes before a high-level command's verb (`gh -R o/r issue list`,
# `gh project --owner o item-list 2`), so the verb parser skips them and their values.
CONST_GH_COMMAND_VALUE_FLAGS: Final[tuple[tuple[str, ...], ...]] = (
    ("-R", "--repo"),
    ("--owner",),
)

# `gh api` as `gh api --help` documents it (gh 2.102.0): the method is GET, or POST when a field
# or `--input` is given; `-F key=@path` and `--input path` read a file, `-` meaning stdin; the
# `graphql` endpoint takes its document and operation name from the `query` and `operationName`
# fields or body keys.
CONST_GH_API_SUBCOMMAND: Final[str] = "api"
CONST_GH_API_GRAPHQL_ENDPOINT: Final[str] = "graphql"
CONST_GH_API_DEFAULT_METHOD: Final[str] = "GET"
CONST_GH_API_PARAMS_METHOD: Final[str] = "POST"
CONST_GH_API_FIELD_SEPARATOR: Final[str] = "="
CONST_GH_API_FILE_VALUE_PREFIX: Final[str] = "@"
CONST_GH_API_STDIN_PATH: Final[str] = "-"
CONST_GRAPHQL_QUERY_KEY: Final[str] = "query"
CONST_GRAPHQL_OPERATION_NAME_KEY: Final[str] = "operationName"
CONST_GRAPHQL_REQUEST_KEYS: Final[tuple[str, ...]] = (
    CONST_GRAPHQL_QUERY_KEY,
    CONST_GRAPHQL_OPERATION_NAME_KEY,
)
# The `gh api` flags after which stdout does not end with the response body as GitHub sent it:
# the values jq selects, a Go template's rendering, no body, all pages in one array, or the
# request and response log around the body (gh 2.103.1). `--include` only puts the status line
# and headers before the body.
CONST_GH_API_OUTPUT_VALUE_FLAGS: Final[tuple[tuple[str, ...], ...]] = (
    ("-q", "--jq"),
    ("-t", "--template"),
)
CONST_GH_API_OUTPUT_SWITCH_FLAGS: Final[tuple[tuple[str, ...], ...]] = (
    ("--silent",),
    ("--slurp",),
    ("--verbose",),
)
# The other `gh api` flags, so the argv parser skips them and their values.
CONST_GH_API_VALUE_FLAGS: Final[tuple[tuple[str, ...], ...]] = (
    ("--cache",),
    ("-H", "--header"),
    ("--hostname",),
    ("-p", "--preview"),
)
CONST_GH_API_SWITCH_FLAGS: Final[tuple[tuple[str, ...], ...]] = (
    ("--allow-escape-sequences",),
    ("-i", "--include"),
    ("--paginate",),
)

CONST_GH_MUTATION_HTTP_METHODS: Final[frozenset[str]] = frozenset(
    {
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    }
)

# gh porcelain command groups that use the GraphQL API (#1415).
CONST_GH_GRAPHQL_GROUPS: Final[frozenset[str]] = frozenset({"project"})

# gh porcelain commands that use the GraphQL API (#1415).
CONST_GH_GRAPHQL_PORCELAIN_COMMANDS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("issue", "create"),
        ("issue", "list"),
        ("issue", "view"),
        ("pr", "checks"),
        ("pr", "close"),
        ("pr", "create"),
        ("pr", "edit"),
        ("pr", "list"),
        ("pr", "ready"),
        ("pr", "view"),
        ("release", "list"),
    }
)

# REST endpoint segments for GitHub rate-limit resource detection (#1415).
CONST_GH_REST_SEARCH_CODE_PREFIX: Final[str] = "search/code"
CONST_GH_REST_SEARCH_PREFIX: Final[str] = "search"
CONST_GH_REST_REPOS_PREFIX: Final[str] = "repos"
CONST_GH_REST_CODE_SCANNING_SEGMENT: Final[str] = "code-scanning"
CONST_GH_REST_AUTOFIX_SEGMENT: Final[str] = "autofix"
CONST_GH_REST_SBOM_SEGMENTS: Final[tuple[str, str]] = ("dependency-graph", "sbom")
# GitHub's issue search returns at most this many results for one query, 100 a page (#2419).
CONST_GITHUB_SEARCH_MAX_RESULTS: Final[int] = 1000

# ── AI Gateway & Distributed Router Constants ─────────────────────────────────
CONST_AI_GATEWAY_VIRTUAL_MODELS: Final[tuple[str, ...]] = (
    "devops-chat",
    "devops-coder",
    "devops-reasoning",
    "devops-embedding",
)
CONST_AI_GATEWAY_PROVIDER: Final[str] = "gateway"
# The providers `ai.provider` takes.
CONST_AI_PROVIDER_IDS: Final[tuple[str, ...]] = (
    "ollama",
    "claude",
    "copilot",
    "openai",
    CONST_AI_GATEWAY_PROVIDER,
)
# Response header in which the LiteLLM gateway names the backend (api_base) that served a call.
CONST_AI_GATEWAY_SERVED_BY_HEADER: Final[str] = "x-litellm-model-api-base"
CONST_CAPABILITY_PROBE_NAMES: Final[tuple[str, ...]] = (
    "json_adherence",
    "tool_choice",
    "deep_recall",
    "explicit_prohibition",
)
CONST_CAPABILITY_PROBE_JSON_FIELDS: Final[tuple[str, ...]] = (
    "file",
    "line",
    "severity",
    "rule_id",
    "description",
)
CONST_CAPABILITY_PROBE_DEFAULT_TOOL: Final[str] = "inspect_ast"
CONST_CAPABILITY_PROBE_CANARY: Final[str] = "CANARY-RECALL-9824"
CONST_CAPABILITY_PROBE_FORBIDDEN_WORDS: Final[tuple[str, ...]] = ("security", "vulnerability")
CONST_CAPABILITY_PROBE_PROHIBITION_PREFIX: Final[str] = "SUMMARY:"

# Response header in which the LiteLLM gateway names the deployment model that served a call,
# such as `openai/gpt-4o`. The router writes the route name in the reply body (#2031).
CONST_AI_GATEWAY_SERVED_MODEL_HEADER: Final[str] = "x-litellm-model-name"
# Why a provider says a reply ended, as pydantic-ai's FinishReason. The OpenAI-compatible and
# Anthropic tables copy pydantic-ai 2.59.0's private maps (models/openai.py, models/anthropic.py),
# which are not imported because they are private. A value absent from a table, or mapped to
# None, is unknown: truncation is never guessed.
CONST_OPENAI_FINISH_REASONS: Final[dict[str, FinishReason]] = {
    "stop": "stop",
    "length": "length",
    "tool_calls": "tool_call",
    "content_filter": "content_filter",
    "function_call": "tool_call",
}
CONST_ANTHROPIC_STOP_REASONS: Final[dict[str, FinishReason | None]] = {
    "compaction": "stop",
    "end_turn": "stop",
    "max_tokens": "length",
    "model_context_window_exceeded": "length",
    "stop_sequence": "stop",
    "tool_use": "tool_call",
    "pause_turn": None,
    "refusal": "content_filter",
}
CONST_OLLAMA_DONE_REASONS: Final[dict[str, FinishReason | None]] = {
    "stop": "stop",
    "length": "length",
    "load": None,
    "unload": None,
}
# A reply cut at its token cap, and the reason a stream that failed after yielding output is
# recorded with.
CONST_FINISH_REASON_LENGTH: Final[FinishReason] = "length"
CONST_FINISH_REASON_ERROR: Final[FinishReason] = "error"
# Replies the response cache never stores: one cut short, filtered, failed or asking for a tool
# call is not the answer the prompt asked for, and serving it again for 7 days would repeat it.
CONST_UNCACHED_FINISH_REASONS: Final[frozenset[FinishReason]] = frozenset(
    {"length", "content_filter", "error", "tool_call"}
)
# How a review profile counts a reply whose provider gave no finish reason.
CONST_FINISH_REASON_UNKNOWN: Final[str] = "unknown"
CONST_AI_GATEWAY_PROVIDERS: Final[tuple[str, ...]] = ("litellm", "portkey")
CONST_AI_GATEWAY_PROVIDER_PORTKEY: Final[str] = "portkey"
CONST_AI_BACKENDS: Final[tuple[str, ...]] = ("ollama",)
# The default fallback cascade, by path: a bare `litellm` or `portkey` member is that gateway's
# default chat route (CONST_AI_GATEWAY_DEFAULT_ROUTE), and a bare `ollama` member is `ai.model`
# on Ollama itself.
CONST_AI_CASCADE_PROVIDERS: Final[tuple[str, ...]] = ("litellm", "portkey", "ollama")
CONST_AI_GATEWAY_DEFAULT_ROUTE: Final[str] = "devops-chat"
CONST_THINKING_STATE_THINKING: Final[str] = "thinking"
# The pydantic-ai model prefix a bare model name takes from `ai.provider`. OpenAI and Copilot
# models use the chat completions API, as `LLMClient` does, which OpenAI-compatible servers at
# `ai.api_base_url` serve. Provider `gateway` takes its gateway's prefix (`ai.gateway_provider`);
# `ollama` models resolve through Ollama.
CONST_AI_PYDANTIC_MODEL_PREFIXES: Final[dict[str, str]] = {
    "openai": "openai-chat",
    "claude": "anthropic",
    "copilot": "openai-chat",
}
# Each gateway model prefix and the `ai` setting naming its URL. Both gateways speak the OpenAI
# chat API, so their models are inferred as `openai-chat:<model>` and sent to that URL.
CONST_AI_GATEWAY_URL_SETTINGS: Final[dict[str, str]] = {
    "litellm": "gateway_url",
    "portkey": "portkey_url",
}
CONST_PIPELINE_STAGE_TRUNCATION_SUFFIX: Final[str] = (
    "\n...[stage output truncated to the stage context budget]"
)
# The loopback host name (RFC 6761). With the loopback addresses, which `ipaddress` recognises,
# it names the workstation itself, so a configured service URL may use it without
# `ai.allow_private_network` (`configured_level`).
CONST_LOOPBACK_HOSTNAME: Final[str] = "localhost"
CONST_CLOUD_METADATA_DNS_HOSTNAMES: Final[frozenset[str]] = frozenset(
    {"metadata", "metadata.google.internal", "metadata.goog"}
)
# Private IP ranges blocked by SSRF checks by default (RFC 1918, RFC 6598 CGNAT, RFC 5737, etc.).
CONST_PRIVATE_NETWORKS: Final[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]] = (
    # IPv4 private ranges
    ipaddress.IPv4Network("0.0.0.0/8"),  # "This" network
    ipaddress.IPv4Network("10.0.0.0/8"),  # Private (RFC 1918)
    ipaddress.IPv4Network("100.64.0.0/10"),  # CGNAT (RFC 6598), includes Alibaba Cloud metadata
    ipaddress.IPv4Network("127.0.0.0/8"),  # Loopback
    ipaddress.IPv4Network("169.254.0.0/16"),  # Link-local (includes cloud metadata)
    ipaddress.IPv4Network("172.16.0.0/12"),  # Private (RFC 1918)
    ipaddress.IPv4Network("192.168.0.0/16"),  # Private (RFC 1918)
    # IPv4 IANA-reserved / special-purpose ranges (not globally routable)
    ipaddress.IPv4Network("192.0.0.0/24"),  # IETF Protocol Assignments (RFC 6890)
    ipaddress.IPv4Network("192.0.2.0/24"),  # TEST-NET-1 (RFC 5737)
    ipaddress.IPv4Network("198.18.0.0/15"),  # Network benchmarking (RFC 2544)
    ipaddress.IPv4Network("198.51.100.0/24"),  # TEST-NET-2 (RFC 5737)
    ipaddress.IPv4Network("203.0.113.0/24"),  # TEST-NET-3 (RFC 5737)
    ipaddress.IPv4Network("224.0.0.0/4"),  # Multicast (RFC 5771)
    ipaddress.IPv4Network("240.0.0.0/4"),  # Reserved + limited broadcast 255.255.255.255 (RFC 1112)
    # IPv6 private ranges
    ipaddress.IPv6Network("::/128"),  # Unspecified address
    ipaddress.IPv6Network("::1/128"),  # Loopback
    ipaddress.IPv6Network("fe80::/10"),  # Link-local
    ipaddress.IPv6Network("fc00::/7"),  # Unique local address (RFC 4193)
    # IPv6 IANA-reserved / special-purpose ranges
    ipaddress.IPv6Network("100::/64"),  # Discard prefix (RFC 6666)
    ipaddress.IPv6Network("2001::/32"),  # Teredo tunneling (RFC 4380)
    ipaddress.IPv6Network("2001:db8::/32"),  # Documentation (RFC 3849)
    ipaddress.IPv6Network("ff00::/8"),  # Multicast (RFC 4291)
)

# Cloud metadata and credential endpoints. Always blocked even when private networks are permitted.
CONST_CLOUD_METADATA_IPV4: Final[frozenset[ipaddress.IPv4Address]] = frozenset(
    ipaddress.IPv4Address(ip)
    for ip in (
        "169.254.169.254",  # AWS IMDS, GCP, Azure, OCI, DigitalOcean, Hetzner, IBM, OpenStack
        "169.254.170.2",  # AWS ECS task IAM role credentials
        "169.254.170.23",  # AWS EKS Pod Identity Agent
        "168.63.129.16",  # Azure WireServer / platform channel (public IP)
        "100.100.100.200",  # Alibaba Cloud
        "192.0.0.192",  # Oracle Cloud (Classic)
        "169.254.42.42",  # Scaleway
    )
)
CONST_CLOUD_METADATA_IPV6: Final[frozenset[ipaddress.IPv6Address]] = frozenset(
    ipaddress.IPv6Address(ip)
    for ip in (
        "fd00:ec2::254",  # AWS IMDS IPv6
        "fd00:ec2::23",  # AWS EKS Pod Identity Agent IPv6
        "fd20:ce::254",  # Scaleway IPv6 metadata
        "fd00:42::42",  # Scaleway IPv6 metadata
    )
)

# RFC 6052 §2.2: byte offsets within a 16-byte IPv6 address for standardized NAT64 prefix lengths.
CONST_NAT64_OFFSETS_BY_PREFIX_LEN: Final[dict[int, tuple[int, int, int, int]]] = {
    32: (4, 5, 6, 7),
    40: (5, 6, 7, 9),
    48: (6, 7, 9, 10),
    56: (7, 9, 10, 11),
    64: (9, 10, 11, 12),
    96: (12, 13, 14, 15),
}
CONST_LOW32_OFFSETS: Final[tuple[int, int, int, int]] = (12, 13, 14, 15)
CONST_SIXTOFOUR_OFFSETS: Final[tuple[int, int, int, int]] = (2, 3, 4, 5)
CONST_ALL_EMBEDDED_OFFSETS: Final[tuple[tuple[int, int, int, int], ...]] = (
    *CONST_NAT64_OFFSETS_BY_PREFIX_LEN.values(),
    CONST_SIXTOFOUR_OFFSETS,
)
CONST_NAT64_PREFIXES: Final[
    tuple[tuple[ipaddress.IPv6Network, tuple[tuple[int, int, int, int], ...]], ...]
] = (
    (ipaddress.IPv6Network("64:ff9b::/96"), (CONST_NAT64_OFFSETS_BY_PREFIX_LEN[96],)),
    (
        ipaddress.IPv6Network("64:ff9b:1::/48"),
        tuple(CONST_NAT64_OFFSETS_BY_PREFIX_LEN[pl] for pl in (48, 56, 64, 96)),
    ),
)
CONST_ISATAP_INTERFACE_IDS: Final[tuple[bytes, ...]] = (
    b"\x00\x00\x5e\xfe",
    b"\x02\x00\x5e\xfe",
)
CONST_TEREDO_PREFIX: Final[ipaddress.IPv6Network] = ipaddress.IPv6Network("2001::/32")

# The /96 prefixes whose last 32 bits carry an IPv4 address: NAT64's well-known prefix (RFC 6052)
# and IPv4-compatible addresses (RFC 4291).
CONST_IPV4_EMBEDDING_IPV6_PREFIXES: Final[tuple[str, ...]] = ("64:ff9b::/96", "::/96")
# The punctuation prose leaves after a network target ("check 100.64.0.1."), which is never part
# of an address, a URL's end or a name, so a target is classified without it.
CONST_PROSE_TRAILING_PUNCTUATION: Final[str] = ".,;)>]\"'"
# The address blocks set aside for documentation and benchmarking, which a network reference
# report tags as documented examples and no threat-intel service is asked about. Python's
# `ipaddress` folds them into `is_private`, so no library tells them from RFC 1918 space.
CONST_DOCUMENTATION_IP_NETWORKS: Final[
    tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]
] = (
    ipaddress.ip_network("192.0.2.0/24"),  # TEST-NET-1 (RFC 5737)
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2 (RFC 5737)
    ipaddress.ip_network("203.0.113.0/24"),  # TEST-NET-3 (RFC 5737)
    ipaddress.ip_network("2001:db8::/32"),  # Documentation (RFC 3849)
    ipaddress.ip_network("3fff::/20"),  # Documentation (RFC 9637)
    ipaddress.ip_network("198.18.0.0/15"),  # Benchmarking (RFC 2544)
    ipaddress.ip_network("2001:2::/48"),  # Benchmarking (RFC 5180)
)
# Space IANA does not list as globally reachable but Python 3.14's `is_global` reads as global.
# It is local, so no threat-intel service is asked about it. Delete a network when CPython
# follows IANA, which `test_the_stdlib_still_reads_each_non_global_network_as_global` reports
# by failing.
CONST_NON_GLOBAL_NETWORKS_STDLIB_READS_GLOBAL: Final[
    tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]
] = (
    # The deprecated 6to4 relay anycast prefix (RFC 7526), whose one live entry in IANA's IPv4
    # special-purpose registry, 192.88.99.2/32 (RFC 6751), is "Globally Reachable: False".
    ipaddress.ip_network("192.88.99.0/24"),
    # Site-local, IPv6's private space until RFC 3879 deprecated it; IANA's IPv6 address space
    # registry lists it as reserved by the IETF.
    ipaddress.ip_network("fec0::/10"),
)
# The name Docker Desktop and Podman give the container runtime's host gateway on the
# workstation. A cluster pod cannot reach that gateway, so the sandbox local whitelist refuses
# the name and asks for the address the cluster reaches the host on.
CONST_DOCKER_HOST_GATEWAY_HOSTNAME: Final[str] = "host.docker.internal"

# ── AI Model Capability Tier Gates & AIMD Constants ───────────────────────────
CONST_MIN_REASONING_MODEL_TIER_B: Final[int] = 30
CONST_MIN_CODING_MODEL_TIER_B: Final[int] = 7
CONST_FRONTIER_EQUIVALENT_TIER_B: Final[int] = 70
CONST_AIMD_MULTIPLICATIVE_DECREASE_FACTOR: Final[float] = 0.5
CONST_AIMD_ADDITIVE_INCREASE_STEP: Final[int] = 2
CONST_AIMD_SUCCESS_THRESHOLD: Final[int] = 2
CONST_FRONTIER_MODEL_PREFIXES: Final[tuple[str, ...]] = (
    "gpt-4",
    "o1",
    "o3",
    "chatgpt-4",
    "claude-3",
    "claude-sonnet",
    "claude-opus",
    "gemini-1.5",
    "gemini-2",
    "deepseek-chat",
    "deepseek-reasoner",
)

# ── Roadmap on GitHub (ADR 0001, ADR 0016) ────────────────────────────────────
# The hidden block at the end of an issue body that holds its job record (ADR 0016).
CONST_ROADMAP_RECORD_MARKER: Final[str] = "devops-roadmap-record"
CONST_ROADMAP_REFINE_START_MARKER: Final[str] = "<!-- devops-roadmap-refine:start -->"
CONST_ROADMAP_REFINE_END_MARKER: Final[str] = "<!-- devops-roadmap-refine:end -->"
CONST_ROADMAP_REFINE_MAX_BODY_CHARS: Final[int] = 65536
CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES: Final[int] = 3
CONST_ROADMAP_REFINE_SEARCH_RESULTS_PER_QUERY: Final[int] = 5
# The `result` of `devops_cli_firecrawl_searches_total` for a search that returned its web results,
# and for one that got no answer or a reply with no web results. A search that Firecrawl refused
# counts under its HTTP status (#2475).
CONST_FIRECRAWL_RESULT_OK: Final[str] = "ok"
CONST_FIRECRAWL_RESULT_ERROR: Final[str] = "error"
# The most comments refine posts on one item in `CONST_ROADMAP_REFINE_COMMENT_CAP_WINDOW_HOURS`.
# A round that finds that many refine comments on the item leaves it alone, so a loop of replies
# from another bot or workflow stops after this many comments (#2475).
CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM: Final[int] = 2
CONST_ROADMAP_REFINE_COMMENT_CAP_WINDOW_HOURS: Final[int] = 24
# Every comment refine posts carries this marker, so a later round tells a person's reply from
# refine's own comments: a comment after refine's last one is a reply (#1758).
CONST_ROADMAP_REFINE_COMMENT_MARKER: Final[str] = "<!-- devops roadmap refine: next step -->"
# What a proposal's `suspected_block` holds when it names no block, lower-cased.
CONST_ROADMAP_REFINE_NO_BLOCK_TEXTS: Final[frozenset[str]] = frozenset({"", "none", "null"})
# The newest replies that reach the model, each cut to this many tokens (#1758).
CONST_ROADMAP_REFINE_MAX_REPLIES: Final[int] = 5
CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS: Final[int] = 1024
# The most paths refine records as the cause of an item's block. A later round reads the newest
# commit of each one while the item waits, so the cap bounds those reads (#2005).
CONST_ROADMAP_REFINE_MAX_BLOCK_PATHS: Final[int] = 5
# The budget of one item's investigation (#2398): its model requests and tool calls, the calls
# one turn can make (the function tools go when fewer are left), and the lines and characters of
# one tool answer, so the run stays inside the analysis context window. qwen3.8:27b made two
# calls in each turn and needed more than 12 calls for the open facts of #2234.
CONST_ROADMAP_REFINE_INVESTIGATION_MAX_REQUESTS: Final[int] = 12
CONST_ROADMAP_REFINE_INVESTIGATION_MAX_TOOL_CALLS: Final[int] = 20
CONST_ROADMAP_REFINE_INVESTIGATION_TURN_CALLS: Final[int] = 4
# The retries the model gets for a tool call or an answer that breaks its schema.
CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES: Final[int] = 2
CONST_ROADMAP_REFINE_TOOL_MAX_LINES: Final[int] = 120
CONST_ROADMAP_REFINE_TOOL_MAX_CHARS: Final[int] = 4000
# `devops roadmap alternatives` (#2650): the block the job keeps in an issue body, the marker of
# its comment (a comment after the job's last one is a reply), the most searches and fact reads of
# one item's check, and how long a tool may go without a push or an upload and stay maintained.
CONST_ROADMAP_ALTERNATIVES_START_MARKER: Final[str] = "<!-- devops-roadmap-alternatives:start -->"
CONST_ROADMAP_ALTERNATIVES_END_MARKER: Final[str] = "<!-- devops-roadmap-alternatives:end -->"
CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER: Final[str] = "<!-- devops roadmap alternatives -->"
CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES: Final[int] = 3
CONST_ROADMAP_ALTERNATIVES_MAX_FACT_READS: Final[int] = 6
CONST_ROADMAP_ALTERNATIVES_SEARCH_RESULTS: Final[int] = 5
CONST_ROADMAP_ALTERNATIVES_MAINTAINED_DAYS: Final[int] = 365
# A PyPI package states its license in `license_expression`, in `license` (a name when it is short,
# else the whole text) or in a classifier that starts with the prefix.
CONST_ROADMAP_ALTERNATIVES_MAX_LICENSE_CHARS: Final[int] = 100
CONST_ROADMAP_ALTERNATIVES_LICENSE_CLASSIFIER: Final[str] = "License :: "
CONST_ROADMAP_ALTERNATIVES_CLASSIFIER_SEPARATOR: Final[str] = " :: "
# The longest body, in tokens, that reaches the model with an item.
CONST_ROADMAP_ALTERNATIVES_MAX_BODY_TOKENS: Final[int] = 4096
# The budget of one step of `devops roadmap implement` (#2664): the model requests and tool calls
# of its run, the characters of one tool result, and the tokens of the window that the inputs
# leave to the turns of the run. The window is `ai.tasks.implement.context_window`.
CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS: Final[int] = 80
CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS: Final[int] = 240
CONST_ROADMAP_IMPLEMENT_TOOL_MAX_CHARS: Final[int] = 16000
# The consecutive refusals that a tool may answer before the run ends, such as a command off the
# allowlist. A refusal is the model's to correct, as the harness's own file tools allow five.
CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES: Final[int] = 5
# How many times in a row a step sends a model request again when the provider fails it inside an
# open stream with the status 400 (#2794): a tool call that the model ended early, which the next
# sample can make whole. The resend adds to the retries of the client (`ai.max_retries`, #2500).
# The client retries only 5xx, 429 and connection errors, and the step only this 400, so a call
# gets at most (1 + `ai.max_retries`) * (1 + this value) sends.
CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS: Final[int] = 1
CONST_ROADMAP_IMPLEMENT_TURN_RESERVE_TOKENS: Final[int] = 40000
# The output cap of one model reply of a step, in tokens, and the deadline of one model call, in
# seconds (#2869). Both go to the agent as model settings. The cap is `max_tokens`: the gateway
# sends it to Ollama as `num_predict`. The longest reply of a step in the Job logs is under 2,000
# tokens, and the longest reply of any client of the tier is 11,634 tokens, so 16,384 cuts only a
# model that does not stop. The deadline is `request_timeout`, one clock over the whole call, the
# read of the stream included. It is more than a cold read of the largest window (about 90 s) and
# a reply at the cap at the average rate of the longest measured call (38 tokens per second, about
# 430 s). The rate fell to 27.55 tokens per second for a short time in that call, so a very slow
# call ends at the deadline before it reaches the cap. Both stops are fine. The deadline is under
# the timeout of the router in `k8s/llm/gateway/config.yaml` (1500 s), which a test holds.
CONST_ROADMAP_IMPLEMENT_MAX_OUTPUT_TOKENS: Final[int] = 16384
CONST_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS: Final[int] = 600
# The tokens of one packed file in the inputs of a step. The agent reads more with its tools.
CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS: Final[int] = 3000
# How long one verification command or static check of a step may run, and how many lines of its
# output a stopped step reports.
CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS: Final[int] = 900
CONST_ROADMAP_IMPLEMENT_OUTPUT_TAIL_LINES: Final[int] = 20
# The job of `devops roadmap implement` (#2665). The longest log of a failed check, in characters
# from its end, that the fix step reads; the longest "why" in a pull request body, as the
# squash message takes it; the longest last message of an agent in a comment; and the most time
# that the checks of a pull request may take to settle.
CONST_ROADMAP_IMPLEMENT_LOG_CHARS: Final[int] = 6000
CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS: Final[int] = 1000
CONST_ROADMAP_IMPLEMENT_LAST_MESSAGE_CHARS: Final[int] = 1500
# The longest diff, in characters, that a stopped step reports (#2721) and the job posts in the
# stop comment. A comment holds at most 65,536 characters, and the comment also holds the reason
# and the last message of the agent.
CONST_ROADMAP_IMPLEMENT_DIFF_CHARS: Final[int] = 20000
# The most of a diff, in characters, that a stopped step masks before it cuts to the limit above:
# the masking of secrets is slower than linear, and a diff has no size limit. The part is a
# multiple of the limit, so a secret in the shown part is masked whole.
CONST_ROADMAP_IMPLEMENT_DIFF_READ_CHARS: Final[int] = 4 * CONST_ROADMAP_IMPLEMENT_DIFF_CHARS
# The most paths that a reason of a stop names, and the most characters of a reason in the stop
# comment (#2721). A reason may be as long as the tail of a command or a list of files.
CONST_ROADMAP_IMPLEMENT_REASON_PATHS: Final[int] = 20
# The most tests of one file that the reason of a stop for a lost test names (#2804). The reason
# gives the count of the rest.
CONST_ROADMAP_IMPLEMENT_REASON_TESTS: Final[int] = 10
CONST_ROADMAP_IMPLEMENT_REASON_CHARS: Final[int] = 4000
# The most characters of the message of a pydantic-ai error that a roadmap job keeps for the reason
# of a stopped run or a warning, and the most that the masking reads (#2758, #2562). The read is a
# multiple of the limit: the masking of secrets is slower than linear, and the message of an error
# can hold a long reply of the model.
CONST_ROADMAP_RUN_ERROR_CHARS: Final[int] = 500
CONST_ROADMAP_RUN_ERROR_READ_CHARS: Final[int] = 4 * CONST_ROADMAP_RUN_ERROR_CHARS
# The most programs that the reason of a stopped run lists in its count of refused commands
# (#2773). The programs beyond that join the count of "other".
CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS: Final[int] = 4
# The most words and characters of the command that the Job log shows before a shell call runs
# (#2806). The log holds the program and its first arguments, so that a call the kernel kills
# leaves its cause. The masking reads `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_READ_CHARS` first, so
# that a cut cannot split a secret.
CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS: Final[int] = 6
CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS: Final[int] = 160
CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_READ_CHARS: Final[int] = (
    4 * CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS
)
# The most characters of the reason of a retried tool call that the Job log shows, and the most
# reasons of one tool that the reason of a stopped run names (#2866). The reason is the message
# of the retry that the tool returned. The log and the reason of the stop cut it to the same length.
CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS: Final[int] = 240
CONST_ROADMAP_IMPLEMENT_STOP_REASONS: Final[int] = 3
CONST_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS: Final[int] = 1800
# After a push, GitHub can still show the old head of the pull request. The job reads this many
# times, `DEFAULT_ROADMAP_IMPLEMENT_POLL_SECONDS` apart, for the pushed commit as the head.
CONST_ROADMAP_IMPLEMENT_HEAD_POLLS: Final[int] = 20
# The comment of a person that clears the stop of an item, and the marker that heads every
# comment of the job on an item.
CONST_ROADMAP_IMPLEMENT_RETRY_COMMENT: Final[str] = "implement: retry"
CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER: Final[str] = "<!-- devops roadmap implement -->"
# The runner Job of the Service's `implement` row (#2667). The label that holds a digest of the
# repository (`owner/name` is no label value), the lines of a Job's log that the report of an ended
# Job quotes, and the step that a stop by the Service records, as the job records a group.
CONST_ROADMAP_IMPLEMENT_JOB_LABEL: Final[str] = "implement-repo"
CONST_ROADMAP_IMPLEMENT_JOB_LOG_LINES: Final[int] = 40
CONST_ROADMAP_IMPLEMENT_JOB_STEP: Final[str] = "job"
# The number of the group of a fix step: a change numbers its groups from 1.
CONST_ROADMAP_IMPLEMENT_FIX_GROUP: Final[int] = 0
# The headings, in lower case, of the two sections of an issue that a step gives the model: the
# problem, as the issue form and refine's proposal word it, and the acceptance criteria.
CONST_ROADMAP_IMPLEMENT_PROBLEM_HEADINGS: Final[frozenset[str]] = frozenset(
    {"problem or motivation", "problem statement"}
)
CONST_ROADMAP_IMPLEMENT_CRITERIA_HEADINGS: Final[frozenset[str]] = frozenset(
    {"acceptance criteria"}
)
# The text that starts a second command in a shell command line. The shell tool refuses a command
# that holds one, because its allowlist reads only the first word. `&` alone is not here, since
# `2>&1` holds it.
CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS: Final[tuple[str, ...]] = (
    ";",
    "&&",
    "||",
    "|",
    "& ",
    " &",
    "`",
    "$(",
    "<(",
    ">(",
    "\n",
)
CONST_ROADMAP_RUN_STATE_FILENAME: Final[str] = "schedule.json"
# The Service's intake record beside schedule.json: what intake decided and left (#1360).
CONST_ROADMAP_INTAKE_RECORD_FILENAME: Final[str] = "intake.json"
CONST_ROADMAP_RUN_CLONE_DIRNAME: Final[str] = "clone"
# The triage lane's clone beside it, so the triage lane's checkout never touches another lane's clone (#1534).
CONST_ROADMAP_RUN_TRIAGE_CLONE_DIRNAME: Final[str] = "triage-clone"
# The model lane's own clone beside it, so the model lane's checkout never touches the status
# lane's `clone` (#1532).
CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME: Final[str] = "model-clone"
CONST_ROADMAP_REFINE_DUE_STAMP: Final[str] = "refine_due"
CONST_ROADMAP_INTAKE_BATCH_KEYS: Final[tuple[tuple[str, str, str], ...]] = (
    ("webhook", "issues", "opened"),
    ("webhook", "issues", "reopened"),
)
# The webhook events the roadmap jobs' batch keys name, the events the Service's roadmap consumer
# takes (#1386): the issues events only.
CONST_ROADMAP_WEBHOOK_EVENTS: Final[frozenset[str]] = frozenset(
    event
    for source, event, _action in CONST_ROADMAP_INTAKE_BATCH_KEYS
    if source == CONST_SERVICE_SOURCE_WEBHOOK
)
CONST_PROJECT_TEMPLATE_PATH: Final[str] = ".github/project-template.json"
CONST_ROADMAP_EPIC_LABEL: Final[str] = "type/epic"
# An Item's Status values, in the order of their labels' family (`status/new`, ...; ADR 0016).
# A closed issue is done, so no label holds Done.
CONST_ROADMAP_STATUS_NEW: Final[str] = "New"
CONST_ROADMAP_STATUS_READY: Final[str] = "Ready"
CONST_ROADMAP_STATUS_PLANNED: Final[str] = "Planned"
CONST_ROADMAP_STATUS_IN_PROGRESS: Final[str] = "In Progress"
CONST_ROADMAP_STATUS_IN_REVIEW: Final[str] = "In Review"
CONST_ROADMAP_STATUS_BLOCKED: Final[str] = "Blocked"
CONST_ROADMAP_STATUS_VALUES: Final[tuple[str, ...]] = (
    CONST_ROADMAP_STATUS_NEW,
    CONST_ROADMAP_STATUS_READY,
    CONST_ROADMAP_STATUS_PLANNED,
    CONST_ROADMAP_STATUS_IN_PROGRESS,
    CONST_ROADMAP_STATUS_IN_REVIEW,
    CONST_ROADMAP_STATUS_BLOCKED,
)
# The Status values of an open item refine never changes, even when `--item` names it (#1758). A
# Planned item has its plan on the default branch (#2920).
CONST_ROADMAP_REFINE_HELD_STATUSES: Final[frozenset[str]] = frozenset(
    {
        CONST_ROADMAP_STATUS_PLANNED,
        CONST_ROADMAP_STATUS_IN_PROGRESS,
        CONST_ROADMAP_STATUS_BLOCKED,
    }
)
# A critical fix is a P0 item that fixes a defect or a security advisory (CONTEXT.md): the
# P0 Priority and one of these `type/*` labels.
CONST_ROADMAP_CRITICAL_PRIORITY: Final[str] = "P0-Critical"
CONST_ROADMAP_P0_PRIORITY: Final[str] = "P0"
CONST_ROADMAP_P1_PRIORITY: Final[str] = "P1-High"
CONST_ROADMAP_P2_PRIORITY: Final[str] = "P2-Medium"
CONST_ROADMAP_P3_PRIORITY: Final[str] = "P3-Low"
# An Item's Priority values, in the order of their labels' family (`priority/p0-critical`, ...).
CONST_ROADMAP_PRIORITY_VALUES: Final[tuple[str, ...]] = (
    CONST_ROADMAP_CRITICAL_PRIORITY,
    CONST_ROADMAP_P1_PRIORITY,
    CONST_ROADMAP_P2_PRIORITY,
    CONST_ROADMAP_P3_PRIORITY,
)
CONST_ROADMAP_P0_PRIORITIES: Final[frozenset[str]] = frozenset(
    {CONST_ROADMAP_CRITICAL_PRIORITY, CONST_ROADMAP_P0_PRIORITY}
)
CONST_ROADMAP_CRITICAL_FIX_LABELS: Final[frozenset[str]] = frozenset({"type/bug", "type/security"})
# An Item's Owner values, in the order of their labels' family (`owner/service`, ...; ADR 0016,
# #2910). The Service claims an Item for the Job it creates, an agent and a person claim by hand.
CONST_ROADMAP_OWNER_SERVICE: Final[str] = "Service"
CONST_ROADMAP_OWNER_AGENT: Final[str] = "Agent"
CONST_ROADMAP_OWNER_HUMAN: Final[str] = "Human"
CONST_ROADMAP_OWNER_VALUES: Final[tuple[str, ...]] = (
    CONST_ROADMAP_OWNER_SERVICE,
    CONST_ROADMAP_OWNER_AGENT,
    CONST_ROADMAP_OWNER_HUMAN,
)
# `devops roadmap intake` (#742). Its reason comment carries this marker, so a run that finds it
# posts no second reason comment.
CONST_ROADMAP_INTAKE_REASON_MARKER: Final[str] = "<!-- devops roadmap intake: reason -->"
# The stage job's comment marker (#2654).
CONST_ROADMAP_STAGE_COMMENT_MARKER: Final[str] = "<!-- devops roadmap stage -->"
# The marker of every roadmap job's comment: a comment that holds none of them is a person's.
CONST_ROADMAP_JOB_COMMENT_MARKERS: Final[tuple[str, ...]] = (
    CONST_ROADMAP_REFINE_COMMENT_MARKER,
    CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER,
    CONST_ROADMAP_INTAKE_REASON_MARKER,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
)
CONST_ROADMAP_LABELS_PATH: Final[str] = ".github/labels.yml"
CONST_ROADMAP_TYPE_LABEL_PREFIX: Final[str] = "type/"
CONST_ROADMAP_PRIORITY_LABEL_PREFIX: Final[str] = "priority/"
CONST_ROADMAP_SCOPE_LABEL_PREFIX: Final[str] = "scope/"
# The `type/*` label of each Conventional Commit type of an item's title (#2715). The title is the
# only source of an item's type label; the model picks a type only for a title with no type.
CONST_ROADMAP_COMMIT_TYPE_LABELS: Final[dict[str, str]] = {
    "feat": "type/feature",
    "fix": "type/bug",
    "perf": "type/infra",
    "build": "type/infra",
    "ci": "type/infra",
    "refactor": "type/refactor",
    "docs": "type/docs",
    "test": "type/test",
    "chore": "type/chore",
    "style": "type/chore",
    "revert": "type/chore",
}
# The label of a candidate an agent files.
CONST_ROADMAP_SOURCE_AGENT_LABEL: Final[str] = "source/agent"
# The Priority options the model may propose; only verified evidence sets P0-Critical.
CONST_ROADMAP_MODEL_PRIORITIES: Final[tuple[str, ...]] = ("P1-High", "P2-Medium", "P3-Low")
# The Value and Effort values, in the order of their labels' families (`value/high`, ...).
CONST_ROADMAP_SIZE_OPTIONS: Final[tuple[str, ...]] = ("High", "Medium", "Low")
# An author with write access, as GitHub's author_association says.
CONST_ROADMAP_TRUSTED_AUTHORS: Final[frozenset[str]] = frozenset(
    {"OWNER", "MEMBER", "COLLABORATOR"}
)
# What each kind of P0 evidence looks like: a GHSA ID, an Actions run id, a commit SHA.
CONST_ROADMAP_EVIDENCE_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "advisory": re.compile(r"GHSA(-[23456789cfghjmpqrvwx]{4}){3}"),
    "failed_run": re.compile(r"[0-9]{1,20}"),
    "regression_commit": re.compile(r"[0-9a-fA-F]{7,40}"),
}
CONST_GH_RAW_CONTENT_ACCEPT: Final[str] = "Accept: application/vnd.github.raw+json"

# ── Multi-Scale Semantic Outline & Inspection Scanner ────────────────────────
CONST_MAX_INSPECT_FILE_SIZE_BYTES: Final[int] = 50 * 1024 * 1024  # 50 MiB limit
CONST_DEFAULT_FOCAL_WINDOW_SIZE: Final[int] = 30
CONST_HOTSPOT_COMPLEXITY_THRESHOLD: Final[int] = 5

# ── File Classification & Review Context Taxonomy ─────────────────────────────
CONST_DOC_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".md",
        ".markdown",
        ".rst",
        ".txt",
        ".adoc",
        ".asciidoc",
        ".tex",
    }
)

CONST_LOCKFILE_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".lock",
        ".lockb",
    }
)

CONST_SEMGREP_EXCLUDED_EXTENSIONS: Final[frozenset[str]] = (
    CONST_DOC_EXTENSIONS | CONST_BINARY_EXTENSIONS | CONST_LOCKFILE_EXTENSIONS
)

# The number of jobs of each Semgrep scan. Semgrep runs one job for each processor by default,
# and each job reserves address space, so the limit of a scan would grow with the host. Four jobs
# scan 100 files of devops-cli in the time that the default 16 jobs take (#2096).
CONST_SEMGREP_JOBS: Final[int] = 4

# Directories of a checkout that hold dependencies, devops-cli's own data or cloned repositories,
# not the code Semgrep scans.
CONST_SEMGREP_EXCLUDED_DIRECTORIES: Final[tuple[str, ...]] = (
    ".venv",
    "venv",
    "node_modules",
    ".data",
    "repos",
    ".git",
)

# Where a registry ruleset is downloaded from, `{ruleset}` being an id such as `p/default`.
CONST_SEMGREP_REGISTRY_URL_TEMPLATE: Final[str] = "https://semgrep.dev/c/{ruleset}"
# The prefixes of a Semgrep registry id, the ones its own `is_registry_id` takes: `p/` for a pack
# of rules, `r/` for one rule, `s/` for a snippet.
CONST_SEMGREP_REGISTRY_RULESET_KINDS: Final[frozenset[str]] = frozenset({"p", "r", "s"})
# The directory of the user data root that holds the downloaded registry rulesets.
CONST_SEMGREP_REGISTRY_CACHE_DIRNAME: Final[str] = "semgrep"


CONST_K8S_MANIFEST_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".yaml",
        ".yml",
        ".json",
    }
)
# The statuses of a resource in a `kubeconform -output json` report that are findings: a resource
# that does not match its schema, and one that kubeconform could not validate (#2214). The other
# two, `statusValid` and `statusSkipped`, are listed only with `-verbose`.
CONST_KUBECONFORM_STATUS_INVALID: Final[str] = "statusInvalid"
CONST_KUBECONFORM_FINDING_STATUSES: Final[frozenset[str]] = frozenset(
    {CONST_KUBECONFORM_STATUS_INVALID, "statusError"}
)

CONST_LOCAL_PROVIDER_NAMES: Final[frozenset[str]] = frozenset(
    {"ollama", "local", "in-process", "internal"}
)
CONST_LOCAL_TRANSPORT_LABELS: Final[frozenset[str]] = frozenset(
    {"local", "in-process", "internal", "none"}
)

# ── Kubernetes Informer & Service Constants ──────────────────────────────────
CONST_K8S_EVENT_ADDED: Final[str] = "ADDED"
CONST_K8S_EVENT_MODIFIED: Final[str] = "MODIFIED"
CONST_K8S_EVENT_DELETED: Final[str] = "DELETED"
CONST_K8S_EVENT_ERROR: Final[str] = "ERROR"
CONST_K8S_INFORMER_EVENTS: Final[tuple[str, ...]] = (
    CONST_K8S_EVENT_ADDED,
    CONST_K8S_EVENT_MODIFIED,
    CONST_K8S_EVENT_DELETED,
    CONST_K8S_EVENT_ERROR,
)

# ── Stack Credential Sync (`devops k8s sync-secrets`, #2156) ─────────────────
# The HTTP statuses with which Argo CD and Grafana refuse a token. Any other status is a failed
# check, and the sync keeps the stored token. Argo CD also refuses a token with HTTP 200 and
# `loggedIn: false` from its userinfo, because that endpoint takes no authentication.
CONST_STACK_TOKEN_REFUSED_HTTP_STATUSES: Final[frozenset[int]] = frozenset({401, 403})
# The statuses with which Grafana refuses to create a service account whose name is in use.
CONST_GRAFANA_ACCOUNT_EXISTS_HTTP_STATUSES: Final[frozenset[int]] = frozenset({400, 409})
CONST_GRAFANA_SERVICE_ACCOUNT_NAME: Final[str] = "devops-cli"

# ── Kubernetes Pod Status ────────────────────────────────────────────────────
# The STATUS kubectl prints for a pod, ported from its `printPod`: the pod's reason or
# phase, unless an init or app container's waiting or terminated reason says more. Every
# value here is one the Kubernetes API itself defines.
CONST_K8S_POD_RUNNING: Final[str] = "Running"
CONST_K8S_POD_COMPLETED: Final[str] = "Completed"
CONST_K8S_POD_NOT_READY: Final[str] = "NotReady"
CONST_K8S_POD_TERMINATING: Final[str] = "Terminating"
CONST_K8S_POD_UNKNOWN: Final[str] = "Unknown"
CONST_K8S_POD_INITIALIZING: Final[str] = "PodInitializing"
CONST_K8S_POD_REASON_NODE_LOST: Final[str] = "NodeLost"
CONST_K8S_POD_REASON_SCHEDULING_GATED: Final[str] = "SchedulingGated"
# Phases a pod never leaves: deleting one does not make it Terminating.
CONST_K8S_POD_TERMINAL_PHASES: Final[frozenset[str]] = frozenset({"Succeeded", "Failed"})
CONST_K8S_INIT_STATUS_PREFIX: Final[str] = "Init:"
CONST_K8S_SIGNAL_STATUS_PREFIX: Final[str] = "Signal:"
CONST_K8S_EXIT_CODE_STATUS_PREFIX: Final[str] = "ExitCode:"
# Pod and node condition types, and the status a condition holds when it is met.
CONST_K8S_CONDITION_READY: Final[str] = "Ready"
CONST_K8S_CONDITION_INITIALIZED: Final[str] = "Initialized"
CONST_K8S_CONDITION_SCHEDULED: Final[str] = "PodScheduled"
CONST_K8S_CONDITION_TRUE: Final[str] = "True"
# An init container with this restart policy is a sidecar that keeps running beside the
# app containers, so it counts toward READY.
CONST_K8S_RESTART_POLICY_ALWAYS: Final[str] = "Always"
# The statuses a pod can show without needing attention. Any other status is unhealthy,
# and so is a Running pod whose READY count is short.
CONST_K8S_HEALTHY_POD_STATUSES: Final[frozenset[str]] = frozenset(
    {CONST_K8S_POD_RUNNING, CONST_K8S_POD_COMPLETED}
)
# A container's current state, named as `kubectl describe pod` names it.
CONST_K8S_CONTAINER_RUNNING: Final[str] = "Running"
CONST_K8S_CONTAINER_WAITING: Final[str] = "Waiting"
CONST_K8S_CONTAINER_TERMINATED: Final[str] = "Terminated"
# The container `kubectl logs` and `kubectl exec` pick when none is named.
CONST_K8S_DEFAULT_CONTAINER_ANNOTATION: Final[str] = "kubectl.kubernetes.io/default-container"
# Matches a pod's events as `kubectl describe pod` does: by uid as well as name, so a
# StatefulSet pod recreated under the same name does not show its predecessor's events.
CONST_K8S_POD_EVENT_FIELD_SELECTOR: Final[str] = (
    "involvedObject.kind=Pod,involvedObject.name={name},involvedObject.uid={uid}"
)
# Set by the kubelet in every pod, and read by the client's in-cluster loader: outside a
# pod there is no service account to connect with.
CONST_K8S_SERVICE_HOST_ENV: Final[str] = "KUBERNETES_SERVICE_HOST"
# What the dashboard banner names when it connects with the pod's service account.
CONST_K8S_IN_CLUSTER_CONTEXT: Final[str] = "in-cluster"
# The default local Minikube cluster context.
CONST_K8S_MINIKUBE_CONTEXT: Final[str] = "minikube"

# ── Kubernetes Doctor Diagnostic Constants ───────────────────────────────────
CONST_K8S_DOCTOR_EVENT_FIELD_SELECTOR: Final[str] = "type=Warning"
CONST_K8S_KIND_PERSISTENT_VOLUME: Final[str] = "PersistentVolume"
CONST_K8S_REASON_VOLUME_FAILED_DELETE: Final[str] = "VolumeFailedDelete"
CONST_K8S_REASON_FAILED_SCHEDULING: Final[str] = "FailedScheduling"
CONST_K8S_REASON_UNHEALTHY: Final[str] = "Unhealthy"
CONST_K8S_REASON_IMAGE_PULL_BACKOFF: Final[str] = "ImagePullBackOff"
CONST_K8S_REASON_ERR_IMAGE_PULL: Final[str] = "ErrImagePull"
CONST_K8S_REASON_CRASH_LOOP_BACKOFF: Final[str] = "CrashLoopBackOff"
CONST_K8S_REASON_OOM_KILLED: Final[str] = "OOMKilled"
CONST_K8S_REASON_ERROR: Final[str] = "Error"

CONST_K8S_DOCTOR_RULE_NODE_NOT_READY: Final[str] = "node-not-ready"
CONST_K8S_DOCTOR_RULE_NODE_CORDONED: Final[str] = "node-cordoned"
CONST_K8S_DOCTOR_RULE_VOLUME_RECLAIM_STUCK: Final[str] = "volume-reclaim-stuck"
CONST_K8S_DOCTOR_RULE_POD_STUCK_TERMINATING: Final[str] = "pod-stuck-terminating"
CONST_K8S_DOCTOR_RULE_POD_CRASHLOOP: Final[str] = "pod-crashloop"
CONST_K8S_DOCTOR_RULE_POD_IMAGE_PULL: Final[str] = "pod-image-pull"
CONST_K8S_DOCTOR_RULE_POD_UNSCHEDULABLE: Final[str] = "pod-unschedulable"
CONST_K8S_DOCTOR_RULE_POD_NOT_READY: Final[str] = "pod-not-ready"
CONST_K8S_DOCTOR_RULE_WARNING_EVENTS: Final[str] = "warning-events"
CONST_K8S_DOCTOR_RULE_VERSION_SKEW: Final[str] = "version-skew"

# ── Kubernetes Doctor: the Gitea stack (#2187) ───────────────────────────────
CONST_K8S_DOCTOR_STACK_GITEA: Final[str] = "gitea"
CONST_K8S_DOCTOR_STACKS: Final[tuple[str, ...]] = (CONST_K8S_DOCTOR_STACK_GITEA,)
"""The stacks that `devops k8s doctor --stack` has checks for."""
CONST_K8S_DOCTOR_GITEA_PLAN_HEADING: Final[str] = "Planned Gitea Stack Checks:"
CONST_K8S_DOCTOR_CHECK_APPLICATION_PREFIX: Final[str] = "application-"
CONST_K8S_DOCTOR_CHECK_VOLUME_RETAINED: Final[str] = "volume-retained"
CONST_K8S_DOCTOR_CHECK_POD_SECURITY: Final[str] = "pod-security-restricted"
CONST_K8S_DOCTOR_CHECK_INGRESS_HOST: Final[str] = "ingress-host"
CONST_K8S_DOCTOR_CHECK_TUNNEL_HOST: Final[str] = "tunnel-host"
CONST_K8S_DOCTOR_CHECK_ANONYMOUS_READ: Final[str] = "anonymous-read-refused"
CONST_K8S_DOCTOR_CHECK_REGISTRY_TOKEN: Final[str] = "registry-token"
CONST_K8S_DOCTOR_CHECK_CLONE_URL: Final[str] = "clone-url"
CONST_K8S_DOCTOR_CHECK_REPOSITORY_DELETED: Final[str] = "temporary-repository-deleted"
CONST_K8S_DOCTOR_CHECK_NO_EGRESS: Final[str] = "no-egress"
CONST_K8S_GITEA_NAMESPACE: Final[str] = "gitea"
CONST_K8S_GITEA_ADMIN_USER: Final[str] = "gitea_admin"
"""Gitea's admin user, the chart's default, which push-secrets writes to Secret gitea-admin."""
CONST_K8S_GITEA_APPLICATIONS: Final[tuple[str, ...]] = ("gitea", "gitea-manifests")
"""The Argo CD Applications of the Gitea stack: the chart and the perimeter."""
CONST_K8S_GITEA_CLAIM: Final[str] = "gitea-shared-storage"
CONST_K8S_GITEA_INGRESS: Final[str] = "gitea-ingress"
CONST_K8S_GITEA_DEPLOYMENT: Final[str] = "gitea"
CONST_K8S_GITEA_CONTAINER: Final[str] = "gitea"
CONST_K8S_GITEA_PLACEHOLDER_HOST: Final[str] = "git.example.com"
"""The host of Ingress gitea-ingress in git; deploy-stack sets the configured domain on it."""
CONST_K8S_ARGOCD_APPLICATION_RESOURCE: Final[str] = "applications.argoproj.io"
CONST_ARGOCD_SYNC_STATUS_SYNCED: Final[str] = "Synced"
CONST_ARGOCD_HEALTH_STATUS_HEALTHY: Final[str] = "Healthy"
CONST_K8S_PVC_PHASE_BOUND: Final[str] = "Bound"
CONST_K8S_RECLAIM_POLICY_RETAIN: Final[str] = "Retain"
CONST_K8S_POD_SECURITY_ENFORCE_LABEL: Final[str] = "pod-security.kubernetes.io/enforce"
CONST_K8S_POD_SECURITY_RESTRICTED: Final[str] = "restricted"
CONST_GITEA_LOGIN_PATH: Final[str] = "/user/login"
CONST_GITEA_REPO_SEARCH_PATH: Final[str] = "/api/v1/repos/search"
CONST_GITEA_REGISTRY_PATH: Final[str] = "/v2/"
CONST_GITEA_CREATE_REPO_PATH: Final[str] = "/api/v1/user/repos"
CONST_GITEA_REPO_PATH_TEMPLATE: Final[str] = "/api/v1/repos/{owner}/{name}"
CONST_GITEA_ANONYMOUS_REFUSALS: Final[frozenset[int]] = frozenset({401, 403})
"""The answers of Gitea to an anonymous API read when `REQUIRE_SIGNIN_VIEW` is set."""
CONST_GITEA_TEMPORARY_REPO_PREFIX: Final[str] = "devops-doctor-"
CONST_GITEA_TEMPORARY_REPO_DESCRIPTION: Final[str] = (
    "A temporary repository of devops k8s doctor. The doctor deletes it."
)
CONST_URL_SCHEME_SSH: Final[str] = "ssh"
"""The scheme of an SSH clone URL in URL form; git's scp-like form has none."""
CONST_HTTP_BEARER_SCHEME: Final[str] = "bearer"
"""The authentication scheme of a token challenge (RFC 6750), compared in lower case."""
CONST_K8S_GITEA_EGRESS_PROBE_URL: Final[str] = "https://github.com"
"""An address outside the cluster that the Gitea pod must not reach."""
CONST_CURL_NO_CONNECTION_EXIT_CODES: Final[frozenset[int]] = frozenset({7, 28})
"""curl's exit codes for a connect that failed (7) or timed out (28) (curl man page, EXIT CODES)."""

CONST_K8S_PV_PHASE_RELEASED: Final[str] = "Released"
CONST_K8S_PV_PHASE_FAILED: Final[str] = "Failed"
CONST_K8S_ORPHAN_VOLUME_PHASES: Final[frozenset[str]] = frozenset(
    {CONST_K8S_PV_PHASE_RELEASED, CONST_K8S_PV_PHASE_FAILED}
)
CONST_K8S_VOLUME_RECLAIM_HEADING: Final[str] = "Planned Kubernetes Volume Reclaim API Requests:"
CONST_K8S_PV_API_PATH_TEMPLATE: Final[str] = "/api/v1/persistentvolumes/{name}"

# ── Local-Path Volume Move (#2186) ─────────────────────────────────────────
CONST_K8S_CONTROL_PLANE_LABEL: Final[str] = f"{CONST_K8S_NODE_ROLE_LABEL_PREFIX}control-plane"
"""The label Kubernetes puts on each control-plane node."""
CONST_K8S_HOSTNAME_LABEL: Final[str] = "kubernetes.io/hostname"
"""The well-known node label that local-path volumes and node selectors match on."""
CONST_K8S_LAST_APPLIED_ANNOTATION: Final[str] = "kubectl.kubernetes.io/last-applied-configuration"
"""Where a client-side apply, Argo CD's included, keeps the object it applied last."""
CONST_ARGOCD_TRACKING_ID_ANNOTATION: Final[str] = "argocd.argoproj.io/tracking-id"
"""Argo CD's annotation tracking: `<application>:<group>/<kind>:<namespace>/<name>`."""
CONST_K8S_ARGOCD_PAUSE_PARENTS: Final[tuple[str, ...]] = ("bootstrap", "cluster")
"""The parent Applications paused, top down, before a child (k8s/README.md, Pausing an Application)."""
CONST_K8S_CLAIM_CONTROLLER_ANNOTATIONS: Final[frozenset[str]] = frozenset(
    {
        "pv.kubernetes.io/bind-completed",
        "pv.kubernetes.io/bound-by-controller",
        "volume.beta.kubernetes.io/storage-provisioner",
        "volume.kubernetes.io/selected-node",
        "volume.kubernetes.io/storage-provisioner",
    }
)
"""The claim annotations the Kubernetes volume controllers write; a claim made again leaves them out."""
CONST_K8S_RECREATED_CLAIM_METADATA_KEYS: Final[tuple[str, ...]] = (
    "name",
    "namespace",
    "labels",
    "ownerReferences",
)
"""The metadata a claim made again from its saved copy keeps, its kept annotations aside."""
CONST_K8S_SCALABLE_WORKLOAD_KINDS: Final[dict[str, str]] = {
    "Deployment": "deployment",
    "StatefulSet": "statefulset",
}
"""The owner kinds a volume move scales, each with its kubectl resource name."""
CONST_K8S_RECLAIM_RETAIN: Final[str] = "Retain"
CONST_K8S_RETENTION_DELETE: Final[str] = "Delete"
CONST_K8S_CLAIM_PHASE_BOUND: Final[str] = "Bound"
CONST_K8S_POD_PHASE_RUNNING: Final[str] = "Running"
CONST_K8S_VOLUME_MOVE_SOURCE_SUFFIX: Final[str] = "-src"
CONST_K8S_VOLUME_MOVE_DESTINATION_SUFFIX: Final[str] = "-dst"
CONST_K8S_VOLUME_MOVE_CLAIM_SUFFIX: Final[str] = "-move"
CONST_K8S_VOLUME_MOVE_SOURCE_DIR: Final[str] = "/src"
CONST_K8S_VOLUME_MOVE_DESTINATION_DIR: Final[str] = "/dst"
CONST_K8S_VOLUME_MOVE_LABELS: Final[dict[str, str]] = {
    "app.kubernetes.io/managed-by": "devops-cli",
    "app.kubernetes.io/component": "volume-move",
}
"""The labels of the copy pods and the temporary claim of a volume move."""
CONST_K8S_VOLUME_MOVE_SAVE_DIR: Final[Path] = Path("k8s") / "volume-move"
"""Where, under the data directory, a volume move saves the claim it deletes."""
CONST_K8S_VOLUME_MOVE_DIGEST_SCRIPT: Final[str] = (
    "set -euo pipefail\n"
    'cd "$1"\n'
    "entries=$(find . -mindepth 1 -printf x | wc -c)\n"
    "files=$(find . -type f -printf x | wc -c)\n"
    "bytes=$(find . -type f -printf '%s\\n' | awk '{s += $1} END {printf \"%.0f\", s}')\n"
    "metadata=$(find . -printf '%y %m %U:%G %P\\n' | LC_ALL=C sort | sha256sum | cut -d' ' -f1)\n"
    "content=$(find . -type f -print0 | LC_ALL=C sort -z | xargs -0r sha256sum | sha256sum"
    " | cut -d' ' -f1)\n"
    "printf 'entries %s\\nfiles %s\\nbytes %s\\nmetadata %s\\ncontent %s\\n'"
    ' "$entries" "$files" "$bytes" "$metadata" "$content"\n'
)
"""The bash script each copy pod runs on its side, with the directory as `$1` (debian:trixie-slim).

It counts the entries and the regular files, adds the bytes of the regular files (not `du`,
which counts directory blocks), and makes a digest of each entry's type, mode, numeric owner and
path, and a digest of the content of the regular files, both in byte order.
"""


# ── Dashboard TUI Domains ────────────────────────────────────────────────────
# Each domain is one tab of the workstation dashboard, refreshed by its own worker.
CONST_DASHBOARD_DOMAIN_K8S: Final[str] = "k8s"
CONST_DASHBOARD_DOMAIN_DOCKER: Final[str] = "docker"
CONST_DASHBOARD_DOMAIN_TELEMETRY: Final[str] = "telemetry"
CONST_DASHBOARD_DOMAIN_VALKEY: Final[str] = "valkey"
CONST_DASHBOARD_DOMAINS: Final[tuple[str, ...]] = (
    CONST_DASHBOARD_DOMAIN_K8S,
    CONST_DASHBOARD_DOMAIN_DOCKER,
    CONST_DASHBOARD_DOMAIN_TELEMETRY,
    CONST_DASHBOARD_DOMAIN_VALKEY,
)
# Human-readable labels used for tab titles and status banners.
CONST_DASHBOARD_DOMAIN_LABELS: Final[dict[str, str]] = {
    CONST_DASHBOARD_DOMAIN_K8S: "Kubernetes",
    CONST_DASHBOARD_DOMAIN_DOCKER: "Docker",
    CONST_DASHBOARD_DOMAIN_TELEMETRY: "Telemetry",
    CONST_DASHBOARD_DOMAIN_VALKEY: "Valkey Cache",
}

# ── Docker Resource Sub-Tabs ─────────────────────────────────────────────────
# Every Docker resource lives under the single Docker tab and is projected from one
# DockerSummary, so the whole inventory costs one daemon round trip per refresh.
CONST_DOCKER_RESOURCE_CONTAINERS: Final[str] = "containers"
CONST_DOCKER_RESOURCE_IMAGES: Final[str] = "images"
CONST_DOCKER_RESOURCE_NETWORKS: Final[str] = "networks"
CONST_DOCKER_RESOURCE_VOLUMES: Final[str] = "volumes"
CONST_DOCKER_RESOURCE_REGISTRIES: Final[str] = "registries"
CONST_DOCKER_RESOURCES: Final[tuple[str, ...]] = (
    CONST_DOCKER_RESOURCE_CONTAINERS,
    CONST_DOCKER_RESOURCE_IMAGES,
    CONST_DOCKER_RESOURCE_NETWORKS,
    CONST_DOCKER_RESOURCE_VOLUMES,
    CONST_DOCKER_RESOURCE_REGISTRIES,
)
CONST_DOCKER_RESOURCE_LABELS: Final[dict[str, str]] = {
    CONST_DOCKER_RESOURCE_CONTAINERS: "Containers",
    CONST_DOCKER_RESOURCE_IMAGES: "Images",
    CONST_DOCKER_RESOURCE_NETWORKS: "Networks",
    CONST_DOCKER_RESOURCE_VOLUMES: "Volumes",
    CONST_DOCKER_RESOURCE_REGISTRIES: "Registries",
}
# Tab holding the streamed log pane. Not a data domain: it has no provider and is filled
# by selecting a pod rather than by the refresh cycle.
CONST_LOGS_TAB_ID: Final[str] = "tab-logs"
# The dashboard's top-level tabs, told apart from the tabs nested inside a panel.
CONST_DASHBOARD_TABS_ID: Final[str] = "dashboard-tabs"
# The widget a tab focuses when it becomes active, so its keys work without pressing Tab.
# A tab not listed here focuses the first widget in it that can take focus.
CONST_DASHBOARD_TAB_FOCUS: Final[dict[str, str]] = {
    f"tab-{CONST_DASHBOARD_DOMAIN_K8S}": f"#{CONST_DASHBOARD_DOMAIN_K8S}-table",
    f"tab-{CONST_DASHBOARD_DOMAIN_TELEMETRY}": "#telemetry-table",
    CONST_LOGS_TAB_ID: "#log-pane",
}

# ── W3C Trace Context ────────────────────────────────────────────────────────
# https://www.w3.org/TR/trace-context/
CONST_TRACEPARENT_VERSION: Final[str] = "00"
# Version "ff" is reserved by the specification and must never be accepted.
CONST_TRACEPARENT_INVALID_VERSION: Final[str] = "ff"
CONST_TRACE_ID_HEX_LENGTH: Final[int] = 32
CONST_SPAN_ID_HEX_LENGTH: Final[int] = 16
CONST_TRACE_FLAGS_HEX_LENGTH: Final[int] = 2
CONST_TRACE_FLAG_SAMPLED: Final[str] = "01"
CONST_TRACE_FLAG_NOT_SAMPLED: Final[str] = "00"
# HTTP headers are lowercase; process environment variables are uppercase. Using one
# spelling for both is what lets an injected value be shadowed by an inherited one.
CONST_TRACEPARENT_HEADER: Final[str] = "traceparent"
CONST_TRACESTATE_HEADER: Final[str] = "tracestate"
CONST_TRACEPARENT_ENV_VAR: Final[str] = "TRACEPARENT"
CONST_TRACESTATE_ENV_VAR: Final[str] = "TRACESTATE"
# The specification caps tracestate at 32 list members.
CONST_TRACESTATE_MAX_MEMBERS: Final[int] = 32

# ── SARIF (Static Analysis Results Interchange Format) ───────────────────────
# https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
CONST_SARIF_VERSION: Final[str] = "2.1.0"
CONST_SARIF_SCHEMA_URI: Final[str] = "https://json.schemastore.org/sarif-2.1.0.json"
# SARIF defines exactly these result levels; anything else is rejected by consumers.
CONST_SARIF_LEVEL_ERROR: Final[str] = "error"
CONST_SARIF_LEVEL_WARNING: Final[str] = "warning"
CONST_SARIF_LEVEL_NOTE: Final[str] = "note"
CONST_SARIF_LEVEL_NONE: Final[str] = "none"
CONST_SARIF_LEVELS: Final[frozenset[str]] = frozenset(
    {
        CONST_SARIF_LEVEL_ERROR,
        CONST_SARIF_LEVEL_WARNING,
        CONST_SARIF_LEVEL_NOTE,
        CONST_SARIF_LEVEL_NONE,
    }
)
# GitHub code scanning ranks by this property rather than by SARIF level, so both are
# emitted: the level for generic consumers, the score for GitHub's severity ordering.
CONST_SARIF_SECURITY_SEVERITY_PROPERTY: Final[str] = "security-severity"
# Fingerprint key. SARIF requires a versioned name so a later change to the scheme does
# not silently re-open every previously suppressed result.
CONST_SARIF_FINGERPRINT_KEY: Final[str] = "devopsCli/v2"

# ── Security Finding Taxonomy ────────────────────────────────────────────────
CONST_SEVERITY_CRITICAL: Final[str] = "CRITICAL"
CONST_SEVERITY_HIGH: Final[str] = "HIGH"
CONST_SEVERITY_MEDIUM: Final[str] = "MEDIUM"
CONST_SEVERITY_LOW: Final[str] = "LOW"
CONST_SEVERITY_INFO: Final[str] = "INFO"
# Ordered most severe first; the index doubles as the ranking key.
CONST_SEVERITY_ORDER: Final[tuple[str, ...]] = (
    CONST_SEVERITY_CRITICAL,
    CONST_SEVERITY_HIGH,
    CONST_SEVERITY_MEDIUM,
    CONST_SEVERITY_LOW,
    CONST_SEVERITY_INFO,
)
CONST_SEVERITY_TO_SARIF_LEVEL: Final[dict[str, str]] = {
    CONST_SEVERITY_CRITICAL: CONST_SARIF_LEVEL_ERROR,
    CONST_SEVERITY_HIGH: CONST_SARIF_LEVEL_ERROR,
    CONST_SEVERITY_MEDIUM: CONST_SARIF_LEVEL_WARNING,
    CONST_SEVERITY_LOW: CONST_SARIF_LEVEL_NOTE,
    CONST_SEVERITY_INFO: CONST_SARIF_LEVEL_NOTE,
}
# GitHub's documented banding: 9.0+ critical, 7.0+ high, 4.0+ medium, 0.1+ low.
CONST_SEVERITY_TO_SECURITY_SCORE: Final[dict[str, str]] = {
    CONST_SEVERITY_CRITICAL: "9.5",
    CONST_SEVERITY_HIGH: "7.5",
    CONST_SEVERITY_MEDIUM: "5.0",
    CONST_SEVERITY_LOW: "2.0",
    CONST_SEVERITY_INFO: "0.5",
}
# Severity vocabularies differ per scanner; these are the spellings actually emitted.
CONST_SEVERITY_ALIASES: Final[dict[str, str]] = {
    "CRITICAL": CONST_SEVERITY_CRITICAL,
    "BLOCKER": CONST_SEVERITY_CRITICAL,
    "HIGH": CONST_SEVERITY_HIGH,
    "ERROR": CONST_SEVERITY_HIGH,
    "MEDIUM": CONST_SEVERITY_MEDIUM,
    "MODERATE": CONST_SEVERITY_MEDIUM,
    "WARNING": CONST_SEVERITY_MEDIUM,
    "WARN": CONST_SEVERITY_MEDIUM,
    "LOW": CONST_SEVERITY_LOW,
    "MINOR": CONST_SEVERITY_LOW,
    "NOTE": CONST_SEVERITY_LOW,
    "INFO": CONST_SEVERITY_INFO,
    "INFORMATIONAL": CONST_SEVERITY_INFO,
    "UNKNOWN": CONST_SEVERITY_INFO,
    "NONE": CONST_SEVERITY_INFO,
}
CONST_SARIF_LEVEL_TO_SEVERITY: Final[dict[str, str]] = {
    CONST_SARIF_LEVEL_ERROR: CONST_SEVERITY_HIGH,
    CONST_SARIF_LEVEL_WARNING: CONST_SEVERITY_MEDIUM,
    CONST_SARIF_LEVEL_NOTE: CONST_SEVERITY_LOW,
    CONST_SARIF_LEVEL_NONE: CONST_SEVERITY_INFO,
}
# What a review prints to the terminal unless asked for all of it (#987): the findings table
# lists MEDIUM and above, detail panels follow for HIGH and above, and the rest are counted on
# one line that points at review.md.
CONST_REVIEW_CONSOLE_TABLE_SEVERITIES: Final[frozenset[str]] = frozenset(
    {CONST_SEVERITY_CRITICAL, CONST_SEVERITY_HIGH, CONST_SEVERITY_MEDIUM}
)
CONST_REVIEW_CONSOLE_PANEL_SEVERITIES: Final[frozenset[str]] = frozenset(
    {CONST_SEVERITY_CRITICAL, CONST_SEVERITY_HIGH}
)
# The order a finding count by status is printed in: verified first.
CONST_REVIEW_STATUS_ORDER: Final[tuple[str, ...]] = (
    CONST_STATUS_VERIFIED,
    CONST_STATUS_UNVERIFIED,
    CONST_STATUS_MITIGATED,
    CONST_STATUS_INVALIDATED,
)
# A scanned dependency's severity is that of its worst known vulnerability; CLEAN and UNCHECKED
# are the only other values (`DependencySpec.severity`).
CONST_DEPENDENCY_VULNERABLE_SEVERITIES: Final[frozenset[str]] = frozenset(
    {CONST_SEVERITY_CRITICAL, CONST_SEVERITY_HIGH, CONST_SEVERITY_MEDIUM, CONST_SEVERITY_LOW}
)
CONST_DEPENDENCY_SEVERITY_CLEAN: Final[str] = "CLEAN"
# Depth limit for suppression policy inheritance, so a misconfigured chain fails with a
# clear error rather than recursing until the interpreter stops it.
CONST_SUPPRESSION_MAX_INHERITANCE_DEPTH: Final[int] = 10

# ── GitHub SSH Host Keys ─────────────────────────────────────────────────────
# GitHub's published OpenSSH known_hosts lines, published at https://api.github.com/meta
# (.ssh_keys) and documented at "GitHub's SSH key fingerprints":
# https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints
CONST_GITHUB_KNOWN_HOSTS_LINES: Final[tuple[str, ...]] = (
    "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl",
    (
        "github.com ecdsa-sha2-nistp256"
        " AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBEmKSENjQEezOmxkZMy7opKgwFB9nkt5YRrYMjNuG5N87uRgg6CLrbo5wAdT/y6v0mKV0U2w0WZ2YB/++Tpockg="
    ),
    (
        "github.com ssh-rsa"
        " AAAAB3NzaC1yc2EAAAADAQABAAABgQCj7ndNxQowgcQnjshcLrqPEiiphnt+VTTvDP6mHBL9j1aNUkY4Ue1gvwnGLVlOhGeYrnZaMgRK6+PKCUXaDbC7qtbW8gIkhL7aGCsOr/C56SJMy/BCZfxd1nWzAOxSDPgVsmerOBYfNqltV9/hWCqBywINIR+5dIg6JTJ72pcEpEjcYgXkE2YEFXV1JHnsKgbLWNlhScqb2UmyRkQyytRLtL+38TGxkxCflmO+5Z8CSSNY7GidjMIZ7Q4zMjA2n1nGrlTDkzwDCsw+wqFPGQA179cnfGWOWRVruj16z6XyvxvjJwbz0wQZ75XK5tKSb7FNyeIEs4TT4jk+S4dhPeAUC5y+bDYirYgM4GC7uEnztnZyaVWQ7B381AK4Qdrwt51ZqExKbQpTUNn+EjqoTwvqNj4kqx5QUCI0ThS/YkOxJCXmPUWZbhjpCg56i+2aB6CmK2JGhn57K5mj0MNdBXA4/WnwH6XoPWJzK5Nyu2zB3nAZp+S5hpQs+p1vN1/wsjk="
    ),
)

# ── Issue And Milestone States ───────────────────────────────────────────────
CONST_ISSUE_STATE_OPEN: Final[str] = "open"
CONST_ISSUE_STATE_CLOSED: Final[str] = "closed"
CONST_GH_MILESTONE_STATE_ALL: Final[str] = "all"
CONST_GH_MILESTONE_STATE_FILTERS: Final[frozenset[str]] = frozenset(
    {CONST_ISSUE_STATE_OPEN, CONST_ISSUE_STATE_CLOSED, CONST_GH_MILESTONE_STATE_ALL}
)
# Series listed in the telemetry panel. A Prometheus instance exposes thousands of metric
# names; rendering all of them costs more than it tells the reader.
CONST_TELEMETRY_PANEL_MAX_SERIES: Final[int] = 50

# ── Pull Request Grounding ───────────────────────────────────────────────────
# Readiness holds a pull request to the one item it delivers: it targets the default branch,
# closes exactly one open issue of its repository that holds a `priority/*` label (a roadmap
# item), and archives that issue's OpenSpec change (`CONST_OPENSPEC_ARCHIVED_FOLDER_RE`). GitHub closes the issue when the
# pull request merges.
# The `pulls/{n}/files` statuses under which the path is new in the pull request's head. GitHub's
# full set is added, removed, modified, renamed, copied, changed (mode only) and unchanged.
CONST_PR_FILE_ADDED_STATUSES: Final[frozenset[str]] = frozenset({"added", "renamed", "copied"})
# The `pulls/{n}/files` status of a file that the pull request deletes from its head.
CONST_PR_FILE_REMOVED_STATUS: Final[str] = "removed"
# GitHub's `closingIssuesReferences` page sizes for one readiness read: the issues a pull request
# closes, where more than one is already a blocker, and the labels of each, GraphQL's page
# maximum of 100.
CONST_PR_CLOSING_ISSUES_PAGE: Final[int] = 10
CONST_PR_CLOSING_ISSUE_LABELS_PAGE: Final[int] = 100
# The `gh pr list --author` value `devops pr update --all` lists with: the account gh runs as,
# so a pull request that a bot or another person owns is never updated.
CONST_PR_UPDATE_AUTHOR: Final[str] = "@me"
# The declared surfaces where defect pull requests must record hardening guardrails or lessons (#697, #1151, #1979).
CONST_HARDENING_SURFACES: Final[tuple[str, ...]] = (
    "docs/TESTING.md",
    "ARCHITECTURE.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "src/devops_cli/ai/tasks/*.md",
    "src/devops_cli/ai/knowledge_base/",
    ".devops/review.toml",
    "src/devops_cli/review/rules/",
)
# Conventional commit title pattern identifying a bug fix pull request (#697).
CONST_DEFECT_TITLE_PATTERN: Final[str] = r"^fix(?:\([^()]*\))?!?:\s*"

# ── Cluster-Native Service Addressing ────────────────────────────────────────
# A k8s:// URL names a Service rather than a host and port, so the same configuration
# resolves on every cluster without a port-forward:
#   k8s://<namespace>/<service>:<port>[/path]        backend speaks http
#   k8s+https://<namespace>/<service>:<port>[/path]  backend speaks https
CONST_K8S_URL_SCHEME: Final[str] = "k8s"
CONST_K8S_URL_SCHEME_TLS: Final[str] = "k8s+https"
CONST_K8S_URL_SCHEMES: Final[frozenset[str]] = frozenset(
    {CONST_K8S_URL_SCHEME, CONST_K8S_URL_SCHEME_TLS}
)
# The API server exposes every Service at this path, which is what removes the need for a
# local port: https://kubernetes.io/docs/tasks/access-application-cluster/access-cluster/
CONST_K8S_SERVICE_PROXY_TEMPLATE: Final[str] = (
    "/api/v1/namespaces/{namespace}/services/{target}/proxy"
)
# How `configure-urls` records endpoints. "nodeport" writes a reachable host and port,
# which is fast but cluster-specific; "proxy" writes k8s:// service addresses, which carry
# no host and therefore resolve on whichever cluster is active.
CONST_ADDRESSING_NODEPORT: Final[str] = "nodeport"
CONST_ADDRESSING_PROXY: Final[str] = "proxy"
CONST_ADDRESSING_FQDN: Final[str] = "fqdn"
CONST_ADDRESSING_INGRESS: Final[str] = "ingress"
CONST_ADDRESSING_MODES: Final[frozenset[str]] = frozenset(
    {
        CONST_ADDRESSING_NODEPORT,
        CONST_ADDRESSING_PROXY,
        CONST_ADDRESSING_FQDN,
        CONST_ADDRESSING_INGRESS,
    }
)
CONST_K8S_INGRESS_SERVICE_PATTERNS: Final[tuple[tuple[str, str, str], ...]] = (
    ("argocd.url", "argocd", "argocd"),
    ("grafana.url", "monitoring", "grafana"),
    ("prometheus.url", "monitoring", "prometheus-server"),
    ("open_webui.url", "llm", "chat"),
    ("qdrant.url", "llm", "qdrant"),
    ("ai.gateway_url", "llm", "ai"),
    ("ai.gateway_url", "llm", "llm-gateway"),
)
# Lines held between the stream reader and the renderer. Bounded so a producer faster than
# the terminal cannot grow it without limit; the log buffer is the retention mechanism.
CONST_LOG_STREAM_QUEUE_SIZE: Final[int] = 2000
# Git ignore evaluation. `.git/info/exclude` is the repository-local ignore file, applied
# before any `.gitignore` so a tracked-in rule can override it.
CONST_GITIGNORE_FILENAME: Final[str] = ".gitignore"
CONST_GIT_INFO_EXCLUDE_RELATIVE: Final[str] = ".git/info/exclude"
# pathspec's git ignore pattern factory. The older "gitwildmatch" alias is deprecated and
# emits a warning per compiled file; the semantics are identical.
CONST_GITIGNORE_PATTERN_STYLE: Final[str] = "gitignore"
# What each built-in Projects v2 workflow must be set to for this repository's task flow
# to keep a board honest without anyone touching it. GitHub's GraphQL API exposes only
# `deleteProjectV2Workflow` -- there is no mutation that enables or configures one -- so
# these are reported as a gap against the live board rather than applied.
# Auto-add stays off because intake (#742) is the one way onto the board; auto-close stays off
# because an issue closes only when the pull request that closes it merges; and auto-archive
# stays off because archived items drop out of the item lists the roadmap jobs read. GitHub
# links a pull request into the default branch to the issues it closes, so the built-in
# workflow sets In Review and `devops gh project sync` reads no pull request text.
CONST_PROJECT_WORKFLOW_EXPECTATIONS: Final[dict[str, str]] = {
    "Item added to project": "Set Status to New",
    "Item closed": "Set Status to Done",
    "Item reopened": "Set Status to New",
    "Pull request linked to issue": "Set Status to In Review",
    "Pull request merged": "Set Status to Done",
}
# Stand-ins for values a dry run cannot know. A node address and an assigned NodePort are
# only resolved by talking to the cluster, so a preview names their shape rather than
# inventing a concrete one that describes some other cluster.
CONST_PLACEHOLDER_NODE: Final[str] = "<node>"
CONST_PLACEHOLDER_PORT: Final[str] = "<port>"
# The representations a command can be asked to write. `table` is the human-readable
# default; the rest are machine-readable and must round-trip the same payload.
CONST_OUTPUT_FORMAT_TABLE: Final[str] = "table"
CONST_OUTPUT_FORMAT_JSON: Final[str] = "json"
CONST_OUTPUT_FORMAT_YAML: Final[str] = "yaml"
CONST_OUTPUT_FORMATS: Final[frozenset[str]] = frozenset(
    {CONST_OUTPUT_FORMAT_TABLE, CONST_OUTPUT_FORMAT_JSON, CONST_OUTPUT_FORMAT_YAML}
)
# The trees that the `constructs` scan reads, and the `files` globs of each rule: the network
# construct rules hold src/, and the test rules hold tests/.
CONST_AST_GREP_SCAN_ROOTS: Final[tuple[str, ...]] = ("src", "tests")
CONST_AST_GREP_SCAN_ARGS: Final[tuple[str, ...]] = (
    "scan",
    "--error=unused-suppression",
    "--error=no-suppress-all",
    *CONST_AST_GREP_SCAN_ROOTS,
)
# Who adjudicated a recorded finding when nothing says. The feedback exporter defaulted to
# "human", which routed every finding the verifier never reached into the human
# ground-truth bucket -- the one part of that dataset trusted because a person wrote it.
CONST_VERIFIED_BY_UNKNOWN: Final[str] = "unknown"
# A verdict a person gave through `devops review verify`: the only ground truth, which review
# history ranks above any number of machine verdicts.
CONST_VERIFIED_BY_HUMAN: Final[str] = "human"
# A verdict an agent gave, which sessions saved before #1150 hold: review history never counts it
# as a person's.
CONST_VERIFIED_BY_AGENT: Final[str] = "agent"
# The prefix of a verdict a deterministic check gave (`deterministic:syntax_error`, ...). Such a
# label is a machine's, not a person's, so `ai prompt-eval` leaves it out unless asked (#950).
CONST_VERIFIED_BY_DETERMINISTIC_PREFIX: Final[str] = "deterministic:"

# ── Review Report Integrity (#948) ───────────────────────────────────────────
# Files a review keeps off persona pages, by repository-relative path: planning documents and
# generated references, where no persona finding held up in past branch reviews. Lockfiles
# (`CONST_REVIEW_GENERATED_FILES`) stay off by name, for their size. Both still reach the secret
# scan. Patterns follow `PurePath.full_match`.
CONST_REVIEW_ROUTED_PATH_PATTERNS: Final[tuple[str, ...]] = (
    CONST_CHANGELOG_FILENAME,
    "docs/adr/**",
    "docs/commands/*.md",
    "docs/CLI_REFERENCE.md",
    "openspec/**",
    ".claude/skills/openspec-*/**",
    ".agents/skills/openspec-*/**",
    ".kilocode/skills/openspec-*/**",
    ".agents/skills/.openspec-target",
)
# The scanner results that are secrets, by tool, with the rule ids that are (None: every rule).
# Gitleaks reports nothing else, and Trivy's secret results carry the `SECRET` rule id its parser
# titles them with. `[severity_caps]` never caps one: a secret in a test or a document is still a
# secret (#1301).
CONST_REVIEW_SECRET_SCANNER_RULES: Final[dict[str, frozenset[str] | None]] = {
    "gitleaks": None,
    "trivy": frozenset({"SECRET"}),
}
# The defect class (`review_schema.DefectClass`) of the CWE ids review findings cite. A CWE not
# listed falls back to the keyword table over the finding's own words.
CONST_REVIEW_CWE_DEFECT_CLASSES: Final[dict[int, str]] = {
    16: "security_misconfiguration",
    20: "input_validation",
    22: "path_traversal",
    23: "path_traversal",
    35: "path_traversal",
    59: "path_traversal",
    74: "injection",
    77: "injection",
    78: "injection",
    79: "injection",
    89: "injection",
    94: "injection",
    95: "injection",
    113: "injection",
    117: "injection",
    190: "logic_error",
    191: "logic_error",
    200: "information_exposure",
    209: "information_exposure",
    250: "access_control",
    256: "secret_exposure",
    259: "secret_exposure",
    269: "access_control",
    276: "access_control",
    284: "access_control",
    285: "access_control",
    287: "authentication",
    295: "insecure_transport",
    306: "authentication",
    307: "authentication",
    310: "cryptography",
    311: "cryptography",
    312: "secret_exposure",
    319: "insecure_transport",
    326: "cryptography",
    327: "cryptography",
    328: "cryptography",
    330: "cryptography",
    352: "access_control",
    362: "race_condition",
    366: "race_condition",
    367: "race_condition",
    377: "race_condition",
    390: "error_handling",
    391: "error_handling",
    396: "error_handling",
    397: "error_handling",
    399: "resource_exhaustion",
    400: "resource_exhaustion",
    434: "input_validation",
    494: "supply_chain",
    502: "injection",
    522: "secret_exposure",
    532: "information_exposure",
    538: "information_exposure",
    542: "information_exposure",
    601: "input_validation",
    611: "injection",
    674: "resource_exhaustion",
    703: "error_handling",
    732: "access_control",
    754: "error_handling",
    755: "error_handling",
    770: "resource_exhaustion",
    798: "secret_exposure",
    829: "supply_chain",
    835: "resource_exhaustion",
    862: "access_control",
    863: "access_control",
    917: "injection",
    918: "ssrf",
    1037: "security",
    1104: "supply_chain",
    1188: "security_misconfiguration",
    1333: "resource_exhaustion",
    1357: "supply_chain",
}
# Words that name a defect class, matched as whole words in a finding's category, or in its title
# when it has none. The first match wins, so narrower classes come first; text that matches none
# is `other`. Keywords are lower case, words joined by single spaces.
CONST_REVIEW_DEFECT_KEYWORDS: Final[tuple[tuple[str, str], ...]] = (
    ("path traversal", "path_traversal"),
    ("directory traversal", "path_traversal"),
    ("traversal", "path_traversal"),
    ("symlink", "path_traversal"),
    ("csrf", "access_control"),
    ("cross site request forgery", "access_control"),
    ("ssrf", "ssrf"),
    ("request forgery", "ssrf"),
    ("injection", "injection"),
    ("xss", "injection"),
    ("cross site scripting", "injection"),
    ("deserialization", "injection"),
    ("code execution", "injection"),
    ("rce", "injection"),
    ("eval", "injection"),
    ("exec", "injection"),
    ("secret", "secret_exposure"),
    ("secrets", "secret_exposure"),
    ("credential", "secret_exposure"),
    ("credentials", "secret_exposure"),
    ("password", "secret_exposure"),
    ("passwords", "secret_exposure"),
    ("api key", "secret_exposure"),
    ("api keys", "secret_exposure"),
    ("private key", "secret_exposure"),
    ("memory leak", "resource_exhaustion"),
    ("information exposure", "information_exposure"),
    ("information disclosure", "information_exposure"),
    ("information leak", "information_exposure"),
    ("information leakage", "information_exposure"),
    ("sensitive data", "information_exposure"),
    ("disclosure", "information_exposure"),
    ("leak", "information_exposure"),
    ("leaks", "information_exposure"),
    ("leakage", "information_exposure"),
    ("authentication", "authentication"),
    ("unauthenticated", "authentication"),
    ("identification", "authentication"),
    ("authorization", "access_control"),
    ("unauthorized", "access_control"),
    ("access control", "access_control"),
    ("privilege", "access_control"),
    ("privileges", "access_control"),
    ("privileged", "access_control"),
    ("rbac", "access_control"),
    ("permission", "access_control"),
    ("permissions", "access_control"),
    ("cryptography", "cryptography"),
    ("cryptographic", "cryptography"),
    ("encryption", "cryptography"),
    ("cipher", "cryptography"),
    ("weak hash", "cryptography"),
    ("tls", "insecure_transport"),
    ("ssl", "insecure_transport"),
    ("transport", "insecure_transport"),
    ("insecure communication", "insecure_transport"),
    ("cleartext", "insecure_transport"),
    ("unencrypted", "insecure_transport"),
    ("certificate", "insecure_transport"),
    ("cors", "network_exposure"),
    ("network", "network_exposure"),
    ("networking", "network_exposure"),
    ("networkpolicy", "network_exposure"),
    ("segmentation", "network_exposure"),
    ("firewall", "network_exposure"),
    ("ingress", "network_exposure"),
    ("egress", "network_exposure"),
    ("0 0 0 0", "network_exposure"),
    ("exposure", "information_exposure"),
    ("supply chain", "supply_chain"),
    ("dependency", "supply_chain"),
    ("dependencies", "supply_chain"),
    ("provenance", "supply_chain"),
    ("unpinned", "supply_chain"),
    ("typosquat", "supply_chain"),
    ("versioning", "supply_chain"),
    ("denial of service", "resource_exhaustion"),
    ("dos", "resource_exhaustion"),
    ("redos", "resource_exhaustion"),
    ("resource", "resource_exhaustion"),
    ("resources", "resource_exhaustion"),
    ("exhaustion", "resource_exhaustion"),
    ("unbounded", "resource_exhaustion"),
    ("rate limit", "resource_exhaustion"),
    ("rate limiting", "resource_exhaustion"),
    ("timeout", "resource_exhaustion"),
    ("performance", "resource_exhaustion"),
    ("race", "race_condition"),
    ("concurrency", "race_condition"),
    ("concurrent", "race_condition"),
    ("toctou", "race_condition"),
    ("thread safety", "race_condition"),
    ("deadlock", "race_condition"),
    ("error handling", "error_handling"),
    ("exception", "error_handling"),
    ("exceptions", "error_handling"),
    ("except", "error_handling"),
    ("swallows", "error_handling"),
    ("swallowed", "error_handling"),
    ("validation", "input_validation"),
    ("unvalidated", "input_validation"),
    ("sanitization", "input_validation"),
    ("unsanitized", "input_validation"),
    ("regex", "input_validation"),
    ("subprocess", "process_safety"),
    ("process", "process_safety"),
    ("processes", "process_safety"),
    ("zombie", "process_safety"),
    ("integrity", "data_integrity"),
    ("corruption", "data_integrity"),
    ("deletion", "data_integrity"),
    ("data loss", "data_integrity"),
    ("resilience", "reliability"),
    ("reliability", "reliability"),
    ("availability", "reliability"),
    ("liveness", "reliability"),
    ("readiness probe", "reliability"),
    ("probe", "reliability"),
    ("probes", "reliability"),
    ("affinity", "reliability"),
    ("retry", "reliability"),
    ("retries", "reliability"),
    ("syntax", "syntax_error"),
    ("test", "testing"),
    ("tests", "testing"),
    ("testing", "testing"),
    ("fixture", "testing"),
    ("fixtures", "testing"),
    ("mock", "testing"),
    ("mocks", "testing"),
    ("coverage", "testing"),
    ("documentation", "documentation"),
    ("docs", "documentation"),
    ("docstring", "documentation"),
    ("docstrings", "documentation"),
    ("readme", "documentation"),
    ("comment", "documentation"),
    ("comments", "documentation"),
    ("typo", "documentation"),
    ("changelog", "documentation"),
    ("logic", "logic_error"),
    ("off by one", "logic_error"),
    ("overflow", "logic_error"),
    ("misconfiguration", "security_misconfiguration"),
    ("hardening", "security_misconfiguration"),
    ("insecure default", "security_misconfiguration"),
    ("security configuration", "security_misconfiguration"),
    ("configuration security", "security_misconfiguration"),
    ("security context", "security_misconfiguration"),
    ("configuration", "configuration"),
    ("config", "configuration"),
    ("deployment", "configuration"),
    ("settings", "configuration"),
    ("manifest", "configuration"),
    ("quality", "code_quality"),
    ("maintainability", "code_quality"),
    ("redundancy", "code_quality"),
    ("redundant", "code_quality"),
    ("duplicate", "code_quality"),
    ("duplication", "code_quality"),
    ("dead code", "code_quality"),
    ("unused", "code_quality"),
    ("best practice", "code_quality"),
    ("best practices", "code_quality"),
    ("naming", "code_quality"),
    ("readability", "code_quality"),
    ("complexity", "code_quality"),
    ("deprecated", "code_quality"),
    ("user experience", "code_quality"),
    ("security", "security"),
    ("insecure", "security"),
    ("unsafe", "security"),
    ("vulnerability", "security"),
    ("vulnerabilities", "security"),
    ("vulnerable", "security"),
    ("owasp", "security"),
)

# Maximum number of schema validation error field paths preserved in error reflection
# prompts to bound token consumption while retaining sufficient diagnostic fidelity.
CONST_MAX_SCHEMA_REFLECTION_ERRORS: Final[int] = 5

# Maximum character length for representing the erroneous input value in error reflection.
CONST_MAX_INPUT_VALUE_REPR_LENGTH: Final[int] = 60

# ── LLM Gateway Dynamic Hardware Routing Constants ────────────────────────────
CONST_CONTINUOUS_BATCHING_ENGINES: Final[frozenset[str]] = frozenset({"vllm", "sglang", "tgi"})
CONST_ENGINE_MULTIPLIER_CONTINUOUS_BATCHING: Final[float] = 3.0
CONST_ENGINE_MULTIPLIER_SERIAL: Final[float] = 1.0
CONST_DEFAULT_CONTINUOUS_CONCURRENCY: Final[int] = 64
CONST_DEFAULT_SERIAL_CONCURRENCY: Final[int] = 1

# ── Bubblewrap Host Sandbox Confinement Constants ──────────────────────────────
CONST_HOST_SANDBOX_DEFAULT_ENV: tuple[tuple[str, str], ...] = (
    ("HOME", "/tmp"),  # nosec B108 # the HOME of a sandboxed child on its own tmpfs
    ("PATH", "/usr/local/bin:/usr/bin:/bin"),
    ("LANG", "C.UTF-8"),
    ("LC_ALL", "C.UTF-8"),
    ("TMPDIR", "/tmp"),  # nosec B108 # the TMPDIR of a sandboxed child on its own tmpfs
    ("PYTHONDONTWRITEBYTECODE", "1"),
    ("PYTHONWARNINGS", "ignore::SyntaxWarning"),
)
CONST_HOST_SANDBOX_SYSTEM_SYMLINKS: tuple[str, ...] = ("/bin", "/lib", "/lib64", "/sbin")
CONST_HOST_SANDBOX_SYSTEM_DIRS: tuple[str, ...] = ("/usr",)
# The reviewed repository's virtualenv `bin`, relative to its root, which leads the sandbox PATH.
CONST_HOST_SANDBOX_VIRTUALENV_BIN: tuple[str, ...] = (".venv", "bin")
# CPython's standard-library landmark below an installation prefix (`lib/python3.14/os.py`,
# `lib/python3.14t/os.py` for a free-threaded build), which `getpath` itself looks for.
CONST_PYTHON_STDLIB_LANDMARK_GLOB: str = "lib/python3.*/os.py"

# The limits a review tool runs under in the sandbox (#772). `prlimit` sets them, so no code of
# devops-cli calls setrlimit. There is no limit on processes: RLIMIT_NPROC counts every process
# of the user, so inside the sandbox it would starve the host's own shells and servers
# (`_run_sandbox_process` in sandbox/host.py has the reason in full).
# CPU seconds one process of a tool may use before the kernel ends it.
CONST_TOOL_CPU_LIMIT_SECONDS: Final[int] = 600
# The least address space, in bytes, a tool may be given. It is the default too. Go tools reserve
# more address space than they use. Measured on 2026-10-24 (#2096): Bandit, Ruff, Trivy,
# kube-linter, Pluto and osv-scanner run under it on a small tree, and mypy runs under it on two
# modules of devops-cli and all that they import, with no cache.
CONST_TOOL_MIN_ADDRESS_SPACE_BYTES: Final[int] = 2 * 1024**3
# The tools that need more address space than the least, by name, with the value they get.
# Measured with `prlimit --as` on 2026-10-24 (#2096). Gitleaks 8.30.1 runs RE2 as WebAssembly in
# wazero, which reserves 4 GiB for the memory of the module: it stops at 5 GiB and runs at 6 GiB,
# on one file and on the source tree of devops-cli. Semgrep 1.179.0 reserves memory for each job:
# with `CONST_SEMGREP_JOBS` jobs it stops at 4 GiB and runs at 8 GiB on 100 files of devops-cli.
# Each value is about twice what the tool needed.
CONST_TOOL_ADDRESS_SPACE_BYTES: Final[dict[str, int]] = {
    "gitleaks": 8 * 1024**3,
    "semgrep": 16 * 1024**3,
}
# The paths of the host that a tool reads when it starts, by tool, which the sandbox binds
# read-only when they exist. The engine of Semgrep 1.179.0 loads the CA bundle when it starts, and
# stops with "ca-certs: no trust anchor file found" without it, though a scan uses no network
# (measured 2026-10-24, #2096). The directory holds public certificates only. Popeye 0.22.1 is
# built without cgo, and stops with "user: Current requires cgo or $USER set in environment" when
# it cannot find the user in the user database (measured 2026-10-28, #2132). The file holds no
# password.
CONST_TOOL_HOST_READ_ONLY_PATHS: Final[dict[str, tuple[str, ...]]] = {
    "semgrep": ("/etc/ssl/certs",),
    "popeye": ("/etc/passwd",),
}
# How long the check that the host can start the sandbox may take, in seconds.
CONST_TOOL_SANDBOX_CHECK_TIMEOUT_SECONDS: Final[float] = 30.0
# The soft memory limit of a Go tool's collector. Programs that are not written in Go ignore it.
CONST_TOOL_GO_MEMORY_LIMIT: Final[str] = "1GiB"
# The program that sets a tool's limits (util-linux).
CONST_TOOL_PRLIMIT_BINARY: Final[str] = "prlimit"
# The element of a tool's arguments that stands for the paths the tool scans.
CONST_TOOL_TARGETS_PLACEHOLDER: Final[str] = "{targets}"
# The elements that stand, in the recorded argument template of a run, for the config files and
# the ruleset files that the arguments name by path. The path of a scratch directory is new in each run.
CONST_TOOL_CONFIG_PLACEHOLDER: Final[str] = "{config}"
CONST_TOOL_RULESET_PLACEHOLDER: Final[str] = "{ruleset}"
# How an executor started a tool, as a record names it: as a child process of devops-cli with no
# confinement, or in the bubblewrap sandbox.
CONST_TOOL_EXECUTOR_DIRECT: Final[str] = "direct"
CONST_TOOL_EXECUTOR_SANDBOX: Final[str] = "sandbox"
# The network of a tool run, as a record names it (#2132): the network of the host for the direct
# executor, and no network for the sandbox, unless the request selects the network profile below.
CONST_TOOL_NETWORK_HOST: Final[str] = "host"
CONST_TOOL_NETWORK_NONE: Final[str] = "none"
# The one network profile of the sandbox. It reaches only the Kubernetes API server of one context,
# only to read, and only the tool `CONST_TOOL_KUBE_API_TOOL` can select it (#2132).
CONST_TOOL_NETWORK_KUBE_API: Final[str] = "kube-api"
CONST_TOOL_KUBE_API_TOOL: Final[str] = "popeye"
# The programs of a kube-api run (`devops_cli.sandbox.kube_api`): the shell of its two scripts,
# the relay in the sandbox, the proxy outside it, and the program that ends the proxy with its
# parent (util-linux). A host without one of them runs no kube-api request.
CONST_KUBE_API_PROGRAMS: Final[tuple[str, ...]] = ("sh", "socat", "kubectl", "setpriv")
# The scratch directory of a kube-api run holds the socket of `kubectl proxy` and the kubeconfig
# of the tool. The sandbox binds it read-only.
CONST_KUBE_API_SCRATCH_PREFIX: Final[str] = "devops-kube-api-"
CONST_KUBE_API_SOCKET_NAME: Final[str] = "kube-api.sock"
CONST_KUBE_API_KUBECONFIG_NAME: Final[str] = "kubeconfig.json"
# The address in the sandbox where `socat` relays each connection to the socket of the proxy. The
# network namespace of the sandbox has only a loopback device, so the port is free in each run.
CONST_KUBE_API_RELAY_HOST: Final[str] = "127.0.0.1"
CONST_KUBE_API_RELAY_PORT: Final[int] = 8001
# How often, and how far apart in seconds, each script tries to connect to the proxy or the relay
# before it gives up: 10 s in all.
CONST_KUBE_API_WAIT_RETRIES: Final[int] = 100
CONST_KUBE_API_WAIT_INTERVAL_SECONDS: Final[float] = 0.1
# The methods and the paths that `kubectl proxy` refuses (`--reject-methods`, `--reject-paths`):
# each method that changes a resource, and each path that reaches a process, a port or a server
# behind the API server. The paths are the default of kubectl (exec and attach of a pod) and the
# port-forward and proxy subresources. The proxy matches the path after it decodes and cleans it.
CONST_KUBE_API_REJECTED_METHODS: Final[str] = "(?i)^(POST|PUT|PATCH|DELETE)$"
CONST_KUBE_API_REJECTED_PATHS: Final[tuple[str, ...]] = (
    "^/api/.*/pods/.*/exec",
    "^/api/.*/pods/.*/attach",
    "^/api/.*/pods/.*/portforward",
    "^/api/.*/pods/.*/proxy",
    "^/api/.*/services/.*/proxy",
    "^/api/.*/nodes/.*/proxy",
)
# The name that each script of a kube-api run has as `$0`, in its messages.
CONST_KUBE_API_SCRIPT_NAME: Final[str] = "devops-kube-api"
# The script that runs a kube-api request outside the sandbox. It starts `kubectl proxy` on the
# socket for the context, under `setpriv --pdeathsig KILL`, so the proxy ends when the shell ends,
# also when the wall-clock limit kills the shell. It waits for the socket, runs the sandbox
# command, stops the proxy and exits with the exit code of the sandbox. The proxy writes to
# standard error, so standard output is the output of the tool. Its arguments are the socket,
# setpriv, kubectl, the context, the rejected methods and paths, socat, the retries and the
# interval of the wait, then the sandbox command.
CONST_KUBE_API_HOST_SCRIPT: Final[str] = (
    "socket=$1 setpriv=$2 kubectl=$3 context=$4 methods=$5 paths=$6 socat=$7 retries=$8 interval=$9\n"
    "shift 9\n"
    '"$setpriv" --pdeathsig KILL -- "$kubectl" proxy --unix-socket="$socket" --context="$context"'
    ' --reject-methods="$methods" --reject-paths="$paths" >&2 &\n'
    "proxy=$!\n"
    'if ! "$socat" -d0 -u /dev/null "UNIX-CONNECT:$socket,retry=$retries,interval=$interval"; then\n'
    '  kill "$proxy" 2>/dev/null\n'
    '  echo "$0: kubectl proxy did not open $socket" >&2\n'
    "  exit 1\n"
    "fi\n"
    '"$@"\n'
    "code=$?\n"
    'kill "$proxy" 2>/dev/null\n'
    'wait "$proxy" 2>/dev/null\n'
    'exit "$code"\n'
)
# The script that runs in the sandbox of a kube-api request. `socat` listens on the relay address
# and relays each connection to the socket of the proxy. The script waits for the listener, then
# becomes the tool command. The listener ends with the process namespace of the sandbox. Its
# arguments are socat, the socket, the port, the retries and the interval of the wait, then the
# tool command.
CONST_KUBE_API_SANDBOX_SCRIPT: Final[str] = (
    "socat=$1 socket=$2 port=$3 retries=$4 interval=$5\n"
    "shift 5\n"
    '"$socat" -d0 "TCP-LISTEN:$port,bind=127.0.0.1,fork,reuseaddr" "UNIX-CONNECT:$socket" &\n'
    '"$socat" -d0 -u /dev/null "TCP:127.0.0.1:$port,retry=$retries,interval=$interval" || exit 1\n'
    'exec "$@"\n'
)
# The digest of a binary or of a group of files that a record could not read. It stands in the record
# of a run that must not fail for the record. The digest of no files is not this value.
CONST_TOOL_DIGEST_UNAVAILABLE: Final[str] = "unavailable"
# The names under which a tool finds its own config file. Ruff looks in the directory of each file
# it checks and in each directory above it (docs.astral.sh/ruff/configuration). It also read the
# nearest `pyproject.toml` when a nearer `.ruff.toml` held the settings. osv-scanner looks in the
# directory of each lockfile only. Both facts come from `strace` on Ruff 0.16.8 and osv-scanner
# 2.6.0. A review hands every other tool its own config file. A request names these files up to
# the tree only. While the direct executor runs, Ruff also applies a config file above the tree and
# one in its user config directory, and the record does not name them.
CONST_RUFF_CONFIG_FILE_NAMES: Final[tuple[str, ...]] = (".ruff.toml", "ruff.toml", "pyproject.toml")
CONST_OSV_CONFIG_FILE_NAMES: Final[tuple[str, ...]] = ("osv-scanner.toml",)
# Where Trivy keeps the metadata of what it scans with, below its cache directory
# (`--cache-dir`, the environment variable `TRIVY_CACHE_DIR`, else `trivy` in the user cache of
# the platform). A `config` scan reads the checks bundle. Any other scan reads the vulnerability
# database. The metadata names the version of the bundle or database and the time of its download.
CONST_TRIVY_CACHE_DIR_ENV: Final[str] = "TRIVY_CACHE_DIR"
CONST_TRIVY_CACHE_DIR_NAME: Final[str] = "trivy"
CONST_TRIVY_CONFIG_SCAN_TYPE: Final[str] = "config"
CONST_TRIVY_CHECKS_METADATA: Final[tuple[str, ...]] = ("policy", "metadata.json")
CONST_TRIVY_DB_METADATA: Final[tuple[str, ...]] = ("db", "metadata.json")

# Maximum window duration permitted for Prometheus pool load queries (30 days in seconds)
# to prevent resource exhaustion and unbounded range vectors (CWE-400).
CONST_MAX_PROMETHEUS_WINDOW_SECONDS: Final[int] = 30 * 86400

# No library finds arbitrary URLs embedded inside prose. linkify-it-py 2.2.0
# misses non-http schemes (mysql://, postgres://) and fails on passwords with '@'.
# Candidate URLs are located by RFC 3986 scheme grammar capped at 32 chars and
# parsed strictly via urllib.parse.urlsplit.
CONST_URL_CANDIDATE_RE: Final[re.Pattern[str]] = re.compile(
    r"[A-Za-z][A-Za-z0-9+.-]{0,31}://(?:(?![A-Za-z][A-Za-z0-9+.-]{0,31}://)\S)*"
)


# ── HTTP Retryable Status Codes ──────────────────────────────────────────────
# Transient HTTP status codes indicating retryable server, gateway, or rate limit conditions.
CONST_RETRYABLE_HTTP_STATUS_CODES: Final[tuple[int, ...]] = (
    408,  # Request Timeout
    429,  # Too Many Requests
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
    520,  # Web Server Returned an Unknown Error (Cloudflare)
    521,  # Web Server Is Down (Cloudflare)
    522,  # Connection Timed Out (Cloudflare)
    523,  # Origin Is Unreachable (Cloudflare)
    524,  # A Timeout Occurred (Cloudflare)
    525,  # SSL Handshake Failed (Cloudflare)
    526,  # Invalid SSL Certificate (Cloudflare)
    527,  # Railgun Error (Cloudflare)
    529,  # Site Is Overloaded (Anthropic / OpenAI)
    530,  # Site Is Frozen / Origin DNS Error (Cloudflare)
)

# ── Review Evidence (Ruff & Mypy) ─────────────────────────────────────────────
CONST_DEFAULT_REVIEW_ADVISORY_RULES: Final[tuple[str, ...]] = ("BLE001",)
CONST_COMPLEXITY_SOURCE: Final[str] = "mccabe (ruff C901)"

# ── AI Research Marginalia & Epistemic Scratchpad ─────────────────────────────
CONST_MARGINALIA_TYPES: Final[tuple[str, ...]] = (
    "ASSUMPTION",
    "HYPOTHESIS",
    "CONTRADICTION",
    "QUESTION",
    "TODO",
)

# ── AI Research Cross-Domain Analogies ────────────────────────────────────────
CONST_STRUCTURAL_PATTERNS: Final[tuple[str, ...]] = (
    "Exponential Backoff & Retry Loop",
    "Write-Ahead Logging & Journaling",
    "Circuit Breaker & Fallback",
    "Reconciliation Loop (Convergence)",
    "Event Sourcing & Stream Projection",
    "Heartbeat & Lease Renewal",
    "Token Bucket Rate Limiting",
    "Two-Phase Commit & Consensus",
    "Bulkhead & Compartment Isolation",
    "Idempotency Key & Deduplication",
)
CONST_STRUCTURAL_PATTERN_DEFINITIONS: Final[dict[str, dict[str, Any]]] = {
    "Exponential Backoff & Retry Loop": {
        "description": "Transient failure absorption via progressive delay, jitter, and bounded retry attempts.",
        "mechanisms": (
            "backoff",
            "retry",
            "jitter",
            "interval",
            "attempt",
            "exponential",
            "transient",
        ),
    },
    "Write-Ahead Logging & Journaling": {
        "description": "Durability and crash recovery via append-only commit records prior to state mutation.",
        "mechanisms": ("wal", "journal", "write_ahead", "log", "append", "replay", "recovery"),
    },
    "Circuit Breaker & Fallback": {
        "description": "Cascade failure mitigation via state transitions (closed, open, half-open) and degradation.",
        "mechanisms": (
            "circuit_breaker",
            "trip",
            "half_open",
            "fallback",
            "threshold",
            "degradation",
        ),
    },
    "Reconciliation Loop (Convergence)": {
        "description": "Continuous state alignment driving observed reality toward declared desired specification.",
        "mechanisms": (
            "reconcile",
            "desired",
            "observed",
            "actual",
            "drift",
            "convergence",
            "controller",
        ),
    },
    "Event Sourcing & Stream Projection": {
        "description": "Derivation of current state through sequential replay of immutable domain events.",
        "mechanisms": (
            "event_sourcing",
            "event_stream",
            "projection",
            "immutable",
            "replay",
            "pubsub",
        ),
    },
    "Heartbeat & Lease Renewal": {
        "description": "Distributed node liveness tracking and leader coordination via periodic lease renewal.",
        "mechanisms": (
            "heartbeat",
            "lease",
            "ttl",
            "liveness",
            "renewal",
            "watchdog",
            "health_check",
        ),
    },
    "Token Bucket Rate Limiting": {
        "description": "Traffic smoothing and resource protection via capacity bursts and refill rate pacing.",
        "mechanisms": ("token_bucket", "refill", "capacity", "burst", "rate_limit", "throttling"),
    },
    "Two-Phase Commit & Consensus": {
        "description": "Atomic multi-node distributed transactions through prepare, vote, and commit phases.",
        "mechanisms": ("two_phase", "prepare", "commit", "consensus", "quorum", "vote", "atomic"),
    },
    "Bulkhead & Compartment Isolation": {
        "description": "Failure containment through resource partition pools and quota boundaries.",
        "mechanisms": ("bulkhead", "pool", "compartment", "quota", "partition", "isolation"),
    },
    "Idempotency Key & Deduplication": {
        "description": "Safe operation retry via deterministic idempotency keys and sliding deduplication windows.",
        "mechanisms": ("idempotency", "deduplication", "replay_prevention", "token", "unique_key"),
    },
}

# ── Review Tool Canary Constants (#1143) ─────────────────────────────────────
# The start of the name of the scratch directory where the canary of a tool runs on its fixtures.
CONST_CANARY_WORKDIR_PREFIX: Final[str] = "devops-canary-"
CONST_CANARY_TOOLS: Final[tuple[str, ...]] = (
    "semgrep",
    "ruff",
    "bandit",
    "mypy",
    "kube-linter",
    "pluto",
)

CONST_CANARY_TOOL_TO_ANALYZER: Final[dict[str, str]] = {
    "semgrep": "Semgrep",
    "bandit": "Bandit",
    "kube-linter": "Kube-linter",
    "pluto": "Pluto",
}

CONST_CANARY_EXPECTED_RESULTS: Final[dict[str, frozenset[tuple[str, int]]]] = {
    "semgrep": frozenset({("canary-pep758-tuple", 17)}),
    "ruff": frozenset({("B006", 21)}),
    "bandit": frozenset({("B307", 26)}),
    "mypy": frozenset({("assignment", 29)}),
    "kube-linter": frozenset({("privileged-container", 15)}),
    "pluto": frozenset({("extensions/v1beta1", 1)}),
}

CONST_CANARY_PYTHON_SOURCE: Final[str] = """from __future__ import annotations

type Items[T] = list[T]


def make_forward(value: ForwardTarget) -> ForwardTarget:
    return value


class ForwardTarget:
    pass


def handle_pep758() -> str:
    try:
        return "ok"
    except ValueError, TypeError:
        return "caught"


def mutable_default(items: list[int] = []) -> list[int]:
    return items


def run_eval(expr: str) -> object:
    return eval(expr)


bad_typed: int = "not-an-int"
"""

CONST_CANARY_SEMGREP_PROBES_YAML: Final[str] = """rules:
  - id: canary-pep758-tuple
    languages: [python]
    severity: ERROR
    message: PEP 758 unparenthesized exception tuple parsed as tuple
    patterns:
      - pattern: |
          try:
              ...
          except ($X, $Y):
              ...
      - focus-metavariable: $X
  - id: canary-pep758-as-binding
    languages: [python]
    severity: ERROR
    message: PEP 758 misparsed as exception binding
    patterns:
      - pattern: |
          try:
              ...
          except $X as $Y:
              ...
      - focus-metavariable: $X
"""

CONST_CANARY_MANIFEST_YAML: Final[str] = """apiVersion: extensions/v1beta1
kind: Ingress
metadata:
  name: canary-ingress
---
apiVersion: v1
kind: Pod
metadata:
  name: canary-pod
spec:
  containers:
    - name: app
      image: nginx:1.27
      securityContext:
        privileged: true
"""

CONST_CANARY_DOCKERFILE_SOURCE: Final[str] = """FROM alpine:3.20
USER root
RUN echo "canary"
"""

# ── Review Finding Group Model Analysis Constants (#1147, #1148) ──────────────
CONST_REVIEW_ANALYSIS_FILENAME: Final[str] = "analysis.json"
CONST_ANALYSIS_PROMPT_FILENAME: Final[str] = "review_group_analysis.md"
CONST_ANALYSIS_PLAN_PROMPT_FILENAME: Final[str] = "review_plan.md"
CONST_ANALYSIS_K8S_TOOLS: Final[frozenset[str]] = frozenset({"kubelinter", "kube-linter", "pluto"})
CONST_ANALYSIS_ADVISORY_TOOLS: Final[frozenset[str]] = frozenset({"osv", "osv-scanner", "trivy"})
CONST_ANALYSIS_DROP_REASON_BUDGET: Final[str] = "budget"
CONST_ANALYSIS_DROP_REASON_UNAVAILABLE: Final[str] = "unavailable"
CONST_ANALYSIS_REJECTION_REPLY_TRUNCATED: Final[str] = "reply-truncated"
CONST_ANALYSIS_REJECTION_SCHEMA_VALIDATION_FAILED: Final[str] = "schema-validation-failed"
CONST_ANALYSIS_REJECTION_MODEL_CALL_ERROR: Final[str] = "model-call-error"
CONST_OSV_OFFLINE_DB_TTL_SECONDS: Final[float] = 86400.0  # 24 hours TTL
# Where osv-scanner 2.6.0 keeps its offline database: `osv-scalibr` below the directory that this
# variable names, else below the user cache directory of the platform. `--download-offline-
# databases` wrote `osv-scalibr/PyPI/all.zip` there on 2026-10-24 (#2096).
CONST_OSV_DB_DIR_ENV: Final[str] = "OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY"
CONST_OSV_DB_DIR_NAME: Final[str] = "osv-scalibr"
CONST_LOCKFILE_NAMES: Final[tuple[str, ...]] = (
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lockb",
    "Cargo.lock",
    "go.sum",
    "composer.lock",
    "Gemfile.lock",
)
CONST_MANIFEST_TO_LOCKFILES: Final[dict[str, tuple[str, ...]]] = {
    "pyproject.toml": ("uv.lock", "poetry.lock", "Pipfile.lock"),
    "requirements.in": ("requirements.txt", "uv.lock"),
    "setup.py": ("uv.lock", "poetry.lock"),
    "package.json": ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb"),
    "Cargo.toml": ("Cargo.lock",),
    "go.mod": ("go.sum",),
    "composer.json": ("composer.lock",),
    "Gemfile": ("Gemfile.lock",),
}

# ── Knowledge Base Version Grounding & Reference Tracking (#1149) ────────────
CONST_KB_METADATA_TARGET_SUBDIRS: Final[tuple[str, ...]] = (
    "devops_cli/libraries",
    "it_domains/tools",
    "it_domains/topics",
)
CONST_KB_REFERENCE_PREFIX: Final[str] = "kb:"
CONST_KB_DATE_FORMAT: Final[str] = "%Y-%m-%d"
CONST_KB_SHA_DIGEST_LENGTH: Final[int] = 16

# ── OpenSpec (ADR 0010) ──────────────────────────────────────────────────────
# The folder the pinned OpenSpec plans into, from a checkout's root, and the file that carries the
# planning conventions for every agent.
CONST_OPENSPEC_DIR: Final[str] = "openspec"
CONST_OPENSPEC_CONFIG_FILENAME: Final[str] = "config.yaml"
CONST_OPENSPEC_CHANGES_DIR: Final[str] = "openspec/changes"
# Where `openspec archive` moves a change, and where it writes the living specs. Only the pull
# request that closes a change writes either, and only for that change (ADR 0010).
CONST_OPENSPEC_ARCHIVE_DIR: Final[str] = f"{CONST_OPENSPEC_CHANGES_DIR}/archive"
CONST_OPENSPEC_SPECS_DIR: Final[str] = f"{CONST_OPENSPEC_DIR}/specs"
# The closed grammar of an active change: the folder is named `<issue>-<slug>`, and a path under it
# is `openspec/changes/<issue>-<slug>/<file>`. The issue is the only link from a folder to GitHub.
# The number is read as an integer, so `089-x` belongs to #89.
CONST_OPENSPEC_CHANGE_NAME_RE: Final[str] = r"(?P<issue>\d+)-[^/]+"
CONST_OPENSPEC_CHANGE_DIR_RE: Final[str] = (
    rf"{CONST_OPENSPEC_CHANGES_DIR}/(?P<change>{CONST_OPENSPEC_CHANGE_NAME_RE})"
)
CONST_OPENSPEC_CHANGE_FOLDER_RE: Final[str] = rf"{CONST_OPENSPEC_CHANGE_DIR_RE}/.+"
# The closed grammar of an archived change: `openspec archive` puts the date of the archive before
# the name, `openspec/changes/archive/<YYYY-MM-DD>-<issue>-<slug>/<file>`. It is a grammar of its
# own, because the active grammar would read the year of the date as the issue.
CONST_OPENSPEC_ARCHIVED_DIR_RE: Final[str] = (
    rf"{CONST_OPENSPEC_ARCHIVE_DIR}/(?P<date>\d{{4}}-\d{{2}}-\d{{2}})-"
    rf"(?P<change>{CONST_OPENSPEC_CHANGE_NAME_RE})"
)
CONST_OPENSPEC_ARCHIVED_FOLDER_RE: Final[str] = rf"{CONST_OPENSPEC_ARCHIVED_DIR_RE}/.+"
# What stops OpenSpec's telemetry and its check for a newer version, and its prompts. The sanitized
# environment `run_subprocess` builds keeps none of them, so the tool's runner sets each.
CONST_OPENSPEC_OPT_OUT_ENV: Final[dict[str, str]] = {
    "DO_NOT_TRACK": "1",
    "OPENSPEC_TELEMETRY": "0",
    "OPENSPEC_NO_UPDATE_CHECK": "1",
    "OPEN_SPEC_INTERACTIVE": "0",
}
# Where OpenSpec reads its per-user configuration, which a run replaces with a directory of its own
# so a developer's profile cannot decide what the tool writes.
CONST_OPENSPEC_CONFIG_HOME_ENV: Final[str] = "XDG_CONFIG_HOME"
# The workflows of the `custom` profile every agent shares: no archive and no sync, since those
# write `openspec/specs/`, which only the pull request that closes a change may.
CONST_OPENSPEC_WORKFLOWS: Final[tuple[str, ...]] = ("propose", "explore", "apply", "update")
# The settings an isolated configuration holds, in the order they are set: telemetry off, skills
# only, and the custom profile with its four workflows.
CONST_OPENSPEC_ISOLATED_SETTINGS: Final[tuple[tuple[str, str], ...]] = (
    ("telemetry.enabled", "false"),
    ("delivery", "skills"),
    ("profile", "custom"),
    ("workflows", json.dumps(list(CONST_OPENSPEC_WORKFLOWS))),
)
# The files `openspec update` writes for the agents the project supports, from a checkout's root.
# Anything else under those directories is not OpenSpec's.
CONST_OPENSPEC_GENERATED_GLOBS: Final[tuple[str, ...]] = (
    ".claude/skills/openspec-*/**/*",
    ".agents/skills/openspec-*/**/*",
    ".kilocode/skills/openspec-*/**/*",
    ".agents/skills/.openspec-target",
)
# The artifacts whose instructions the gate renders for a probe change, and that change's name.
CONST_OPENSPEC_INSTRUCTION_ARTIFACTS: Final[tuple[str, ...]] = (
    "proposal",
    "specs",
    "design",
    "tasks",
    "apply",
)
CONST_OPENSPEC_PROBE_CHANGE: Final[str] = "gate-probe"
# The delta operations that rewrite a requirement a spec already holds: of the four OpenSpec
# defines, all but ADDED. Two active changes that apply one to one requirement overwrite each other
# when both archive, and the tool says nothing.
CONST_OPENSPEC_REWRITING_OPERATIONS: Final[frozenset[str]] = frozenset(
    {"MODIFIED", "REMOVED", "RENAMED"}
)
# The function names that count as presence checks in test assertions. A test that asserts
# only presence or compares a presence call with a boolean literal in a tuple certifies
# an object exists without verifying its values or behavior (#851).
CONST_PRESENCE_CHECK_NAMES: Final[frozenset[str]] = frozenset({"callable", "hasattr", "isinstance"})
