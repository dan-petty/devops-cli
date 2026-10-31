"""Unit tests for mapping changed source files onto their covering test modules."""

from __future__ import annotations

import ast
import shutil
from pathlib import Path
from typing import NoReturn

import pytest
from typer.testing import CliRunner, Result

from devops_cli.ci.cache import resolve_coverage_index_path
from devops_cli.commands import ci as ci_module
from devops_cli.commands.ci import _normalize_repo_rel_path, get_check_spec
from devops_cli.commands.ci import app as ci_app
from devops_cli.config.constants import (
    CONST_CI_SLOWEST_TESTS_SHOWN,
    CONST_CONFTEST_FILENAME,
    CONST_FULL_RUN_TRIGGER_NAMES,
    CONST_TESTS_ROOT_DIR,
)
from devops_cli.config.defaults import (
    DEFAULT_CI_TEST_NARROWED_WORKERS,
    DEFAULT_CI_TEST_SERIAL_MAX_FILES,
)
from devops_cli.core.coverage_index import CoverageIndex, save_index
from devops_cli.core.test_selection import (
    SuiteImports,
    forces_full_run,
    is_test_module,
    module_path_for_source,
    select_tests_for_sources,
)
from tests.support.paths import REPO_ROOT, TESTS_ROOT
from tests.support.session_spawns import RecordedSpawn, record_spawns

pytestmark = pytest.mark.usefixtures("refuse_nested_test_runs")

runner = CliRunner()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Build a miniature project with a source tree and a matching test tree."""
    src = tmp_path / "src" / "devops_cli"
    (src / "security").mkdir(parents=True)
    (src / "security" / "secrets.py").write_text("VALUE = 1\n", encoding="utf-8")
    (src / "security" / "__init__.py").write_text("", encoding="utf-8")
    (src / "orphan.py").write_text("UNCOVERED = True\n", encoding="utf-8")

    tests = tmp_path / "tests"
    tests.mkdir()
    # Covers by import, but its name matches no convention.
    (tests / "test_credential_flow.py").write_text(
        "from devops_cli.security.secrets import VALUE\n", encoding="utf-8"
    )
    # Covers by naming convention, without importing the module.
    (tests / "test_secrets.py").write_text("def test_noop() -> None: ...\n", encoding="utf-8")
    # Unrelated.
    (tests / "test_unrelated.py").write_text(
        "from devops_cli.other import thing\n", encoding="utf-8"
    )
    return tmp_path


# ─────────────────────────────────────────────────────────────────────────────
# 1. Module path derivation
# ─────────────────────────────────────────────────────────────────────────────


def test_module_path_derived_from_source_layout(project: Path) -> None:
    """A source file maps to its importable dotted module path."""
    path = project / "src" / "devops_cli" / "security" / "secrets.py"
    assert module_path_for_source(path, project) == "devops_cli.security.secrets"


def test_package_init_maps_to_the_package(project: Path) -> None:
    """An `__init__.py` addresses its package, not a module named `__init__`."""
    path = project / "src" / "devops_cli" / "security" / "__init__.py"
    assert module_path_for_source(path, project) == "devops_cli.security"


def test_non_source_paths_have_no_module_path(project: Path) -> None:
    """Files outside the source tree, or that are not Python, map to nothing."""
    (project / "README.md").write_text("# docs\n", encoding="utf-8")
    assert module_path_for_source(project / "README.md", project) is None
    assert module_path_for_source(project / "tests" / "test_secrets.py", project) is None


# ─────────────────────────────────────────────────────────────────────────────
# 2. Selection
# ─────────────────────────────────────────────────────────────────────────────


def test_selection_unions_convention_and_import_matches(project: Path) -> None:
    """Both naming convention and actual imports contribute covering tests.

    Convention alone misses a test whose name does not follow the module, and imports
    alone miss a conventionally named test that exercises behaviour indirectly.
    """
    selection = select_tests_for_sources(["src/devops_cli/security/secrets.py"], project)

    assert selection.pytest_targets() == [
        "tests/test_credential_flow.py",
        "tests/test_secrets.py",
    ]
    assert selection.unmapped_sources == []


def test_unrelated_tests_are_not_selected(project: Path) -> None:
    """A test covering a different module is left out of the narrowed run."""
    selection = select_tests_for_sources(["src/devops_cli/security/secrets.py"], project)
    assert "tests/test_unrelated.py" not in selection.pytest_targets()


def test_source_without_covering_tests_is_reported(project: Path) -> None:
    """An uncovered source is surfaced rather than silently yielding an empty run."""
    selection = select_tests_for_sources(["src/devops_cli/orphan.py"], project)

    assert (selection.pytest_targets(), selection.unmapped_sources) == (
        [],
        ["src/devops_cli/orphan.py"],
    )
    assert selection.has_selection is False


def test_test_files_pass_straight_through(project: Path) -> None:
    """A test file supplied directly is run as given."""
    selection = select_tests_for_sources(["tests/test_unrelated.py"], project)
    assert selection.pytest_targets() == ["tests/test_unrelated.py"]


def test_non_python_files_are_ignored_without_being_flagged(project: Path) -> None:
    """Docs and manifests are neither run nor reported as uncovered code."""
    (project / "README.md").write_text("# docs\n", encoding="utf-8")
    selection = select_tests_for_sources(["README.md"], project)

    assert (selection.pytest_targets(), selection.unmapped_sources) == ([], [])


def test_multiple_sources_deduplicate_shared_tests(project: Path) -> None:
    """Two sources covered by one test module produce a single pytest target."""
    selection = select_tests_for_sources(
        ["src/devops_cli/security/secrets.py", "tests/test_secrets.py"], project
    )
    assert selection.pytest_targets().count("tests/test_secrets.py") == 1


def test_absolute_paths_are_accepted(project: Path) -> None:
    """Pre-commit may pass absolute paths; they resolve the same as relative ones."""
    absolute = project / "src" / "devops_cli" / "security" / "secrets.py"
    assert select_tests_for_sources([absolute], project).pytest_targets() == [
        "tests/test_credential_flow.py",
        "tests/test_secrets.py",
    ]


def test_missing_tests_tree_yields_no_targets(tmp_path: Path) -> None:
    """A project without a tests directory selects nothing rather than raising."""
    (tmp_path / "src" / "devops_cli").mkdir(parents=True)
    (tmp_path / "src" / "devops_cli" / "mod.py").write_text("X = 1\n", encoding="utf-8")

    selection = select_tests_for_sources(["src/devops_cli/mod.py"], tmp_path)
    assert (selection.pytest_targets(), selection.unmapped_sources) == (
        [],
        ["src/devops_cli/mod.py"],
    )


def test_a_module_selects_no_test_module_only_for_sitting_in_its_package_directory(
    project: Path,
) -> None:
    """A test module in the directory under `tests/` that mirrors a module's package runs only
    when it names or imports the module: replayed over 15 commits, the ones it added beside it
    never ran it (#1312)."""
    mirror = project / "tests" / "security"
    mirror.mkdir()
    (mirror / "test_policy.py").write_text("def test_policy() -> None: ...\n", encoding="utf-8")
    sources = ["src/devops_cli/security/secrets.py", "src/devops_cli/security/__init__.py"]
    assert [select_tests_for_sources([source], project).pytest_targets() for source in sources] == [
        ["tests/test_credential_flow.py", "tests/test_secrets.py"],
        ["tests/test_credential_flow.py"],
    ]


_FIXTURES_ONLY = "import pytest\n\n\n@pytest.fixture\ndef policy() -> str:\n    return 'deny'\n"
_HOOK = "\n\ndef pytest_collection_modifyitems(config, items):\n    items.reverse()\n"


@pytest.mark.parametrize(
    ("text", "selected"),
    [
        pytest.param(_FIXTURES_ONLY, ["tests/security"], id="fixtures-only"),
        pytest.param(_FIXTURES_ONLY + _HOOK, ["tests"], id="hook"),
        pytest.param(
            "from tests.support.hooks import pytest_runtest_setup\n", ["tests"], id="imported-hook"
        ),
        pytest.param("from tests.support.hooks import *\n", ["tests"], id="star-import"),
        pytest.param("def broken(:\n", ["tests"], id="unparsable"),
        pytest.param(None, ["tests"], id="deleted"),
    ],
)
def test_a_nested_conftest_selects_the_whole_suite_when_it_binds_a_hook(
    project: Path, text: str | None, selected: list[str]
) -> None:
    """pytest calls a `pytest_*` hook of every conftest for every test, so one bound in
    `tests/security/conftest.py`, defined or imported, can change a test in any directory; a
    conftest of fixtures only reaches its own directory. It is read with `ast`, and one it
    cannot read, or that imports `*`, counts as binding a hook (#1312)."""
    (project / "tests" / "security").mkdir()
    if text is not None:
        (project / "tests" / "security" / "conftest.py").write_text(text, encoding="utf-8")
    targets = select_tests_for_sources(["tests/security/conftest.py"], project).pytest_targets()
    assert targets == selected


_FIXTURE_MODULE = (
    "import pytest\n\n\n@pytest.fixture\ndef identity() -> str:\n    return 'nobody'\n"
)
_HOOK_MODULE = "def pytest_runtest_setup(item: object) -> None:\n    pass\n"
_PLAIN_MODULE = '"""Rows that a fixture would read; the word registers nothing."""\n\nROWS = 1\n'
_ROWS_IMPORTER = "from tests.support.rows import ROWS\n"
_MID_IMPORTER = "from tests.support.mid import MID\n"
_CONFTEST_IMPORTING_ROWS = (
    "import pytest\n\n\n@pytest.fixture\ndef rows() -> int:\n"
    "    from tests.support.rows import ROWS\n\n    return ROWS\n"
)
_FIXTURE_FROM_PYTEST = (
    "from pytest import fixture\n\n\n@fixture\ndef identity() -> str:\n    return 'nobody'\n"
)


@pytest.mark.parametrize(
    ("files", "selected"),
    [
        pytest.param(
            {"tests/support/rows.py": _PLAIN_MODULE, "tests/test_rows.py": _ROWS_IMPORTER},
            ["tests/test_rows.py"],
            id="plain-helper",
        ),
        pytest.param({"tests/support/rows.py": _FIXTURE_MODULE}, ["tests"], id="fixture-module"),
        pytest.param(
            {"tests/support/rows.py": _FIXTURE_FROM_PYTEST, "tests/test_rows.py": _ROWS_IMPORTER},
            ["tests"],
            id="fixture-imported-from-pytest",
        ),
        pytest.param({"tests/support/rows.py": _HOOK_MODULE}, ["tests"], id="hook-module"),
        pytest.param(
            {
                "tests/support/rows.py": _PLAIN_MODULE,
                "tests/support/identity.py": _ROWS_IMPORTER + _FIXTURE_MODULE,
                "tests/test_rows.py": _ROWS_IMPORTER,
            },
            ["tests"],
            id="imported-by-a-fixture-module",
        ),
        pytest.param(
            {
                "tests/support/rows.py": _PLAIN_MODULE,
                "tests/support/mid.py": _ROWS_IMPORTER + "MID = ROWS\n",
                "tests/support/identity.py": _MID_IMPORTER + _FIXTURE_MODULE,
                "tests/test_rows.py": _ROWS_IMPORTER,
            },
            ["tests"],
            id="imported-two-hops-from-a-fixture-module",
        ),
        pytest.param(
            {
                "tests/support/rows.py": _PLAIN_MODULE,
                "tests/support/builders.py": _ROWS_IMPORTER,
                "tests/test_builders.py": "from tests.support.builders import ROWS\n",
                "tests/test_rows.py": "import tests.support.rows\n",
            },
            ["tests/test_builders.py", "tests/test_rows.py"],
            id="transitive-importer",
        ),
        pytest.param(
            {
                "tests/support/rows.py": _PLAIN_MODULE + _MID_IMPORTER,
                "tests/support/mid.py": _ROWS_IMPORTER + "MID = ROWS\n",
                "tests/test_mid.py": _MID_IMPORTER,
            },
            ["tests/test_mid.py"],
            id="import-cycle",
        ),
        pytest.param(
            {
                "tests/support/rows.py": _PLAIN_MODULE,
                "tests/security/conftest.py": _ROWS_IMPORTER,
                "tests/test_rows.py": _ROWS_IMPORTER,
            },
            ["tests"],
            id="imported-by-a-plain-conftest",
        ),
        pytest.param(
            {
                "tests/support/rows.py": _PLAIN_MODULE,
                "tests/security/conftest.py": _CONFTEST_IMPORTING_ROWS,
                "tests/test_rows.py": _ROWS_IMPORTER,
            },
            ["tests"],
            id="imported-inside-a-conftest-fixture",
        ),
        pytest.param({"tests/test_rows.py": _ROWS_IMPORTER}, ["tests"], id="deleted"),
    ],
)
def test_a_support_module_reaches_every_test_by_what_it_registers_who_imports_it_or_when_unread(
    project: Path, files: dict[str, str], selected: list[str]
) -> None:
    """Every submodule and subpackage of `tests.support` is registered as a plugin, so one that
    defines a fixture or a `pytest_*` hook reaches every test, as does one that such a module or
    a conftest imports, directly or through other modules, inside a function too; any other
    reaches only the test modules that import it, directly or through another module, an import
    cycle included. `ast` reads the tree, so a docstring naming a fixture registers nothing, and
    a module it cannot read, as one deleted, reaches every test (#1312)."""
    _write(project, files)
    targets = select_tests_for_sources(["tests/support/rows.py"], project).pytest_targets()
    assert targets == selected


def _write(project: Path, files: dict[str, str]) -> None:
    """Write each file of `files` under the project."""
    for relative, text in files.items():
        (project / relative).parent.mkdir(parents=True, exist_ok=True)
        (project / relative).write_text(text, encoding="utf-8")


def test_a_package_init_selects_the_test_modules_importing_its_modules_not_its_empty_directory(
    project: Path,
) -> None:
    """Importing a module of a package runs the package's `__init__.py` first, so a change to it
    selects the test modules that import any of its modules; the package's own directory holds no
    test module, so it is not handed to pytest, which would collect nothing there (#1312)."""
    _write(
        project,
        {
            "tests/support/__init__.py": "",
            "tests/support/fakes/__init__.py": "",
            "tests/support/fakes/github.py": "SESSION = None\n",
            "tests/test_github.py": "from tests.support.fakes.github import SESSION\n",
        },
    )
    selection = select_tests_for_sources(["tests/support/fakes/__init__.py"], project)
    assert selection.pytest_targets() == ["tests/test_github.py"]


def test_the_tests_package_init_reaches_every_test_through_the_conftest(project: Path) -> None:
    """The root conftest runs `tests/__init__.py` first, as its package, so a change to it forces
    a full run (#1312)."""
    _write(project, {"tests/__init__.py": "", "tests/conftest.py": ""})
    assert forces_full_run("tests/__init__.py", SuiteImports(project)) is True


@pytest.mark.parametrize(
    "trigger",
    [
        "tests/conftest.py",
        "conftest.py",
        "pyproject.toml",
        "uv.lock",
        ".python-version",
    ],
)
def test_a_change_that_forces_a_full_run_selects_the_suite_without_reading_the_tests(
    project: Path, trigger: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A change `forces_full_run` names reaches every test, so the selector returns `tests` at
    once, listing and reading no test module for the source changed beside it (#1312)."""

    def unread(self: Path, *args: object, **kwargs: object) -> NoReturn:
        raise AssertionError(f"the selector read {self}")

    for method in ("glob", "rglob", "read_text"):
        monkeypatch.setattr(Path, method, unread)
    selection = select_tests_for_sources(["src/devops_cli/security/secrets.py", trigger], project)
    assert (selection.pytest_targets(), selection.unmapped_sources) == (["tests"], [])


# ─────────────────────────────────────────────────────────────────────────────
# 3. CLI behaviour
# ─────────────────────────────────────────────────────────────────────────────


def test_cli_runs_only_the_covering_tests(monkeypatch: pytest.MonkeyPatch, project: Path) -> None:
    """Passing a source file narrows the pytest invocation to its covering tests."""
    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)

    result = runner.invoke(ci_app, ["test", "src/devops_cli/security/secrets.py"])

    assert result.exit_code == 0
    assert "tests/test_credential_flow.py" in called[0]
    assert "tests/test_unrelated.py" not in called[0]


def test_cli_without_paths_runs_the_whole_suite(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """Omitting paths preserves the original full-suite behaviour."""
    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)

    result = runner.invoke(ci_app, ["test"])

    assert result.exit_code == 0
    assert not any(arg.startswith("tests/") for arg in called[0])


def test_cli_falls_back_to_full_suite_for_uncovered_sources(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """An uncovered source escalates to the full suite rather than verifying nothing."""
    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)

    result = runner.invoke(ci_app, ["test", "src/devops_cli/orphan.py"])

    assert result.exit_code == 0
    assert not any(arg.startswith("tests/") for arg in called[0])
    assert "Falling back to the full suite" in result.output


def test_cli_refuses_a_silent_green_with_no_fallback(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """With --no-fallback an uncovered source fails instead of reporting success.

    Reporting a pass without executing a single test is the one outcome a pre-commit
    hook must never produce.
    """
    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)

    result = runner.invoke(ci_app, ["test", "src/devops_cli/orphan.py", "--no-fallback"])

    assert result.exit_code == 1
    assert called == []
    assert "Refusing to report success" in result.output


def test_cli_exits_cleanly_for_documentation_only_changes(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """A docs-only commit runs nothing and succeeds, without a spurious failure."""
    called: list[list[str]] = []
    (project / "README.md").write_text("# docs\n", encoding="utf-8")
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)

    result = runner.invoke(ci_app, ["test", "README.md"])

    assert (result.exit_code, called) == (0, [])


def _invoke_test_with(
    monkeypatch: pytest.MonkeyPatch, project: Path, *args: str
) -> tuple[Result, list[list[str]]]:
    """`devops ci test <args>` run on the project with pytest doubled: the result and the pytest
    command lines the run started."""
    called: list[list[str]] = []

    def record(cmd: list[str], **_: object) -> bool:
        called.append(cmd)
        return True

    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", record)
    return runner.invoke(ci_app, ["test", *args]), called


def test_cli_runs_the_test_modules_of_a_tests_directory(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """A directory under tests/ runs its test modules at any depth, and not its helpers (#2868)."""
    (project / "tests" / "pkg" / "deep").mkdir(parents=True)
    for name in ("test_a.py", "deep/test_b.py", "helper.py"):
        (project / "tests" / "pkg" / name).write_text("X = 1\n", encoding="utf-8")

    result, called = _invoke_test_with(monkeypatch, project, "tests/pkg/")

    run_targets = sorted(arg for arg in called[0] if arg.startswith("tests/"))
    assert (result.exit_code, run_targets) == (
        0,
        ["tests/pkg/deep/test_b.py", "tests/pkg/test_a.py"],
    )


@pytest.mark.parametrize("directory", ["tests/empty", "tests/..", "docs", "."])
def test_cli_refuses_a_directory_that_gives_no_test_module(
    monkeypatch: pytest.MonkeyPatch, project: Path, directory: str
) -> None:
    """A directory without a test module under tests/, and one outside src/ and tests/, exit 1
    with an error that names it, and start no pytest (#2868)."""
    (project / "tests" / "empty").mkdir()
    (project / "tests" / "empty" / "helper.py").write_text("X = 1\n", encoding="utf-8")
    (project / "docs").mkdir()

    result, called = _invoke_test_with(monkeypatch, project, directory)

    assert (result.exit_code, called, f"'{directory}'" in result.output) == (1, [], True)


def test_cli_refuses_a_directory_with_a_fallback_too(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """The full-suite fallback does not turn a refused directory into a run: the argument is the
    mistake, not a source without a test (#2868)."""
    (project / "docs").mkdir()

    result, called = _invoke_test_with(monkeypatch, project, "docs", "--fallback")

    assert (result.exit_code, called) == (1, [])


@pytest.mark.parametrize("missing", ["tests/invariantz", "tests/pkg/test_nothere.py"])
@pytest.mark.parametrize("extra", [(), ("--fallback",)])
def test_cli_refuses_a_path_that_does_not_exist(
    monkeypatch: pytest.MonkeyPatch, project: Path, missing: str, extra: tuple[str, ...]
) -> None:
    """A mistyped or renamed path exits 1 with an error that names it, and starts no pytest, so a
    green exit always means that a test ran (#2868)."""
    (project / "tests" / "pkg").mkdir(parents=True)

    result, called = _invoke_test_with(monkeypatch, project, missing, *extra)

    assert (result.exit_code, called, f"'{missing}'" in result.output) == (1, [], True)


def test_cli_runs_the_tests_covering_a_source_directory(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """A directory under src/ runs the tests that cover the modules inside it (#2868)."""
    result, called = _invoke_test_with(monkeypatch, project, "src/devops_cli/security")

    run_targets = [arg for arg in called[0] if arg.startswith("tests/")]
    assert (result.exit_code, "tests/test_credential_flow.py" in run_targets) == (0, True)


def _worker_options(argv: list[str]) -> list[list[str]]:
    """The `-n` options of a pytest command line, each with its value."""
    return [argv[at : at + 2] for at, arg in enumerate(argv) if arg in ("-n", "--numprocesses")]


def _started_runs(
    monkeypatch: pytest.MonkeyPatch, project: Path, *args: str
) -> tuple[int, list[RecordedSpawn]]:
    """`devops ci test <args>` run from the project, its exit code and the children it started,
    doubled at `asyncio.create_subprocess_exec`, so none of them is real."""
    monkeypatch.chdir(project)
    spawns = record_spawns(monkeypatch)
    result = runner.invoke(ci_app, ["test", *args])
    return result.exit_code, spawns


def _test_modules(project: Path, count: int) -> list[str]:
    """Write `count` test modules into the project and return their paths."""
    paths = [f"tests/test_selected_{number}.py" for number in range(count)]
    for path in paths:
        (project / path).write_text("def test_noop() -> None: ...\n", encoding="utf-8")
    return paths


@pytest.mark.parametrize(
    ("args", "workers"),
    [
        pytest.param((), [], id="full-suite"),
        pytest.param(("src/devops_cli/orphan.py",), [], id="full-suite-fallback"),
        pytest.param(("src/devops_cli/security/secrets.py",), [["-n", "0"]], id="narrowed"),
        pytest.param(
            ("-n", "3", "src/devops_cli/security/secrets.py"), [["-n", "3"]], id="workers-given"
        ),
    ],
)
def test_a_narrowed_run_chooses_its_workers_and_the_full_suite_keeps_addopts(
    monkeypatch: pytest.MonkeyPatch, project: Path, args: tuple[str, ...], workers: list[list[str]]
) -> None:
    """A narrowed run with no `-n` given runs serially; the full suite and the fallback to it
    pass no `-n`, so `addopts`' `-n logical` applies; a given `-n` is kept as it is (#1669)."""
    exit_code, spawns = _started_runs(monkeypatch, project, *args)

    assert (exit_code, [_worker_options(spawn.argv) for spawn in spawns]) == (0, [workers])


def test_a_selection_past_the_serial_limit_runs_on_the_capped_workers(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """A selection of up to DEFAULT_CI_TEST_SERIAL_MAX_FILES test modules runs serially, where
    starting workers costs more than it saves; one module more runs on
    DEFAULT_CI_TEST_NARROWED_WORKERS workers, never on every logical CPU (#1669)."""
    modules = _test_modules(project, DEFAULT_CI_TEST_SERIAL_MAX_FILES + 1)

    _code, at_limit = _started_runs(monkeypatch, project, *modules[:-1])
    _code, past_limit = _started_runs(monkeypatch, project, *modules)

    assert [_worker_options(spawn.argv) for spawn in at_limit + past_limit] == [
        [["-n", "0"]],
        [["-n", str(DEFAULT_CI_TEST_NARROWED_WORKERS)]],
    ]


def test_the_test_run_starts_pytest_in_a_session_of_its_own(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """`devops ci test`, narrowed or whole, starts pytest through asyncio in a session of its
    own, whose whole process group a timeout or a signal stops, and not through
    `subprocess.run`, whose timeout kills only `uv`: `refuse_nested_test_runs` fails the real
    `uv` that would start. The double sits at the stdlib, so `devops_cli.commands.ci` is left
    with no session runner of its own that a later test's patch would miss (#1669)."""
    _code, narrowed = _started_runs(monkeypatch, project, "src/devops_cli/security/secrets.py")
    _code, full = _started_runs(monkeypatch, project)

    assert (
        [("pytest" in run.argv, run.kwargs.get("start_new_session")) for run in narrowed + full],
        "run_subprocess_async" in vars(ci_module),
    ) == ([(True, True), (True, True)], False)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Coverage index test selection and fallback lifecycle
# ─────────────────────────────────────────────────────────────────────────────


def test_cli_selects_tests_from_coverage_index_and_names_selector(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """With an index mapping src/a.py to test_a.py and test_far.py, test runs both and names index."""
    (project / "src" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (project / "tests" / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")
    (project / "tests" / "test_far.py").write_text("def test_far(): pass\n", encoding="utf-8")

    index_path = resolve_coverage_index_path(project)
    index = CoverageIndex(
        covering_tests={"src/a.py": ["tests/test_a.py", "tests/test_far.py"]},
        source_hashes={"src/a.py": "h_a", "tests/test_a.py": "h_ta", "tests/test_far.py": "h_tf"},
        built_at=100.0,
    )
    save_index(index, index_path)

    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_worktree_blob_hashes",
        lambda root=Path("."): {
            "src/a.py": "h_a",
            "tests/test_a.py": "h_ta",
            "tests/test_far.py": "h_tf",
        },
    )

    result = runner.invoke(ci_app, ["test", "src/a.py"])

    targets = [arg for arg in called[0] if arg.startswith("tests/")]
    assert (result.exit_code, targets, "coverage index" in result.output) == (
        0,
        ["tests/test_a.py", "tests/test_far.py"],
        True,
    )


def test_cli_test_selects_tests_for_modified_files_since_build(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """When a file is modified since index build, its covering tests are also selected."""
    (project / "src" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (project / "src" / "b.py").write_text("B = 1\n", encoding="utf-8")
    (project / "tests" / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")
    (project / "tests" / "test_b.py").write_text("def test_b(): pass\n", encoding="utf-8")

    index_path = resolve_coverage_index_path(project)
    index = CoverageIndex(
        covering_tests={"src/a.py": ["tests/test_a.py"], "src/b.py": ["tests/test_b.py"]},
        source_hashes={
            "src/a.py": "h_a",
            "src/b.py": "h_b_old",
            "tests/test_a.py": "h_ta",
            "tests/test_b.py": "h_tb",
        },
        built_at=100.0,
    )
    save_index(index, index_path)

    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_worktree_blob_hashes",
        lambda root=Path("."): {
            "src/a.py": "h_a",
            "src/b.py": "h_b_new",
            "tests/test_a.py": "h_ta",
            "tests/test_b.py": "h_tb",
        },
    )

    result = runner.invoke(ci_app, ["test", "src/a.py"])

    targets = [arg for arg in called[0] if arg.startswith("tests/")]
    assert (result.exit_code, targets) == (
        0,
        ["tests/test_a.py", "tests/test_b.py"],
    )


def test_cli_test_added_test_file_selects_itself_without_fallback(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """A newly added test file selects itself and causes no fallback."""
    (project / "src" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (project / "tests" / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")
    (project / "tests" / "test_new.py").write_text("def test_new(): pass\n", encoding="utf-8")

    index_path = resolve_coverage_index_path(project)
    index = CoverageIndex(
        covering_tests={"src/a.py": ["tests/test_a.py"]},
        source_hashes={"src/a.py": "h_a", "tests/test_a.py": "h_ta"},
        built_at=100.0,
    )
    save_index(index, index_path)

    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_worktree_blob_hashes",
        lambda root=Path("."): {
            "src/a.py": "h_a",
            "tests/test_a.py": "h_ta",
            "tests/test_new.py": "h_new",
        },
    )

    result_direct = runner.invoke(ci_app, ["test", "tests/test_new.py", "--no-fallback"])
    targets_direct = [arg for arg in called[0] if arg.startswith("tests/")]

    result_drift = runner.invoke(ci_app, ["test", "src/a.py", "--no-fallback"])
    targets_drift = [arg for arg in called[1] if arg.startswith("tests/")]

    assert (
        result_direct.exit_code,
        targets_direct,
        result_drift.exit_code,
        targets_drift,
    ) == (
        0,
        ["tests/test_new.py"],
        0,
        ["tests/test_a.py", "tests/test_new.py"],
    )


def test_cli_test_deleted_test_file_is_dropped(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """A deleted test file in the index is not passed to pytest."""
    (project / "src" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (project / "tests" / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")

    index_path = resolve_coverage_index_path(project)
    index = CoverageIndex(
        covering_tests={"src/a.py": ["tests/test_a.py", "tests/test_far.py"]},
        source_hashes={"src/a.py": "h_a", "tests/test_a.py": "h_ta"},
        built_at=100.0,
    )
    save_index(index, index_path)

    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_worktree_blob_hashes",
        lambda root=Path("."): {"src/a.py": "h_a", "tests/test_a.py": "h_ta"},
    )

    result = runner.invoke(ci_app, ["test", "src/a.py"])

    targets = [arg for arg in called[0] if arg.startswith("tests/")]
    assert (result.exit_code, targets) == (0, ["tests/test_a.py"])


def test_cli_test_trigger_file_conftest_forces_full_run(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """tests/conftest.py forces full suite run with or without index, and fails on --no-fallback."""
    (project / "tests" / "conftest.py").write_text("# fixture\n", encoding="utf-8")
    (project / "src" / "a.py").write_text("A = 1\n", encoding="utf-8")

    index_path = resolve_coverage_index_path(project)
    index = CoverageIndex(
        covering_tests={"src/a.py": ["tests/test_a.py"]},
        source_hashes={"src/a.py": "h_a", "tests/conftest.py": "h_c"},
        built_at=100.0,
    )

    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_worktree_blob_hashes",
        lambda root=Path("."): {"src/a.py": "h_a", "tests/conftest.py": "h_c"},
    )

    res_no_idx = runner.invoke(ci_app, ["test", "tests/conftest.py"])
    targets_no_idx = [arg for arg in called[0] if arg.startswith("tests/")]

    save_index(index, index_path)
    res_with_idx = runner.invoke(ci_app, ["test", "tests/conftest.py"])
    targets_with_idx = [arg for arg in called[1] if arg.startswith("tests/")]

    res_no_fb = runner.invoke(ci_app, ["test", "tests/conftest.py", "--no-fallback"])

    assert (
        res_no_idx.exit_code,
        targets_no_idx,
        "tests/conftest.py" in res_no_idx.output,
        res_with_idx.exit_code,
        targets_with_idx,
        "tests/conftest.py" in res_with_idx.output,
        res_no_fb.exit_code,
        "tests/conftest.py" in res_no_fb.output,
    ) == (0, [], True, 0, [], True, 1, True)


def test_cli_test_a_support_module_that_registers_a_fixture_forces_full_run(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """A module under tests/support/ that defines a fixture forces the full suite with or
    without an index, as a conftest does, because the fixture it registers reaches tests that
    never import it; with --no-fallback it fails naming the file (#1312)."""
    support = "tests/support/identity.py"
    (project / "tests" / "support").mkdir()
    (project / support).write_text(_FIXTURE_MODULE, encoding="utf-8")
    (project / "tests" / "test_identity.py").write_text(
        "from tests.support.identity import identity\n", encoding="utf-8"
    )
    (project / "src" / "a.py").write_text("A = 1\n", encoding="utf-8")

    index_path = resolve_coverage_index_path(project)
    index = CoverageIndex(
        covering_tests={"src/a.py": ["tests/test_a.py"]},
        source_hashes={"src/a.py": "h_a", support: "h_s"},
        built_at=100.0,
    )

    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_worktree_blob_hashes",
        lambda root=Path("."): {"src/a.py": "h_a", support: "h_s"},
    )

    res_no_idx = runner.invoke(ci_app, ["test", support])
    targets_no_idx = [arg for arg in called[0] if arg.startswith("tests/")]

    save_index(index, index_path)
    res_with_idx = runner.invoke(ci_app, ["test", support])
    targets_with_idx = [arg for arg in called[1] if arg.startswith("tests/")]

    res_no_fb = runner.invoke(ci_app, ["test", support, "--no-fallback"])

    assert (
        res_no_idx.exit_code,
        targets_no_idx,
        support in res_no_idx.output,
        res_with_idx.exit_code,
        targets_with_idx,
        support in res_with_idx.output,
        res_no_fb.exit_code,
        support in res_no_fb.output,
    ) == (0, [], True, 0, [], True, 1, True)


def test_cli_test_a_plain_support_module_runs_the_test_modules_importing_it(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """A module under tests/support/ that registers nothing runs the test modules that import
    it, directly or through another support module, even under --no-fallback, and not the whole
    suite (#1312)."""
    (project / "tests" / "support").mkdir()
    (project / "tests" / "support" / "paths.py").write_text("ROOT = None\n", encoding="utf-8")
    (project / "tests" / "support" / "builders.py").write_text(
        "from tests.support.paths import ROOT\n", encoding="utf-8"
    )
    (project / "tests" / "test_paths.py").write_text(
        "from tests.support.paths import ROOT\n", encoding="utf-8"
    )
    (project / "tests" / "test_builders.py").write_text(
        "from tests.support.builders import ROOT\n", encoding="utf-8"
    )
    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)

    result = runner.invoke(ci_app, ["test", "tests/support/paths.py", "--no-fallback"])

    targets = [arg for cmd in called for arg in cmd if arg.startswith("tests")]
    assert (result.exit_code, targets) == (0, ["tests/test_builders.py", "tests/test_paths.py"])


@pytest.mark.parametrize("prefix", ["", "./"])
@pytest.mark.parametrize("name", sorted(CONST_FULL_RUN_TRIGGER_NAMES))
def test_cli_test_every_trigger_name_forces_a_full_run_as_given_or_after_a_dot_slash(
    monkeypatch: pytest.MonkeyPatch, project: Path, name: str, prefix: str
) -> None:
    """With no index, each trigger name refuses under --no-fallback and runs the full suite
    under --fallback, whether or not it is given after `./`: only that prefix is dropped, so
    `.python-version` keeps its leading dot and stays a trigger."""
    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr("devops_cli.core.coverage_index.load_index", lambda _: CoverageIndex())

    refused = runner.invoke(ci_app, ["test", f"{prefix}{name}", "--no-fallback"])
    full = runner.invoke(ci_app, ["test", f"{prefix}{name}", "--fallback"])

    targets = [arg for cmd in called for arg in cmd if arg.startswith("tests")]
    assert (refused.exit_code, name in refused.output, full.exit_code, len(called), targets) == (
        1,
        True,
        0,
        1,
        [],
    )


@pytest.mark.parametrize(
    ("given", "normalized"),
    [("./.python-version", ".python-version"), ("../x.py", "../x.py"), ("./src/a.py", "src/a.py")],
)
def test_a_relative_path_loses_only_a_leading_dot_slash(
    tmp_path: Path, given: str, normalized: str
) -> None:
    assert _normalize_repo_rel_path(given, tmp_path) == normalized


@pytest.mark.parametrize(
    ("trigger", "text"),
    [
        pytest.param("tests/support/identity.py", _FIXTURE_MODULE, id="tests/support/identity.py"),
        pytest.param("pyproject.toml", None, id="pyproject.toml"),
    ],
)
def test_cli_test_a_trigger_changed_since_the_index_was_built_selects_by_text(
    monkeypatch: pytest.MonkeyPatch, project: Path, trigger: str, text: str | None
) -> None:
    """Once a support module that registers a fixture, or the project's dependencies, changed
    and were committed, the index is stale, not a reason to run the whole suite on every later
    run: an unrelated source is selected by name and import, even under --no-fallback, and the
    warning names the file (#1312)."""
    if text is not None:
        (project / trigger).parent.mkdir(parents=True, exist_ok=True)
        (project / trigger).write_text(text, encoding="utf-8")
    secrets = "src/devops_cli/security/secrets.py"
    index = CoverageIndex(
        covering_tests={secrets: ["tests/test_secrets.py"]},
        source_hashes={secrets: "h_s", trigger: "h_old"},
        built_at=100.0,
    )
    save_index(index, resolve_coverage_index_path(project))
    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_worktree_blob_hashes",
        lambda root=Path("."): {secrets: "h_s", trigger: "h_new"},
    )

    result = runner.invoke(ci_app, ["test", secrets, "--no-fallback"])

    targets = [arg for cmd in called for arg in cmd if arg.startswith("tests/")]
    output = " ".join(result.output.split())
    assert (result.exit_code, targets, trigger in output, "stale" in output) == (
        0,
        ["tests/test_credential_flow.py", "tests/test_secrets.py"],
        True,
        True,
    )


def test_cli_test_a_helper_deleted_since_the_index_was_built_forces_a_full_run(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """A helper module under tests/ that the index knew and that is gone now, deleted or renamed
    away, may have registered a fixture and leaves its importers broken, neither of which can be
    read any more, so it forces the full suite, or a refusal naming it under --no-fallback,
    rather than only leaving the index stale (#1312)."""
    secrets = "src/devops_cli/security/secrets.py"
    gone = "tests/support/gone.py"
    index = CoverageIndex(
        covering_tests={secrets: ["tests/test_secrets.py"]},
        source_hashes={secrets: "h_s", gone: "h_gone"},
        built_at=100.0,
    )
    save_index(index, resolve_coverage_index_path(project))
    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_worktree_blob_hashes", lambda root=Path("."): {secrets: "h_s"}
    )

    refused = runner.invoke(ci_app, ["test", secrets, "--no-fallback"])
    full = runner.invoke(ci_app, ["test", secrets])

    targets = [arg for cmd in called for arg in cmd if arg.startswith("tests")]
    outputs = " ".join(" ".join(result.output.split()) for result in (refused, full))
    assert (
        refused.exit_code,
        gone in refused.output,
        full.exit_code,
        len(called),
        targets,
        "selected by name and import" in outputs,
    ) == (1, True, 0, 1, [], False)


def test_cli_test_helper_without_index_runs_importing_tests(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """With no index, tests/helper.py runs tests importing it and never passes helper itself."""
    (project / "tests" / "helper.py").write_text("HELPER = 1\n", encoding="utf-8")
    (project / "tests" / "test_importing.py").write_text(
        "from tests.helper import HELPER\n", encoding="utf-8"
    )
    (project / "tests" / "test_other.py").write_text("def test_x(): pass\n", encoding="utf-8")

    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)

    result = runner.invoke(ci_app, ["test", "tests/helper.py"])

    targets = [arg for arg in called[0] if arg.startswith("tests/")]
    assert (
        result.exit_code,
        targets,
        "tests/helper.py" not in targets,
    ) == (0, ["tests/test_importing.py"], True)


def test_cli_test_text_fallback_with_no_index_and_version_1_index(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """Text-based selector is attributed when index is missing or version 1."""
    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)

    res_no_idx = runner.invoke(ci_app, ["test", "src/devops_cli/security/secrets.py"])

    index_path = resolve_coverage_index_path(project)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text('{"format_version": 1, "covering_tests": {}}', encoding="utf-8")
    res_v1_idx = runner.invoke(ci_app, ["test", "src/devops_cli/security/secrets.py"])

    assert (
        res_no_idx.exit_code,
        "text-based selector" in res_no_idx.output,
        res_v1_idx.exit_code,
        "text-based selector" in res_v1_idx.output,
    ) == (0, True, 0, True)


def test_cli_test_unindexed_source_falls_back_per_source(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    """An index with src/a.py but not src/c.py runs index tests for a.py and text tests for c.py."""
    (project / "src" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (project / "src" / "c.py").write_text("C = 1\n", encoding="utf-8")
    (project / "tests" / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")
    (project / "tests" / "test_c.py").write_text("import c\n", encoding="utf-8")

    index_path = resolve_coverage_index_path(project)
    index = CoverageIndex(
        covering_tests={"src/a.py": ["tests/test_a.py"]},
        source_hashes={
            "src/a.py": "h_a",
            "src/c.py": "h_c",
            "tests/test_a.py": "h_ta",
            "tests/test_c.py": "h_tc",
        },
        built_at=100.0,
    )
    save_index(index, index_path)

    called: list[list[str]] = []
    monkeypatch.setattr("devops_cli.commands.ci._get_project_root", lambda: project)
    monkeypatch.setattr("devops_cli.commands.ci._run", lambda cmd, **kw: called.append(cmd) or True)
    monkeypatch.setattr(
        "devops_cli.ci.cache.compute_worktree_blob_hashes",
        lambda root=Path("."): {
            "src/a.py": "h_a",
            "src/c.py": "h_c",
            "tests/test_a.py": "h_ta",
            "tests/test_c.py": "h_tc",
        },
    )

    result = runner.invoke(ci_app, ["test", "src/a.py", "src/c.py"])

    targets = [arg for arg in called[0] if arg.startswith("tests/")]
    assert (
        result.exit_code,
        targets,
        "src/a.py → tests/test_a.py (coverage index)" in result.output,
        "src/c.py → tests/test_c.py (text-based selector)" in result.output,
    ) == (
        0,
        ["tests/test_a.py", "tests/test_c.py"],
        True,
        True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Checks that run in the full gate only
# ─────────────────────────────────────────────────────────────────────────────

# The ban on reading `__file__` and importing a test module, which parses every test file.
_TEST_MODULE_BAN = Path("tests/invariants/test_test_module_independence.py")


def test_no_narrowed_selection_over_a_changed_source_or_helper_runs_the_test_module_ban(
    tmp_path: Path,
) -> None:
    """The ban on reading `__file__` and importing a test module parses every test file, so it
    runs only in the full gate (#1312). In a repository whose `src/` is this one's and whose
    `tests/` holds the ban's module beside every other module of this suite but its test
    modules, no selection short of the whole suite reaches it: not one over every source
    module, by name or import; not one over every helper module that does not reach the whole
    suite, the union of their own selections; and not one over each conftest, which may narrow
    to its own directory. So a narrowed `devops ci test` or `devops test run --changed` runs it
    only when given its module or when it runs the whole suite."""
    (tmp_path / "src").symlink_to(REPO_ROOT / "src", target_is_directory=True)
    shared = [
        path.relative_to(REPO_ROOT)
        for path in sorted(TESTS_ROOT.rglob("*.py"))
        if not is_test_module(path)
    ]
    for relative in (_TEST_MODULE_BAN, *shared):
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative, tmp_path / relative)
    imports = SuiteImports(tmp_path)
    conftests = [path for path in shared if path.name == CONST_CONFTEST_FILENAME]
    helpers = [path for path in shared if path not in conftests and path.name != "__init__.py"]
    selections = {
        "every source module": [
            path.relative_to(REPO_ROOT) for path in sorted((REPO_ROOT / "src").rglob("*.py"))
        ],
        "every helper module short of the whole suite": [
            path for path in helpers if not imports.reaches_every_test(path)
        ],
        **{str(path): [path] for path in conftests},
    }
    reaching_the_ban = {
        changed: targets
        for changed, paths in selections.items()
        if (targets := select_tests_for_sources(paths, tmp_path).pytest_targets())
        != [CONST_TESTS_ROOT_DIR]
        and any(_TEST_MODULE_BAN.is_relative_to(target) for target in targets)
    }
    assert reaching_the_ban == {}


# The names by which a conftest or a plugin keeps files out of collection.
_COLLECTION_FILTERS = frozenset({"collect_ignore", "collect_ignore_glob", "pytest_ignore_collect"})


def _bound_name(node: ast.AST) -> str | None:
    """The name a definition, an assignment target or an import binds, or None."""
    match node:
        case ast.FunctionDef(name=name) | ast.AsyncFunctionDef(name=name) | ast.ClassDef(name=name):
            return name
        case ast.Name(id=name, ctx=ast.Store()):
            return name
        case ast.alias(name=name, asname=asname):
            return asname or name
    return None


def _collection_filters() -> list[str]:
    """`path:line` of each binding of a collection filter in a conftest under `tests/` or in a
    support module, which registration makes a plugin."""
    support = TESTS_ROOT / "support"
    plugins = sorted({*TESTS_ROOT.rglob(CONST_CONFTEST_FILENAME), *support.rglob("*.py")})
    return [
        f"{path.relative_to(REPO_ROOT).as_posix()}:{node.lineno}"
        for path in plugins
        for node in ast.walk(ast.parse(path.read_bytes()))
        if _bound_name(node) in _COLLECTION_FILTERS
    ]


def test_the_full_gate_collects_the_test_module_ban(pytestconfig: pytest.Config) -> None:
    """`uv run devops ci`, whose test step CI runs, collects the ban's module (#1312): its
    test step hands pytest exactly these options and `pyproject.toml` exactly these `addopts`,
    none of which names a path, ignores, deselects or selects by keyword or marker; pytest
    collects `test_*.py` and `*_test.py` under `tests`; and no conftest or support plugin keeps
    a file out of collection. A new option or filter fails this until its effect on what the
    full gate collects is weighed."""
    gate = get_check_spec("test").cmd
    assert (
        gate[gate.index("pytest") + 1 :],
        pytestconfig.getini("addopts"),
        pytestconfig.getini("testpaths"),
        pytestconfig.getini("python_files"),
        _collection_filters(),
    ) == (
        [
            f"--durations={CONST_CI_SLOWEST_TESTS_SHOWN}",
            "--cov=src",
            "--cov-report=term-missing",
        ],
        [
            *("-n", "logical", "--dist", "worksteal"),
            *("-p", "no:logfire", "-p", "no:pytest_logfire", "-p", "no:randomly"),
            "--hypothesis-profile=ci",
        ],
        [CONST_TESTS_ROOT_DIR],
        ["test_*.py", "*_test.py"],
        [],
    )
