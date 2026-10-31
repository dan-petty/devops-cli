"""Unit tests for FastMCP server integration (devops_cli.mcp and devops_cli.commands.mcp)."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import PropertyMock, patch

import pytest
from fastmcp.exceptions import ToolError
from typer.testing import CliRunner

from devops_cli.ai.mcp.server import (
    _run_mcp_cmd,
    _validate_mcp_arg,
    list_mcp_tools,
    mcp,
    review_branch,
    review_findings,
    review_path,
    review_pr,
    review_stats,
    run_mcp_server,
)
from devops_cli.commands.mcp import app
from devops_cli.config.constants import CONST_MCP_EXPOSURE_TABLE
from devops_cli.exceptions import ValidationError
from tests.support.fakes.scanners import ScannerFake
from tests.support.registry_cache import CACHED_RULESET_FILE_NAME

if TYPE_CHECKING:
    pass


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ── FastMCP server ───────────────────────────────────────────────────────────


class TestMcpServer:
    """Tests for the FastMCP server instance and tool registrations."""

    def test_server_name(self) -> None:
        """FastMCP server must be named 'devops-cli'."""
        assert mcp.name == "devops-cli"

    def test_tools_registered(self) -> None:
        """All expected MCP tools must be registered on the server."""
        from devops_cli.config.constants import CONST_MCP_EXPOSURE_TABLE

        tools = asyncio.run(mcp._list_tools())
        tool_names = {t.name for t in tools}

        expected_exposure = {"_".join(e[0]).replace("-", "_") for e in CONST_MCP_EXPOSURE_TABLE}
        expected_hand_written = {
            "hydrate_tool_domain",
            "security_intel_package",
            "security_intel_network",
            "scan_uv_audit",
            "k8s_tempo_info",
        }
        assert tool_names == (expected_exposure | expected_hand_written)

    def test_list_mcp_tools_returns_list_of_dicts(self) -> None:
        """list_mcp_tools() must return a list of dicts with name and description keys."""
        tools = list_mcp_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0
        for t in tools:
            assert "name" in t
            assert "description" in t

    def test_all_tools_have_descriptions(self) -> None:
        """All registered tools must have non-empty docstrings used as descriptions."""
        tools = asyncio.run(mcp._list_tools())
        missing_desc = [t.name for t in tools if not t.description]
        assert missing_desc == [], f"Tools missing descriptions: {missing_desc}"


# ── run_mcp_server ───────────────────────────────────────────────────────────


class TestRunMcpServer:
    """Tests for run_mcp_server launch helper."""

    def test_run_stdio(self) -> None:
        """run_mcp_server stdio must call mcp.run(transport='stdio', show_banner=False)."""
        with patch("devops_cli.ai.mcp.server.mcp") as mock_mcp:
            run_mcp_server(transport="stdio")
            mock_mcp.run.assert_called_once_with(transport="stdio", show_banner=False)

    def test_run_sse(self) -> None:
        """run_mcp_server sse must call mcp.run with host and port when allowed."""
        bind_all = "0.0.0.0"  # nosec B104  # the remote bind allow_remote permits, under test
        with patch("devops_cli.ai.mcp.server.mcp") as mock_mcp:
            run_mcp_server(transport="sse", host=bind_all, port=9000, allow_remote=True)
            mock_mcp.run.assert_called_once_with(transport="sse", host=bind_all, port=9000)

    def test_run_sse_rejects_non_loopback_by_default(self) -> None:
        """run_mcp_server sse must reject non-loopback host unless allow_remote=True."""
        bind_all = "0.0.0.0"  # nosec B104  # the remote bind refused by default, under test
        with pytest.raises(ValueError, match="Refusing to bind SSE transport"):
            run_mcp_server(transport="sse", host=bind_all, port=9000)

    @pytest.mark.parametrize(
        "loopback_host",
        ["127.0.0.2", "::ffff:127.0.0.1", "LOCALHOST."],
    )
    def test_run_sse_permits_loopback_variants(self, loopback_host: str) -> None:
        """run_mcp_server sse permits loopback addresses without allow_remote."""
        with patch("devops_cli.ai.mcp.server.mcp") as mock_mcp:
            run_mcp_server(transport="sse", host=loopback_host, port=9000)
            mock_mcp.run.assert_called_once_with(transport="sse", host=loopback_host, port=9000)


# ── commands/mcp.py CLI ──────────────────────────────────────────────────────


class TestMcpCli:
    """Tests for `devops mcp` CLI subcommands."""

    def test_tools_command_outputs_table(self, runner: CliRunner) -> None:
        """devops mcp tools must print a table with tool names."""
        result = runner.invoke(app, ["tools"])
        assert result.exit_code == 0
        assert "review_path" in result.output

    def test_serve_invalid_transport(self, runner: CliRunner) -> None:
        """devops mcp serve with invalid transport must exit with code 1."""
        result = runner.invoke(app, ["serve", "--transport", "grpc"])
        assert result.exit_code == 1
        assert "Invalid transport" in result.output

    def test_serve_stdio_calls_run_mcp_server(self, runner: CliRunner) -> None:
        """devops mcp serve --transport stdio must delegate to run_mcp_server."""
        with patch("devops_cli.commands.mcp.run_mcp_server") as mock_run:
            result = runner.invoke(app, ["serve", "--transport", "stdio"])
            assert result.exit_code == 0
            mock_run.assert_called_once_with(
                transport="stdio", host="127.0.0.1", port=8000, allow_remote=False
            )

    def test_serve_sse_calls_run_mcp_server(self, runner: CliRunner) -> None:
        """devops mcp serve --transport sse must pass host and port to run_mcp_server."""
        with patch("devops_cli.commands.mcp.run_mcp_server") as mock_run:
            result = runner.invoke(
                app, ["serve", "--transport", "sse", "--host", "::1", "--port", "9090"]
            )
            assert result.exit_code == 0
            mock_run.assert_called_once_with(
                transport="sse", host="::1", port=9090, allow_remote=False
            )

    def test_export_schemas_command(self, runner: CliRunner, tmp_path: Path) -> None:
        """devops mcp export-schemas must write JSON files with annotations and instructions."""
        import json

        out_dir = tmp_path / "mcp_schemas"
        result = runner.invoke(app, ["export-schemas", "--output-dir", str(out_dir)])
        trivy_schema = json.loads((out_dir / "scan_trivy.json").read_text(encoding="utf-8"))
        vault_schema = json.loads((out_dir / "vault_set.json").read_text(encoding="utf-8"))
        assert (
            result.exit_code,
            (out_dir / "instructions.md").exists(),
            trivy_schema.get("annotations"),
            vault_schema.get("annotations"),
            "Exported" in result.output and "instructions" in result.output,
        ) == (0, True, {"readOnlyHint": True}, {"readOnlyHint": False}, True)

    def test_export_schemas_without_instructions(self, runner: CliRunner, tmp_path: Path) -> None:
        """devops mcp export-schemas without instructions writes empty file and adjusts message."""
        from devops_cli.ai.mcp.server import mcp

        out_dir = tmp_path / "mcp_schemas_no_inst"
        with patch.object(type(mcp), "instructions", new_callable=PropertyMock, return_value=""):
            result = runner.invoke(app, ["export-schemas", "--output-dir", str(out_dir)])
            assert result.exit_code == 0
            assert (out_dir / "instructions.md").exists()
            assert (out_dir / "instructions.md").read_text(encoding="utf-8") == ""
            assert "Exported" in result.output
            assert "instructions" not in result.output


# ── Prompt Templates ──────────────────────────────────────────────────────────


def test_mcp_prompts_execution() -> None:
    """Verify architecture analysis and security audit prompt templates return populated markdown."""
    from devops_cli.ai.mcp.server import architecture_analysis_prompt, security_audit_prompt

    arch_p = architecture_analysis_prompt(target="src/devops_cli")
    sec_p = security_audit_prompt(target="src")
    assert (
        "src/devops_cli" in arch_p,
        "security audit" in sec_p.lower(),
        "src" in sec_p,
    ) == (True, True, True)


def test_ai_architecture_tool_is_removed() -> None:
    """Verify the tool that ran the never-existing `devops analyze architecture` is gone,
    with no shim left behind."""
    from devops_cli.ai.mcp import server

    tool_names = {tool.name for tool in asyncio.run(mcp._list_tools())}

    assert "ai_architecture" not in tool_names
    assert "ai_architecture" not in dir(server)


def test_mcp_helpers_and_error_branches() -> None:
    """Verify _run_mcp_cmd timeout, error exit code, _validate_mcp_arg, and review tool calls."""
    # 1. _validate_mcp_arg
    with pytest.raises(ValidationError, match="must not start with a hyphen"):
        _validate_mcp_arg("target", "--malicious-flag")

    _validate_mcp_arg("target", "src/main.py")

    # 2. _run_mcp_cmd timeout
    with patch(
        "devops_cli.ai.mcp.server.run_subprocess",
        side_effect=subprocess.TimeoutExpired(cmd=["uv"], timeout=5.0),
    ):
        res_to = _run_mcp_cmd(
            ["uv", "ghp_secrettoken1234567890abcdefghijklmn"],
            timeout=5.0,
        )
        assert ("timed out after 5.0 seconds" in res_to, "ghp_secrettoken" not in res_to) == (
            True,
            True,
        )

    # 3. _run_mcp_cmd OSError
    with patch(
        "devops_cli.ai.mcp.server.run_subprocess",
        side_effect=OSError("binary not found with ghp_secrettoken1234567890abcdefghijklmn"),
    ):
        res_os = _run_mcp_cmd(["uv"])
        assert "Execution failed" in res_os
        assert "ghp_secrettoken" not in res_os

    # 4. _run_mcp_cmd non-zero exit code
    mock_fail = subprocess.CompletedProcess(
        args=["uv"], returncode=2, stdout="bad input", stderr="error details"
    )
    with patch("devops_cli.ai.mcp.server.run_subprocess", return_value=mock_fail):
        with pytest.raises(ToolError) as exc_info:
            _run_mcp_cmd(["uv"])
        assert "Command exited with status 2" in str(exc_info.value)
        assert "error details" in str(exc_info.value)

    # 5. Review tools
    with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="Review Output"):
        assert (
            review_path(["src"], "*.py"),
            review_branch("feat/new", "main"),
            review_pr(42, post_comment=True),
            review_findings("20260826-session", status_filter="verified"),
            review_stats(),
        ) == ("Review Output", "Review Output", "Review Output", "Review Output", "Review Output")


# ── Dynamic Tool Generation, Coverage & Failure Contract Tests ──────────────────


@pytest.mark.parametrize(
    ("path", "timeout", "read_only", "format_json"),
    CONST_MCP_EXPOSURE_TABLE,
)
def test_mcp_tool_schema_and_argv_parsing(
    path: tuple[str, ...],
    timeout: float,
    read_only: bool,
    format_json: bool,
) -> None:
    """Walk exposure table, assert schema properties match Click parameters and argv parses."""
    from devops_cli.ai.mcp.generator import (
        _IGNORED_PARAM_NAMES,
        _JSON_PARAM_NAMES,
        _PATH_PARAM_RESTRICTIONS,
        _build_command_argv,
        _introspect_command_parameters,
        resolve_click_command,
    )

    tool_name = "_".join(path).replace("-", "_")
    tool = asyncio.run(mcp.get_tool(tool_name))
    assert tool is not None, f"Tool '{tool_name}' not found on server"

    click_cmd = resolve_click_command(path)
    restrictions = _PATH_PARAM_RESTRICTIONS.get(path)
    expected_params = [
        p.name
        for p in click_cmd.params
        if p.name not in _IGNORED_PARAM_NAMES
        and not (format_json and p.name in _JSON_PARAM_NAMES)
        and (not restrictions or p.name in restrictions["allowed"])
    ]
    schema_props = list(tool.parameters.get("properties", {}).keys())
    assert schema_props == expected_params

    parameters, _ = _introspect_command_parameters(click_cmd, format_json, path)
    sample_kwargs: dict[str, Any] = {}
    for p in parameters:
        sample_kwargs[p.name] = p.default if p.default is not p.empty else "sample"

    argv = _build_command_argv(path, click_cmd, format_json, sample_kwargs)
    args = argv[len(path) :]
    ctx = click_cmd.make_context(path[-1], list(args), resilient_parsing=True)
    assert ctx is not None


def test_all_cli_commands_are_either_exposed_or_excluded() -> None:
    """Exhaustive coverage test fails if any CLI command is neither exposed nor in exclusions."""
    from devops_cli.config.constants import (
        CONST_MCP_EXPOSURE_TABLE,
    )
    from devops_cli.core.command_resolver import module_click_command
    from devops_cli.main import _COMMAND_SPECS

    mcp_command_exclusions: frozenset[tuple[str, ...]] = frozenset(
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
            ("ai", "review", "intake"),
            ("ai", "review", "path"),
            ("ai", "review", "pr"),
            ("ai", "review", "rules", "fetch"),
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
            ("argo", "cd", "apps", "retire-helm-records"),
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
            ("ci", "build"),
            ("ci", "coverage"),
            ("ci", "deps"),
            ("ci", "devcontainer"),
            ("ci", "docs"),
            ("ci", "fail-to-pass"),
            ("ci", "format"),
            ("ci", "job-time"),
            ("ci", "lint"),
            ("ci", "lockfile"),
            ("ci", "maintain"),
            ("ci", "mutate"),
            ("ci", "outdated"),
            ("ci", "run"),
            ("ci", "security"),
            ("ci", "test"),
            ("ci", "test-settings"),
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
            ("config", "unset"),
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
            ("gh", "pr", "create"),
            ("gh", "pr", "diff"),
            ("gh", "pr", "edit"),
            ("gh", "pr", "hardening-report"),
            ("gh", "pr", "list"),
            ("gh", "pr", "monitor"),
            ("gh", "pr", "ready"),
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
            ("k8s", "image-pins"),
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
            ("k8s", "tunnel", "start"),
            ("k8s", "tunnel", "status"),
            ("k8s", "tunnel", "stop"),
            ("k8s", "validate-policy"),
            ("k8s", "volume", "move"),
            ("k8s", "volume", "reclaim"),
            ("kustomize", "apply"),
            ("kustomize", "build"),
            ("kustomize", "diff"),
            ("lint",),
            ("mcp", "export-schemas"),
            ("mcp", "serve"),
            ("mcp", "tools"),
            ("openspec", "archive"),
            ("openspec", "check"),
            ("openspec", "regenerate"),
            ("pipeline",),
            ("pr", "create"),
            ("pr", "hardening-report"),
            ("pr", "threads", "resolve-all"),
            ("pr", "threads", "unresolve"),
            ("pr", "view"),
            ("pr", "wait"),
            ("prometheus", "analyze"),
            ("prometheus", "query-range"),
            ("prometheus", "rules"),
            ("prometheus", "targets"),
            ("repos", "clone"),
            ("repos", "clone-org"),
            ("repos", "update"),
            ("repos", "worktrees", "add"),
            ("repos", "worktrees", "prune"),
            ("repos", "worktrees", "status"),
            ("review", "benchmark"),
            ("review", "corpus", "generate"),
            ("review", "corpus", "score"),
            ("review", "rules", "fetch"),
            ("review", "rules", "test"),
            ("review", "samples", "fetch"),
            ("review", "samples", "list"),
            ("review", "samples", "validate"),
            ("review", "score"),
            ("review", "templates", "check"),
            ("review", "templates", "list"),
            ("review", "templates", "sweep"),
            ("review", "intake"),
            ("review", "verify"),
            ("roadmap", "alternatives"),
            ("roadmap", "claim"),
            ("roadmap", "explain"),
            ("roadmap", "implement"),
            ("roadmap", "intake-eval"),
            ("roadmap", "release"),
            ("roadmap", "return"),
            ("roadmap", "stage"),
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
            ("survey",),
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

    exposed_paths = {entry[0] for entry in CONST_MCP_EXPOSURE_TABLE}
    excluded_paths = set(mcp_command_exclusions)
    assert exposed_paths.isdisjoint(excluded_paths)

    all_cli_commands: set[tuple[str, ...]] = set()
    for top_name, spec in _COMMAND_SPECS.items():
        if top_name in ("format", "lint"):
            all_cli_commands.add((top_name,))
            continue
        top_cmd = module_click_command(spec[0])
        if top_cmd is None:
            continue

        def walk(cmd: Any, path: tuple[str, ...]) -> None:
            if getattr(cmd, "hidden", False):
                return
            if hasattr(cmd, "commands") and cmd.commands:
                if path == ("ci",):
                    all_cli_commands.add(path)
                for sub_name, sub_cmd in cmd.commands.items():
                    walk(sub_cmd, path + (sub_name,))
            else:
                all_cli_commands.add(path)

        walk(top_cmd, (top_name,))

    unaccounted = all_cli_commands - (exposed_paths | excluded_paths)
    extra = (exposed_paths | excluded_paths) - all_cli_commands
    assert (unaccounted, extra) == (set(), set())


def test_mcp_command_failure_contract_raises_tool_error() -> None:
    """A failing CLI command in-process returns output with error exit code and raises ToolError (#839)."""
    with patch("devops_cli.ai.mcp.dispatcher.InProcessDispatcher._dispatch_typer") as mock_dispatch:
        mock_dispatch.return_value = (2, "Unknown option: --nonexistent")
        with pytest.raises(ToolError) as exc_info:
            _run_mcp_cmd(["uv", "run", "devops", "ci", "--nonexistent"])
        err_msg = str(exc_info.value)
        assert (
            "Command exited with status 2" in err_msg,
            "Unknown option: --nonexistent" in err_msg,
        ) == (True, True)


@pytest.mark.usefixtures("cached_default_ruleset")
def test_the_mcp_semgrep_tool_scans_with_the_default_ruleset_unless_the_caller_names_one(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The MCP `scan_sast` tool runs the Semgrep adapter with `DEFAULT_SEMGREP_CONFIG`, read from
    its cached ruleset, and with the ruleset that the caller names in its place (#1435)."""
    monkeypatch.chdir(tmp_path)

    for arguments in ({"target": str(tmp_path)}, {"target": str(tmp_path), "config": "./rules"}):
        asyncio.run(mcp.call_tool("scan_sast", arguments, run_middleware=False))

    assert [run.argv[run.argv.index("--config") + 1] for run in scanner_fake.runs] == [
        f"./{CACHED_RULESET_FILE_NAME}",
        "./rules",
    ]


def test_the_mcp_uv_audit_tool_takes_a_directory_and_runs_the_uv_audit_adapter_there(
    scanner_fake: ScannerFake, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The MCP `scan_uv_audit` tool takes only the directory of the project, and runs the uv audit
    adapter there, as the agent tool does (#2106)."""
    monkeypatch.chdir(tmp_path)
    recorded = scanner_fake.script_run_with_findings("uv", tree=tmp_path.resolve())

    tool = asyncio.run(mcp.get_tool("scan_uv_audit"))
    result = asyncio.run(
        mcp.call_tool("scan_uv_audit", {"directory": str(tmp_path)}, run_middleware=False)
    )

    assert (tool.parameters["properties"], scanner_fake.runs, result.content[0].text) == (
        {"directory": {"default": ".", "type": "string"}},
        [recorded],
        "\n".join(
            [
                "uv audit scan status: ok",
                "Findings (4):",
                "- [MEDIUM] uv.lock:idna: [GHSA-65pc-fj4g-8rjx] Internationalized Domain Names in "
                "Applications (IDNA): Specially crafted inputs to idna.encode() can bypass "
                "CVE-2024-3651 fix (Upgrade idna from 3.6 to 3.15)",
                "- [MEDIUM] uv.lock:idna: [GHSA-jjg7-2v4v-x38h] Internationalized Domain Names in "
                "Applications (IDNA) vulnerable to denial of service from specially crafted "
                "inputs to idna.encode (Upgrade idna from 3.6 to 3.7)",
                "- [MEDIUM] uv.lock:idna: [PYSEC-2024-60] idna 3.6 has a known vulnerability "
                "(Upgrade idna from 3.6 to 3.7)",
                "- [MEDIUM] uv.lock:idna: [PYSEC-2026-215] idna 3.6 has a known vulnerability "
                "(Upgrade idna from 3.6 to 3.15)",
            ]
        ),
    )
