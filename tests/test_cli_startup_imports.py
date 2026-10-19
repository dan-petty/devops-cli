"""Integration tests verifying CLI startup imports no telemetry when disabled."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

import pytest

from devops_cli.config.constants import (
    CONST_CLI_HEAVY_MODULES,
)
from devops_cli.config.defaults import (
    DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_COMMAND_HELP,
    DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_MAIN_AND_VERSION,
    DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_COMMAND_HELP,
    DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION,
)
from devops_cli.main import _COMMAND_SPECS
from tests.support.paths import REPO_ROOT


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


@pytest.mark.parametrize(
    "argv",
    [
        ["--help"],
        ["ci", "--help"],
        ["workspace", "--help"],
    ],
)
def test_cli_help_imports_no_telemetry(argv: list[str]) -> None:
    """Verify top-level and subcommand help dispatches import neither logfire nor pydantic_ai."""
    code = f"""
import json
import sys
import devops_cli.entry

try:
    devops_cli.entry.main({argv!r})
except SystemExit:
    pass

result = {{
    "logfire": "logfire" in sys.modules,
    "opentelemetry.sdk": "opentelemetry.sdk" in sys.modules,
    "pydantic_ai": "pydantic_ai" in sys.modules,
}}
print("__TELEMETRY_STATUS__" + json.dumps(result))
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env=_clean_subprocess_env(),
        capture_output=True,
        text=True,
        check=True,
    )

    found_line = next(
        line for line in proc.stdout.splitlines() if line.startswith("__TELEMETRY_STATUS__")
    )
    status = json.loads(found_line.removeprefix("__TELEMETRY_STATUS__"))

    assert (
        status["logfire"],
        status["opentelemetry.sdk"],
        status["pydantic_ai"],
    ) == (False, False, False)


def test_entry_toggle_ast_invariants() -> None:
    """Verify PYDANTIC_DISABLE_PLUGINS is assigned unconditionally at module level before devops_cli imports."""
    entry_file = REPO_ROOT / "src" / "devops_cli" / "entry.py"
    tree = ast.parse(entry_file.read_text(encoding="utf-8"), filename=str(entry_file))

    toggle_lineno: int | None = None
    first_devops_import_lineno: int | None = None

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and target.value.attr == "environ"
                    and isinstance(target.slice, ast.Constant)
                    and target.slice.value == "PYDANTIC_DISABLE_PLUGINS"
                ):
                    toggle_lineno = node.lineno
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else [alias.name for alias in node.names]
            )
            if first_devops_import_lineno is None and any(
                name.startswith("devops_cli") for name in names
            ):
                first_devops_import_lineno = node.lineno

    assert (
        toggle_lineno is not None,
        first_devops_import_lineno is not None,
        (toggle_lineno or 0) < (first_devops_import_lineno or 0),
    ) == (True, True, True)


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

_ALL_HELP_ARGVS = [
    ["--version"],
    ["--help"],
] + [[cmd, "--help"] for cmd in sorted(_COMMAND_SPECS.keys())]


@pytest.mark.parametrize("argv", _ALL_HELP_ARGVS)
def test_cli_help_imports_no_heavy_modules(argv: list[str]) -> None:
    """Verify top-level and subcommand help dispatches import zero heavy modules."""
    code = f"""
import json
import sys
import devops_cli.entry

try:
    devops_cli.entry.main({argv!r})
except SystemExit:
    pass

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


def _parse_importtime_lines(
    stderr: str,
) -> tuple[set[str], set[str], list[tuple[str, float]]]:
    module_cum_s: dict[str, float] = {}
    for line in stderr.splitlines():
        parsed = _parse_importtime_line(line)
        if parsed is None:
            continue
        mod, cum_s = parsed
        if mod not in module_cum_s or cum_s > module_cum_s[mod]:
            module_cum_s[mod] = cum_s
    unique_mods = set(module_cum_s.keys())
    devops_mods = {m for m in unique_mods if m.startswith("devops_cli")}
    slowest = sorted(module_cum_s.items(), key=lambda item: item[1], reverse=True)
    return unique_mods, devops_mods, slowest


def _measure_startup_imports(
    argv: list[str],
) -> tuple[set[str], set[str], list[tuple[str, float]]]:
    """Execute devops command with -X importtime and extract imported modules and timing."""
    proc = subprocess.run(
        [sys.executable, "-X", "importtime", "-m", "devops_cli.entry", *argv],
        env=_clean_subprocess_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    return _parse_importtime_lines(proc.stderr)


def _format_slowest_report(slowest: list[tuple[str, float]], limit: int = 10) -> str:
    """Format the slowest imported modules as an informational diagnostic report."""
    return "\n".join(f"  {mod}: {sec:.4f}s" for mod, sec in slowest[:limit])


@pytest.mark.parametrize("argv", [["--version"], ["--help"]])
def test_cli_startup_import_budget_main_and_version(argv: list[str]) -> None:
    """Verify devops --help and --version stay within structural module budgets."""
    unique_mods, devops_mods, slowest = _measure_startup_imports(argv)
    report = _format_slowest_report(slowest)
    print(
        f"\nStartup import timing report for {argv} "
        f"({len(unique_mods)} total modules, {len(devops_mods)} devops_cli modules):\n{report}"
    )

    heavy_found = [m for m in CONST_CLI_HEAVY_MODULES if m in unique_mods]
    assert (
        heavy_found,
        len(unique_mods) <= DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION,
        len(devops_mods) <= DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_MAIN_AND_VERSION,
    ) == ([], True, True), (
        f"{argv} breached structural budget: heavy={heavy_found}, "
        f"total={len(unique_mods)} (limit {DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION}), "
        f"devops={len(devops_mods)} (limit {DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_MAIN_AND_VERSION}).\n"
        f"Slowest imports:\n{report}"
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["--help"],
        ["ai", "--help"],
        ["ai", "benchmark", "--help"],
        ["review", "--help"],
        ["k8s", "--help"],
    ],
)
def test_cli_startup_import_budget_command_help(argv: list[str]) -> None:
    """Verify any devops <command> --help stays within structural module budgets."""
    unique_mods, devops_mods, slowest = _measure_startup_imports(argv)
    report = _format_slowest_report(slowest)
    print(
        f"\nStartup import timing report for {argv} "
        f"({len(unique_mods)} total modules, {len(devops_mods)} devops_cli modules):\n{report}"
    )

    heavy_found = [m for m in CONST_CLI_HEAVY_MODULES if m in unique_mods]
    assert (
        heavy_found,
        len(unique_mods) <= DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_COMMAND_HELP,
        len(devops_mods) <= DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_COMMAND_HELP,
    ) == ([], True, True), (
        f"{argv} breached structural budget: heavy={heavy_found}, "
        f"total={len(unique_mods)} (limit {DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_COMMAND_HELP}), "
        f"devops={len(devops_mods)} (limit {DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_COMMAND_HELP}).\n"
        f"Slowest imports:\n{report}"
    )


def test_startup_structural_budget_fails_when_extra_heavy_package_imported() -> None:
    """Verify injecting a heavy package causes the structural import budget to fail."""
    code = (
        "import pydantic_ai\n"
        "import devops_cli.entry\n"
        "try:\n"
        "    devops_cli.entry.main(['--help'])\n"
        "except SystemExit:\n"
        "    pass\n"
    )
    proc = subprocess.run(
        [sys.executable, "-X", "importtime", "-c", code],
        env=_clean_subprocess_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    unique_mods, _, _ = _parse_importtime_lines(proc.stderr)
    heavy_found = [m for m in CONST_CLI_HEAVY_MODULES if m in unique_mods]

    assert (
        "pydantic_ai" in heavy_found,
        len(unique_mods) > DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION,
    ) == (True, True)


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
        unique_mods, devops_mods, _ = _measure_startup_imports(["--help"])
        heavy_found = [m for m in CONST_CLI_HEAVY_MODULES if m in unique_mods]
        assert (
            heavy_found,
            len(unique_mods) <= DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION,
            len(devops_mods) <= DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_MAIN_AND_VERSION,
        ) == ([], True, True)
    finally:
        for p in workers:
            try:
                p.terminate()
                p.wait(timeout=1.0)
            except OSError, subprocess.TimeoutExpired:
                p.kill()
                p.wait()


def test_cli_dry_run_imports_only_plan_dependencies() -> None:
    """Verify --dry-run paths import only what their plan needs.

    - ai benchmark --dry-run: loads zero heavy modules (simulation only).
    - k8s deploy-stack --dry-run: loads zero heavy modules (manifest planning without cluster client).
    - review path --dry-run: loads only review pipeline modules (pydantic_ai, fastmcp, opentelemetry)
      and neither kubernetes, docker, nor qdrant_client.
    """
    dry_runs = [
        (["ai", "benchmark", "--dry-run"], CONST_CLI_HEAVY_MODULES),
        (["k8s", "deploy-stack", "--dry-run"], CONST_CLI_HEAVY_MODULES),
        (["review", "path", "README.md", "--dry-run"], ("kubernetes", "docker", "qdrant_client")),
    ]
    for argv, forbidden in dry_runs:
        code = f"""
import sys, json, devops_cli.entry
try:
    devops_cli.entry.main({argv!r})
except SystemExit:
    pass
forbidden = {forbidden!r}
loaded = [m for m in forbidden if m in sys.modules]
print("__FORBIDDEN__" + json.dumps(loaded))
"""
        proc = subprocess.run(
            [sys.executable, "-c", code],
            env=_clean_subprocess_env(),
            capture_output=True,
            text=True,
            check=True,
        )
        found_line = next(
            line for line in proc.stdout.splitlines() if line.startswith("__FORBIDDEN__")
        )
        loaded = json.loads(found_line.removeprefix("__FORBIDDEN__"))
        assert loaded == [], f"{argv} eagerly imported forbidden modules: {loaded}"
