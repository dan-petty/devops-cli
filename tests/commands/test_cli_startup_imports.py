"""The startup-import budget: the AST invariant of the entry point and the logic of the check.

The probes themselves are the `startup-imports` row of `devops ci`
(`tests/gate/startup_imports.py`, #2164): each one starts a fresh interpreter, so they
run once in the row and not in a pytest worker. These cases give the check the output of a probe
and read the verdict, so no interpreter starts.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from devops_cli.commands.ci import get_check_spec
from tests.gate.startup_imports import (
    BUDGETS_BY_ARGV,
    CONST_CLI_HEAVY_MODULES,
    DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_COMMAND_HELP,
    DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_MAIN_AND_VERSION,
    DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_COMMAND_HELP,
    DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION,
    SCRIPT_PROBES,
    StartupImports,
    control_problems,
    dry_run_problems,
    help_argvs,
    help_problems,
    parse_importtime,
    read_startup_imports,
    script_problems,
)
from tests.support.paths import REPO_ROOT


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


def _imports(total: int, devops: int, *heavy: str) -> StartupImports:
    """The imports of a run that imported `total` modules, `devops` of them from devops_cli."""
    names = [f"devops_cli.m{n}" for n in range(devops)] + [f"lib{n}" for n in range(total - devops)]
    return StartupImports(
        loaded=frozenset(heavy), imported=frozenset(names), slowest=(("lib0", 0.5),)
    )


def test_the_four_limits_keep_their_values() -> None:
    """The structural budgets are those of #1687."""
    assert (
        DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION,
        DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_MAIN_AND_VERSION,
        DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_COMMAND_HELP,
        DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_COMMAND_HELP,
    ) == (550, 75, 1100, 250)


def test_every_command_help_and_the_budgeted_argvs_are_probed() -> None:
    """`--version`, the root help, and each argv a table names have a probe."""
    argvs = set(help_argvs())

    assert {("--version",), ("--help",), ("ci", "--help"), ("ai", "benchmark", "--help")} <= argvs
    assert set(BUDGETS_BY_ARGV) <= argvs


def test_a_help_run_within_its_budgets_breaks_nothing() -> None:
    """A start that imports few modules and no heavy module passes."""
    assert help_problems(("--help",), _imports(100, 20)) == []


@pytest.mark.parametrize(
    ("probe", "named"),
    [
        pytest.param(_imports(551, 20), "main and version", id="too-many-modules"),
        pytest.param(_imports(100, 76), "main and version", id="too-many-devops-modules"),
        pytest.param(_imports(100, 20, "pydantic_ai"), "pydantic_ai", id="heavy-module"),
    ],
)
def test_a_help_run_over_a_budget_or_with_a_heavy_module_is_named_with_its_slowest_imports(
    probe: StartupImports, named: str
) -> None:
    """The failure names the budget or module, and lists the slowest imports."""
    (message,) = help_problems(("--help",), probe)

    assert (named in message, "Slowest imports:\n  lib0: 0.5000s" in message) == (True, True)


def test_the_telemetry_free_help_may_not_load_telemetry() -> None:
    """The root help may not load pydantic_ai, logfire or opentelemetry.sdk (#858)."""
    assert help_problems(("ci", "--help"), _imports(100, 20, "logfire")) != []
    assert help_problems(("review", "--help"), _imports(100, 20, "logfire")) == []


def test_the_control_fails_the_budget_when_a_heavy_package_is_imported() -> None:
    """A run that imports a heavy package, with imports over the budget, is caught; a run
    that misses it is a failure of the control."""
    over = _imports(DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION + 1, 20, "pydantic_ai")

    assert (control_problems(over), len(control_problems(_imports(100, 20)))) == ([], 1)


def test_a_dry_run_that_imports_a_forbidden_module_is_named() -> None:
    """Only the modules that the plan forbids count."""
    probe = _imports(100, 20, "kubernetes", "fastmcp")

    assert dry_run_problems(("review", "path"), ("kubernetes", "docker"), probe) == [
        "devops review path: imported ['kubernetes']"
    ]


def test_the_report_of_importtime_gives_the_largest_cumulative_time_of_each_module() -> None:
    """A module that `-X importtime` reports twice keeps its largest time."""
    stderr = (
        "import time: self [us] | cumulative | imported package\n"
        "import time:       100 |        200 | json\n"
        "import time:       100 |       4000 | json\n"
        "import time:        50 |         70 |   re\n"
        "not a line\n"
    )

    assert parse_importtime(stderr) == {"json": 0.004, "re": 0.00007}


def test_the_output_of_a_probe_gives_the_loaded_and_the_imported_modules() -> None:
    """`__MODULES__` lists `sys.modules`; `-X importtime` lists the imports and the slowest."""
    stdout = "text\n__MODULES__ sys json\n"
    stderr = "import time:        10 |        500 | json\nimport time: 5 | 90 | sys\n"
    probe = read_startup_imports(stdout, stderr)

    assert (probe.loaded, probe.imported, probe.slowest[0]) == (
        frozenset({"sys", "json"}),
        frozenset({"json", "sys"}),
        ("json", 0.0005),
    )


def test_a_script_probe_that_prints_another_value_is_named() -> None:
    """Each script probe prints one marked JSON value, and a different value fails it."""
    probe = SCRIPT_PROBES[-1]

    assert (script_problems(probe, '__R__"1"\n'), len(script_problems(probe, '__R__""\n'))) == (
        [],
        1,
    )


def test_the_startup_imports_row_runs_the_check_module() -> None:
    """The row `startup-imports` starts the check of `tests/gate/startup_imports.py`."""
    assert "startup_imports" in get_check_spec("startup-imports").cmd[-1]
    assert CONST_CLI_HEAVY_MODULES[0] == "pydantic_ai"
