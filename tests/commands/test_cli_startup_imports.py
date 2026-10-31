"""Integration tests verifying CLI startup imports no telemetry when disabled."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from devops_cli.main import _COMMAND_SPECS
from tests.support.paths import REPO_ROOT
from tests.support.waits import wait_while_running

CONST_CLI_HEAVY_MODULES: tuple[str, ...] = (
    "pydantic_ai",
    "kubernetes",
    "docker",
    "fastmcp",
    "qdrant_client",
    "google.genai",
    "anthropic",
    "openai",
    "agentops",
    "litellm",
    "libtmux",
    "textual",
)
DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION: int = 550
DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_MAIN_AND_VERSION: int = 75
DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_COMMAND_HELP: int = 1100
DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_COMMAND_HELP: int = 250


def _clean_subprocess_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return environment cleansed of telemetry and plugin overrides with PYTHONPATH set."""
    env = dict(os.environ)
    env.pop("PYDANTIC_DISABLE_PLUGINS", None)
    env.pop("LOGFIRE_TOKEN", None)
    for k in list(env):
        if k.startswith("DEVOPS_CLI_TELEMETRY__"):
            env.pop(k, None)

    src_dir = str(REPO_ROOT / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{src_dir}:{existing_pythonpath}" if existing_pythonpath else src_dir

    if extra:
        env.update(extra)
    return env


def _is_pydantic_disable_plugins_assign(node: ast.AST) -> bool:
    if not isinstance(node, ast.Assign):
        return False
    for target in node.targets:
        if (
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Attribute)
            and target.value.attr == "environ"
            and isinstance(target.slice, ast.Constant)
            and target.slice.value == "PYDANTIC_DISABLE_PLUGINS"
        ):
            return True
    return False


def _is_devops_cli_import(node: ast.AST) -> bool:
    if isinstance(node, ast.ImportFrom):
        return (node.module or "").startswith("devops_cli")
    if isinstance(node, ast.Import):
        return any(alias.name.startswith("devops_cli") for alias in node.names)
    return False


def _scan_entry_ast(entry_file: Path) -> tuple[int | None, int | None]:
    tree = ast.parse(entry_file.read_text(encoding="utf-8"), filename=str(entry_file))
    toggle_lineno: int | None = None
    first_devops_import_lineno: int | None = None
    for node in tree.body:
        if _is_pydantic_disable_plugins_assign(node):
            toggle_lineno = node.lineno
            continue
        if first_devops_import_lineno is None and _is_devops_cli_import(node):
            first_devops_import_lineno = node.lineno
    return toggle_lineno, first_devops_import_lineno


def test_entry_toggle_ast_invariants() -> None:
    """Verify PYDANTIC_DISABLE_PLUGINS is assigned unconditionally at module level before imports that load pydantic."""
    for entry_file, require_devops_import in [
        (REPO_ROOT / "src" / "devops_cli" / "entry.py", True),
        (REPO_ROOT / "src" / "devops_cli" / "__init__.py", False),
    ]:
        toggle_lineno, first_devops_import_lineno = _scan_entry_ast(entry_file)

        assert toggle_lineno is not None
        if require_devops_import:
            assert first_devops_import_lineno is not None
            assert (toggle_lineno or 0) < (first_devops_import_lineno or 0)
        else:
            assert first_devops_import_lineno is None


@pytest.mark.live("python")
def test_entry_toggle_merges_existing_plugin() -> None:
    """Verify PYDANTIC_DISABLE_PLUGINS merges logfire-plugin with existing caller plugins."""
    code = """
import os
import sys
import devops_cli.entry

try:
    devops_cli.entry.main(["--help"])
except SystemExit:
    pass

val = os.environ.get("PYDANTIC_DISABLE_PLUGINS", "")
print("__RESULT__" + val)
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env=_clean_subprocess_env({"PYDANTIC_DISABLE_PLUGINS": "some-other-plugin"}),
        capture_output=True,
        text=True,
        check=True,
    )

    found_line = next(line for line in proc.stdout.splitlines() if line.startswith("__RESULT__"))
    val = found_line.removeprefix("__RESULT__")
    plugins = [p.strip() for p in val.split(",")]

    assert (
        "some-other-plugin" in plugins,
        "logfire-plugin" in plugins,
    ) == (True, True)


@pytest.mark.live("python")
def test_entry_prevents_logfire_plugin_when_telemetry_enabled() -> None:
    """Verify logfire plugin is not loaded into pydantic even when telemetry is configured enabled."""
    code = """
import json
import sys
import devops_cli.entry

try:
    devops_cli.entry.main(["--help"])
except SystemExit:
    pass

import pydantic.plugin._loader as loader
plugins = [getattr(p, "__name__", str(p)).lower() for p in loader.get_plugins()]
has_logfire = any("logfire" in p for p in plugins)
print("__HAS_LOGFIRE__" + json.dumps(has_logfire))
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env=_clean_subprocess_env({"DEVOPS_CLI_TELEMETRY__LOGFIRE": "true"}),
        capture_output=True,
        text=True,
        check=True,
    )

    found_line = next(
        line for line in proc.stdout.splitlines() if line.startswith("__HAS_LOGFIRE__")
    )
    has_logfire = json.loads(found_line.removeprefix("__HAS_LOGFIRE__"))

    assert has_logfire is False


@pytest.mark.live("python")
def test_ai_agents_and_providers_import_no_model_sdks() -> None:
    """Verify loading ai.agents.agent and ai.providers imports neither anthropic, google.genai, nor openai."""
    code = """
import json
import sys

import devops_cli.ai.agents.agent
import devops_cli.ai.providers

result = {
    "anthropic": "anthropic" in sys.modules,
    "google.genai": "google.genai" in sys.modules,
    "openai": "openai" in sys.modules,
}
print("__SDKS__" + json.dumps(result))
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env=_clean_subprocess_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    found_line = next(line for line in proc.stdout.splitlines() if line.startswith("__SDKS__"))
    status = json.loads(found_line.removeprefix("__SDKS__"))
    assert (status["anthropic"], status["google.genai"], status["openai"]) == (False, False, False)


_HEAVY_MODULES = CONST_CLI_HEAVY_MODULES

_GITHUB_HELP_ARGVS = [["--help"], ["gh", "--help"], ["roadmap", "--help"], ["pr", "--help"]]


@pytest.mark.live("python")
def test_help_leaves_the_github_sessions_etag_store_unloaded() -> None:
    """`cachetools` holds the GitHub session's ETags (#983) and loads with the session's
    transport, on its first request; neither the top-level help nor the help of a command
    that reads through the session loads it."""
    code = f"""
import json
import sys
import devops_cli.entry

for argv in {_GITHUB_HELP_ARGVS!r}:
    try:
        devops_cli.entry.main(argv)
    except SystemExit:
        pass

print("__ETAG_STORE__" + json.dumps("cachetools" in sys.modules))
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env=_clean_subprocess_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    found_line = next(
        line for line in proc.stdout.splitlines() if line.startswith("__ETAG_STORE__")
    )
    assert json.loads(found_line.removeprefix("__ETAG_STORE__")) is False


@pytest.mark.live("python")
def test_running_commands_import_no_heavy_modules() -> None:
    """Verify importing devops_cli.main, commands.ci, tracer, and http loads zero heavy modules."""
    code = f"""
import json
import sys

import devops_cli.main
import devops_cli.commands.ci
from devops_cli.telemetry.tracer import get_tracer
get_tracer()
import devops_cli.http

heavy = {_HEAVY_MODULES!r}
loaded = [m for m in heavy if m in sys.modules]
print("__HEAVY_STATUS__" + json.dumps(loaded))
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env=_clean_subprocess_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    found_line = next(
        line for line in proc.stdout.splitlines() if line.startswith("__HEAVY_STATUS__")
    )
    loaded = json.loads(found_line.removeprefix("__HEAVY_STATUS__"))
    assert loaded == []


@pytest.mark.live("python")
def test_ssrf_helpers_lazy_pydantic_ai() -> None:
    """Verify devops_cli.core.validation and devops_cli.http.egress do not eagerly import pydantic_ai."""
    code = """
import json
import sys

import devops_cli.core.validation
import devops_cli.http.egress

loaded = "pydantic_ai" in sys.modules
print("__SSRF_STATUS__" + json.dumps(loaded))
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env=_clean_subprocess_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    found_line = next(
        line for line in proc.stdout.splitlines() if line.startswith("__SSRF_STATUS__")
    )
    loaded = json.loads(found_line.removeprefix("__SSRF_STATUS__"))
    assert loaded is False


@pytest.mark.live("python")
def test_pydantic_ai_exceptions_lazy() -> None:
    """Verify importing devops_cli.exceptions.ai does not eagerly import pydantic_ai."""
    code = """
import json
import sys

import devops_cli.exceptions.ai

before = "pydantic_ai" in sys.modules
_ = devops_cli.exceptions.ai.ModelRetry
after = "pydantic_ai" in sys.modules
print("__EXC_STATUS__" + json.dumps({"before": before, "after": after}))
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env=_clean_subprocess_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    found_line = next(
        line for line in proc.stdout.splitlines() if line.startswith("__EXC_STATUS__")
    )
    status = json.loads(found_line.removeprefix("__EXC_STATUS__"))
    assert (status["before"], status["after"]) == (False, True)


# Each argv below runs once, in a fresh interpreter of its own, and every check on that argv reads
# that one run: separate interpreters keep one command's imports out of another's count, and one
# run per argv keeps two checks from measuring the same start twice.
_STARTUP_PROBE = """
import sys
import devops_cli.entry

try:
    devops_cli.entry.main(sys.argv[1:])
except SystemExit:
    pass
print("\\n__MODULES__", *sys.modules)
"""


@dataclass(frozen=True)
class _StartupImports:
    """What one fresh interpreter running `devops <argv>` imported."""

    loaded: frozenset[str]
    """Every name in `sys.modules` once the command returned."""
    imported: frozenset[str]
    """Every module `-X importtime` reported, failed imports included: what the budgets count."""
    slowest: tuple[tuple[str, float], ...]
    """The ten slowest imports by cumulative seconds, a diagnostic only."""

    @property
    def devops_modules(self) -> frozenset[str]:
        """The devops_cli modules among those imported."""
        return frozenset(m for m in self.imported if m.startswith("devops_cli"))

    def found(self, modules: tuple[str, ...]) -> list[str]:
        """Return those of `modules` the run loaded or tried to import."""
        return [m for m in modules if m in self.loaded or m in self.imported]

    def report(self) -> str:
        """Describe the counts and the slowest imports for a failure message."""
        slowest = "\n".join(f"  {mod}: {sec:.4f}s" for mod, sec in self.slowest)
        return (
            f"{len(self.imported)} modules, {len(self.devops_modules)} devops_cli modules. "
            f"Slowest imports:\n{slowest}"
        )


@dataclass(frozen=True)
class _ImportBudget:
    """A structural startup budget (#1687): how many modules, and devops_cli modules, a start imports."""

    name: str
    total: int
    devops: int

    def admits(self, probe: _StartupImports) -> bool:
        """Return whether the run stayed within both counts."""
        return len(probe.imported) <= self.total and len(probe.devops_modules) <= self.devops


_MAIN_AND_VERSION_BUDGET = _ImportBudget(
    "main and version",
    DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION,
    DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_MAIN_AND_VERSION,
)
_COMMAND_HELP_BUDGET = _ImportBudget(
    "command help",
    DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_COMMAND_HELP,
    DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_COMMAND_HELP,
)

# The budgets an argv holds besides the heavy-module check every help argv holds.
_BUDGETS_BY_ARGV: dict[tuple[str, ...], tuple[_ImportBudget, ...]] = {
    ("--version",): (_MAIN_AND_VERSION_BUDGET,),
    ("--help",): (_MAIN_AND_VERSION_BUDGET, _COMMAND_HELP_BUDGET),
    ("ai", "--help"): (_COMMAND_HELP_BUDGET,),
    ("ai", "benchmark", "--help"): (_COMMAND_HELP_BUDGET,),
    ("review", "--help"): (_COMMAND_HELP_BUDGET,),
    ("k8s", "--help"): (_COMMAND_HELP_BUDGET,),
}

# The argvs that also import no telemetry and no pydantic_ai (#858).
_TELEMETRY_FREE_ARGVS: frozenset[tuple[str, ...]] = frozenset(
    {("--help",), ("ci", "--help"), ("workspace", "--help")}
)
_TELEMETRY_MODULES = ("logfire", "opentelemetry.sdk", "pydantic_ai")

# `--version`, the root `--help`, every command group's `--help`, and every argv the tables name.
_HELP_ARGVS: list[tuple[str, ...]] = sorted(
    {
        ("--version",),
        ("--help",),
        *((cmd, "--help") for cmd in _COMMAND_SPECS),
        *_BUDGETS_BY_ARGV,
        *_TELEMETRY_FREE_ARGVS,
    }
)


def _parse_importtime_line(line: str) -> tuple[str, float] | None:
    if not line.strip().startswith("import time:"):
        return None
    parts = line.split("|")
    if len(parts) != 3:
        return None
    s_str = parts[0].replace("import time:", "").strip()
    if not s_str.isdigit():
        return None
    cum_us = int(parts[1].strip())
    mod = parts[2].strip()
    return mod, cum_us / 1_000_000


def _parse_importtime(stderr: str) -> dict[str, float]:
    """Map each module `-X importtime` reported to its largest cumulative import time in seconds."""
    cumulative: dict[str, float] = {}
    for parsed in map(_parse_importtime_line, stderr.splitlines()):
        if parsed is not None:
            mod, seconds = parsed
            cumulative[mod] = max(seconds, cumulative.get(mod, 0.0))
    return cumulative


def _probe_startup_imports(argv: list[str], preamble: str = "") -> _StartupImports:
    """Run `devops <argv>` in a fresh interpreter under `-X importtime` and record its imports.

    The interpreter imports `devops_cli.entry` and calls its `main`, as the `devops` script does.
    `preamble` runs first in the same interpreter, for the control that imports a heavy package.
    """
    proc = subprocess.run(
        [sys.executable, "-X", "importtime", "-c", preamble + _STARTUP_PROBE, *argv],
        env=_clean_subprocess_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    modules_line = next(line for line in proc.stdout.splitlines() if line.startswith("__MODULES__"))
    cumulative = _parse_importtime(proc.stderr)
    slowest = sorted(cumulative.items(), key=lambda item: item[1], reverse=True)[:10]
    return _StartupImports(
        loaded=frozenset(modules_line.split()[1:]),
        imported=frozenset(cumulative),
        slowest=tuple(slowest),
    )


@pytest.mark.live("python")
@pytest.mark.parametrize("argv", _HELP_ARGVS)
def test_cli_help_startup_imports(argv: tuple[str, ...]) -> None:
    """Verify each help argv, run once in a fresh interpreter, imports no heavy module.

    The same run checks what else applies to the argv: the root help and the help of `ci` and
    `workspace` import neither logfire, opentelemetry.sdk nor pydantic_ai (#858), and `--version`,
    the root help and a few commands' help stay within their structural module budgets (#1687).
    """
    probe = _probe_startup_imports(list(argv))
    telemetry = (
        [m for m in _TELEMETRY_MODULES if m in probe.loaded]
        if argv in _TELEMETRY_FREE_ARGVS
        else []
    )
    budgets = _BUDGETS_BY_ARGV.get(argv, ())
    breached = [budget for budget in budgets if not budget.admits(probe)]
    print(f"\nStartup imports for {list(argv)}: {probe.report()}")

    assert (probe.found(CONST_CLI_HEAVY_MODULES), telemetry, breached) == ([], [], []), (
        f"{list(argv)} imported heavy or telemetry modules or breached a budget of {budgets}: "
        f"{probe.report()}"
    )


@pytest.mark.live("python")
def test_startup_structural_budget_fails_when_extra_heavy_package_imported() -> None:
    """Verify injecting a heavy package causes the structural import budget to fail."""
    probe = _probe_startup_imports(["--help"], preamble="import pydantic_ai\n")

    assert (
        "pydantic_ai" in probe.found(CONST_CLI_HEAVY_MODULES),
        len(probe.imported) > DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION,
    ) == (True, True)


@pytest.mark.live("python")
def test_startup_structural_budget_passes_under_cpu_load() -> None:
    """Verify structural import module counts remain invariant and within budget under high CPU load."""
    worker_count = min(os.cpu_count() or 4, 8)
    burn_code = (
        "import time\n"
        "end = time.monotonic() + 3.0\n"
        "while time.monotonic() < end:\n"
        "    _ = sum(i * i for i in range(1000))\n"
    )
    workers: list[subprocess.Popen[bytes]] = []
    try:
        for _ in range(worker_count):
            workers.append(
                subprocess.Popen(
                    [sys.executable, "-c", burn_code],
                    start_new_session=True,
                )
            )
        probe = _probe_startup_imports(["--help"])
        assert (
            probe.found(CONST_CLI_HEAVY_MODULES),
            len(probe.imported) <= DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION,
            len(probe.devops_modules)
            <= DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_MAIN_AND_VERSION,
        ) == ([], True, True)
    finally:
        for p in workers:
            try:
                p.terminate()
                wait_while_running(lambda proc=p: proc.poll() is not None, p)
            except OSError:
                p.kill()
                p.wait()


@pytest.mark.live("python")
@pytest.mark.parametrize(
    ("argv", "forbidden"),
    [
        (["ai", "benchmark", "--dry-run"], CONST_CLI_HEAVY_MODULES),
        (["k8s", "deploy-stack", "--dry-run"], CONST_CLI_HEAVY_MODULES),
        (["review", "path", "README.md", "--dry-run"], ("kubernetes", "docker", "qdrant_client")),
    ],
)
def test_cli_dry_run_imports_only_plan_dependencies(
    argv: list[str], forbidden: tuple[str, ...]
) -> None:
    """Verify --dry-run paths import only what their plan needs.

    - ai benchmark --dry-run: loads zero heavy modules (simulation only).
    - k8s deploy-stack --dry-run: loads zero heavy modules (manifest planning without cluster client).
    - review path --dry-run: loads only review pipeline modules (pydantic_ai, fastmcp, opentelemetry)
      and neither kubernetes, docker, nor qdrant_client.

    The review case can take over 5 s: its one run imports the whole review pipeline, about 2,500
    modules, and runs the review's dry run, and what that run imports is what the case checks.
    """
    probe = _probe_startup_imports(argv)
    loaded = [m for m in forbidden if m in probe.loaded]
    assert loaded == [], f"{argv} eagerly imported forbidden modules: {loaded}"


@pytest.mark.live("python")
def test_entry_turns_off_the_pydantic_ai_banner() -> None:
    """Verify the entry point sets PYDANTIC_AI_NO_BANNER, so pydantic-ai prints no first-run banner
    into the CLI's output (#2398)."""
    code = 'import os, devops_cli.entry\nprint("__RESULT__" + os.environ.get("PYDANTIC_AI_NO_BANNER", ""))\n'
    env = _clean_subprocess_env()
    env.pop("PYDANTIC_AI_NO_BANNER", None)
    proc = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    )

    assert [line for line in proc.stdout.splitlines() if line.startswith("__RESULT__")] == [
        "__RESULT__1"
    ]
