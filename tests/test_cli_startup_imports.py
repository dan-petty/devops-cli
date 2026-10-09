"""Integration tests verifying CLI startup imports no telemetry when disabled."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _clean_subprocess_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return environment cleansed of telemetry and plugin overrides with PYTHONPATH set."""
    env = dict(os.environ)
    env.pop("PYDANTIC_DISABLE_PLUGINS", None)
    env.pop("LOGFIRE_TOKEN", None)
    for k in list(env):
        if k.startswith("DEVOPS_CLI_TELEMETRY__"):
            env.pop(k, None)

    src_dir = str(_PROJECT_ROOT / "src")
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
    entry_file = _PROJECT_ROOT / "src" / "devops_cli" / "entry.py"
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
