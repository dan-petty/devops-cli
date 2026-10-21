"""Non-configurable constants used across the CLI."""

from __future__ import annotations

import ipaddress
import re
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
CONST_PROJECT_CONFIG_FILENAME = "config.yaml"
CONST_PROJECT_CONFIG_CANDIDATES: Final[tuple[str, ...]] = (
    CONST_PROJECT_CONFIG_FILENAME,
    f".devcontainer/{CONST_PROJECT_CONFIG_FILENAME}",
    f".devops/{CONST_PROJECT_CONFIG_FILENAME}",
    ".devops.yaml",
    ".devcontainer/.devops.yaml",
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
    "tavily": (
        "Tavily Search Configuration (`tavily`)",
        "Tavily web search API authentication settings.",
    ),
}
CONST_DOMAIN_EXCEPTION_MODULES: Final[tuple[str, ...]] = (
    "devops_cli.ai.agents.spend",
    "devops_cli.ai.agents.testing",
    "devops_cli.ai.client.models",
    "devops_cli.ai.gateway_tune",
    "devops_cli.ai.harness.memory",
    "devops_cli.ai.pool_load",
    "devops_cli.ai.rag.embeddings",
    "devops_cli.ai.rag.qdrant",
    "devops_cli.ai.run_store",
    "devops_cli.core.templating",
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
CONST_AGENTS_MD_MAX_CHARS: Final[int] = 40_000
CONST_PYPROJECT_FILENAME = "pyproject.toml"
CONST_UV_LOCK_FILENAME = "uv.lock"
CONST_PRE_COMMIT_CONFIG_FILENAME = ".pre-commit-config.yaml"
CONST_CHANGELOG_FILENAME = "CHANGELOG.md"
CONST_README_FILENAME = "README.md"
CONST_INIT_PY_PATH = Path("src/devops_cli/__init__.py")
CONST_CONVENTIONAL_COMMIT_CATEGORIES: Final[dict[str, str]] = {
    "feat": "Added",
    "fix": "Fixed & Hardened",
    "sec": "Fixed & Hardened",
    "security": "Fixed & Hardened",
    "perf": "Changed & Improved",
    "refactor": "Changed & Improved",
    "docs": "Changed & Improved",
    "chore": "Changed & Improved",
    "ci": "Changed & Improved",
    "test": "Changed & Improved",
    "style": "Changed & Improved",
}
CONST_CONVENTIONAL_COMMIT_CATEGORY_ORDER: Final[tuple[str, ...]] = (
    "Added",
    "Fixed & Hardened",
    "Changed & Improved",
    "Other Changes",
)
# A pull request into a release branch adds its changelog entry as `changelog.d/<issue>.md`, a
# file no other pull request writes; the cut collects them into the version's section. The
# directory holds fragments and its README only.
CONST_CHANGELOG_FRAGMENTS_DIR: Final[str] = "changelog.d"
CONST_CHANGELOG_FRAGMENT_NAME_RE: Final[re.Pattern[str]] = re.compile(r"(?P<issue>\d+)\.md")
# Keep a Changelog 1.0.0's complete set of change types, in its order.
CONST_KEEP_A_CHANGELOG_CATEGORIES: Final[tuple[str, ...]] = (
    "Added",
    "Changed",
    "Deprecated",
    "Removed",
    "Fixed",
    "Security",
)
# GitHub refuses a Release body over 125,000 characters and a pull request body over 65,536.
# `devops release notes` and `devops release pr` fit a version's notes under them (#1097).
CONST_GITHUB_RELEASE_BODY_MAX_CHARS: Final[int] = 125_000
CONST_GITHUB_PULL_REQUEST_BODY_MAX_CHARS: Final[int] = 65_536
CONST_CURRENT_DIR = Path(".")
CONST_ROOT_DIR = Path("/")
CONST_SRC_DIR_NAME = "src"
CONST_DOCS_DIR_NAME = "docs"
CONST_DOCS_DIR_PATH = Path(CONST_DOCS_DIR_NAME)
CONST_TESTS_DIR_NAME = "tests"
CONST_TESTS_DIR_PATH = Path(CONST_TESTS_DIR_NAME)
CONST_VSCODE_DIR_NAME = ".vscode"
CONST_MCP_JSON_NAME = "mcp.json"
# Claude Code reads project-scoped MCP servers from `.mcp.json` at the repository root.
# VS Code's own MCP support reads `.vscode/mcp.json`, and the two are not interchangeable:
# `${workspaceFolder}` is a VS Code substitution that Claude Code does not expand, so a
# copy of the VS Code file would hand the server a literal `${workspaceFolder}` on PATH.
CONST_CLAUDE_MCP_JSON_NAME = ".mcp.json"
CONST_MCP_RESOURCE_SCHEME = "resource://"
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
        "release",
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
CONST_MCP_ARGUMENT_MUTATING_TOOLS_FLOOR: Final[frozenset[str]] = frozenset(
    {
        "argo_rollouts_analyze",
        "docker_sign",
        "gh_project_reconcile",
        "ai_rag_drift",
        "roadmap_render",
    }
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
    (("ai", "failover"), 60.0, False, False),
    (("ai", "gateway", "failover"), 30.0, False, True),
    (("ai", "gateway", "probe-backend"), 30.0, True, True),
    (("ai", "gateway", "routes"), 30.0, True, True),
    (("ai", "gateway", "status"), 30.0, True, True),
    (("ai", "harness", "offload"), 60.0, True, False),
    (("ai", "harness", "status"), 30.0, True, False),
    (("ai", "ingest", "library"), 300.0, False, True),
    (("ai", "ingest", "query-library"), 60.0, True, True),
    (("ai", "pack-context"), 60.0, True, True),
    (("ai", "prewarm"), 600.0, False, False),
    (("ai", "quiesce"), 60.0, False, False),
    (("ai", "rag", "drift"), 60.0, False, True),
    (("ai", "rag", "index"), 300.0, False, False),
    (("ai", "rag", "query"), 60.0, True, False),
    (("ai", "read"), 60.0, True, False),
    (("ai", "repomap"), 60.0, True, False),
    (("ai", "resume"), 60.0, False, False),
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
    (("docs", "compact"), 60.0, False, False),
    (("gh", "issues", "create"), 60.0, False, False),
    (("gh", "issues", "edit"), 60.0, False, False),
    (("gh", "issues", "list"), 60.0, True, False),
    (("gh", "issues", "status"), 60.0, True, False),
    (("gh", "issues", "triage"), 60.0, True, False),
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
    (("k8s", "doctor"), 60.0, True, True),
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
    (("release", "status"), 30.0, True, False),
    (("repos", "list"), 30.0, True, False),
    (("repos", "sync"), 120.0, False, False),
    (("review", "branch"), 300.0, True, False),
    (("review", "export-feedback"), 60.0, False, False),
    (("review", "findings"), 60.0, True, False),
    (("review", "path"), 300.0, True, False),
    (("review", "pr"), 300.0, False, False),
    (("review", "stats"), 60.0, True, False),
    (("roadmap", "close"), 300.0, True, False),
    (("roadmap", "intake"), 300.0, False, False),
    (("roadmap", "migrate"), 300.0, True, False),
    (("roadmap", "refine"), 300.0, True, False),
    (("roadmap", "render"), 300.0, False, False),
    (("roadmap", "reprioritize"), 300.0, False, False),
    (("roadmap", "run"), 300.0, True, False),
    (("sandbox", "deploy"), 300.0, False, False),
    (("sandbox", "exec"), 300.0, False, False),
    (("sandbox", "network-policy"), 300.0, True, False),
    (("sandbox", "status"), 30.0, True, True),
    (("sandbox", "stop"), 60.0, False, False),
    (("scan", "aibom"), 60.0, True, False),
    (("scan", "complexity"), 60.0, True, False),
    (("scan", "fix"), 300.0, False, False),
    (("scan", "iac"), 300.0, True, False),
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

# Unexposed CLI leaf commands that must not be registered as MCP tools
CONST_MCP_COMMAND_EXCLUSIONS: Final[frozenset[tuple[str, ...]]] = frozenset(
    (
        ("ai", "agents"),
        ("ai", "analyze", "branch"),
        ("ai", "analyze", "path"),
        ("ai", "analyze", "pr"),
        ("ai", "audit-library-usage"),
        ("ai", "bundle-models"),
        ("ai", "cache", "clear"),
        ("ai", "cache", "status"),
        ("ai", "chat"),
        ("ai", "config"),
        ("ai", "cost", "list-pricing"),
        ("ai", "cost", "prometheus"),
        ("ai", "cost", "reset"),
        ("ai", "cost", "roi"),
        ("ai", "cost", "set-price"),
        ("ai", "cost", "update-pricing"),
        ("ai", "gateway", "connect"),
        ("ai", "gateway", "load"),
        ("ai", "gateway", "render"),
        ("ai", "gateway", "tune"),
        ("ai", "harness", "run"),
        ("ai", "ingest", "docs"),
        ("ai", "ingest", "index-libraries"),
        ("ai", "models"),
        ("ai", "pipeline"),
        ("ai", "preload"),
        ("ai", "prompt-eval"),
        ("ai", "rag", "clear"),
        ("ai", "rag", "index-kb"),
        ("ai", "rag", "search"),
        ("ai", "rag", "status"),
        ("ai", "research", "analogies"),
        ("ai", "research", "annotate"),
        ("ai", "research", "forage"),
        ("ai", "research", "model"),
        ("ai", "research", "socratic"),
        ("ai", "review", "benchmark"),
        ("ai", "review", "branch"),
        ("ai", "review", "corpus", "generate"),
        ("ai", "review", "corpus", "score"),
        ("ai", "review", "export-feedback"),
        ("ai", "review", "findings"),
        ("ai", "review", "path"),
        ("ai", "review", "pr"),
        ("ai", "review", "rules", "test"),
        ("ai", "review", "samples", "fetch"),
        ("ai", "review", "samples", "list"),
        ("ai", "review", "samples", "validate"),
        ("ai", "review", "score"),
        ("ai", "review", "stats"),
        ("ai", "review", "templates", "check"),
        ("ai", "review", "templates", "list"),
        ("ai", "review", "templates", "sweep"),
        ("ai", "review", "verify"),
        ("ai", "runs", "baseline", "list"),
        ("ai", "runs", "baseline", "set"),
        ("ai", "runs", "baseline", "show"),
        ("ai", "runs", "check"),
        ("ai", "runs", "compare"),
        ("ai", "runs", "connect"),
        ("ai", "runs", "list"),
        ("ai", "runs", "reindex"),
        ("ai", "runs", "show"),
        ("ai", "spec"),
        ("ai", "spend", "list-pricing"),
        ("ai", "spend", "prometheus"),
        ("ai", "spend", "report"),
        ("ai", "spend", "reset"),
        ("ai", "spend", "roi"),
        ("ai", "spend", "set-price"),
        ("ai", "spend", "update-pricing"),
        ("ai", "test"),
        ("ai", "token-count"),
        ("argo", "cd", "apps", "bootstrap-gitops"),
        ("argo", "cd", "apps", "sync"),
        ("argo", "cd", "fleet", "sync"),
        ("argo", "cd", "gitops", "drift"),
        ("argo", "cd", "gitops", "sync"),
        ("argo", "cd", "gitops", "watch"),
        ("argo", "gitops", "drift"),
        ("argo", "gitops", "sync"),
        ("argo", "gitops", "watch"),
        ("argo", "rollouts", "abort"),
        ("argo", "rollouts", "list"),
        ("argo", "rollouts", "promote"),
        ("argo", "rollouts", "restart"),
        ("argo", "rollouts", "status"),
        ("argo", "sync"),
        ("argo", "workflows", "list"),
        ("argo", "workflows", "logs"),
        ("argo", "workflows", "submit"),
        ("branches", "clean"),
        ("branches", "jira"),
        ("branches", "sync"),
        ("branches", "update"),
        ("ci", "actionlint"),
        ("ci", "audit"),
        ("ci", "coverage"),
        ("ci", "deps"),
        ("ci", "devcontainer"),
        ("ci", "docs"),
        ("ci", "fail-to-pass"),
        ("ci", "format"),
        ("ci", "lint"),
        ("ci", "lockfile"),
        ("ci", "maintain"),
        ("ci", "mutate"),
        ("ci", "outdated"),
        ("ci", "run"),
        ("ci", "security"),
        ("ci", "test"),
        ("ci", "typecheck"),
        ("ci", "uv-check"),
        ("cloudflare", "access", "policies"),
        ("cloudflare", "access", "status"),
        ("cloudflare", "access", "sync"),
        ("cloudflare", "dns", "delete"),
        ("cloudflare", "dns", "list"),
        ("cloudflare", "dns", "sync"),
        ("cloudflare", "service-status"),
        ("cloudflare", "status"),
        ("cloudflare", "tunnel", "routes"),
        ("cloudflare", "tunnel", "sync"),
        ("config", "audit-stream"),
        ("config", "auth-headless"),
        ("config", "env"),
        ("config", "env-vars"),
        ("config", "get"),
        ("config", "init"),
        ("config", "set"),
        ("dashboard",),
        ("devcontainer", "bootstrap-k8s"),
        ("devcontainer", "init"),
        ("devcontainer", "list"),
        ("devcontainer", "post-create"),
        ("devcontainer", "post-start"),
        ("devcontainer", "run-lifecycle"),
        ("devcontainer", "unlock-keyring"),
        ("devcontainer", "update"),
        ("devcontainer", "validate"),
        ("docker", "analyze-layers"),
        ("docker", "build"),
        ("docker", "cache"),
        ("docker", "prune"),
        ("docker", "push"),
        ("docker", "stats"),
        ("docs", "check"),
        ("docs", "generate"),
        ("docs", "sync-readme"),
        ("format",),
        ("gh", "api"),
        ("gh", "branch-protection", "audit"),
        ("gh", "branch-protection", "sync"),
        ("gh", "labels", "audit"),
        ("gh", "metrics"),
        ("gh", "milestones", "status"),
        ("gh", "pages", "builds"),
        ("gh", "pr", "check-readiness"),
        ("gh", "pr", "checks"),
        ("gh", "pr", "close"),
        ("gh", "pr", "copilot-pass"),
        ("gh", "pr", "create"),
        ("gh", "pr", "diff"),
        ("gh", "pr", "edit"),
        ("gh", "pr", "hardening-report"),
        ("gh", "pr", "list"),
        ("gh", "pr", "monitor"),
        ("gh", "pr", "ready"),
        ("gh", "pr", "threads", "file-issues"),
        ("gh", "pr", "threads", "list"),
        ("gh", "pr", "threads", "reply"),
        ("gh", "pr", "threads", "resolve"),
        ("gh", "pr", "threads", "resolve-all"),
        ("gh", "pr", "threads", "unresolve"),
        ("gh", "pr", "update"),
        ("gh", "pr", "view"),
        ("gh", "pr", "wait"),
        ("gh", "project", "link"),
        ("gh", "project", "template"),
        ("gh", "project", "workflows", "list"),
        ("gh", "secrets", "list"),
        ("gh", "secrets", "sync"),
        ("gh", "status"),
        ("gh", "views", "list"),
        ("grafana", "alerts"),
        ("grafana", "dashboards", "export"),
        ("grafana", "dashboards", "import"),
        ("grafana", "dashboards", "lint"),
        ("grafana", "dashboards", "sync"),
        ("grafana", "datasources"),
        ("grafana", "search"),
        ("install-tools", "status"),
        ("k8s", "apply"),
        ("k8s", "bootstrap-openwebui"),
        ("k8s", "check-deprecated"),
        ("k8s", "configure-urls"),
        ("k8s", "contexts"),
        ("k8s", "gpu-matrix"),
        ("k8s", "port-forward"),
        ("k8s", "port-forward-status"),
        ("k8s", "port-forward-stop"),
        ("k8s", "push-secrets"),
        ("k8s", "rbac-audit"),
        ("k8s", "render"),
        ("k8s", "run-job"),
        ("k8s", "service-url"),
        ("k8s", "stream-logs"),
        ("k8s", "switch-context"),
        ("k8s", "sync-secrets"),
        ("k8s", "validate-policy"),
        ("k8s", "volume", "reclaim"),
        ("kustomize", "apply"),
        ("kustomize", "build"),
        ("kustomize", "diff"),
        ("lint",),
        ("mcp", "export-schemas"),
        ("mcp", "serve"),
        ("mcp", "tools"),
        ("pipeline",),
        ("pr", "copilot-pass"),
        ("pr", "create"),
        ("pr", "hardening-report"),
        ("pr", "threads", "file-issues"),
        ("pr", "threads", "resolve-all"),
        ("pr", "threads", "unresolve"),
        ("pr", "view"),
        ("pr", "wait"),
        ("prometheus", "analyze"),
        ("prometheus", "query-range"),
        ("prometheus", "rules"),
        ("prometheus", "targets"),
        ("release", "changelog"),
        ("release", "check"),
        ("release", "notes"),
        ("release", "pr"),
        ("release", "prepare"),
        ("release", "sync-notes"),
        ("release", "tag"),
        ("repos", "clone"),
        ("repos", "clone-org"),
        ("repos", "update"),
        ("repos", "worktrees", "prune"),
        ("repos", "worktrees", "status"),
        ("review", "benchmark"),
        ("review", "corpus", "generate"),
        ("review", "corpus", "score"),
        ("review", "rules", "test"),
        ("review", "samples", "fetch"),
        ("review", "samples", "list"),
        ("review", "samples", "validate"),
        ("review", "score"),
        ("review", "templates", "check"),
        ("review", "templates", "list"),
        ("review", "templates", "sweep"),
        ("review", "verify"),
        ("roadmap", "return"),
        ("sandbox", "logs"),
        ("sandbox", "metrics"),
        ("sandbox", "probe"),
        ("sandbox", "traces"),
        ("scan", "report"),
        ("scan", "sarif"),
        ("scan", "workflows"),
        ("serve",),
        ("ssh", "generate"),
        ("ssh", "list"),
        ("ssh", "register"),
        ("ssh", "rotate"),
        ("status",),
        ("telemetry", "connect"),
        ("telemetry", "open-ui"),
        ("telemetry", "semconv", "refresh"),
        ("test", "load"),
        ("test", "profile-memory"),
        ("test", "run"),
        ("test", "sandbox"),
        ("tf", "cost", "diff"),
        ("tf", "deploy-cloud"),
        ("tf", "destroy"),
        ("tf", "drift"),
        ("tf", "fmt"),
        ("tf", "graph"),
        ("tf", "init"),
        ("tf", "lint"),
        ("tf", "status"),
        ("tf", "validate"),
        ("tls", "enable-k8s"),
        ("tls", "homelab"),
        ("tls", "verify"),
        ("tui",),
        ("uv", "lock"),
        ("uv", "python-install"),
        ("uv", "run"),
        ("uv", "sync"),
        ("valkey", "backup"),
        ("valkey", "cli"),
        ("valkey", "keys"),
        ("vault", "audit"),
        ("vault", "leases"),
        ("vault", "login"),
        ("vault", "logout"),
        ("workspace", "add"),
        ("workspace", "clean"),
        ("workspace", "generate"),
        ("workspace", "open"),
        ("workspace", "remove"),
    )
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
# Well-known placeholder tokens and handwritten documentation files checked for command argv resolution (#921).
CONST_DOCS_ARGV_KNOWN_PLACEHOLDERS: Final[frozenset[str]] = frozenset(
    {"...", "COMMAND", "ARGS", "OPTIONS", "SUBCOMMAND", "PARAMS"}
)
CONST_HANDWRITTEN_DOCS_PATHS: Final[tuple[Path, ...]] = (
    Path("README.md"),
    Path("ARCHITECTURE.md"),
    Path("RELEASE_CYCLE.md"),
    Path("docs/SDLC.md"),
    Path("docs/ROUTINE_TASKS.md"),
    Path("docs/DEVCONTAINER_USAGE.md"),
    Path("docs/VISION.md"),
)
# The list methods that add tokens to a `devops` argv built up in a variable.
CONST_ARGV_EXTENDING_METHODS: Final[frozenset[str]] = frozenset({"append", "extend"})
# Bound on the length of command output returned to an MCP client.
CONST_MCP_MAX_COMMAND_OUTPUT_CHARS: Final[int] = 4000
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
# HTML chrome and non-content tags decomposed during untrusted page rendering (#896).
CONST_WEB_FETCH_CHROME_TAGS: Final[frozenset[str]] = frozenset(
    {"header", "nav", "footer", "aside", "dialog", "script", "style", "noscript"}
)
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
CONST_SYSTEM_TEMP_DIRS: tuple[Path, ...] = (Path("/tmp"), Path("/var/tmp"))  # nosec B108
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
# working directory or the scanned tree (#972). Each keeps the scanner's defaults: kube-linter's
# default checks, Trivy's defaults, Gitleaks' default rules, and Bandit's defaults with no
# `[bandit]` option. The ignore files they are handed are empty.
CONST_REVIEW_SCAN_KUBELINTER_CONFIG = "checks: {}\n"
CONST_REVIEW_SCAN_TRIVY_CONFIG = "{}\n"
CONST_REVIEW_SCAN_GITLEAKS_CONFIG = "[extend]\nuseDefault = true\n"
CONST_REVIEW_SCAN_BANDIT_INI = "[bandit]\n"
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
# Click context meta key the `devops ci` group sets when a subcommand only prints its help,
# so the gate does not announce the root it would check.
CONST_CI_SUBCOMMAND_SHOWS_HELP_META_KEY: Final[str] = "devops_cli.ci.subcommand_shows_help"
# The gate runs before every push, so its test step must stay inside this budget; past it, the
# gate names the slowest tests from a pytest durations report of this many entries.
CONST_CI_TEST_BUDGET_SECONDS: Final[float] = 300.0
# Margin added to the CI test budget when computing MCP tool timeouts for `ci_run`.
CONST_CI_TEST_BUDGET_MARGIN_SECONDS: Final[float] = 60.0
CONST_CI_SLOWEST_TESTS_SHOWN: Final[int] = 10
# Host-folder shares (WSL's drvfs over 9p) answer each file check hundreds of times slower than
# a Linux filesystem, which multiplies the gate's time for a workspace checked out on them.
CONST_SLOW_WORKSPACE_FSTYPES: Final[frozenset[str]] = frozenset({"9p", "drvfs"})
CONST_LLM_CACHE_DIR_NAME = "llm"
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
# Test-only paths that must never appear in the project root; the workspace tripwire reports any
CONST_FORBIDDEN_PROJECT_TEST_PATHS: Final[tuple[str, ...]] = (
    "test_config.yaml",
    "test_data",
    "test_llm_cache",
    "gh-config",
    ".data/test_llm_cache",
    ".data/test_data",
)

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
CONST_DEVCONTAINER_POST_CREATE_NAME = "postCreate.sh"
CONST_DEVCONTAINER_JSON_PATH = Path(CONST_DEVCONTAINER_DIR_NAME) / CONST_DEVCONTAINER_JSON_NAME
CONST_DEVCONTAINER_POST_CREATE_PATH = (
    Path(CONST_DEVCONTAINER_DIR_NAME) / CONST_DEVCONTAINER_POST_CREATE_NAME
)
CONST_DEVCONTAINER_IMAGE_PREFIX = "mcr.microsoft.com/devcontainers/python:"
CONST_DEVCONTAINER_PUBLISHED_IMAGE = "ghcr.io/dan-petty/devops-cli/devcontainer:latest"
CONST_DEVCONTAINER_CLAUDE_EXTENSION: Final[str] = "anthropic.claude-code"
CONST_DEVCONTAINER_CLAUDE_FEATURE: Final[str] = (
    "ghcr.io/anthropics/devcontainer-features/claude-code:1"
)
CONST_CANONICAL_OCI_SOURCE: Final[str] = "https://github.com/dan-petty/devops-cli"
CONST_REQUIRED_OCI_IMAGE_LABELS: Final[tuple[str, ...]] = (
    "org.opencontainers.image.source",
    "org.opencontainers.image.description",
    "org.opencontainers.image.licenses",
    "org.opencontainers.image.title",
    "org.opencontainers.image.revision",
    "org.opencontainers.image.version",
    "org.opencontainers.image.created",
    "org.opencontainers.image.documentation",
)
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
CONST_REVIEW_CONVENTIONS_FILE = ".devops/review.md"
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
CONST_CHAOS_DIR_NAME = "k8s/chaos"
CONST_CHAOS_DIR_PATH = Path(CONST_CHAOS_DIR_NAME)
CONST_LOAD_TESTS_DIR_NAME = "tests/load"
CONST_LOAD_TESTS_DIR_PATH = Path(CONST_LOAD_TESTS_DIR_NAME)

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
CONST_ENTITY_SEPARATOR = "/"

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
# No login, or one GitHub refused (HTTP 401).
CONST_GITHUB_UNAUTHENTICATED_PATTERNS: tuple[str, ...] = (
    "not logged in",
    "http 401",
    "bad credentials",
)
# gh's exit status for a command that requires authentication (`gh help exit-codes`).
CONST_GH_AUTH_REQUIRED_EXIT_CODE: Final[int] = 4
# The HTTP status gh names on stderr: `gh api` writes `<message> (HTTP <status>)` or
# `HTTP <status>`, and its other commands go-gh's `HTTP <status>: <message> (<url>)`.
CONST_GH_HTTP_STATUS_RE: Final[re.Pattern[str]] = re.compile(r"\bHTTP (?P<status>\d{3})\b")
# The scope gh project's commands need to create and edit boards; it includes read:project.
CONST_GH_PROJECT_SCOPE: Final[str] = "project"

CONST_URL_OLLAMA_LOCALHOST = "http://localhost:11434"
CONST_URL_ANTHROPIC_API_BASE = "https://api.anthropic.com"
CONST_URL_GITHUB_COPILOT_API_BASE = "https://api.githubcopilot.com"
CONST_URL_OPENAI_API_BASE = "https://api.openai.com"
# The API a hosted provider's requests, and the AI key, go to when no api_base_url is set.
CONST_AI_PROVIDER_API_BASES: Final[dict[str, str]] = {
    "claude": CONST_URL_ANTHROPIC_API_BASE,
    "copilot": CONST_URL_GITHUB_COPILOT_API_BASE,
    "openai": CONST_URL_OPENAI_API_BASE,
}
# What `backend_host` reports for a provider with no configured or default endpoint. It names
# no server, so LLM spans write no `server.address` for it.
CONST_AI_BACKEND_HOST_UNKNOWN = "unknown"
# The `backend_info` of a reply the response cache answered, and the server its spend-ledger row
# names: no backend served it, so spend reports leave it out of their server counts (#816).
CONST_RESPONSE_CACHE_SERVER: Final[str] = "cache"
CONST_URL_GITHUB_API_BASE = "https://api.github.com"
# What the GitHub session sends with every REST request (#983): GitHub requires a User-Agent
# naming the project or user, and the API version pins the REST contract the session reads.
CONST_GITHUB_USER_AGENT: Final[str] = CONST_APP_NAME
CONST_GITHUB_API_VERSION: Final[str] = "2022-11-28"
CONST_GITHUB_HEADER_API_VERSION: Final[str] = "x-github-api-version"
# The media type GitHub serves a pull request's unified diff as.
CONST_GITHUB_DIFF_MEDIA_TYPE: Final[str] = "application/vnd.github.diff"
# The characters that open and close an expression in a URI template (RFC 6570, section 2.2).
# gidgethub expands every path as a template, so the session sends them percent-encoded.
CONST_URI_TEMPLATE_EXPRESSION_DELIMITERS: Final[str] = "{}"
# Response headers the session's error classifier and quota ledger read, named as GitHub's REST
# documentation names them ("Rate limits for the REST API", "Scopes for OAuth apps").
CONST_GITHUB_HEADER_RATE_LIMIT_RESOURCE: Final[str] = "x-ratelimit-resource"
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
CONST_STATUSPAGE_INDICATORS: Final[tuple[str, ...]] = (
    "none",
    "minor",
    "major",
    "critical",
)
CONST_STATUSPAGE_COMPONENT_STATUSES: Final[tuple[str, ...]] = (
    "operational",
    "degraded_performance",
    "partial_outage",
    "major_outage",
    "under_maintenance",
)
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
CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS: Final[tuple[str, ...]] = ("devops", "ingress")
"""The Argo CD Applications whose hosts deploy-stack sets from the configured domain (#1290)."""
CONST_K8S_KUSTOMIZATION_NAMES: Final[tuple[str, ...]] = (
    "kustomization.yaml",
    "kustomization.yml",
    "Kustomization",
)
"""The standard file names Kustomize recognizes for a directory overlay."""
CONST_K8S_ARGOCD_APPLICATION_DIRS: Final[tuple[Path, ...]] = (
    Path("k8s/argocd/apps"),
    Path("k8s/argocd/bootstrap"),
)
"""Directories scanned for Argo CD Applications (#1343)."""
CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS_BY_STACK: Final[dict[str, tuple[str, ...]]] = {
    "infra": ("ingress",),
    "devops": ("devops", "ingress"),
}
"""The homelab Applications whose hosts a stack's deploy sets."""
CONST_K8S_ARGOCD_FETCH_TIMEOUT_SECONDS: Final[float] = 300.0
"""How long fetching an Application's revision may take before deploy-stack gives up."""
CONST_K8S_ARGOCD_PRE_POST_DELETE_FINALIZERS_JQ: Final[str] = (
    '.metadata.finalizers[] | select(startswith("pre-delete-finalizer.argocd.argoproj.io") '
    'or startswith("post-delete-finalizer.argocd.argoproj.io"))'
)
"""JQ expression in cluster.yaml ignoreDifferences matching Argo CD PreDelete/PostDelete finalizers (#1674)."""
CONST_GIT_NONINTERACTIVE_ENV: Final[dict[str, str]] = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_SSH_COMMAND": "ssh -o BatchMode=yes",
}
"""Environment that makes git fail instead of prompting for credentials or a passphrase."""
CONST_GIT_NO_TERMINAL_PROMPT_ENV: Final[dict[str, str]] = {"GIT_TERMINAL_PROMPT": "0"}
"""Environment that stops git from asking for a username or password on the terminal.

An askpass program the person configured (`GIT_ASKPASS`, `core.askPass` or `SSH_ASKPASS`, such as
VS Code's) still runs. Only when none is set, or it answers nothing, does git fail with "terminal
prompts disabled". It leaves ssh alone, unlike `CONST_GIT_NONINTERACTIVE_ENV`, so a person's own
`core.sshCommand` still applies to the git devops-cli runs against their remote (#1124).
"""
CONST_K8S_TEMPLATE_EXTENSIONS: Final[tuple[str, ...]] = (".yaml", ".yml")
# Where each workload kind keeps its pod spec: Pod; PodTemplate; Deployment, ReplicaSet,
# StatefulSet, DaemonSet, Job and ReplicationController; CronJob.
CONST_K8S_POD_SPEC_PATHS: Final[tuple[tuple[str, ...], ...]] = (
    ("spec",),
    ("template", "spec"),
    ("spec", "template", "spec"),
    ("spec", "jobTemplate", "spec", "template", "spec"),
)
# Every container list a pod spec carries.
CONST_K8S_POD_CONTAINER_KEYS: Final[tuple[str, ...]] = (
    "containers",
    "initContainers",
    "ephemeralContainers",
)
# Where a document keeps other resources: a `List` kind, which `kubectl get -o yaml` writes, in
# `items`; an OpenShift Template in `objects`.
CONST_K8S_NESTED_RESOURCE_KEYS: Final[tuple[str, ...]] = ("items", "objects")
# The line match for a manifest that does not parse as YAML, such as a Helm template.
CONST_K8S_PRIVILEGED_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*privileged:\s*(?:true|yes|on)\b", re.IGNORECASE
)
# The tag the YAML resolver gives a plain boolean scalar.
CONST_YAML_BOOL_TAG: Final[str] = "tag:yaml.org,2002:bool"

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

# ── Dockerfile Fallback Checks ────────────────────────────────────────────────
# A FROM instruction: any `--flag=value` options, the image, and an optional stage name.
CONST_DOCKERFILE_FROM_RE: Final[re.Pattern[str]] = re.compile(
    r"^FROM\s+(?:--\S+\s+)*(?P<image>\S+)(?:\s+AS\s+(?P<alias>\S+))?", re.IGNORECASE
)
CONST_DOCKERFILE_USER_RE: Final[re.Pattern[str]] = re.compile(r"^USER\s+", re.IGNORECASE)
# A parser directive, `# name=value`, read only at the top of the file (moby/buildkit
# frontend/dockerfile/parser). `escape` sets the line-continuation character.
CONST_DOCKERFILE_PARSER_DIRECTIVE_RE: Final[re.Pattern[str]] = re.compile(
    r"^#\s*(?P<name>[a-zA-Z][a-zA-Z0-9]*)\s*=\s*(?P<value>.+?)\s*$"
)
CONST_DOCKERFILE_ESCAPE_DIRECTIVE: Final[str] = "escape"
CONST_DOCKERFILE_ESCAPE_CHARACTERS: Final[tuple[str, ...]] = ("\\", "`")
# A BuildKit heredoc opener word, `<<EOF`, `<<-EOF` (terminator may be tab-indented) or
# `<<'EOF'`; a RUN, COPY or ADD reads the lines after it up to its terminator.
CONST_DOCKERFILE_HEREDOC_RE: Final[re.Pattern[str]] = re.compile(
    r"^\d*<<(?P<chomp>-?)(?P<quote>[\"']?)(?P<word>[^<\"']+)(?P=quote)$"
)
CONST_DOCKERFILE_HEREDOC_INSTRUCTIONS: Final[frozenset[str]] = frozenset({"RUN", "COPY", "ADD"})
# The instruction that defers another, which may then open a heredoc: `ONBUILD RUN <<EOF`.
CONST_DOCKERFILE_ONBUILD_INSTRUCTION: Final[str] = "ONBUILD"
# A `$VAR` or `${VAR...}` reference, which stands for text the check cannot see.
CONST_DOCKERFILE_VARIABLE_RE: Final[re.Pattern[str]] = re.compile(r"\$(?:\{[^}]*\}|\w+)")
# The reserved empty base image, which has nothing to pin.
CONST_DOCKERFILE_SCRATCH_IMAGE: Final[str] = "scratch"
# The tag a registry serves for an image reference that names none.
CONST_DOCKER_DEFAULT_TAG: Final[str] = "latest"

# ── AI Prompt & Injection Mitigation ──────────────────────────────────────────
CONST_PROMPT_INJECTION_TAGS_RE: re.Pattern[str] = re.compile(
    r"<\/?(?:system|instructions?|prompt|untrusted)[^>]*>",
    re.IGNORECASE,
)
CONST_PROMPT_INJECTION_TAGS_REGEX = CONST_PROMPT_INJECTION_TAGS_RE

# ── File Permissions ──────────────────────────────────────────────────────────
CONST_PERM_DIR = 0o700
CONST_PERM_PRIVATE_KEY = 0o600
CONST_PERM_PUBLIC_KEY = 0o644
CONST_PERM_EXEC = 0o755
# A file the repository commits, such as a generated table under src/.
CONST_PERM_REPO_FILE = 0o644

CONST_MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024
CONST_MAX_PROBE_FILE_SIZE_BYTES: Final[int] = (
    512 * 1024
)  # 512 KiB pre-flight file size cap for review probes
CONST_PROBE_MANIFEST_NAMES: Final[tuple[str, ...]] = (
    "pyproject.toml",
    "package.json",
    "cargo.toml",
    "cargo.lock",
    "go.mod",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements.in",
)

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
# Share of the context window a review page's diff may fill; the rest holds the persona system
# prompt, instructions and the model's reply.
CONST_REVIEW_PAGE_WINDOW_SHARE: Final[float] = 0.6
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

CONST_RECOMMENDATION_APPROVE = "APPROVE"
CONST_RECOMMENDATION_REQUEST_CHANGES = "REQUEST CHANGES"
CONST_RECOMMENDATION_BLOCK = "BLOCK"

# ── GitHub CLI & Pull Requests ────────────────────────────────────────────────
CONST_GH_CLI = "gh"
CONST_CI_WORKFLOW_FILE = "ci.yml"
CONST_GIT_CLI = "git"
CONST_GH_AUTH_SUBCOMMAND = "auth"
# The token gh reads first; the session pins it on every gh and git child (#767).
CONST_GH_TOKEN_ENV = "GH_TOKEN"
# Every variable gh reads a token from, so a pinned child is given none but the session's.
CONST_GH_TOKEN_ENV_VARS: Final[tuple[str, ...]] = (CONST_GH_TOKEN_ENV, "GITHUB_TOKEN")
# Where `gh auth token` finds a stored login: its config directory and the keyring's session bus.
CONST_GH_LOGIN_ENV_VARS: Final[frozenset[str]] = frozenset(
    {"GH_CONFIG_DIR", "XDG_CONFIG_HOME", "DBUS_SESSION_BUS_ADDRESS"}
)
# Hex characters of the token's SHA-256 that name an identity's cache directory.
CONST_GITHUB_IDENTITY_DIGEST_CHARS: Final[int] = 16
# Identities whose rate limiters a process keeps in memory at once; a process acts as one, and a
# second session with another token adds one more. Older ones are read from disk again.
CONST_GITHUB_IDENTITY_LIMITERS_KEPT: Final[int] = 4
CONST_GITHUB_UNAUTHENTICATED_ERROR_CODE = "GITHUB_UNAUTHENTICATED"
# How the session's HTTP failures are told apart (#983): a token without a scope the endpoint
# needs, an answer that what was asked for does not exist, and no readable answer at all.
CONST_GITHUB_SCOPE_ERROR_CODE: Final[str] = "GITHUB_SCOPE_MISSING"
CONST_GITHUB_NOT_FOUND_ERROR_CODE: Final[str] = "GITHUB_NOT_FOUND"
CONST_GITHUB_UNREAD_ERROR_CODE: Final[str] = "GITHUB_UNREAD"
# Copilot code review is the GitHub App `copilot-pull-request-reviewer`, and GitHub names an app's
# bot account `<slug>[bot]` (#1345). The reviews endpoint names the bot
# `copilot-pull-request-reviewer[bot]`, and GraphQL names it `copilot-pull-request-reviewer`, gh's
# `CopilotReviewerLogin` (gh 2.102.0, api/queries_repo.go): a review record is Copilot's only when
# its author's login is exactly one of them. The issue timeline names the same account (id
# 175728472) `Copilot`, type Bot, a login the Copilot coding agent shares, so a timeline `reviewed`
# event is matched by the id of one of Copilot's reviews, never by login, and a review request by
# the account's type and its app's page, `/apps/<slug>` (read on #1283's timeline).
CONST_COPILOT_REVIEWER_APP_SLUG: Final[str] = "copilot-pull-request-reviewer"
CONST_COPILOT_REVIEWER_LOGINS: Final[frozenset[str]] = frozenset(
    {f"{CONST_COPILOT_REVIEWER_APP_SLUG}[bot]", CONST_COPILOT_REVIEWER_APP_SLUG}
)
CONST_COPILOT_REVIEWER_APP_PATH: Final[str] = f"/apps/{CONST_COPILOT_REVIEWER_APP_SLUG}"
# The `type` GitHub gives an app's bot account.
CONST_GITHUB_BOT_ACCOUNT_TYPE: Final[str] = "Bot"
# The issue timeline events that request a review or withdraw the request, each with whether it
# leaves the reviewer requested.
CONST_GH_REVIEW_REQUEST_EVENTS: Final[dict[str, bool]] = {
    "review_requested": True,
    "review_request_removed": False,
}
# The keys a review record names its author under: `user` in a REST review, `author` in a
# GraphQL one.
CONST_GITHUB_REVIEW_AUTHOR_KEYS: Final[tuple[str, ...]] = ("user", "author")
# The reviewer `gh pr edit --add-reviewer` requests a Copilot review with (gh 2.102.0).
CONST_GH_COPILOT_REVIEWER: Final[str] = "@copilot"
# A Copilot pass `devops pr copilot-pass` refuses: on any pull request but the release pull
# request, or once the release pull request's Copilot budget is spent (#1345).
CONST_COPILOT_PASS_REFUSED_ERROR_CODE: Final[str] = "COPILOT_PASS_REFUSED"
# The line `devops pr threads file-issues` ends the reply naming a thread's follow-up issue
# with, and the pattern a line must match whole to be one, giving the issue's number (#1345). A
# rerun counts it only in a reply the account running it wrote, never in the thread's first
# comment, so a suggestion or another person's reply quoting it cannot resolve a thread.
CONST_PR_THREAD_FILED_MARKER: Final[str] = "<!-- devops-cli: filed as #{issue} -->"
CONST_PR_THREAD_FILED_MARKER_RE: Final[re.Pattern[str]] = re.compile(
    r"<!-- devops-cli: filed as #([1-9][0-9]*) -->"
)
# The login GitHub shows for a deleted account, whose GraphQL `author` is null.
CONST_GITHUB_GHOST_LOGIN: Final[str] = "ghost"
# `devops pr threads file-issues` refuses any pull request but the open release pull request.
CONST_THREAD_FILING_REFUSED_ERROR_CODE: Final[str] = "THREAD_FILING_REFUSED"
CONST_GH_QUOTA_CACHE_FILENAME = "gh_quota.json"
# GitHub's rate limit `reset` is whole epoch seconds, so a window can still be reported within the
# second after it. A call at a reset that has passed waits until this long past it, the margin
# PyGithub 2.10.0 adds ("plus 1s as it is not clear when in that second the reset occurs",
# github/GithubRetry.py) (#1364).
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
CONST_GH_WEBHOOK_EVENT_HEADER: Final[str] = "X-GitHub-Event"
CONST_GH_WEBHOOK_DELIVERY_HEADER: Final[str] = "X-GitHub-Delivery"
CONST_SERVICE_MAX_BODY_BYTES: Final[int] = 25 * 1024 * 1024
CONST_SERVICE_DELIVERY_LRU_CAPACITY: Final[int] = 10_000
CONST_SERVICE_SOURCE_WEBHOOK: Final[str] = "webhook"
CONST_SERVICE_SOURCE_POLL: Final[str] = "poll"
CONST_SERVICE_PING_EVENT: Final[str] = "ping"
CONST_SERVICE_METRIC_WEBHOOK_DELIVERIES: Final[str] = "devops_cli_service_webhook_deliveries_total"
CONST_SERVICE_METRIC_TRIGGERS: Final[str] = "devops_cli_service_triggers_total"
CONST_SERVICE_METRIC_JOBS: Final[str] = "devops_cli_service_jobs_total"
CONST_SERVICE_METRIC_JOB_SECONDS: Final[str] = "devops_cli_service_job_seconds_total"
CONST_SERVICE_METRIC_JOB_START_TIMESTAMP: Final[str] = (
    "devops_cli_service_job_start_timestamp_seconds"
)
CONST_SERVICE_METRIC_QUEUE_DEPTH: Final[str] = "devops_cli_service_queue_depth"
# The Service's lanes (#1532): each repository has one worker per lane. The release lane runs the
# jobs that close items and start and ship releases, the model lane those that call the model, so
# a release-lane round never waits for a model-lane round. A service app given no jobs runs its
# logging job in the default lane.
CONST_SERVICE_LANE_RELEASE: Final[str] = "release"
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

CONST_GH_CHECK_BUCKETS: Final[frozenset[str]] = frozenset(
    {
        CONST_GH_CHECK_BUCKET_PASS,
        CONST_GH_CHECK_BUCKET_FAIL,
        CONST_GH_CHECK_BUCKET_PENDING,
        CONST_GH_CHECK_BUCKET_SKIPPING,
        CONST_GH_CHECK_BUCKET_CANCEL,
        CONST_GH_CHECK_BUCKET_UNREAD,
    }
)

CONST_PR_API_STATE_MAP: Final[dict[str, str]] = {
    "all": "all",
    "closed": "closed",
    "merged": "closed",
}
CONST_GH_PROJECT_ITEM_ISSUE_TYPE: Final[str] = "Issue"
CONST_GH_PROJECT_JOB_RECORD_FIELD: Final[str] = "Job record"
CONST_GH_ISSUE_EVENT_CHANGE_KINDS: Final[dict[str, str]] = {
    "milestoned": "joined_release",
    "demilestoned": "left_release",
    "labeled": "labeled",
    "unlabeled": "unlabeled",
    "closed": "closed",
    "reopened": "reopened",
}
CONST_GH_ISSUE_STATE_REASON_REOPENED: Final[str] = "reopened"
"""GitHub's `state_reason` on an issue someone reopened, which it keeps while the issue is open.
No roadmap job reopens an issue, so it marks a person's reopen (ADR 0002)."""

# ── Exception & Domain Error Codes ────────────────────────────────────────────
CONST_ERROR_CODE_DEVOPS_CLI = "DEVOPS_CLI_ERROR"
CONST_ERROR_CODE_LLM_INFERENCE = "LLM_INFERENCE_ERROR"
CONST_ERROR_CODE_EMBEDDINGS = "EMBEDDINGS_ERROR"
CONST_ERROR_CODE_MODEL_GATEWAY_UNREACHABLE = "MODEL_GATEWAY_UNREACHABLE"
CONST_ERROR_CODE_CONFIG = "CONFIGURATION_ERROR"
CONST_ERROR_CODE_GIT = "GIT_OPERATION_ERROR"
CONST_ERROR_CODE_SECURITY = "SECURITY_ERROR"
CONST_ERROR_CODE_TOOL = "TOOL_EXECUTION_ERROR"
CONST_ERROR_CODE_VALIDATION = "VALIDATION_ERROR"
CONST_ERROR_CODE_VAULT = "VAULT_ERROR"
CONST_ERROR_CODE_VAULT_AUTH = "VAULT_AUTH_ERROR"
CONST_ERROR_CODE_VAULT_LEASE = "VAULT_LEASE_ERROR"
CONST_ERROR_CODE_VALKEY = "VALKEY_ERROR"
CONST_ERROR_CODE_DOCKER_SANDBOX = "DOCKER_SANDBOX_ERROR"
CONST_ERROR_CODE_DOCKER_ENGINE = "DOCKER_ENGINE_ERROR"
CONST_ERROR_CODE_DOCKER_DAEMON_UNAVAILABLE = "DOCKER_DAEMON_UNAVAILABLE"
CONST_ERROR_CODE_K8S = "K8S_ERROR"
CONST_ERROR_CODE_ARGO = "ARGO_ERROR"
CONST_ERROR_CODE_ARGO_RESOURCE_NOT_FOUND = "ARGO_RESOURCE_NOT_FOUND"
CONST_ERROR_CODE_MODEL_BUNDLE = "MODEL_BUNDLE_ERROR"
CONST_ERROR_CODE_HARNESS = "HARNESS_ERROR"
CONST_ERROR_CODE_HARNESS_VALIDATION = "HARNESS_VALIDATION_ERROR"
CONST_ERROR_CODE_HARNESS_EXECUTION = "HARNESS_EXECUTION_ERROR"
CONST_ERROR_CODE_CONSTELLATION_QUIESCE = "CONSTELLATION_QUIESCE_ERROR"
CONST_ERROR_CODE_CONSTELLATION_FAILOVER = "CONSTELLATION_FAILOVER_ERROR"
CONST_ERROR_CODE_CONSTELLATION_RESUME = "CONSTELLATION_RESUME_ERROR"
CONST_ERROR_CODE_REVIEW_POOL = "REVIEW_POOL_ERROR"
CONST_ERROR_CODE_TELEMETRY = "TELEMETRY_ERROR"
CONST_ERROR_CODE_LOGFIRE = "LOGFIRE_CONFIG_ERROR"
CONST_ERROR_CODE_SERVICE_STATUS = "SERVICE_STATUS_ERROR"
CONST_ERROR_CODE_ROADMAP_CARD_CHANGED = "ROADMAP_CARD_CHANGED"
CONST_ERROR_CODE_ROADMAP_REFINE_FAILED = "ROADMAP_REFINE_FAILED"
CONST_ERROR_CODE_ROADMAP_INTAKE_FAILED = "ROADMAP_INTAKE_FAILED"
CONST_ERROR_CODE_LIBRARY_INGESTION = "LIBRARY_INGESTION_ERROR"
CONST_ERROR_CODE_LIBRARY_NOT_FOUND = "LIBRARY_NOT_FOUND_ERROR"
CONST_ERROR_CODE_DOCS_INGESTION = "DOCS_INGESTION_ERROR"
CONST_ERROR_CODE_DOC_COMPACTION = "DOC_COMPACTION_ERROR"
CONST_ERROR_CODE_SANDBOX = "SANDBOX_ERROR"
CONST_ERROR_CODE_SANDBOX_VALIDATION = "SANDBOX_VALIDATION_ERROR"
CONST_ERROR_CODE_SANDBOX_PORT_ALLOCATION = "SANDBOX_PORT_ALLOCATION_ERROR"
CONST_ERROR_CODE_SANDBOX_NOT_FOUND = "SANDBOX_NOT_FOUND_ERROR"
CONST_ERROR_CODE_COSIGN = "COSIGN_ERROR"
CONST_ERROR_CODE_COSIGN_VERIFY = "COSIGN_VERIFICATION_FAILED"
CONST_ERROR_CODE_STRUCTURED_VALIDATION = "STRUCTURED_VALIDATION_ERROR"
CONST_ERROR_CODE_CAPABILITY_DEGRADATION = "CAPABILITY_DEGRADATION"
CONST_MAX_ERROR_DETAIL_LENGTH = 256

# ── AI Client Structured Output Metric Invariants ─────────────────────────────
CONST_METRIC_AI_STRUCTURED_SUCCESS = "ai.client.structured_success"
CONST_METRIC_AI_STRUCTURED_RETRY_COUNT = "ai.client.structured_retry_count"
CONST_METRIC_AI_STRUCTURED_VALIDATION_FAILURE = "ai.client.structured_validation_failure"
CONST_JSON_REPAIR_SOURCE_REPAIR_JSON_STRING: Final[str] = "repair_json_string"
CONST_JSON_REPAIR_SOURCE_EXTRACT_JSON_BLOCK: Final[str] = "extract_json_block"
CONST_JSON_REPAIR_SOURCE_CHAT_STRUCTURED: Final[str] = "chat_structured"


CONST_EXIT_SUCCESS: int = 0
CONST_EXIT_FAILURE: int = 1
CONST_EXIT_USAGE: int = 2
CONST_EXIT_ERROR_INFERENCE: int = 10
# The status the subprocess runners report when the program is not on PATH, as POSIX shells do.
CONST_EXIT_COMMAND_NOT_FOUND: int = 127
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
# The signals besides Ctrl-C's SIGINT that cancel a `devops ci test` run, whose pytest runs in a
# session of its own that no terminal hangup or supervisor's SIGTERM reaches (#1669).
CONST_CI_RUN_STOP_SIGNAL_NAMES: Final[tuple[str, ...]] = ("SIGTERM", "SIGHUP")

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
# The Valkey holding the shared run index (k8s/llm/valkey-runs.yaml) and its password secret.
CONST_RUNS_INDEX_NAMESPACE = "llm"
CONST_RUNS_INDEX_SERVICE = "valkey-runs"
CONST_RUNS_INDEX_SECRET = "valkey-runs-auth"

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

# Minimum length at which a single shared identifier is specific enough, on its own,
# to conclude two findings describe the same defect.
REVIEW_STRONG_SYMBOL_MIN_LENGTH: Final[int] = 6

# Minimum description token overlap required before two findings that merely share an
# enclosing symbol are treated as one defect. Set high enough that different defects in
# the same function stay separate, since dropping a real finding is the costlier error.
REVIEW_DESCRIPTION_SIMILARITY_THRESHOLD: Final[float] = 0.35

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
CONST_SECRET_PROVIDER_TOOL: Final[str] = "tool"

# Upper bound on retained credential access records, preventing unbounded growth in
CONST_SECRET_AUDIT_MAX_ENTRIES: Final[int] = 1000

# Illustrative placeholder markers and documentation tokens ignored by native secret scanner.
CONST_SECRET_PLACEHOLDER_MARKERS: Final[tuple[str, ...]] = (
    "your_",
    "placeholder",
    "dummy",
    "token_here",
    "key_here",
    "insert_",
    "change_me",
    "changeme",
    "masked",
    "xxx",
)

# Vault API paths. Fixed by the Vault HTTP API, so this set is closed and exhaustive.
CONST_VAULT_API_PREFIX: Final[str] = "/v1"
# Conventional KV-v2 mount and folder holding this project's managed credentials.
CONST_VAULT_SECRET_MOUNT: Final[str] = "secret/data/devops-cli"
CONST_VAULT_PATH_APPROLE_LOGIN: Final[str] = "auth/approle/login"
CONST_VAULT_PATH_KUBERNETES_LOGIN: Final[str] = "auth/kubernetes/login"

# Supported Vault authentication methods, closed by what this CLI implements.
CONST_VAULT_AUTH_METHODS: Final[frozenset[str]] = frozenset({"approle", "kubernetes"})
CONST_VAULT_PATH_TOKEN_LOOKUP_SELF: Final[str] = "auth/token/lookup-self"
CONST_VAULT_PATH_TOKEN_RENEW_SELF: Final[str] = "auth/token/renew-self"
CONST_VAULT_PATH_TOKEN_REVOKE_SELF: Final[str] = "auth/token/revoke-self"
CONST_VAULT_PATH_HEALTH: Final[str] = "sys/health"
CONST_VAULT_PATH_LEASE_RENEW: Final[str] = "sys/leases/renew"
CONST_VAULT_PATH_LEASE_REVOKE: Final[str] = "sys/leases/revoke"
CONST_VAULT_PATH_TRANSIT_ENCRYPT: Final[str] = "transit/encrypt"
CONST_VAULT_PATH_TRANSIT_DECRYPT: Final[str] = "transit/decrypt"

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

# ── Tiered Cache Namespacing & Tiers ─────────────────────────────────────────
# Root prefix for every cache key this project writes, so a shared Valkey instance can
# be swept per-project and keys never collide with another tenant's.
CONST_CACHE_NAMESPACE_ROOT: Final[str] = "devops-cli"
CONST_CACHE_KEY_SEPARATOR: Final[str] = ":"

# Cache tiers. Closed set: L1 is the in-process LRU, L2 is Valkey, and L1_L2 writes both.
CONST_CACHE_TIER_L1: Final[str] = "l1"
CONST_CACHE_TIER_L2: Final[str] = "l2"
CONST_CACHE_TIER_L1_L2: Final[str] = "l1_l2"
CONST_CACHE_TIERS: Final[frozenset[str]] = frozenset(
    {CONST_CACHE_TIER_L1, CONST_CACHE_TIER_L2, CONST_CACHE_TIER_L1_L2}
)

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
CONST_FAIL_TO_PASS_ESCAPE_PATTERN: Final[str] = (
    r"(?im)^Fail-to-pass:\s*not\s+applicable:\s*(.+?)\s*$"
)
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
CONST_HCL_JSON_FILE_EXTENSION: Final[str] = ".tf.json"

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
CONST_HCL_BLOCK_LOCALS: Final[str] = "locals"
CONST_HCL_BLOCK_PROVIDER: Final[str] = "provider"
CONST_HCL_BLOCK_TERRAFORM: Final[str] = "terraform"
CONST_HCL_BLOCK_MOVED: Final[str] = "moved"
CONST_HCL_BLOCK_IMPORT: Final[str] = "import"
CONST_HCL_BLOCK_CHECK: Final[str] = "check"

CONST_HCL_BLOCK_TYPES: Final[frozenset[str]] = frozenset(
    {
        CONST_HCL_BLOCK_RESOURCE,
        CONST_HCL_BLOCK_DATA,
        CONST_HCL_BLOCK_MODULE,
        CONST_HCL_BLOCK_VARIABLE,
        CONST_HCL_BLOCK_OUTPUT,
        CONST_HCL_BLOCK_LOCALS,
        CONST_HCL_BLOCK_PROVIDER,
        CONST_HCL_BLOCK_TERRAFORM,
        CONST_HCL_BLOCK_MOVED,
        CONST_HCL_BLOCK_IMPORT,
        CONST_HCL_BLOCK_CHECK,
    }
)

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

CONST_ARGO_RESOURCE_PLURALS: Final[frozenset[str]] = frozenset(
    {
        CONST_ARGO_PLURAL_APPLICATIONS,
        CONST_ARGO_PLURAL_APPLICATION_SETS,
        CONST_ARGO_PLURAL_ROLLOUTS,
        CONST_ARGO_PLURAL_ANALYSIS_RUNS,
        CONST_ARGO_PLURAL_WORKFLOWS,
    }
)

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

# ── Docker Engine Socket API & BuildKit Cache Introspection ──────────────────
# Container CPU utilisation severity thresholds for live stats rendering.
CONST_DOCKER_CPU_WARNING_PERCENT: Final[float] = 50.0
CONST_DOCKER_CPU_CRITICAL_PERCENT: Final[float] = 80.0

# The scheme docker-py's `parse_host` gives a unix socket endpoint; its client then speaks over
# the socket its `UnixHTTPAdapter` derives from that URL.
CONST_DOCKER_UNIX_ADAPTER_SCHEME: Final[str] = "http+unix"

# `GET /system/df` object types returned by the Engine API disk-usage endpoint.
CONST_DOCKER_DF_BUILD_CACHE_KEY: Final[str] = "BuildCache"
CONST_DOCKER_DF_IMAGES_KEY: Final[str] = "Images"
CONST_DOCKER_DF_CONTAINERS_KEY: Final[str] = "Containers"
CONST_DOCKER_DF_VOLUMES_KEY: Final[str] = "Volumes"

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
CONST_X11_SOCKET_DIR: Final[Path] = Path("/tmp/.X11-unix")  # nosec B108

# Multi-tier sandbox networking mode constants
CONST_SANDBOX_NETWORK_ISOLATED: Final[str] = "isolated"
CONST_SANDBOX_NETWORK_NAMESPACE: Final[str] = "sandbox_namespace"
CONST_SANDBOX_NETWORK_PUBLIC_WHITELIST: Final[str] = "public_whitelist"
CONST_SANDBOX_NETWORK_LOCAL_WHITELIST: Final[str] = "local_whitelist"
CONST_SANDBOX_NETWORK_BRIDGE: Final[str] = "bridge"

CONST_SANDBOX_DEFAULT_NAMESPACE: Final[str] = "sandbox"
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

# Schemes recognized for Valkey and Redis connection endpoints
CONST_VALKEY_SCHEMES: Final[frozenset[str]] = frozenset(
    {"valkey", "valkeys", "redis", "rediss", "tcp"}
)

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

# Consecutive transient embedding failures before pausing RAG lookups
CONST_RAG_CIRCUIT_BREAKER_FAILURES: Final[int] = 3

# Duration in seconds to pause RAG lookups when circuit breaker opens
CONST_RAG_CIRCUIT_BREAKER_PAUSE_SECONDS: Final[float] = 60.0

# Project identifier used for bundled DevOps CLI Knowledge Base chunks in Qdrant
CONST_RAG_KB_PROJECT: Final[str] = "devops-cli-kb"

# Helm releases that deploy DaemonSets across all cluster nodes
CONST_HELM_DAEMONSET_RELEASES: Final[frozenset[str]] = frozenset(
    {"k8s-monitoring", "dcgm-exporter"}
)

# Helm releases teardown-stack leaves installed: deleting a CRD deletes every object of its kind
# in the cluster, so uninstalling the Prometheus Operator CRDs would delete every ServiceMonitor
CONST_HELM_TEARDOWN_RETAINED_RELEASES: Final[frozenset[str]] = frozenset(
    {"prometheus-operator-crds"}
)

# A resource Helm refuses to adopt, as its resourceString prints it: `<Kind> "<name>" in namespace
# "<namespace>"`, where the namespace is empty for a cluster-scoped resource such as a CRD
CONST_HELM_OWNERSHIP_CONFLICT_RE: Final[re.Pattern[str]] = re.compile(
    r'([A-Za-z0-9_-]+)\s+"([^"]+)"\s+in namespace\s+"([^"]*)"'
)

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
# The other `gh api` flags, so the argv parser skips them and their values.
CONST_GH_API_VALUE_FLAGS: Final[tuple[tuple[str, ...], ...]] = (
    ("--cache",),
    ("-H", "--header"),
    ("--hostname",),
    ("-q", "--jq"),
    ("-p", "--preview"),
    ("-t", "--template"),
)
CONST_GH_API_SWITCH_FLAGS: Final[tuple[tuple[str, ...], ...]] = (
    ("--allow-escape-sequences",),
    ("-i", "--include"),
    ("--paginate",),
    ("--silent",),
    ("--slurp",),
    ("--verbose",),
)

CONST_GH_MUTATION_HTTP_METHODS: Final[frozenset[str]] = frozenset(
    {
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    }
)

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
# Why a provider says a reply ended, as pydantic-ai's FinishReason. The OpenAI-compatible and
# Anthropic tables copy pydantic-ai 2.54.0's private maps (models/openai.py, models/anthropic.py),
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
# Replies the response cache never stores: one cut short, filtered or failed is not the answer
# the prompt asked for, and serving it again for 7 days would repeat the cut.
CONST_UNCACHED_FINISH_REASONS: Final[frozenset[FinishReason]] = frozenset(
    {"length", "content_filter", "error"}
)
# How a review profile counts a reply whose provider gave no finish reason.
CONST_FINISH_REASON_UNKNOWN: Final[str] = "unknown"
CONST_AI_GATEWAY_PROVIDERS: Final[tuple[str, ...]] = ("litellm", "portkey")
CONST_AI_GATEWAY_PROVIDER_LITELLM: Final[str] = "litellm"
CONST_AI_GATEWAY_PROVIDER_PORTKEY: Final[str] = "portkey"
CONST_AI_GATEWAY_DEFAULT_PORT: Final[int] = 4000
CONST_AI_PORTKEY_DEFAULT_PORT: Final[int] = 8787
CONST_AI_BACKENDS: Final[tuple[str, ...]] = ("ollama",)
CONST_AI_PROMPT_CACHE_TTL_5M: Final[str] = "5m"
CONST_AI_PROMPT_CACHE_TTL_1H: Final[str] = "1h"
CONST_AI_PROMPT_CACHE_TTLS: Final[tuple[str, ...]] = ("5m", "1h")
# The default fallback cascade, by path: a bare `litellm` or `portkey` member is that gateway's
# default chat route (CONST_AI_GATEWAY_DEFAULT_ROUTE), and a bare `ollama` member is `ai.model`
# on Ollama itself.
CONST_AI_CASCADE_PROVIDERS: Final[tuple[str, ...]] = ("litellm", "portkey", "ollama")
CONST_AI_GATEWAY_DEFAULT_ROUTE: Final[str] = "devops-chat"
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
CONST_AI_DEFAULT_CACHE_MARKER_KIND: Final[str] = "cache-point"
CONST_PIPELINE_STAGE_TRUNCATION_SUFFIX: Final[str] = (
    "\n...[stage output truncated to the stage context budget]"
)
# The loopback host name (RFC 6761). With the loopback addresses, which `ipaddress` recognises,
# it names the workstation itself, so a configured service URL may use it without
# `ai.allow_private_network` (`validate_configured_service_url`).
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

# ── Roadmap on GitHub (ADR 0001) ──────────────────────────────────────────────
# Repository files every roadmap runner reads through the contents API at one ref.
CONST_ROADMAP_CONFIG_PATH: Final[str] = ".github/roadmap.toml"
# The Projects filter each board read passes at the source, archived items always left out
# (#1125). "" reads every item not archived, open and closed: reprioritize judges a Release's
# closed members, render lists them, intake looks up any issue it is given, and migrate's
# one-time reads may include closed items. The backlog and the candidates read open items only.
CONST_ROADMAP_OPEN_ITEMS_FILTER: Final[str] = "is:open"
CONST_ROADMAP_MIGRATE_BOARD_FILTER: Final[str] = ""
CONST_ROADMAP_RENDER_BOARD_FILTER: Final[str] = ""
CONST_ROADMAP_REPRIORITIZE_BOARD_FILTER: Final[str] = ""
CONST_ROADMAP_INTAKE_BOARD_FILTER: Final[str] = ""
CONST_ROADMAP_RUN_BOARD_FILTER: Final[str] = ""
CONST_ROADMAP_REFINE_BOARD_FILTER: Final[str] = ""
CONST_ROADMAP_REFINE_START_MARKER: Final[str] = "<!-- devops-roadmap-refine:start -->"
CONST_ROADMAP_REFINE_END_MARKER: Final[str] = "<!-- devops-roadmap-refine:end -->"
CONST_ROADMAP_REFINE_MAX_BODY_CHARS: Final[int] = 65536
CONST_ROADMAP_REFINE_MAX_SEARCH_QUERIES: Final[int] = 3
CONST_ROADMAP_REFINE_SEARCH_RESULTS_PER_QUERY: Final[int] = 5
CONST_ROADMAP_RUN_STATE_FILENAME: Final[str] = "schedule.json"
# The Service's intake record beside schedule.json: what intake decided and left (#1360).
CONST_ROADMAP_INTAKE_RECORD_FILENAME: Final[str] = "intake.json"
CONST_ROADMAP_RUN_CLONE_DIRNAME: Final[str] = "clone"
# The model lane's own clone beside it, so the model lane's checkout never touches a cut the
# release lane is making in `clone` (#1532).
CONST_ROADMAP_RUN_MODEL_CLONE_DIRNAME: Final[str] = "model-clone"
CONST_ROADMAP_INTAKE_BATCH_KEYS: Final[tuple[tuple[str, str, str], ...]] = (
    ("webhook", "issues", "opened"),
    ("webhook", "issues", "reopened"),
)
CONST_ROADMAP_CLOSURE_BATCH_KEYS: Final[tuple[tuple[str, str, str], ...]] = (
    ("webhook", "pull_request", "closed"),
)
# A milestone closing and a GitHub Release published are a ship's webhook hints (#1360).
CONST_ROADMAP_REPRIORITIZE_BATCH_KEYS: Final[tuple[tuple[str, str, str], ...]] = (
    ("webhook", "milestone", "closed"),
    ("webhook", "release", "published"),
)
CONST_ROADMAP_DOCUMENT_PATH: Final[str] = "docs/ROADMAP.md"
CONST_PROJECT_TEMPLATE_PATH: Final[str] = ".github/project-template.json"
CONST_ROADMAP_ADR_PATH: Final[str] = "docs/adr/0001-github-is-the-roadmap-source.md"
# The first line `devops roadmap render` writes. A file carrying it is a generated view, so
# `devops roadmap migrate` never imports it.
CONST_ROADMAP_RENDER_MARKER: Final[str] = (
    "<!-- Generated by `devops roadmap render` from GitHub issues, milestones and the board. "
    "Open an issue instead of editing this file. -->"
)
# A rendered roadmap is a tracked repository file, readable by everyone like any other.
CONST_ROADMAP_RENDER_FILE_MODE: Final[int] = 0o644
CONST_ROADMAP_EPIC_LABEL: Final[str] = "type/epic"
CONST_ROADMAP_STATUS_FIELD: Final[str] = "Status"
# A hand-written ROADMAP entry heading ends in a parenthetical such as
# `(P1 - High, Issues #287, #289, PR #288, Overlaps #740)`. These tags name the entry's issues
# and the roadmap item it overlaps; every other tag (`PR`) is ignored.
CONST_ROADMAP_ISSUE_TAGS: Final[frozenset[str]] = frozenset({"Issue", "Issues"})
CONST_ROADMAP_OVERLAP_TAG: Final[str] = "Overlaps"
CONST_ROADMAP_P0_PRIORITY: Final[str] = "P0"
# The Value vs. Effort matrix's columns, and the Status cell prefixes that mark a row done
# with: delivered or rejected. Every other row is open.
CONST_ROADMAP_MATRIX_FEATURE_COLUMN: Final[str] = "Feature / Focus"
CONST_ROADMAP_MATRIX_VALUE_COLUMN: Final[str] = "Value"
CONST_ROADMAP_MATRIX_EFFORT_COLUMN: Final[str] = "Effort"
CONST_ROADMAP_MATRIX_STATUS_COLUMN: Final[str] = "Status"
CONST_ROADMAP_MATRIX_COMPLETED_STATUS: Final[str] = "✅ Completed"
CONST_ROADMAP_MATRIX_REJECTED_STATUS: Final[str] = "❌ Rejected"
# The phrase that marks an entry heading as investigated and not built.
CONST_ROADMAP_NOT_BUILDING_MARKER: Final[str] = "not building"
# A workflow whose name starts with this adds issues to the board behind intake's back.
CONST_ROADMAP_AUTO_ADD_WORKFLOW_PREFIX: Final[str] = "Auto-add"
# The board's Status options (`.github/project-template.json`) the release rules read. An item
# is started once it is in progress, in review or done; every other Status, or none, is
# unstarted (CONTEXT.md).
CONST_ROADMAP_STATUS_NEW: Final[str] = "New"
CONST_ROADMAP_STATUS_READY: Final[str] = "Ready"
CONST_ROADMAP_STATUS_IN_PROGRESS: Final[str] = "In Progress"
CONST_ROADMAP_STATUS_IN_REVIEW: Final[str] = "In Review"
CONST_ROADMAP_STATUS_DONE: Final[str] = "Done"
CONST_ROADMAP_STATUS_BLOCKED: Final[str] = "Blocked"
CONST_ROADMAP_STARTED_STATUSES: Final[frozenset[str]] = frozenset(
    {CONST_ROADMAP_STATUS_IN_PROGRESS, CONST_ROADMAP_STATUS_IN_REVIEW, CONST_ROADMAP_STATUS_DONE}
)
# The Status options #739's template replaces with New: while the board still has one,
# `devops roadmap migrate` has cards left to move, and its release epics are still Items.
CONST_ROADMAP_PREMIGRATE_STATUSES: Final[frozenset[str]] = frozenset({"Backlog", "Todo"})
# A critical fix is a P0 item that fixes a defect or a security advisory (CONTEXT.md): the
# board's P0 Priority option and one of these `type/*` labels.
CONST_ROADMAP_CRITICAL_PRIORITY: Final[str] = "P0-Critical"
CONST_ROADMAP_P1_PRIORITY: Final[str] = "P1-High"
CONST_ROADMAP_P2_PRIORITY: Final[str] = "P2-Medium"
CONST_ROADMAP_P3_PRIORITY: Final[str] = "P3-Low"
CONST_ROADMAP_P0_PRIORITIES: Final[frozenset[str]] = frozenset(
    {CONST_ROADMAP_CRITICAL_PRIORITY, CONST_ROADMAP_P0_PRIORITY}
)
CONST_ROADMAP_P1_PRIORITIES: Final[frozenset[str]] = frozenset({"P1-High", "P1"})
CONST_ROADMAP_HIGH_PRIORITIES: Final[frozenset[str]] = frozenset(
    CONST_ROADMAP_P0_PRIORITIES | CONST_ROADMAP_P1_PRIORITIES
)
CONST_ROADMAP_P3_PRIORITIES: Final[frozenset[str]] = frozenset({"P3-Low", "P3"})
CONST_ROADMAP_CRITICAL_FIX_LABELS: Final[frozenset[str]] = frozenset({"type/bug", "type/security"})
# A person applies it to an item too big for one pull request; reprioritization descopes it.
CONST_ROADMAP_NEEDS_SPLIT_LABEL: Final[str] = "needs-split"
# The `Left` mark of an item a person took out of the backlog, where a job last placed it; every
# other `Left` mark names a Release.
CONST_ROADMAP_LEFT_BACKLOG: Final[str] = "backlog"
# The draft issue card whose job record is the run record: what a roadmap job keeps about the
# repository as a whole, such as the Release reprioritization last started. The store finds it
# by this title.
CONST_ROADMAP_RUN_RECORD_TITLE: Final[str] = "Roadmap run record"
CONST_ROADMAP_RUN_RECORD_BODY: Final[str] = (
    "The roadmap jobs keep their run record in this card's Job record field, such as the "
    "release `devops roadmap reprioritize` last started. Leave the card on the board: without "
    "it, the job refuses to run until the card is back."
)
# `devops roadmap intake` (#742). Its reason comment and its duplicate close each carry their own
# marker, so a run that finds one posts no second comment of that kind.
CONST_ROADMAP_INTAKE_REASON_MARKER: Final[str] = "<!-- devops roadmap intake: reason -->"
CONST_ROADMAP_INTAKE_DUPLICATE_MARKER: Final[str] = "<!-- devops roadmap intake: duplicate -->"
CONST_ROADMAP_LABELS_PATH: Final[str] = ".github/labels.yml"
CONST_ROADMAP_TYPE_LABEL_PREFIX: Final[str] = "type/"
CONST_ROADMAP_PRIORITY_LABEL_PREFIX: Final[str] = "priority/"
CONST_ROADMAP_CONVENTIONAL_COMMIT_TYPE_MAPPINGS: Final[dict[str, str]] = {
    "perf": "type/infra",
    "build": "type/infra",
    "ci": "type/infra",
}
# The agent filing quota's labels (#1153): an agent's candidate, and one opened beyond the allowance.
CONST_ROADMAP_SOURCE_AGENT_LABEL: Final[str] = "source/agent"
CONST_ROADMAP_BORROWED_LABEL: Final[str] = "budget/borrowed"
# The Priority options the model may propose; only verified evidence sets P0-Critical.
CONST_ROADMAP_MODEL_PRIORITIES: Final[tuple[str, ...]] = ("P1-High", "P2-Medium", "P3-Low")
# A bug or security opening at these priorities may borrow beyond the allowance (#1153).
CONST_ROADMAP_BORROWING_PRIORITIES: Final[frozenset[str]] = frozenset({"P0-Critical", "P1-High"})
# The Value and Effort options (`.github/project-template.json`).
CONST_ROADMAP_SIZE_OPTIONS: Final[tuple[str, ...]] = ("High", "Medium", "Low")
# An author with write access, the machine account included, as GitHub's author_association says.
CONST_ROADMAP_TRUSTED_AUTHORS: Final[frozenset[str]] = frozenset(
    {"OWNER", "MEMBER", "COLLABORATOR"}
)
# What each kind of P0 evidence looks like: a GHSA ID, an Actions run id, a commit SHA.
CONST_ROADMAP_EVIDENCE_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "advisory": re.compile(r"GHSA(-[23456789cfghjmpqrvwx]{4}){3}"),
    "failed_run": re.compile(r"[0-9]{1,20}"),
    "regression_commit": re.compile(r"[0-9a-fA-F]{7,40}"),
}
CONST_GH_PROJECT_SINGLE_SELECT_TYPE: Final[str] = "SINGLE_SELECT"
CONST_GH_PROJECT_TEXT_TYPE: Final[str] = "TEXT"
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


CONST_DOC_FILENAMES: Final[frozenset[str]] = frozenset(
    {
        "license",
        "copying",
        "notice",
        "authors",
        "contributors",
        "changelog",
        "readme",
        "agents.md",
        "claude.md",
    }
)

CONST_CONFIG_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".env",
        ".tf",
        ".hcl",
        ".xml",
        ".properties",
        ".plist",
    }
)

CONST_K8S_MANIFEST_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".yaml",
        ".yml",
        ".json",
    }
)

CONST_CONFIG_FILENAMES: Final[frozenset[str]] = frozenset(
    {
        "dockerfile",
        "containerfile",
        ".dockerignore",
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
        ".flake8",
        ".pylintrc",
        "helmfile.yaml",
        "chart.yaml",
        "values.yaml",
        "kustomization.yaml",
        "requirements.txt",
        "constraints.txt",
        "cmakelists.txt",
        "makefile",
        "gnumakefile",
        "justfile",
        "go.mod",
        "go.sum",
        "gemfile",
        "pipfile",
        "procfile",
        "jenkinsfile",
        "vagrantfile",
        "brewfile",
    }
)

CONST_CODE_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".py",
        ".pyi",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".go",
        ".rs",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".kts",
        ".scala",
        ".sh",
        ".bash",
        ".zsh",
        ".sql",
        ".lua",
        ".html",
        ".htm",
        ".j2",
        ".jinja",
        ".jinja2",
        ".tmpl",
        ".tpl",
        ".hbs",
        ".ejs",
        ".vue",
        ".svelte",
        ".cmake",
        ".mk",
    }
)

CONST_AI_SPEND_TABLE_NAME: Final[str] = "ai_spend_records"
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

# ── Kubernetes Doctor Diagnostic Constants ───────────────────────────────────
CONST_K8S_DOCTOR_EVENT_FIELD_SELECTOR: Final[str] = "type=Warning"
CONST_K8S_KIND_PERSISTENT_VOLUME: Final[str] = "PersistentVolume"
CONST_K8S_KIND_NODE: Final[str] = "Node"
CONST_K8S_KIND_POD: Final[str] = "Pod"
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

CONST_K8S_DOCTOR_RULES: Final[tuple[str, ...]] = (
    CONST_K8S_DOCTOR_RULE_NODE_NOT_READY,
    CONST_K8S_DOCTOR_RULE_NODE_CORDONED,
    CONST_K8S_DOCTOR_RULE_VOLUME_RECLAIM_STUCK,
    CONST_K8S_DOCTOR_RULE_POD_STUCK_TERMINATING,
    CONST_K8S_DOCTOR_RULE_POD_CRASHLOOP,
    CONST_K8S_DOCTOR_RULE_POD_IMAGE_PULL,
    CONST_K8S_DOCTOR_RULE_POD_UNSCHEDULABLE,
    CONST_K8S_DOCTOR_RULE_POD_NOT_READY,
    CONST_K8S_DOCTOR_RULE_WARNING_EVENTS,
)

CONST_K8S_PV_PHASE_RELEASED: Final[str] = "Released"
CONST_K8S_PV_PHASE_FAILED: Final[str] = "Failed"
CONST_K8S_PV_PHASE_BOUND: Final[str] = "Bound"
CONST_K8S_ORPHAN_VOLUME_PHASES: Final[frozenset[str]] = frozenset(
    {CONST_K8S_PV_PHASE_RELEASED, CONST_K8S_PV_PHASE_FAILED}
)
CONST_K8S_VOLUME_RECLAIM_HEADING: Final[str] = "Planned Kubernetes Volume Reclaim API Requests:"
CONST_K8S_PV_API_PATH_TEMPLATE: Final[str] = "/api/v1/persistentvolumes/{name}"


# ── Dashboard TUI Domains ────────────────────────────────────────────────────
# Each domain is one tab of the workstation dashboard, refreshed by its own worker.
CONST_DASHBOARD_DOMAIN_K8S: Final[str] = "k8s"
CONST_DASHBOARD_DOMAIN_DOCKER: Final[str] = "docker"
CONST_DASHBOARD_DOMAIN_TELEMETRY: Final[str] = "telemetry"
CONST_DASHBOARD_DOMAIN_AI: Final[str] = "ai"
CONST_DASHBOARD_DOMAIN_VALKEY: Final[str] = "valkey"
CONST_DASHBOARD_DOMAINS: Final[tuple[str, ...]] = (
    CONST_DASHBOARD_DOMAIN_K8S,
    CONST_DASHBOARD_DOMAIN_DOCKER,
    CONST_DASHBOARD_DOMAIN_TELEMETRY,
    CONST_DASHBOARD_DOMAIN_AI,
    CONST_DASHBOARD_DOMAIN_VALKEY,
)
# Human-readable labels used for tab titles and status banners.
CONST_DASHBOARD_DOMAIN_LABELS: Final[dict[str, str]] = {
    CONST_DASHBOARD_DOMAIN_K8S: "Kubernetes",
    CONST_DASHBOARD_DOMAIN_DOCKER: "Docker",
    CONST_DASHBOARD_DOMAIN_TELEMETRY: "Telemetry",
    CONST_DASHBOARD_DOMAIN_AI: "AI Review",
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
    CONST_LOGS_TAB_ID: "#log-pane",
}

# ── Dashboard Finding Detail ─────────────────────────────────────────────────
# The AI Review pane beside the findings table: these short fields as `label: value`
# lines, in this order, then each long field as a titled section. Every other finding
# field is left out on purpose: `recommendation` is the persona's merge verdict, not
# advice about the finding, `thinking` is the model's scratchpad, and the rest are
# verification bookkeeping.
CONST_FINDING_DETAIL_HEADER_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("title", "Title"),
    ("severity", "Severity"),
    ("status", "Status"),
    ("persona_title", "Persona"),
    ("category", "Category"),
    ("confidence_score", "Confidence"),
    ("location", "Location"),
    ("citation_line", "Citation line"),
    ("verified_by", "Verified by"),
)
CONST_FINDING_DETAIL_SECTION_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("description", "Description"),
    ("observed_value", "Observed value"),
    ("expected_value", "Expected value"),
    ("fix", "Fix"),
    ("references", "References"),
    ("invalidation_reason", "Invalidation reason"),
    ("mitigating_mechanism", "Mitigating mechanism"),
)
# A field read in place of a blank one: an untitled persona is named by its key, as
# `review findings --details` names it.
CONST_FINDING_DETAIL_FIELD_FALLBACKS: Final[dict[str, str]] = {"persona_title": "persona"}
# Finding text is model output, so every Unicode control character (general category Cc)
# is written as a visible escape before it reaches the terminal, except line breaks and
# tabs, which lay the text out.
CONST_UNICODE_CONTROL_CATEGORY: Final[str] = "Cc"
CONST_FINDING_DETAIL_KEPT_CONTROLS: Final[frozenset[str]] = frozenset({"\n", "\t"})

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

# ── Issue Closure From Merged Pull Requests ──────────────────────────────────
# GitHub's closing keywords. A pull request body using any of these links the issue, but
# GitHub only acts on the link when the pull request merges into the DEFAULT branch, so a
# pull request targeting a release branch leaves its issue open indefinitely.
# https://docs.github.com/en/issues/tracking-your-work-with-issues/linking-a-pull-request-to-an-issue
CONST_ISSUE_CLOSING_KEYWORDS: Final[frozenset[str]] = frozenset(
    {
        "close",
        "closes",
        "closed",
        "fix",
        "fixes",
        "fixed",
        "resolve",
        "resolves",
        "resolved",
    }
)
# The phrase a pull request body names an item with when it delivers part of it: an item planned
# as several pull requests says `Part of #N` in each but the last, which closes it. GitHub gives
# the phrase no meaning, so it closes nothing; it is matched case-insensitively, word by word.
CONST_ISSUE_PART_PHRASE: Final[str] = "part of"
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
# Readiness requires a pull request to close exactly one issue and to change that issue's task
# file. The release pull request, `release/vX.Y.Z` into `main`, delivers a release rather than
# one item, and is exempt. So is a release-process pull request from the same repository into
# `release/vX.Y.Z`, but only by the files it changes (#1344): the cut, `chore/cut-vX.Y.Z`, only
# modifies the cut's files and removes changelog fragments, and the merge of `main`,
# `chore/open-vX.Y.Z`, changes only the cut's files and what `main` changed since its merge
# base with the release branch. Either head may end in `-<slug>`.
CONST_RELEASE_BRANCH_PREFIX: Final[str] = "release/"
CONST_RELEASE_BRANCH_RE: Final[re.Pattern[str]] = re.compile(
    rf"{CONST_RELEASE_BRANCH_PREFIX}v(?P<version>\d+\.\d+\.\d+)"
)
CONST_RELEASE_PROCESS_CUT_KIND: Final[str] = "cut"
CONST_RELEASE_PROCESS_OPEN_KIND: Final[str] = "open"
CONST_RELEASE_PROCESS_BRANCH_RE: Final[re.Pattern[str]] = re.compile(
    rf"chore/(?P<kind>{CONST_RELEASE_PROCESS_CUT_KIND}|{CONST_RELEASE_PROCESS_OPEN_KIND})"
    r"-v(?P<version>\d+\.\d+\.\d+)(?:-[^/\s]+)?"
)
# The files the cut commit modifies, besides the `changelog.d/` fragments it removes: what
# `devops roadmap close` lists for the cut, and all a cut pull request may modify.
CONST_RELEASE_CUT_FILES: Final[tuple[str, ...]] = (
    CONST_PYPROJECT_FILENAME,
    str(CONST_INIT_PY_PATH),
    CONST_UV_LOCK_FILENAME,
    CONST_CHANGELOG_FILENAME,
    CONST_ROADMAP_DOCUMENT_PATH,
)
# Files every pull request into a release branch used to edit, so each merge made every other
# open pull request conflict. The cut commit writes both: `CHANGELOG.md`'s section for the
# version from `changelog.d/`, and `docs/ROADMAP.md` with `devops roadmap render`. Once the cut
# has written that section, a critical fix edits it in its own pull request (#1450).
CONST_RELEASE_SHARED_FILES: Final[tuple[str, ...]] = (
    CONST_CHANGELOG_FILENAME,
    CONST_ROADMAP_DOCUMENT_PATH,
)
CONST_AGENT_TASKS_DIR: Final[str] = "docs/agent/tasks"
# `task-<issue>-<slug>.md` directly under the tasks directory. The number is read as an
# integer, so `task-089-x.md` belongs to #89.
CONST_AGENT_TASK_FILE_RE: Final[re.Pattern[str]] = re.compile(
    rf"{re.escape(CONST_AGENT_TASKS_DIR)}/task-(?P<issue>\d+)-[^/]*\.md"
)
# The `pulls/{n}/files` statuses under which the file is in the pull request's head and was
# written by it. GitHub's full set is added, removed, modified, renamed, copied, changed (mode
# only) and unchanged. `modified` is an edit in place under the same name.
CONST_PR_FILE_MODIFIED_STATUS: Final[str] = "modified"
CONST_PR_FILE_REMOVED_STATUS: Final[str] = "removed"
CONST_PR_FILE_WRITTEN_STATUSES: Final[frozenset[str]] = frozenset(
    {"added", CONST_PR_FILE_MODIFIED_STATUS, "renamed"}
)
# The statuses under which a pull request adds, modifies, renames or removes the file.
CONST_PR_FILE_CHANGED_STATUSES: Final[frozenset[str]] = CONST_PR_FILE_WRITTEN_STATUSES | {
    CONST_PR_FILE_REMOVED_STATUS
}
# `GET repos/{repo}/compare/{base}...{head}` lists the changed files on its first page only, at
# most 300 for the whole comparison whatever the page size, so a list that long may be cut
# short. One commit per page keeps the commits it also returns small.
CONST_GH_COMPARE_FILES_CAP: Final[int] = 300
CONST_GH_COMPARE_COMMITS_PER_PAGE: Final[int] = 1
# The declared surfaces where defect pull requests must record hardening guardrails or lessons (#697, #1151).
# docs/ROADMAP.md is explicitly excluded because it is a generated view.
CONST_HARDENING_SURFACES: Final[tuple[str, ...]] = (
    "AGENTS.md",
    "src/devops_cli/ai/tasks/*.md",
    "src/devops_cli/ai/knowledge_base/",
    ".devops/review.toml",
    "src/devops_cli/review/rules/",
)
# Taxonomy labels that classify a pull request as addressing a defect (#697).
CONST_DEFECT_LABELS: Final[frozenset[str]] = frozenset({"type/bug", "type/security"})
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
# because it closes an issue whose Status is set to Done, skipping closure's summary (#743); and
# auto-archive stays off because archived items drop out of the item lists the roadmap jobs
# read. A pull request is linked only when it targets the default branch, so for one into
# `release/*` reconcile's own title and body parser is the only path to In Review.
CONST_PROJECT_WORKFLOW_EXPECTATIONS: Final[dict[str, str]] = {
    "Item added to project": "Set Status to New",
    "Item closed": "Set Status to Done",
    "Item reopened": "Set Status to New",
    "Pull request linked to issue": "Set Status to In Review",
    "Pull request merged": "Set Status to Done",
}
# The heading GitHub writes above its generated release summary. A release here is cut
# from one `feat(release)` pull request, so the summary lists that pull request alone and
# carries no information the changelog does not.
CONST_GENERATED_NOTES_HEADING: Final[str] = "What's Changed"
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
# The closed set of CLI leaf commands whose output is a serializable value (e.g. query,
# diagnostic, inspect, or inventory report) rather than a lifecycle action, mutation, daemon,
# or interactive session (#411). Every value command exposes `--format` and routes machine-readable
# serialization through `emit_serialized`.
CONST_CLI_VALUE_COMMANDS: Final[frozenset[str]] = frozenset(
    {
        "ai ast graph",
        "ai ast parse",
        "ai audit-library-usage",
        "ai benchmark",
        "ai cache status",
        "ai chaos-model",
        "ai constellation",
        "ai cost list-pricing",
        "ai cost payback",
        "ai cost payoff",
        "ai cost report",
        "ai cost roi",
        "ai diagram",
        "ai failover",
        "ai gateway failover",
        "ai gateway load",
        "ai gateway probe-backend",
        "ai gateway routes",
        "ai gateway status",
        "ai gateway tune",
        "ai harness offload",
        "ai harness run",
        "ai harness status",
        "ai ingest docs",
        "ai ingest index-libraries",
        "ai ingest library",
        "ai ingest query-library",
        "ai pack-context",
        "ai prewarm",
        "ai prompt-eval",
        "ai quiesce",
        "ai rag drift",
        "ai read",
        "ai repomap",
        "ai research analogies",
        "ai research annotate",
        "ai research forage",
        "ai research model",
        "ai research socratic",
        "ai resume",
        "ai review corpus score",
        "ai review score",
        "ai review templates check",
        "ai review templates list",
        "ai review templates sweep",
        "ai runs baseline list",
        "ai runs baseline show",
        "ai runs check",
        "ai runs compare",
        "ai runs list",
        "ai runs show",
        "ai spec",
        "ai spend list-pricing",
        "ai spend payback",
        "ai spend payoff",
        "ai spend report",
        "ai spend roi",
        "ai test-gen",
        "ai token-count",
        "argo cd fleet sync",
        "argo cd gitops drift",
        "argo cd gitops sync",
        "argo cd gitops watch",
        "argo fleet sync",
        "argo gitops drift",
        "argo gitops sync",
        "argo gitops watch",
        "argo rollouts analyze",
        "argo sync",
        "cloudflare access policies",
        "cloudflare access status",
        "cloudflare access sync",
        "cloudflare dns delete",
        "cloudflare dns list",
        "cloudflare dns sync",
        "cloudflare service-status",
        "cloudflare status",
        "cloudflare tunnel routes",
        "cloudflare tunnel sync",
        "config audit-keys",
        "config env",
        "config env-vars",
        "config output",
        "docker analyze-layers",
        "docker cache",
        "docs generate",
        "gh branch-protection audit",
        "gh metrics",
        "gh pr hardening-report",
        "gh pr monitor",
        "gh pr threads list",
        "gh pr wait",
        "gh project workflows list",
        "gh rate-limit",
        "gh rate_limit",
        "gh runs list",
        "gh status",
        "grafana dashboards lint",
        "k8s chaos",
        "k8s doctor",
        "k8s gpu-matrix",
        "k8s logs",
        "k8s security-stream",
        "k8s service-url",
        "k8s validate",
        "k8s validate-policy",
        "pr hardening-report",
        "pr monitor",
        "pr threads list",
        "pr wait",
        "prometheus analyze",
        "repos worktrees prune",
        "repos worktrees status",
        "review corpus score",
        "review score",
        "review templates check",
        "review templates list",
        "review templates sweep",
        "sandbox logs",
        "sandbox metrics",
        "sandbox probe",
        "sandbox status",
        "sandbox traces",
        "scan aibom",
        "scan complexity",
        "scan iac",
        "scan report",
        "scan sarif",
        "scan sast",
        "scan sbom",
        "scan secrets",
        "scan trivy",
        "status",
        "telemetry logfire",
        "telemetry profile",
        "test profile-memory",
        "tf cost breakdown",
        "tf cost diff",
        "tf drift",
        "tf graph",
        "tf lint",
        "tf notify-plan",
        "tf output",
        "vault audit",
    }
)
# The roots of the exception hierarchy. Naming one of these as the expected type of a
# `pytest.raises` block asks nothing of the code under test: any failure at all satisfies
# it, so the assertion keeps reporting green through the very regression it was written to
# catch. A test that expects a failure has to say which one.
CONST_BLIND_EXCEPTION_TYPES: Final[frozenset[str]] = frozenset({"Exception", "BaseException"})
# The Ruff rules that keep the blind-assertion class from coming back: B011/B015/B018
# for assertions that cannot fail, B017 for `pytest.raises(Exception)`, PT011/PT015/PT017
# for broad exception raises or assertions, and RUF043 for a `match=` pattern whose
# metacharacters are neither escaped nor declared raw. All of these defects read as
# correct tests, so they belong in the lint selection rather than in a reviewer's memory.
CONST_TEST_ASSERTION_LINT_RULES: Final[frozenset[str]] = frozenset(
    {"B011", "B015", "B017", "B018", "PT011", "PT015", "PT017", "RUF043"}
)
# The Ruff rules that govern suppression integrity: PGH003 bans blanket type ignores
# without a specific error code, and RUF100 removes unused noqa directives.
CONST_SUPPRESSION_LINT_RULES: Final[frozenset[str]] = frozenset({"PGH003", "RUF100"})
# The Ruff rules that hold the complexity cap of 10 (#586): C901 is the cap (standard McCabe),
# RUF100 reports a C901 marker left on a function back under the cap, and PGH004 bans the
# blanket noqa that would silence C901 without naming it.
CONST_COMPLEXITY_LINT_RULES: Final[frozenset[str]] = frozenset({"C901", "PGH004", "RUF100"})
# The keys `[tool.ruff]`, `[tool.ruff.lint]` and `[tool.ruff.lint.mccabe]` may hold (#586). Any
# other key can take a file out of the cap: Ruff 0.16 still honours the deprecated top-level
# `per-file-ignores` and `extend-ignore`, `include` and `extend` change which files or which
# settings apply, and `lint.exclude` drops files from linting. A key Ruff adds later stays out
# until a reviewed change admits it.
CONST_RUFF_TOP_LEVEL_KEYS: Final[frozenset[str]] = frozenset(
    {"target-version", "line-length", "exclude", "lint"}
)
CONST_RUFF_PER_FILE_IGNORE_KEYS: Final[tuple[str, ...]] = (
    "per-file-ignores",
    "extend-per-file-ignores",
)
CONST_RUFF_LINT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "select",
        "extend-select",
        "ignore",
        "extend-ignore",
        "allowed-confusables",
        "mccabe",
        "flake8-tidy-imports",
        *CONST_RUFF_PER_FILE_IGNORE_KEYS,
    }
)
CONST_RUFF_MCCABE_KEYS: Final[frozenset[str]] = frozenset({"max-complexity"})
# `[tool.ruff] exclude` replaces Ruff's default exclusions, so any other value can drop a source.
CONST_RUFF_EXCLUDE: Final[tuple[str, ...]] = ("repos",)
# Where the cap holds, the suffixes Ruff lints there by default, and the config file names Ruff
# reads in any directory; one under a covered root outranks pyproject.toml for the files below it.
CONST_COMPLEXITY_CAP_ROOTS: Final[tuple[str, ...]] = ("src", "tests")
CONST_RUFF_SOURCE_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyi", ".ipynb"})
CONST_RUFF_CONFIG_FILE_NAMES: Final[frozenset[str]] = frozenset(
    {"pyproject.toml", "ruff.toml", ".ruff.toml"}
)
# The ignore files Ruff's file walk honours by default (`respect-gitignore`). One under a covered
# root, or a `.ignore` beside pyproject.toml, drops the files it lists from every rule.
CONST_RUFF_IGNORE_FILE_NAMES: Final[frozenset[str]] = frozenset(
    {CONST_GITIGNORE_FILENAME, ".ignore"}
)
# The suppression comments below are matched on the raw text, not on comment tokens, so a string
# literal that looks like one overcounts, which fails safe. Ruff reads any whitespace but a
# newline as a separator inside them, form feed and no-break space included, hence `[^\S\n]`.
# A file-level exemption, Ruff's or the flake8 spelling Ruff honours, with or without codes.
CONST_RUFF_FILE_EXEMPTION: Final[re.Pattern[str]] = re.compile(
    r"#[^\S\n]*(?:ruff|flake8)[^\S\n]*:[^\S\n]*noqa\b", re.IGNORECASE
)
# One line-level noqa comment naming C901 among any codes: the marker the ceiling counts.
CONST_C901_SUPPRESSION: Final[re.Pattern[str]] = re.compile(
    r"#[^\S\n]*noqa[^\S\n]*:(?:[A-Z0-9,]|[^\S\n])*?\bC901\b", re.IGNORECASE
)
# Ruff's own bracketed suppression comment naming C901, whatever its verb: a line `ignore`, a
# `disable` that holds until its `enable` or the end of the file, or a `file-ignore`. One such
# comment can hide any number of functions without a marker to count, so each is an escape.
CONST_RUFF_C901_SUPPRESSION_COMMENT: Final[re.Pattern[str]] = re.compile(
    r"#[^\S\n]*ruff[^\S\n]*:[^\S\n]*[\w-]+[^\S\n]*\[[^\]\n]*\bC901\b", re.IGNORECASE
)
# Suppression comment and configuration kinds tracked against ceilings (#849).
CONST_SUPPRESSION_KIND_TYPE_IGNORE: Final[str] = "type: ignore"
CONST_SUPPRESSION_KIND_NOQA_PREFIX: Final[str] = "noqa"
CONST_SUPPRESSION_KIND_NOSEC: Final[str] = "nosec"
CONST_SUPPRESSION_KIND_PRAGMA_NO_COVER: Final[str] = "pragma: no cover"
CONST_SUPPRESSION_KIND_PRAGMA_NO_MUTATE: Final[str] = "pragma: no mutate"
CONST_SUPPRESSION_KIND_FILE_DIRECTIVE: Final[str] = "file-level directive"
CONST_SUPPRESSION_KIND_AST_GREP_IGNORE: Final[str] = "ast-grep-ignore"
CONST_SUPPRESSION_KIND_PER_FILE_IGNORES: Final[str] = "per-file-ignores"
CONST_SUPPRESSION_KIND_MYPY_OVERRIDES: Final[str] = "[[tool.mypy.overrides]]"
CONST_SUPPRESSION_KIND_COVERAGE_OMIT: Final[str] = "coverage omit"
CONST_COMMENT_SUPPRESSION_KINDS: Final[tuple[str, ...]] = (
    CONST_SUPPRESSION_KIND_TYPE_IGNORE,
    CONST_SUPPRESSION_KIND_NOQA_PREFIX,
    CONST_SUPPRESSION_KIND_NOSEC,
    CONST_SUPPRESSION_KIND_PRAGMA_NO_COVER,
    CONST_SUPPRESSION_KIND_PRAGMA_NO_MUTATE,
    CONST_SUPPRESSION_KIND_FILE_DIRECTIVE,
    CONST_SUPPRESSION_KIND_AST_GREP_IGNORE,
)
CONST_PYPROJECT_SUPPRESSION_KINDS: Final[tuple[str, ...]] = (
    CONST_SUPPRESSION_KIND_PER_FILE_IGNORES,
    CONST_SUPPRESSION_KIND_MYPY_OVERRIDES,
    CONST_SUPPRESSION_KIND_COVERAGE_OMIT,
)
CONST_SUPPRESSION_KINDS: Final[tuple[str, ...]] = (
    *CONST_COMMENT_SUPPRESSION_KINDS,
    *CONST_PYPROJECT_SUPPRESSION_KINDS,
)
# Fast pre-filter over source text before tokenizing, and comment-token patterns (#849).
CONST_SUPPRESSION_COMMENT_PREFILTER_RE: Final[re.Pattern[str]] = re.compile(
    r"#[^\n]*(?:type[^\S\n]*:[^\S\n]*ignore\b|noqa\b|nosec\b"
    r"|pragma[^\S\n]*:[^\S\n]*no[^\S\n]+(?:cover|mutate)\b"
    r"|(?:ruff|flake8|mypy|pyright|pylint|bandit)[^\S\n]*:|ast-grep-ignore\b)",
    re.IGNORECASE,
)
CONST_TYPE_IGNORE_COMMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[^\S\n])#[^\S\n]*type[^\S\n]*:[^\S\n]*ignore\b", re.IGNORECASE
)
CONST_NOQA_COMMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[^\S\n])#[^\S\n]*noqa(?:[^\S\n]*:[^\S\n]*"
    r"(?P<codes>[A-Z0-9]+(?:(?:[^\S\n]*,[^\S\n]*|[^\S\n]+)[A-Z0-9]+)*)|(?=$|[^\S\n]+#))",
    re.IGNORECASE,
)
CONST_NOQA_RULE_CODE_RE: Final[re.Pattern[str]] = re.compile(r"[A-Z0-9]+")
CONST_NOSEC_COMMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[^\S\n])#[^\S\n]*nosec\b", re.IGNORECASE
)
CONST_PRAGMA_NO_COVER_COMMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[^\S\n])#[^\S\n]*pragma[^\S\n]*:[^\S\n]*no[^\S\n]+cover\b", re.IGNORECASE
)
CONST_PRAGMA_NO_MUTATE_COMMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[^\S\n])#[^\S\n]*pragma[^\S\n]*:[^\S\n]*no[^\S\n]+mutate\b", re.IGNORECASE
)
CONST_FILE_DIRECTIVE_COMMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[^\S\n])#[^\S\n]*(?:(?:ruff|flake8)[^\S\n]*:[^\S\n]*noqa\b"
    r"|ruff[^\S\n]*:[^\S\n]*(?:file-ignore|disable|ignore)\b"
    r"|(?:mypy|pyright)[^\S\n]*:|(?:pylint|bandit)[^\S\n]*:[^\S\n]*skip-file\b)",
    re.IGNORECASE,
)
CONST_AST_GREP_IGNORE_COMMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[^\S\n])#[^\S\n]*ast-grep-ignore(?:[^\S\n]*:[^\S\n]*(?P<ids>[^\n#]+))?\b",
    re.IGNORECASE,
)
CONST_AST_GREP_NET_RULE_ID_RE: Final[re.Pattern[str]] = re.compile(
    r"\bnet-[a-z0-9-]+\b", re.IGNORECASE
)
CONST_NET_CONSTRUCT_RULES: Final[tuple[str, ...]] = (
    "net-address-list",
    "net-bracket-affix",
    "net-cidr-build",
    "net-ip-literal",
    "net-port-table",
    "net-scheme-affix",
    "net-scheme-in",
    "net-url-build",
)
CONST_AST_GREP_SCAN_ARGS: Final[tuple[str, ...]] = (
    "scan",
    "--error=unused-suppression",
    "--error=no-suppress-all",
    "src",
)
CONST_BANNED_HAND_ROLLED_APIS: Final[tuple[str, ...]] = (
    "socket.inet_aton",
    "socket.inet_ntoa",
    "socket.inet_pton",
    "socket.inet_ntop",
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
# generated references, where no persona finding held up in the release/v0.2.25 reviews. Lockfiles
# (`CONST_REVIEW_GENERATED_FILES`) stay off by name, for their size. Both still reach the secret
# scan. Patterns follow `PurePath.full_match`.
CONST_REVIEW_ROUTED_PATH_PATTERNS: Final[tuple[str, ...]] = (
    CONST_CHANGELOG_FILENAME,
    f"{CONST_CHANGELOG_FRAGMENTS_DIR}/**",
    CONST_ROADMAP_DOCUMENT_PATH,
    f"{CONST_AGENT_TASKS_DIR}/**",
    "docs/adr/**",
    "docs/commands/*.md",
    "docs/CLI_REFERENCE.md",
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

# Persona review reply outcomes: a persona returns valid findings, a clean empty findings list,
# or an unparsed reply (malformed response or extraction failure).
CONST_PERSONA_REPLY_FINDINGS: Final[str] = "findings"
CONST_PERSONA_REPLY_EMPTY: Final[str] = "empty"
CONST_PERSONA_REPLY_UNPARSED: Final[str] = "unparsed"

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
    ("HOME", "/tmp"),  # nosec B108
    ("PATH", "/usr/local/bin:/usr/bin:/bin"),
    ("LANG", "C.UTF-8"),
    ("LC_ALL", "C.UTF-8"),
    ("TMPDIR", "/tmp"),  # nosec B108
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

# Maximum window duration permitted for Prometheus pool load queries (30 days in seconds)
# to prevent resource exhaustion and unbounded range vectors (CWE-400).
CONST_MAX_PROMETHEUS_WINDOW_SECONDS: Final[int] = 30 * 86400

# Receiver objects and prefixes permitted for code expression exemptions in secret masking.
CONST_CODE_EXEMPTION_RECEIVERS: Final[frozenset[str]] = frozenset(
    {
        "req",
        "request",
        "res",
        "response",
        "params",
        "props",
        "self",
        "this",
        "process",
        "config",
        "settings",
        "context",
        "ctx",
        "session",
    }
)

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

# ── SQLite Database Names ────────────────────────────────────────────────────
# The names `sqlite3.connect` opens as a database private to that one connection (#958):
# `:memory:` is held in memory and the empty name is a temporary file, and each is gone when the
# connection closes. Without `uri=True` no other name does that, so the set is complete. A store
# that opens a connection per call loses every write to either.
CONST_SQLITE_PER_CONNECTION_DATABASES: Final[frozenset[str]] = frozenset({":memory:", ""})

# ── Swallowed Failures Ratchet Invariant ───────────────────────────────────────
# Ruff rule codes and process return object attributes inspected by the ratchet (#1347).
CONST_SWALLOWED_FAILURES_RUFF_RULES: Final[tuple[str, ...]] = ("BLE001", "S110", "S112")
CONST_SWALLOWED_FAILURES_CHECK_ATTRS: Final[tuple[str, ...]] = ("returncode", "stdout", "stderr")

# ── Review Evidence (Ruff & Mypy) ─────────────────────────────────────────────
CONST_DEFAULT_REVIEW_ADVISORY_RULES: Final[tuple[str, ...]] = ("BLE001",)
CONST_COMPLEXITY_SOURCE: Final[str] = "mccabe (ruff C901)"

# ── AI Research Information Foraging Constants ────────────────────────────────
CONST_FORAGE_EDGE_TYPES: Final[tuple[str, ...]] = (
    "import",
    "markdown_link",
    "git_co_change",
)

# ── AI Research Marginalia & Epistemic Scratchpad ─────────────────────────────
CONST_MARGINALIA_TYPES: Final[tuple[str, ...]] = (
    "ASSUMPTION",
    "HYPOTHESIS",
    "CONTRADICTION",
    "QUESTION",
    "TODO",
)

# ── AI Research Socratic Inquiry ──────────────────────────────────────────────
CONST_SOCRATIC_GAP_TYPES: Final[tuple[str, ...]] = (
    "GAP",
    "AMBIGUITY",
    "UNDERSPECIFIED_CONTRACT",
)
CONST_SOCRATIC_LOOKUP_TYPES: Final[tuple[str, ...]] = (
    "file",
    "symbol",
    "search",
)

# ── AI Research Mental Model & Causal Graph ───────────────────────────────────
CONST_CAUSAL_NODE_TYPES: Final[tuple[str, ...]] = (
    "cause",
    "effect",
    "mediator",
    "outcome",
)
CONST_CAUSAL_RELATIONSHIPS: Final[tuple[str, ...]] = (
    "causes",
    "inhibits",
    "triggers",
    "mediates",
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
CONST_ANALYSIS_GROUP_KINDS: Final[frozenset[str]] = frozenset({"region", "kubernetes", "advisory"})
CONST_ANALYSIS_RELATIONS: Final[frozenset[str]] = frozenset(
    {"caller", "callee", "same-symbol", "same-rule", "same-root-cause"}
)
CONST_ANALYSIS_CORRELATION_KEY_KINDS: Final[frozenset[str]] = frozenset(
    {"cwe", "rule_family", "symbol_component", "purl", "manifest_source"}
)
CONST_ANALYSIS_K8S_TOOLS: Final[frozenset[str]] = frozenset({"kubelinter", "kube-linter", "pluto"})
CONST_ANALYSIS_ADVISORY_TOOLS: Final[frozenset[str]] = frozenset({"osv", "osv-scanner", "trivy"})
CONST_ANALYSIS_DROP_REASON_BUDGET: Final[str] = "budget"
CONST_ANALYSIS_DROP_REASON_UNAVAILABLE: Final[str] = "unavailable"
CONST_ANALYSIS_G10_REJECTION_REASONS: Final[tuple[str, ...]] = (
    "unknown-finding-id",
    "invalid-related-target",
    "unmatched-code-quote",
    "unmatched-doc-quote",
    "unverified-version-or-package",
    "invalid-python-code-block",
    "unshared-root-cause-key",
    "plan-incomplete-coverage",
    "plan-order-violation",
)
CONST_ANALYSIS_REJECTION_REPLY_TRUNCATED: Final[str] = "reply-truncated"
CONST_ANALYSIS_REJECTION_SCHEMA_VALIDATION_FAILED: Final[str] = "schema-validation-failed"
CONST_ANALYSIS_REJECTION_MODEL_CALL_ERROR: Final[str] = "model-call-error"
CONST_ANALYSIS_REJECTION_UNSHARED_ROOT_CAUSE_KEY: Final[str] = "unshared-root-cause-key"
CONST_ANALYSIS_REJECTION_PLAN_INCOMPLETE_COVERAGE: Final[str] = "plan-incomplete-coverage"
CONST_ANALYSIS_REJECTION_PLAN_ORDER_VIOLATION: Final[str] = "plan-order-violation"

# ── OSV-Scanner Constants (#1146) ───────────────────────────────────────────
CONST_BIN_OSV_SCANNER: Final[str] = "osv-scanner"
CONST_OSV_OFFLINE_DB_TTL_SECONDS: Final[float] = 86400.0  # 24 hours TTL
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
CONST_MANIFEST_NAMES: Final[tuple[str, ...]] = (
    "pyproject.toml",
    "requirements.in",
    "setup.py",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "composer.json",
    "Gemfile",
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

# ── CLI Startup & Heavy Modules (#1002, #1687) ───────────────────────────────
CONST_CLI_HEAVY_MODULES: Final[tuple[str, ...]] = (
    "pydantic_ai",
    "kubernetes",
    "docker",
    "fastmcp",
    "qdrant_client",
    "opentelemetry",
)

# ── Knowledge Base Version Grounding & Reference Tracking (#1149) ────────────
CONST_KB_METADATA_TARGET_SUBDIRS: Final[tuple[str, ...]] = (
    "devops_cli/libraries",
    "it_domains/tools",
    "it_domains/topics",
)
CONST_KB_REFERENCE_PREFIX: Final[str] = "kb:"
CONST_KB_DATE_FORMAT: Final[str] = "%Y-%m-%d"
CONST_KB_SHA_DIGEST_LENGTH: Final[int] = 16
