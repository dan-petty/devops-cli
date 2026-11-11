"""Source-tree invariants: rules that hold over every module under `src/`."""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import pytest

from tests.support.paths import REPO_ROOT
from tests.support.trees import ParsedTreeMap, parse_python_file

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


# Product code that changes its behavior when a test runs is an accommodation (#1333). No module
# under `src/` reads `PYTEST_CURRENT_TEST`.
_PYTEST_CURRENT_TEST = "PYTEST_CURRENT_TEST"


def _pytest_current_test_reads(trees: ParsedTreeMap) -> list[str]:
    src = (REPO_ROOT / "src").resolve()
    return sorted(
        f"{Path(path).resolve().relative_to(src).as_posix()}:{node.lineno}"
        for path, tree in trees.items()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and node.value == _PYTEST_CURRENT_TEST
    )


def test_product_code_never_reads_pytest_current_test(
    parsed_source_trees: ParsedTreeMap,
) -> None:
    """No module under `src/` names `PYTEST_CURRENT_TEST`, so none changes its behavior when a
    test runs (#1333)."""
    assert _pytest_current_test_reads(parsed_source_trees) == []


def _function_identity_checks(trees: ParsedTreeMap) -> list[str]:
    """The reads of an attribute of `subprocess.run`, through `getattr` or directly, which tell a
    stdlib function from the one a test put in its place."""
    src = (REPO_ROOT / "src").resolve()
    return sorted(
        f"{Path(path).resolve().relative_to(src).as_posix()}:{node.lineno}"
        for path, tree in trees.items()
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Call)
            and _called_name(node) == "getattr"
            and node.args
            and ast.unparse(node.args[0]) == "subprocess.run"
        )
        or (isinstance(node, ast.Attribute) and ast.unparse(node.value) == "subprocess.run")
    )


def test_product_code_does_not_tell_a_replaced_subprocess_run_from_the_stdlib_one(
    parsed_source_trees: ParsedTreeMap,
) -> None:
    """The async runner started a program through the sync path when a test had replaced
    `subprocess.run` (#1333). It goes through the active process runner and looks at no test."""
    assert _function_identity_checks(parsed_source_trees) == []


_MOCK_ATTRIBUTES = frozenset(
    {
        "mock_calls",
        "call_count",
        "call_args",
        "call_args_list",
        "method_calls",
        "assert_called",
        "assert_called_once",
        "assert_called_with",
        "assert_called_once_with",
        "assert_any_call",
        "assert_has_calls",
        "assert_not_called",
    }
)


def _probe_in_node(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        name = _called_name(node)
        if name in ("hasattr", "getattr") and len(node.args) >= 2:
            arg1 = node.args[1]
            if isinstance(arg1, ast.Constant) and arg1.value in _MOCK_ATTRIBUTES:
                return f"probe of {arg1.value}"
    elif isinstance(node, ast.Compare):
        for comp in node.comparators:
            if isinstance(comp, ast.Constant) and comp.value == "unittest.mock":
                return "patch detection through unittest.mock"
    return None


def _mock_attribute_probes_in_src(trees: ParsedTreeMap) -> list[str]:
    """Each place in src/ that checks mock attributes or detects unittest.mock (#1309, #1336)."""
    src = (REPO_ROOT / "src").resolve()
    violations: list[str] = []
    for path, tree in trees.items():
        rel = Path(path).resolve().relative_to(src).as_posix()
        for node in ast.walk(tree):
            probe = _probe_in_node(node)
            if probe is not None:
                violations.append(f"{rel}:{node.lineno}: {probe} (docs/TESTING.md # Doubles)")
    return sorted(violations)


def test_no_mock_attribute_probes_in_src(parsed_source_trees: ParsedTreeMap) -> None:
    """Product code under src/ never probes mock attributes or detects unittest.mock (#1336)."""
    assert _mock_attribute_probes_in_src(parsed_source_trees) == []


def test_mock_attribute_probe_in_src_fails_ban() -> None:
    """A mock attribute probe in src/ fails the ban and cites docs/TESTING.md (#1336)."""
    source = (
        "def fn(x):\n"
        "    if hasattr(x, 'mock_calls'):\n"
        "        return True\n"
        "    return x == 'unittest.mock'\n"
    )
    tree = ast.parse(source)
    trees = {REPO_ROOT / "src" / "devops_cli" / "probe.py": tree}
    violations = _mock_attribute_probes_in_src(trees)
    assert len(violations) == 2
    assert "devops_cli/probe.py:2" in violations[0]
    assert "docs/TESTING.md # Doubles" in violations[0]
    assert "devops_cli/probe.py:4" in violations[1]
    assert "docs/TESTING.md # Doubles" in violations[1]


def _unreachable_calls_in_src(trees: ParsedTreeMap) -> list[str]:
    """Each place in src/ that calls unreachable(...) (#1336)."""
    src = (REPO_ROOT / "src").resolve()
    violations: list[str] = []
    for path, tree in trees.items():
        rel = Path(path).resolve().relative_to(src).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _called_name(node) == "unreachable":
                violations.append(
                    f"{rel}:{node.lineno}: call to unreachable() (docs/TESTING.md # Doubles)"
                )
    return sorted(violations)


def test_no_unreachable_calls_in_src(parsed_source_trees: ParsedTreeMap) -> None:
    """Product code under src/ never calls the interim unreachable() marker (#1336)."""
    assert _unreachable_calls_in_src(parsed_source_trees) == []


def test_unreachable_call_in_src_fails_ban() -> None:
    """An unreachable() call in src/ fails the ban and cites docs/TESTING.md (#1336)."""
    source = "def fn():\n    unreachable('not implemented')\n"
    tree = ast.parse(source)
    trees = {REPO_ROOT / "src" / "devops_cli" / "interim.py": tree}
    violations = _unreachable_calls_in_src(trees)
    assert len(violations) == 1
    assert "devops_cli/interim.py:2" in violations[0]
    assert "docs/TESTING.md # Doubles" in violations[0]


_TEST_RESERVED_DIRECTORIES = frozenset(
    {"fixtures", "golden", "__snapshots__", "__pycache__", "support", "invariants", "gate"}
)


def find_loose_root_test_files(repo_root: Path) -> list[str]:
    """Find any .py files directly in tests/ other than conftest.py and __init__.py (#1336)."""
    tests_dir = repo_root / "tests"
    if not tests_dir.is_dir():
        return []
    allowed = {"conftest.py", "__init__.py"}
    violations: list[str] = []
    for path in sorted(tests_dir.glob("*.py")):
        if path.name not in allowed:
            violations.append(
                f"{path.relative_to(repo_root).as_posix()}: loose file directly in tests/ (docs/TESTING.md # Layout)"
            )
    return violations


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
    """Every test file sits in a directory mirroring its devops_cli package or in tests/invariants/ (#1313, #1336)."""
    assert find_root_test_files(REPO_ROOT) == []
    assert find_non_mirror_test_files(REPO_ROOT) == []
    assert find_orphan_test_directories(REPO_ROOT) == []


def test_no_loose_files_directly_in_tests() -> None:
    """Shared helpers live in tests/support/, not directly in tests/ (#1336)."""
    assert find_loose_root_test_files(REPO_ROOT) == []


def test_loose_files_directly_in_tests_fails(tmp_path: Path) -> None:
    """A helper file directly in tests/ fails the ban and cites docs/TESTING.md (#1336)."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "helper.py").touch()
    violations = find_loose_root_test_files(tmp_path)
    assert len(violations) == 1
    assert "tests/helper.py" in violations[0]
    assert "docs/TESTING.md # Layout" in violations[0]


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


# ── The roadmap package layout (#3187) ───────────────────────────────────────

_ROADMAP_SRC = REPO_ROOT / "src" / "devops_cli" / "roadmap"
_ROADMAP_TESTS = REPO_ROOT / "tests" / "roadmap"
_ROADMAP_JOBS = ("intake", "refine", "stage", "implement")
_ROADMAP_STORE_MODULES = ("store", "github_store")


def _module_stems(directory: Path) -> list[str]:
    """The names of the modules in `directory`, without the package module."""
    return sorted(p.stem for p in directory.glob("*.py") if p.name != "__init__.py")


def test_each_roadmap_job_module_sits_in_its_subpackage() -> None:
    """No top-level roadmap module starts with a job name, and each job and the stores have a
    subpackage that holds its modules (#3187)."""
    assert [m for m in _module_stems(_ROADMAP_SRC) if m.startswith(_ROADMAP_JOBS)] == []
    for job in _ROADMAP_JOBS:
        assert _module_stems(_ROADMAP_SRC / job), job
    assert set(_ROADMAP_STORE_MODULES) <= set(_module_stems(_ROADMAP_SRC / "stores"))
    assert set(_ROADMAP_STORE_MODULES).isdisjoint(_module_stems(_ROADMAP_SRC))


def test_the_roadmap_package_module_holds_only_its_docstring() -> None:
    """The package module re-exports no name, so each caller imports a submodule (#3187)."""
    body = ast.parse((_ROADMAP_SRC / "__init__.py").read_text(encoding="utf-8")).body
    assert len(body) == 1
    assert isinstance(body[0], ast.Expr)
    assert isinstance(body[0].value, ast.Constant)
    assert isinstance(body[0].value.value, str)


def test_a_moved_roadmap_module_keeps_its_history() -> None:
    """`git log --follow` reaches the commits that touched a moved module before the move (#3187)."""
    shallow = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if shallow.returncode != 0 or shallow.stdout.strip() != "false":
        pytest.skip("The checkout holds no full git history.")
    log = subprocess.run(
        ["git", "log", "--follow", "--oneline", "--", "src/devops_cli/roadmap/stores/store.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert len(log.stdout.splitlines()) > 1


def test_the_roadmap_tests_mirror_the_roadmap_subpackages() -> None:
    """A test module of a job or of the stores sits in the directory of its subpackage, with its
    snapshot file beside it (#3187)."""
    flat = sorted(p.name for p in _ROADMAP_TESTS.glob("test_*.py"))
    prefixes = tuple(f"test_roadmap_{job}" for job in _ROADMAP_JOBS)
    stores = tuple(f"test_roadmap_{name}" for name in _ROADMAP_STORE_MODULES)
    assert [name for name in flat if name.startswith((*prefixes, *stores))] == []
    flat_snapshots = sorted(p.stem for p in (_ROADMAP_TESTS / "__snapshots__").glob("*.ambr"))
    assert [name for name in flat_snapshots if name.startswith(prefixes)] == []
    for package in (*_ROADMAP_JOBS, "stores"):
        directory = _ROADMAP_TESTS / package
        assert list(directory.glob("test_*.py")), package
        for snapshot in (directory / "__snapshots__").glob("*.ambr"):
            assert (directory / f"{snapshot.stem}.py").is_file(), snapshot.name


# The test directories that patch no name inside devops-cli (#3769, #1336).
_PATCH_FREE_COMMAND_TEST_DIRECTORIES = ("tests/commands", "tests/invariants")
_PATCH_CALLS = frozenset({"patch", "setattr"})


def _string_patches_of_devops_cli(tree: ast.Module) -> list[tuple[int, str]]:
    """The line and target of patch and setattr calls whose first argument is a string
    that names a devops_cli module, class, function, or attribute (#1336)."""
    patches: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and _called_name(node) in _PATCH_CALLS
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and node.args[0].value.split(".")[0] == "devops_cli"
        ):
            patches.append((node.lineno, node.args[0].value))
    return patches


def find_devops_cli_string_patches(test_file: Path, repo_root: Path = REPO_ROOT) -> list[str]:
    """Find string patches of devops_cli in a test file (#1336)."""
    rel = test_file.relative_to(repo_root).as_posix()
    return [
        f"{rel}:{line}: patch('{target}') (docs/TESTING.md # Doubles)"
        for line, target in _string_patches_of_devops_cli(parse_python_file(test_file))
    ]


def test_command_and_invariant_tests_patch_no_devops_cli_name() -> None:
    """No test of tests/commands/ or tests/invariants/ patches a name inside devops-cli (#1336, #4086)."""
    violations = [
        violation
        for directory in _PATCH_FREE_COMMAND_TEST_DIRECTORIES
        for path in sorted((REPO_ROOT / directory).rglob("*.py"))
        for violation in find_devops_cli_string_patches(path)
    ]
    assert violations == []


def test_patch_of_devops_cli_name_fails_ban(tmp_path: Path) -> None:
    """A test module patching a devops_cli name fails the ban and cites docs/TESTING.md (#1336)."""
    test_file = tmp_path / "test_patch.py"
    test_file.write_text(
        "from unittest.mock import patch\n"
        "def test_example(monkeypatch):\n"
        "    patch('devops_cli.config.settings.load_settings')\n"
        "    monkeypatch.setattr('devops_cli.core.cli.app', None)\n",
        encoding="utf-8",
    )
    violations = find_devops_cli_string_patches(test_file, repo_root=tmp_path)
    assert len(violations) == 2
    assert "test_patch.py:3" in violations[0]
    assert "docs/TESTING.md # Doubles" in violations[0]
    assert "test_patch.py:4" in violations[1]
    assert "docs/TESTING.md # Doubles" in violations[1]


def test_stdlib_patch_and_seam_install_are_allowed(tmp_path: Path) -> None:
    """Patching stdlib edges and installing seam fakes do not fail the patch ban (#1336)."""
    test_file = tmp_path / "test_allowed.py"
    test_file.write_text(
        "from unittest.mock import patch\n"
        "def test_allowed(git_fake):\n"
        "    patch('subprocess.run')\n"
        "    patch('socket.getaddrinfo')\n"
        "    git_fake.replay('status')\n",
        encoding="utf-8",
    )
    violations = find_devops_cli_string_patches(test_file, repo_root=tmp_path)
    assert violations == []


def _private_devops_cli_import_aliases(node: ast.AST) -> list[tuple[int, str, str]]:
    if not (
        isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("devops_cli")
    ):
        return []
    return [
        (node.lineno, alias.name, node.module) for alias in node.names if alias.name.startswith("_")
    ]


def find_private_devops_cli_imports(directory: Path, repo_root: Path = REPO_ROOT) -> list[str]:
    """Find any import from devops_cli of a name starting with '_' in directory (#1336)."""
    violations: list[str] = []
    for path in sorted(directory.rglob("*.py")):
        rel = path.relative_to(repo_root).as_posix()
        try:
            tree = parse_python_file(path)
        except Exception:
            continue
        for node in ast.walk(tree):
            for lineno, name, module in _private_devops_cli_import_aliases(node):
                violations.append(
                    f"{rel}:{lineno}: private import {name} from {module} (docs/TESTING.md # Doubles)"
                )
    return violations


def test_invariants_import_no_private_devops_cli_names() -> None:
    """Invariant tests import only public devops_cli names (#1336)."""
    assert find_private_devops_cli_imports(REPO_ROOT / "tests" / "invariants") == []


def test_private_devops_cli_import_fails_ban(tmp_path: Path) -> None:
    """A test module importing a private devops_cli name fails the ban and cites docs/TESTING.md (#1336)."""
    test_file = tmp_path / "test_private.py"
    test_file.write_text(
        "from devops_cli.core.cli import _lazy_proxy\n",
        encoding="utf-8",
    )
    violations = find_private_devops_cli_imports(tmp_path, repo_root=tmp_path)
    assert len(violations) == 1
    assert "test_private.py:1" in violations[0]
    assert "_lazy_proxy" in violations[0]
    assert "docs/TESTING.md # Doubles" in violations[0]


def find_module_level_cli_runners(directory: Path, repo_root: Path = REPO_ROOT) -> list[str]:
    """Find any module-level CliRunner() assignment in directory (#1336)."""
    violations: list[str] = []
    for path in sorted(directory.rglob("*.py")):
        rel = path.relative_to(repo_root).as_posix()
        try:
            tree = parse_python_file(path)
        except Exception:
            continue
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                if _called_name(node.value) == "CliRunner":
                    violations.append(
                        f"{rel}:{node.lineno}: module-level CliRunner (docs/TESTING.md # CLI tests)"
                    )
    return violations


def test_invariants_bind_no_module_level_cli_runner() -> None:
    """Invariant tests bind no module-level CliRunner (#1336)."""
    assert find_module_level_cli_runners(REPO_ROOT / "tests" / "invariants") == []


def test_module_level_cli_runner_ban_fails(tmp_path: Path) -> None:
    """A module-level CliRunner fails the ban and cites docs/TESTING.md (#1336)."""
    test_file = tmp_path / "test_runner.py"
    test_file.write_text(
        "from typer.testing import CliRunner\nrunner = CliRunner()\n",
        encoding="utf-8",
    )
    violations = find_module_level_cli_runners(tmp_path, repo_root=tmp_path)
    assert len(violations) == 1
    assert "test_runner.py:2" in violations[0]
    assert "docs/TESTING.md # CLI tests" in violations[0]


def _read_testing_md_invariant_subjects(doc_path: Path) -> frozenset[str]:
    """Parse the list of invariant subject files from docs/TESTING.md (#1336)."""
    content = doc_path.read_text(encoding="utf-8")
    match = re.search(r"-\s+`tests/invariants/`[^\n]*one file per subject:\s*([^\n]+)", content)
    if not match:
        return frozenset()
    subject_line = match.group(1)
    return frozenset(re.findall(r"`(test_[a-zA-Z0-9_]+\.py)`", subject_line))


def find_unlisted_invariant_files(repo_root: Path) -> list[str]:
    """Find any test_*.py in tests/invariants/ not listed in docs/TESTING.md (#1336)."""
    testing_md = repo_root / "docs" / "TESTING.md"
    allowed = _read_testing_md_invariant_subjects(testing_md)
    invariants_dir = repo_root / "tests" / "invariants"
    violations: list[str] = []
    for path in sorted(invariants_dir.glob("test_*.py")):
        if path.name not in allowed:
            violations.append(
                f"{path.relative_to(repo_root).as_posix()}: unlisted invariant file (docs/TESTING.md # Layout)"
            )
    return violations


def test_invariant_files_are_listed_in_testing_doc() -> None:
    """Every test file in tests/invariants/ is listed in docs/TESTING.md (#1336)."""
    assert find_unlisted_invariant_files(REPO_ROOT) == []


def test_unlisted_invariant_file_fails_ban(tmp_path: Path) -> None:
    """An unlisted invariant file fails the ban and cites docs/TESTING.md (#1336)."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "TESTING.md").write_text(
        "- `tests/invariants/` is the only place for test files outside the mirror. "
        "It holds the invariant tests, one file per subject: `test_source_tree.py`.\n",
        encoding="utf-8",
    )
    inv_dir = tmp_path / "tests" / "invariants"
    inv_dir.mkdir(parents=True)
    (inv_dir / "test_source_tree.py").touch()
    (inv_dir / "test_unlisted.py").touch()
    violations = find_unlisted_invariant_files(tmp_path)
    assert len(violations) == 1
    assert "tests/invariants/test_unlisted.py" in violations[0]
    assert "docs/TESTING.md # Layout" in violations[0]
