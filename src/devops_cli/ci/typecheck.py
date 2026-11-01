"""The type check of the quality gate, defined once (#3090).

The row `typecheck` of `devops ci` and the implement step of `devops roadmap implement` both build
their `mypy` command from here. The gate type-checks the paths in `TYPECHECK_PATHS` and no other
path, so a step that changes a test file runs no type check on it, and a change of the gate changes
the step.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath

from devops_cli.config.commands import BIN_MYPY, BIN_UV
from devops_cli.config.defaults import DEFAULT_PYTHON_VERSION

# The paths that the gate type-checks. `mypy --strict` runs on them as a whole.
TYPECHECK_PATHS: tuple[str, ...] = ("src",)

# The options of the gate. `pyproject.toml` holds the rest of the mypy settings.
TYPECHECK_OPTIONS: tuple[str, ...] = ("--python-version", DEFAULT_PYTHON_VERSION, "--strict")


def typecheck_argv(targets: Sequence[str]) -> list[str]:
    """The `mypy` command of the gate for `targets`: the paths of the gate for the gate itself, or
    the changed files that `typecheck_files` keeps (after `--`) for a step."""
    return [BIN_UV, "run", BIN_MYPY, *TYPECHECK_OPTIONS, *targets]


def typecheck_files(changed: Sequence[str]) -> list[str]:
    """The Python files of `changed` that the gate type-checks: those below a path of
    `TYPECHECK_PATHS`. Git gives the paths relative to the checkout, with `/`."""
    roots = [PurePosixPath(root) for root in TYPECHECK_PATHS]
    return [
        path
        for path in changed
        if path.endswith(".py") and any(PurePosixPath(path).is_relative_to(root) for root in roots)
    ]
