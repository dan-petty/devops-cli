"""Verification of test-suite settings in pyproject.toml and tests/conftest.py (#2173)."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from tests.support.paths import REPO_ROOT


def check_test_settings(root: Path = REPO_ROOT) -> int:
    """Verify test-suite settings that cannot be tested by starting processes.

    Returns:
        0 when all settings are correct, 1 when any setting is broken.
    """
    failed = False
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.is_file():
        print(f"Error: {pyproject_path} not found", file=sys.stderr)
        return 1

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    pytest_ini = data.get("tool", {}).get("pytest", {}).get("ini_options", {})
    timeout = pytest_ini.get("timeout")
    timeout_method = pytest_ini.get("timeout_method")

    if not isinstance(timeout, int) or timeout <= 0:
        print(f"Error: pytest timeout must be positive integer, got: {timeout}", file=sys.stderr)
        failed = True

    if timeout_method != "signal":
        print(
            f"Error: pytest timeout_method must be 'signal', got: {timeout_method}", file=sys.stderr
        )
        failed = True

    conftest_path = root / "tests" / "conftest.py"
    if not conftest_path.is_file():
        print(f"Error: {conftest_path} not found", file=sys.stderr)
        return 1

    conftest_text = conftest_path.read_text(encoding="utf-8")
    if "OPENBLAS_NUM_THREADS" not in conftest_text or '"1"' not in conftest_text:
        print("Error: tests/conftest.py must set OPENBLAS_NUM_THREADS to '1'", file=sys.stderr)
        failed = True

    if failed:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    return check_test_settings()
