"""Unit tests for the test session workspace isolation tripwire (Issue #749), and for the
registration that loads it and every other module under `tests/support/` (#1312)."""

from __future__ import annotations

import importlib
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.support.bootstrap import is_xdist_worker, register_support_plugins
from tests.support.paths import REPO_ROOT
from tests.support.workspace_tripwire import (
    check_config_diff,
    check_forbidden_test_paths,
    check_tracked_diff,
    check_worker_home_leaks,
    evaluate_workspace_tripwire,
    find_location_leaks,
    get_git_tracked_files,
    pytest_sessionfinish,
    pytest_sessionstart,
    pytest_terminal_summary,
    snapshot_tracked_files,
    worker_home_locations,
)

pytest_plugins = ("pytester",)

_BOOTSTRAP_CONFTEST = 'pytest_plugins = ("tests.support.bootstrap",)\n'
_SUPPORT_UNDER_TEST = "registered_support_under_test"


def test_support_fixtures_reach_a_nested_test_and_load_after_home_is_isolated(
    pytester: pytest.Pytester,
) -> None:
    """A conftest whose only line names `tests.support.bootstrap` gives a test two directories
    down a fixture that `tests.support.github_identity` defines, and that module, which imports
    devops-cli at its top, loads after HOME is isolated: devops-cli binds its config directory
    under the isolated HOME, which it would not had the module loaded through `pytest_plugins`
    or `-p`, before `pytest_configure` (#1312)."""
    pytester.makeconftest(_BOOTSTRAP_CONFTEST)
    pytester.makepyfile(
        **{
            "a/b/test_x": """
import os
from pathlib import Path

from devops_cli.config.constants import CONST_CONFIG_DIR
from devops_cli.core import process


def test_a_support_fixture_reaches_a_nested_test(no_github_identity: None) -> None:
    assert process._github_token is None


def test_devops_cli_binds_its_config_directory_under_the_isolated_home() -> None:
    assert CONST_CONFIG_DIR.is_relative_to(Path(os.environ["HOME"]))
"""
        }
    )
    res = pytester.runpytest_subprocess("-o", f"pythonpath={REPO_ROOT}")
    res.assert_outcomes(passed=2)


@pytest.fixture
def support_under_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Where to write a package that `tmp_path` makes importable, forgotten by the import system
    after the test."""
    monkeypatch.syspath_prepend(tmp_path)
    yield tmp_path / _SUPPORT_UNDER_TEST
    for name in [name for name in sys.modules if name.split(".")[0] == _SUPPORT_UNDER_TEST]:
        del sys.modules[name]


def _write_package(root: Path, files: dict[str, str]) -> ModuleType:
    """Write a package's files under `root` and import the package."""
    for relative, text in files.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8")
    return importlib.import_module(_SUPPORT_UNDER_TEST)


def test_a_support_package_that_fails_to_import_fails_the_registration_naming_it(
    support_under_test: Path,
) -> None:
    """Registration walks into subpackages and imports every module there, and one that fails
    to import fails the registration, named by `import_plugin`, instead of being skipped
    (#1312)."""
    package = _write_package(
        support_under_test,
        {
            "__init__.py": "",
            "plain.py": "VALUE = 1\n",
            "broken/__init__.py": "",
            "broken/inner.py": "raise ImportError('a name the module needs is gone')\n",
        },
    )
    with pytest.raises(ImportError) as raised:
        register_support_plugins(pytest.PytestPluginManager(), package)
    assert (
        f'"{_SUPPORT_UNDER_TEST}.broken.inner"' in str(raised.value),
        "a name the module needs is gone" in str(raised.value),
    ) == (True, True)


_FIXTURE_DEFS = "import pytest\n\n\n@pytest.fixture\ndef identity() -> str:\n    return 'nobody'\n"


@pytest.mark.parametrize(
    ("files", "named"),
    [
        pytest.param(
            {
                "factories.py": (
                    "import pytest\n\n\ndef autouse(function):\n"
                    "    return pytest.fixture(autouse=True)(function)\n"
                ),
                "guarded.py": (
                    f"from {_SUPPORT_UNDER_TEST}.factories import autouse\n\n\n"
                    "@autouse\ndef guard() -> None:\n    pass\n"
                ),
            },
            "guarded.guard",
            id="decorator-factory",
        ),
        pytest.param(
            {
                "hidden.py": (
                    "import pytest\n\nmake = getattr(pytest, 'fixture')\n\n\n"
                    "@make\ndef hidden() -> str:\n    return 'nobody'\n"
                )
            },
            "hidden.hidden",
            id="getattr",
        ),
        pytest.param(
            {
                "defs.py": _FIXTURE_DEFS,
                "renamed.py": f"from {_SUPPORT_UNDER_TEST}.defs import identity as who\n",
            },
            "renamed.who",
            id="re-exported-under-a-new-name",
        ),
        pytest.param(
            {
                "defs.py": _FIXTURE_DEFS,
                "lazy.py": (
                    "import importlib\n\n\ndef __getattr__(name: str) -> object:\n"
                    "    if name == 'who':\n"
                    f"        return importlib.import_module('{_SUPPORT_UNDER_TEST}.defs').identity\n"
                    "    raise AttributeError(name)\n\n\n"
                    "def __dir__() -> list[str]:\n    return ['who']\n"
                ),
            },
            "lazy.who",
            id="handed-out-by-a-module-getattr",
        ),
    ],
)
def test_registration_fails_naming_a_fixture_the_test_selector_cannot_see(
    support_under_test: Path, files: dict[str, str], named: str
) -> None:
    """A support module that pytest would give a fixture its source does not name, through a
    decorator factory, `getattr`, an import under a new name or a module-level `__getattr__`
    that pytest reads through `dir()`, fails the registration naming it, in a narrowed run as in
    the full one: the test selector would take the module for one that reaches only its
    importers (#1312)."""
    package = _write_package(support_under_test, {"__init__.py": "", **files})
    with pytest.raises(pytest.UsageError) as raised:
        register_support_plugins(pytest.PytestPluginManager(), package)
    assert f"{_SUPPORT_UNDER_TEST}.{named}" in str(raised.value)


@pytest.mark.parametrize("name", ["test_hidden", "conftest"])
def test_a_test_module_or_conftest_under_the_support_package_fails_the_registration(
    support_under_test: Path, name: str
) -> None:
    """The test selector takes a test module for one no other test reaches and a conftest for
    one that reaches its own directory, so registration, which would make either a plugin of
    every test, refuses one under the support package, naming it (#1312)."""
    package = _write_package(
        support_under_test,
        {"__init__.py": "", "inner/__init__.py": "", f"inner/{name}.py": _FIXTURE_DEFS},
    )
    with pytest.raises(pytest.UsageError) as raised:
        register_support_plugins(pytest.PytestPluginManager(), package)
    assert f"{_SUPPORT_UNDER_TEST}.inner.{name}" in str(raised.value)


def test_a_support_module_that_defines_its_fixture_with_the_decorator_registers(
    support_under_test: Path,
) -> None:
    """A fixture defined with `pytest.fixture` in the module itself registers (#1312)."""
    package = _write_package(support_under_test, {"__init__.py": "", "defs.py": _FIXTURE_DEFS})
    pluginmanager = pytest.PytestPluginManager()
    register_support_plugins(pluginmanager, package)
    assert pluginmanager.get_plugin(f"{_SUPPORT_UNDER_TEST}.defs") is not None


def test_devops_cli_binds_its_config_directory_under_the_home_bootstrap_isolated() -> None:
    """In this run, under the real root conftest, devops-cli's config directory lies under the
    HOME bootstrap isolated: nothing imported devops-cli before the isolation (#1311, #1312)."""
    from devops_cli.config.constants import CONST_CONFIG_DIR

    assert CONST_CONFIG_DIR.is_relative_to(Path(os.environ["HOME"]))


def test_is_xdist_worker_detection() -> None:
    """Verify is_xdist_worker accurately distinguishes controller from xdist workers."""
    controller_cfg = pytest.Config.fromdictargs({}, [])
    worker_cfg = SimpleNamespace(workerinput={"workerid": "gw0"})

    assert (
        is_xdist_worker(controller_cfg),
        is_xdist_worker(worker_cfg),  # type: ignore[arg-type]
    ) == (False, True)


def test_get_git_tracked_files_resolves_repo(tmp_path: Path) -> None:
    """Verify get_git_tracked_files executes git ls-files and handles non-git folders gracefully."""
    tracked = get_git_tracked_files(tmp_path)
    assert tracked == []


def test_snapshot_tracked_files_captures_mtime_and_size(tmp_path: Path) -> None:
    """Verify snapshot_tracked_files records stat stamps for existing files only."""
    f1 = tmp_path / "file1.txt"
    f1.write_text("hello", encoding="utf-8")
    st = f1.stat()

    stamps = snapshot_tracked_files(tmp_path, ["file1.txt", "nonexistent.txt"])
    assert stamps == {"file1.txt": (st.st_mtime_ns, st.st_size)}


def test_check_config_diff_permutations(tmp_path: Path) -> None:
    """Verify check_config_diff identifies creation, deletion, and modification states."""
    repo_dir = tmp_path / "custom_repo"
    repo_dir.mkdir()
    cfg = repo_dir / "config.yaml"

    # Case 1: Unchanged (absent)
    res_absent = check_config_diff(repo_dir, None)

    # Case 2: Created
    cfg.write_text("foo: 1", encoding="utf-8")
    res_created = check_config_diff(repo_dir, None)

    # Case 3: Unchanged (present)
    res_unchanged = check_config_diff(repo_dir, b"foo: 1")

    # Case 4: Modified
    cfg.write_text("foo: 2", encoding="utf-8")
    res_modified = check_config_diff(repo_dir, b"foo: 1")

    # Case 5: Deleted
    cfg.unlink()
    res_deleted = check_config_diff(repo_dir, b"foo: 1")

    assert (
        res_absent,
        res_created,
        res_unchanged,
        res_modified,
        res_deleted,
    ) == (
        None,
        "config.yaml (created by tests)",
        None,
        "config.yaml (content modified by tests)",
        "config.yaml (deleted by tests)",
    )


def test_check_tracked_diff_detects_mutations(tmp_path: Path) -> None:
    """Verify check_tracked_diff detects deleted and modified tracked files."""
    f1 = tmp_path / "tracked1.py"
    f1.write_text("print('v1')", encoding="utf-8")
    init_st1 = f1.stat()

    f2 = tmp_path / "tracked2.py"
    f2.write_text("print('orig')", encoding="utf-8")
    init_st2 = f2.stat()

    snapshot = {
        "tracked1.py": (init_st1.st_mtime_ns, init_st1.st_size),
        "tracked2.py": (init_st2.st_mtime_ns, init_st2.st_size),
    }

    # Simulate f1 modified and f2 deleted
    f1.write_text("print('v2-modified')", encoding="utf-8")
    f2.unlink()

    diffs = check_tracked_diff(tmp_path, snapshot)
    assert diffs == [
        "tracked1.py (modified by tests)",
        "tracked2.py (deleted by tests)",
    ]


def test_check_tracked_diff_compares_content_in_a_linked_worktree(
    nested_worktree: tuple[Path, Path],
) -> None:
    """In a linked worktree, where `.git` is a file, a tracked file rewritten unchanged is not
    a mutation and an edited one is. `devops ci` regenerates the docs while the tests run, so
    requiring `.git/index` failed the gate from every worktree."""
    _, worktree = nested_worktree
    touched, edited = worktree / ".gitignore", worktree / "pyproject.toml"
    snapshot = snapshot_tracked_files(worktree, [".gitignore", "pyproject.toml"])

    stamp = touched.stat()
    os.utime(touched, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000_000))
    edited.write_text(edited.read_text(encoding="utf-8") + "# edited\n", encoding="utf-8")

    assert ((worktree / ".git").is_file(), check_tracked_diff(worktree, snapshot)) == (
        True,
        ["pyproject.toml (modified by tests)"],
    )


def test_check_forbidden_test_paths_detects_test_artifacts(tmp_path: Path) -> None:
    """Verify check_forbidden_test_paths identifies test artifacts created in project root."""
    repo_dir = tmp_path / "custom_repo"
    repo_dir.mkdir()

    # Initially empty
    assert check_forbidden_test_paths(repo_dir) == []

    # Create forbidden test paths
    (repo_dir / "test_config.yaml").write_text("dummy", encoding="utf-8")
    (repo_dir / ".data").mkdir(parents=True, exist_ok=True)
    (repo_dir / ".data" / "test_llm_cache").mkdir(parents=True, exist_ok=True)

    violations = check_forbidden_test_paths(repo_dir)
    assert (
        "test_config.yaml (test path found in project directory)" in violations,
        ".data/test_llm_cache (test path found in project directory)" in violations,
    ) == (True, True)


def test_evaluate_workspace_tripwire_aggregates_failures(tmp_path: Path) -> None:
    """Verify evaluate_workspace_tripwire aggregates config, tracked, and forbidden failures."""
    repo_dir = tmp_path / "eval_repo"
    repo_dir.mkdir()
    (repo_dir / "config.yaml").write_text("bad: true", encoding="utf-8")
    (repo_dir / "test_config.yaml").write_text("leak: true", encoding="utf-8")

    snapshot: dict[str, Any] = {
        "repo_root": repo_dir,
        "config_state": None,
        "tracked_snapshot": {},
    }
    failures = evaluate_workspace_tripwire(snapshot)

    assert (
        "config.yaml (created by tests)" in failures,
        "test_config.yaml (test path found in project directory)" in failures,
    ) == (True, True)


def test_session_hooks_lifecycle(tmp_path: Path) -> None:
    """Verify pytest_sessionstart and pytest_sessionfinish hooks record and trigger failure."""
    session = MagicMock()
    session.config = SimpleNamespace(rootpath=tmp_path)

    # Session start snapshots pytest's root directory
    pytest_sessionstart(session)
    assert (
        hasattr(session.config, "_tripwire_snapshot"),
        session.config._tripwire_snapshot["repo_root"],
    ) == (True, tmp_path)

    # Worker skips finish
    worker_session = MagicMock()
    worker_session.config = SimpleNamespace(workerinput={"workerid": "gw0"})
    pytest_sessionfinish(worker_session, 0)
    assert not hasattr(worker_session.config, "_tripwire_failures")

    # Controller with simulated failure
    repo_dir = tmp_path / "sim_repo"
    repo_dir.mkdir()
    cfg_leak = SimpleNamespace(
        _tripwire_snapshot={
            "repo_root": repo_dir,
            "config_state": b"initial",
            "tracked_snapshot": {},
        }
    )
    fail_session = MagicMock()
    fail_session.config = cfg_leak
    pytest_sessionfinish(fail_session, 0)
    assert (
        fail_session.exitstatus,
        getattr(cfg_leak, "_tripwire_failures", []),
    ) == (
        pytest.ExitCode.TESTS_FAILED,
        ["config.yaml (deleted by tests)"],
    )


def test_terminal_summary_reporting() -> None:
    """Verify pytest_terminal_summary prints section on failure and skips on workers."""
    reporter = MagicMock()

    # Worker skips
    worker_cfg = SimpleNamespace(workerinput={"workerid": "gw0"})
    pytest_terminal_summary(reporter, 0, worker_cfg)  # type: ignore[arg-type]
    assert not reporter.section.called

    # Controller with failures writes section
    ctrl_cfg = SimpleNamespace(_tripwire_failures=["config.yaml (created by tests)"])
    pytest_terminal_summary(reporter, 0, ctrl_cfg)  # type: ignore[arg-type]
    assert (
        reporter.section.called,
        reporter.write_line.called,
    ) == (True, True)


def test_worker_home_locations_and_leaks(tmp_path: Path) -> None:
    """Verify worker_home_locations identifies key paths and find_location_leaks detects leaks (#1311)."""
    fake_home = tmp_path / "home"
    locs = worker_home_locations(fake_home)
    assert locs == (
        fake_home / ".config" / "devops-cli",
        fake_home / ".local" / "share" / "devops-cli",
        fake_home / ".ssh",
        fake_home / ".local" / "bin",
    )

    # Empty location does not leak
    cfg_dir = fake_home / ".config" / "devops-cli"
    assert (
        find_location_leaks(cfg_dir),
        check_worker_home_leaks({"worker_homes": [fake_home]}),
    ) == ([], [])

    # Leaked file in config dir
    cfg_dir.mkdir(parents=True, exist_ok=True)
    leak_file = cfg_dir / "test.yaml"
    leak_file.write_text("leak: true", encoding="utf-8")

    # Leaked directory in ssh
    ssh_dir = fake_home / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)

    leaks = check_worker_home_leaks({"worker_homes": [fake_home]})
    assert (
        f"{leak_file} (state left in worker home)" in leaks,
        f"{ssh_dir} (state left in worker home)" in leaks,
    ) == (True, True)


def test_tripwire_fails_when_test_writes_under_const_config_dir(
    pytester: pytest.Pytester,
) -> None:
    """A pytester test shows a test that writes under CONST_CONFIG_DIR failing the session with that path (#1311)."""
    pytester.makeconftest(_BOOTSTRAP_CONFTEST)
    pytester.makepyfile(
        """
import pytest
from devops_cli.config.constants import CONST_CONFIG_DIR

def test_mutates_config_dir():
    leak = CONST_CONFIG_DIR / "leaked_settings.yaml"
    leak.parent.mkdir(parents=True, exist_ok=True)
    leak.write_text("leaked: true\\n", encoding="utf-8")
"""
    )
    res = pytester.runpytest_subprocess("-o", f"pythonpath={REPO_ROOT}")
    stdout = res.stdout.str()
    assert (
        res.ret == pytest.ExitCode.TESTS_FAILED,
        "TRIPWIRE FAILURE: Workspace mutated during test run" in stdout,
        "leaked_settings.yaml" in stdout,
    ) == (True, True, True)


def test_tripwire_passes_when_no_leaks(
    pytester: pytest.Pytester,
) -> None:
    """Verify tripwire succeeds when test creates no state in devops-cli locations (#1311)."""
    pytester.makeconftest(_BOOTSTRAP_CONFTEST)
    pytester.makepyfile("def test_clean(): pass\n")
    res = pytester.runpytest_subprocess("-o", f"pythonpath={REPO_ROOT}")
    assert res.ret == pytest.ExitCode.OK
