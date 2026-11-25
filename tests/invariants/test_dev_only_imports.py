"""The commands import without the dev-only packages that product modules can name (#7212).

`DEP004` of deptry lets a product module import a package of the `dev` group, for code that runs
only at build time. An install with no `dev` group, such as the MCP server image, must still import
each command module: the MCP server imports them all to build its tools.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib

import pytest

from tests.support.paths import REPO_ROOT

CHILD_TIMEOUT_SECONDS = 180

# The child blocks each package (`None` in `sys.modules` fails its import), then imports every
# module of `devops_cli.commands` and prints each one that fails.
CHILD_SOURCE = """
import importlib, pkgutil, sys

for name in sys.argv[1:]:
    sys.modules[name] = None

import devops_cli.commands

for found in pkgutil.walk_packages(devops_cli.commands.__path__, "devops_cli.commands."):
    try:
        importlib.import_module(found.name)
    except ModuleNotFoundError as error:
        print(f"{found.name}: {error}")
"""


@pytest.mark.live("python")
def test_each_command_module_imports_without_the_dev_only_packages() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev_only = pyproject["tool"]["deptry"]["per_rule_ignores"]["DEP004"]

    child = subprocess.run(
        [sys.executable, "-P", "-c", CHILD_SOURCE, *dev_only],
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=CHILD_TIMEOUT_SECONDS,
        check=False,
    )

    assert child.returncode == 0, child.stderr[-2000:]
    assert child.stdout == ""
