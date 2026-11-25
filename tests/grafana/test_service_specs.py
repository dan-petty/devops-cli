"""The commands import without the dev-only Grafana SDK (#7212).

`grafana/service_specs.py` holds the specs of the service dashboards with no SDK. An install with no
`dev` dependency group, such as the MCP server image, must import each command module: the MCP
server imports them all to build its tools.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from tests.support.paths import REPO_ROOT

CHILD_TIMEOUT_SECONDS = 180

# The child blocks the SDK (`None` in `sys.modules` fails its import), then imports every module of
# `devops_cli.commands` and prints each one that fails.
CHILD_SOURCE = """
import importlib, pkgutil, sys

sys.modules["grafana_foundation_sdk"] = None

import devops_cli.commands

for found in pkgutil.walk_packages(devops_cli.commands.__path__, "devops_cli.commands."):
    try:
        importlib.import_module(found.name)
    except ModuleNotFoundError as error:
        print(f"{found.name}: {error}")
"""


@pytest.mark.live("python")
def test_each_command_module_imports_without_the_grafana_sdk() -> None:
    child = subprocess.run(
        [sys.executable, "-P", "-c", CHILD_SOURCE],
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=CHILD_TIMEOUT_SECONDS,
        check=False,
    )

    assert child.returncode == 0, child.stderr[-2000:]
    assert child.stdout == ""
