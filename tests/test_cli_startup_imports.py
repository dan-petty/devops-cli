"""Integration tests verifying CLI startup imports no telemetry when disabled."""

from __future__ import annotations

import ast
import fcntl
import json
import os
import subprocess
import sys

import pytest

from devops_cli.config.constants import (
    CONST_CLI_HEAVY_MODULES,
    CONST_STARTUP_IMPORT_BUDGET_HELP_SECONDS,
    CONST_STARTUP_IMPORT_BUDGET_MAIN_SECONDS,
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


def _parse_importtime_lines(stderr: str) -> tuple[float | None, list[tuple[str, float]]]:
    all_imports: list[tuple[str, float]] = []
    main_cum_s: float | None = None
    for line in stderr.splitlines():
        parsed = _parse_importtime_line(line)
        if parsed is None:
            continue
        mod, cum_s = parsed
        all_imports.append((mod, cum_s))
        if mod == "devops_cli.main":
            main_cum_s = cum_s
    all_imports.sort(key=lambda item: item[1], reverse=True)
    return main_cum_s, all_imports


def _measure_importtime(
    argv: list[str], runs: int = 2
) -> tuple[float | None, list[tuple[str, float]]]:
    """Execute devops command with -X importtime and parse stderr import durations.

    Uses an flock to serialize measurements across parallel test workers and takes the best of
    runs (minimum cumulative time) to eliminate transient CPU/scheduling jitter.
    """
    lock_file = REPO_ROOT / ".data" / "importtime.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    best_main: float | None = None
    best_imports: list[tuple[str, float]] = []
    min_measured_s: float = float("inf")

    with open(lock_file, "w") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            for _ in range(runs):
                proc = subprocess.run(
                    [sys.executable, "-X", "importtime", "-m", "devops_cli.entry", *argv],
                    env=_clean_subprocess_env(),
                    capture_output=True,
                    text=True,
                    check=True,
                )
                main_cum_s, all_imports = _parse_importtime_lines(proc.stderr)
                key_metric = (
                    main_cum_s
                    if main_cum_s is not None
                    else (all_imports[0][1] if all_imports else 0.0)
                )
                if key_metric < min_measured_s:
                    min_measured_s = key_metric
                    best_main = main_cum_s
                    best_imports = all_imports
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)

    return best_main, best_imports


@pytest.mark.parametrize("argv", [["--version"], ["--help"]])
def test_cli_startup_import_budget_main_and_version(argv: list[str]) -> None:
    """Verify devops --help and --version stay within 0.5s cumulative import time for devops_cli.main."""
    main_cum_s, all_imports = _measure_importtime(argv)
    assert main_cum_s is not None, f"devops_cli.main was not found in -X importtime for {argv}"
    slowest_report = [f"{m}: {s:.4f}s" for m, s in all_imports[:10]]
    assert main_cum_s <= CONST_STARTUP_IMPORT_BUDGET_MAIN_SECONDS, (
        f"devops_cli.main import took {main_cum_s:.4f}s > {CONST_STARTUP_IMPORT_BUDGET_MAIN_SECONDS}s for {argv}. Slowest: {slowest_report}"
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
    """Verify any devops <command> --help stays within 1.0s of import time, reporting slowest imports on failure."""
    _, all_imports = _measure_importtime(argv)
    slowest_s = all_imports[0][1] if all_imports else 0.0
    slowest_report = [f"{m}: {s:.4f}s" for m, s in all_imports[:10]]
    assert slowest_s <= CONST_STARTUP_IMPORT_BUDGET_HELP_SECONDS, (
        f"Command help import took {slowest_s:.4f}s > {CONST_STARTUP_IMPORT_BUDGET_HELP_SECONDS}s for {argv}. Slowest: {slowest_report}"
    )


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
