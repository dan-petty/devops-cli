"""Source-tree invariants: rules that hold over every module under `src/`."""

from __future__ import annotations

import ast
from pathlib import Path

from tests.support.paths import REPO_ROOT
from tests.support.trees import ParsedTreeMap

# The one structured-output path, and the module that defines the reflection it sends (#1003).
_STRUCTURED_OUTPUT_MODULES = frozenset(
    {"devops_cli/ai/client/structured.py", "devops_cli/ai/schema_reflection.py"}
)
_SCHEMA_REFLECTION_CALLS = frozenset(
    {"extract_schema_reflection", "build_schema_reflection_message"}
)


# The module that declares the settings, and the package that may read a setting's default (#2447).
_SETTINGS_MODULE = "devops_cli/config/settings.py"
_CONFIG_PACKAGE = "devops_cli/config/"
_DEFAULTS_MODULE = "devops_cli.config.defaults"


def _field_default_expressions(value: ast.expr) -> list[ast.expr]:
    """The expressions that give a settings field its default: `Field(<default>)`,
    `Field(default=...)`, `Field(default_factory=...)`, or the assigned value itself."""
    if not (isinstance(value, ast.Call) and _called_name(value) == "Field"):
        return [value]
    return [*value.args[:1]] + [
        keyword.value for keyword in value.keywords if keyword.arg in ("default", "default_factory")
    ]


def _setting_default_names(settings_tree: ast.Module) -> frozenset[str]:
    """The names that the settings module imports from `config/defaults.py` and gives a settings
    field as its default."""
    imported = {
        alias.asname or alias.name
        for node in settings_tree.body
        if isinstance(node, ast.ImportFrom) and node.module == _DEFAULTS_MODULE
        for alias in node.names
    }
    return frozenset(
        name.id
        for cls in ast.walk(settings_tree)
        if isinstance(cls, ast.ClassDef)
        for field in cls.body
        if isinstance(field, ast.AnnAssign) and field.value is not None
        for expression in _field_default_expressions(field.value)
        for name in ast.walk(expression)
        if isinstance(name, ast.Name) and name.id in imported
    )


def _setting_default_reads_outside_config(trees: ParsedTreeMap) -> list[str]:
    """Each place outside `config/` that imports or reads a setting's default by its name."""
    src = (REPO_ROOT / "src").resolve()
    names = _setting_default_names(trees[src / _SETTINGS_MODULE])
    reads: list[str] = []
    for path, tree in trees.items():
        rel = Path(path).resolve().relative_to(src).as_posix()
        if rel.startswith(_CONFIG_PACKAGE):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "devops_cli.config"
            ):
                reads.extend(f"{rel}:{node.lineno} {a.name}" for a in node.names if a.name in names)
            elif isinstance(node, ast.Attribute) and node.attr in names:
                reads.append(f"{rel}:{node.lineno} {node.attr}")
    return sorted(reads)


def _called_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _schema_reflection_calls_outside(trees: ParsedTreeMap, allowed: frozenset[str]) -> list[str]:
    src = (REPO_ROOT / "src").resolve()
    calls: list[str] = []
    for path, tree in trees.items():
        rel = Path(path).resolve().relative_to(src).as_posix()
        if rel in allowed:
            continue
        calls.extend(
            f"{rel}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _called_name(node) in _SCHEMA_REFLECTION_CALLS
        )
    return sorted(calls)


def _reports_of_a_devops_error(node: ast.AST) -> list[tuple[int, str]]:
    """The lines at which `node` reports a `DevOpsCLIError` itself, each with what it uses."""
    if isinstance(node, ast.keyword) and node.arg == "exit_on":
        return [(node.value.lineno, "exit_on=")]
    if isinstance(node, ast.Name) and node.id == "exit_on_error":
        return [(node.lineno, "exit_on_error")]
    if not isinstance(node, ast.ExceptHandler) or node.name is None:
        return []
    exit_status = f"{node.name}.exit_code"
    return [
        (raised.lineno, f"typer.Exit({exit_status})")
        for raised in ast.walk(node)
        if isinstance(raised, ast.Raise)
        and raised.exc is not None
        and exit_status in ast.unparse(raised.exc)
    ]


def _reports_of_devops_errors_in_commands(trees: ParsedTreeMap) -> list[str]:
    src = (REPO_ROOT / "src").resolve()
    found: list[str] = []
    for path, tree in trees.items():
        rel = Path(path).resolve().relative_to(src).as_posix()
        if rel.startswith("devops_cli/commands/"):
            found.extend(
                f"{rel}:{line} {used}"
                for node in ast.walk(tree)
                for line, used in _reports_of_a_devops_error(node)
            )
    return sorted(found)


def test_commands_leave_the_report_of_a_devops_error_to_the_exit_seam(
    parsed_source_trees: ParsedTreeMap,
) -> None:
    """The wrapper of `new_typer()` reports every `DevOpsCLIError` that a command raises (#2487),
    so no command module reports one itself: no `exit_on=`, no `exit_on_error` and no
    `raise typer.Exit(exc.exit_code)` in an `except`."""
    assert _reports_of_devops_errors_in_commands(parsed_source_trees) == []


def test_a_default_that_backs_a_setting_is_read_through_the_settings(
    parsed_source_trees: ParsedTreeMap,
) -> None:
    """A `DEFAULT_*` value that the settings give a field as its default is read only in
    `config/` (#2447). A module elsewhere reads the loaded setting, or the field's declared
    default through `setting_default`, so a config file or variable that sets it is not ignored."""
    assert _setting_default_reads_outside_config(parsed_source_trees) == []


def test_one_path_validates_a_structured_reply_and_reflects_its_errors(
    parsed_source_trees: ParsedTreeMap,
) -> None:
    """`chat_structured` is the one path that validates a model reply against a schema, sends the
    model the errors and asks again (#1003): no other module builds a schema reflection."""
    assert _schema_reflection_calls_outside(parsed_source_trees, _STRUCTURED_OUTPUT_MODULES) == []
