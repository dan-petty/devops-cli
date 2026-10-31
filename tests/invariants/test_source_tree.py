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


# The origin lookup, which takes the root of its repository from the caller (#2127). The ast-grep
# rule `review-cwd-read` holds the scanner entry points, but `core/repo.py` is outside it.
_ORIGIN_LOOKUP = ("devops_cli/core/repo.py", "get_repo_origin_name")


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


def _origin_lookup_root_default(trees: ParsedTreeMap) -> str:
    """The default of the root parameter of the origin lookup, `missing` if the lookup is gone,
    or an empty string."""
    rel, name = _ORIGIN_LOOKUP
    tree = trees[(REPO_ROOT / "src").resolve() / rel]
    function = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name), None
    )
    if function is None:
        return "missing"
    positional = [*function.args.posonlyargs, *function.args.args]
    if positional and len(function.args.defaults) == len(positional):
        return ast.unparse(function.args.defaults[0])
    return ""


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


def test_the_origin_lookup_takes_its_repository_root_from_the_caller(
    parsed_source_trees: ParsedTreeMap,
) -> None:
    """`get_repo_origin_name` takes the root of its repository from the caller, with no default
    (#2127). A default of no root made a call that gave none read the working directory of the
    process."""
    assert _origin_lookup_root_default(parsed_source_trees) == ""


def _is_mock_import(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return any(
            alias.name == "unittest.mock" or alias.name.startswith("unittest.mock.")
            for alias in node.names
        )
    if isinstance(node, ast.ImportFrom):
        return bool(
            node.module == "unittest.mock"
            or (node.module is not None and node.module.startswith("unittest.mock."))
        )
    return False


def _mock_imports_in_src(trees: ParsedTreeMap) -> list[str]:
    src = (REPO_ROOT / "src").resolve()
    found: list[str] = []
    for path, tree in trees.items():
        rel = Path(path).resolve().relative_to(src).as_posix()
        for node in ast.walk(tree):
            if _is_mock_import(node) and hasattr(node, "lineno"):
                found.append(f"{rel}:{node.lineno}")
    return sorted(found)


def test_no_mock_imports_in_src(parsed_source_trees: ParsedTreeMap) -> None:
    """Product code under `src/` never imports unittest.mock (#1328)."""
    assert _mock_imports_in_src(parsed_source_trees) == []


CONST_ROOT_TESTS_CEILING = 0
CONST_NON_MIRROR_TEST_CEILING = 0

_TEST_RESERVED_DIRECTORIES = frozenset(
    {"fixtures", "golden", "__snapshots__", "__pycache__", "support", "invariants"}
)


def find_root_test_files(repo_root: Path) -> list[str]:
    """Find all test_*.py files located directly in the tests/ directory."""
    tests_dir = repo_root / "tests"
    return sorted(p.name for p in tests_dir.glob("test_*.py"))


def find_non_mirror_test_files(repo_root: Path) -> list[str]:
    """Find test_*.py files situated in invalid or non-mirror directories."""
    tests_dir = repo_root / "tests"
    src_dir = repo_root / "src" / "devops_cli"
    violations: list[str] = []
    for path in sorted(tests_dir.rglob("test_*.py")):
        rel = path.relative_to(tests_dir)
        if len(rel.parts) == 1:
            violations.append(rel.as_posix())
            continue
        if rel.parts[0] == "invariants":
            continue
        if rel.parts[0] == "support":
            violations.append(rel.as_posix())
            continue
        if not (src_dir / rel.parent).is_dir():
            violations.append(rel.as_posix())
    return sorted(violations)


def find_orphan_test_directories(repo_root: Path) -> list[str]:
    """Find test directories that do not mirror a package in src/devops_cli/."""
    tests_dir = repo_root / "tests"
    src_dir = repo_root / "src" / "devops_cli"
    orphans: list[str] = []
    for path in sorted(tests_dir.rglob("*")):
        if not path.is_dir():
            continue
        rel = path.relative_to(tests_dir)
        if rel.parts[0] in _TEST_RESERVED_DIRECTORIES:
            continue
        if any(part in ("__pycache__", "__snapshots__") for part in rel.parts):
            continue
        if not (src_dir / rel).is_dir():
            orphans.append(rel.as_posix())
    return sorted(orphans)


def test_tests_mirror_source_tree_layout() -> None:
    """Every test file sits in a directory mirroring its devops_cli package or in tests/invariants/ (#1313)."""
    assert len(find_root_test_files(REPO_ROOT)) <= CONST_ROOT_TESTS_CEILING
    assert len(find_non_mirror_test_files(REPO_ROOT)) <= CONST_NON_MIRROR_TEST_CEILING
    assert find_orphan_test_directories(REPO_ROOT) == []


def test_layout_ratchet_flags_root_test_file(tmp_path: Path) -> None:
    """The layout ratchet rejects test files located directly in the tests/ directory."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_orphan.py").touch()
    (tmp_path / "src" / "devops_cli").mkdir(parents=True)
    assert find_root_test_files(tmp_path) == ["test_orphan.py"]


def test_layout_ratchet_flags_test_file_under_support(tmp_path: Path) -> None:
    """The layout ratchet rejects test files placed under tests/support/."""
    support_dir = tmp_path / "tests" / "support"
    support_dir.mkdir(parents=True)
    (support_dir / "test_helper.py").touch()
    (tmp_path / "src" / "devops_cli").mkdir(parents=True)
    assert "support/test_helper.py" in find_non_mirror_test_files(tmp_path)


def test_layout_ratchet_flags_non_mirror_directory(tmp_path: Path) -> None:
    """The layout ratchet rejects test files placed under directories without a src/devops_cli/ counterpart."""
    pkg_tests = tmp_path / "tests" / "unknown_pkg"
    pkg_tests.mkdir(parents=True)
    (pkg_tests / "test_unknown.py").touch()
    (tmp_path / "src" / "devops_cli").mkdir(parents=True)
    assert "unknown_pkg/test_unknown.py" in find_non_mirror_test_files(tmp_path)
    assert "unknown_pkg" in find_orphan_test_directories(tmp_path)


def test_layout_ratchet_flags_orphan_mirror_directory(tmp_path: Path) -> None:
    """The layout ratchet rejects test directories whose counterpart in src/devops_cli/ does not exist."""
    removed_tests = tmp_path / "tests" / "legacy_module"
    removed_tests.mkdir(parents=True)
    (tmp_path / "src" / "devops_cli").mkdir(parents=True)
    assert find_orphan_test_directories(tmp_path) == ["legacy_module"]
