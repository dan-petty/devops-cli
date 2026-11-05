"""A runner for the checks of a package that a row of `devops ci` runs (#2164).

Each module of the package holds functions named `check_*`. The runner calls each one and prints
the ones that fail, so a row checks the committed files once, and no pytest worker repeats it.

A check may carry `pytest.mark.parametrize` marks: the runner expands them as pytest does. A check
may name a fixture as a parameter: `tmp_path` is an empty directory that the runner removes after
the case, and every other name is one of the `fixtures` that the row gives the runner, each made
once and shared.
"""

from __future__ import annotations

import functools
import importlib
import inspect
import itertools
import pkgutil
import shutil
import sys
import tempfile
import traceback
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from _pytest.mark.structures import Mark, ParameterSet


def _check_modules(package: ModuleType) -> list[ModuleType]:
    """Import every module of the package."""
    return [
        importlib.import_module(f"{package.__name__}.{info.name}")
        for info in pkgutil.iter_modules(package.__path__)
    ]


def _checks(module: ModuleType) -> list[Callable[..., None]]:
    """The functions of one module whose name starts with `check_`, in file order."""
    found = [
        function
        for name, function in inspect.getmembers(module, inspect.isfunction)
        if name.startswith("check_") and function.__module__ == module.__name__
    ]
    return sorted(found, key=lambda function: function.__code__.co_firstlineno)


def _cases(mark: Mark) -> list[tuple[str, dict[str, Any]]]:
    """The cases of one `parametrize` mark as (id, arguments)."""
    names_arg, values = mark.args[0], mark.args[1]
    names = (
        [n.strip() for n in names_arg.split(",")] if isinstance(names_arg, str) else list(names_arg)
    )
    ids = mark.kwargs.get("ids")
    cases: list[tuple[str, dict[str, Any]]] = []
    for position, value in enumerate(values):
        if isinstance(value, ParameterSet):
            row, label = value.values, value.id
        else:
            row, label = (value,) if len(names) == 1 else tuple(value), None
        if label is None and isinstance(ids, (list, tuple)) and position < len(ids):
            label = str(ids[position])
        cases.append((label or f"{position}", dict(zip(names, row, strict=True))))
    return cases


def expand(check: Callable[..., None]) -> list[tuple[str, dict[str, Any]]]:
    """Every case of a check: one for a plain check, the product of its `parametrize` marks."""
    marks = [m for m in getattr(check, "pytestmark", []) if m.name == "parametrize"]
    if not marks:
        return [("", {})]
    expanded: list[tuple[str, dict[str, Any]]] = []
    for combination in itertools.product(*(_cases(m) for m in marks)):
        label = "-".join(part for part, _ in combination)
        arguments: dict[str, Any] = {}
        for _, case in combination:
            arguments.update(case)
        expanded.append((label, arguments))
    return expanded


def _run_case(
    check: Callable[..., None], arguments: dict[str, Any], fixtures: Mapping[str, Callable[[], Any]]
) -> str | None:
    """Run one case. Return why it failed, or None when it passed."""
    scratch: Path | None = None
    try:
        for name in inspect.signature(check).parameters:
            if name in arguments:
                continue
            if name == "tmp_path":
                scratch = Path(tempfile.mkdtemp(prefix="check-"))
                arguments = {**arguments, name: scratch}
            else:
                arguments = {**arguments, name: fixtures[name]()}
        check(**arguments)
    except AssertionError, pytest.fail.Exception:
        return traceback.format_exc(limit=-3)
    except Exception:
        return traceback.format_exc(limit=-6)
    finally:
        if scratch is not None:
            shutil.rmtree(scratch, ignore_errors=True)
    return None


def run_checks(
    package: ModuleType, fixtures: Mapping[str, Callable[[], Any]]
) -> Iterator[tuple[str, str | None]]:
    """Yield (name, failure) for each case of each check of the package."""
    shared = {name: functools.cache(make) for name, make in fixtures.items()}
    for module in _check_modules(package):
        for check in _checks(module):
            for label, arguments in expand(check):
                name = f"{module.__name__.rpartition('.')[2]}.{check.__name__}"
                label_name = f"{name}[{label}]" if label else name
                yield label_name, _run_case(check, arguments, shared)


def main(
    row: str, package: ModuleType, fixtures: Mapping[str, Callable[[], Any]] | None = None
) -> int:
    """Print each failing check of the package, and return 1 when one fails."""
    count = 0
    failed = 0
    for name, failure in run_checks(package, fixtures or {}):
        count += 1
        if failure is not None:
            failed += 1
            print(f"{row}: {name} failed:\n{failure}", file=sys.stderr)
    print(f"{row}: {count} cases, {failed} failed")
    return 1 if failed else 0
