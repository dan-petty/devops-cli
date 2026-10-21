"""The suite's floor: HOME isolated before devops-cli is imported, then each submodule and
subpackage of `tests.support` that could give pytest a fixture or hook registered as a plugin
(#1311, #1312, #1735).

The root conftest names this module in its one `pytest_plugins` entry. devops-cli binds HOME
when it is imported, so a support module that imports devops-cli must load after HOME is
isolated; listing the support modules in `pytest_plugins` would load them before
`pytest_configure` runs, so they are registered here, from a trylast `pytest_configure`, after
the isolation. This module imports nothing from devops-cli at its top; the registration imports
the test selector's check once HOME is isolated. A support module added later is registered
with no list to edit.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import os
import pkgutil
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

from tests import support


def is_xdist_worker(config: pytest.Config) -> bool:
    """Report whether the pytest process is an xdist worker rather than the controller."""
    return getattr(config, "workerinput", None) is not None


def isolate_home(config: pytest.Config) -> None:
    """Isolate HOME into an empty directory under pytest basetemp, with a git identity on
    `example.com`, and record it for the workspace tripwire's worker-home check (#1311)."""
    factory = getattr(config, "_tmp_path_factory", None)
    if factory is None:
        from _pytest.tmpdir import TempPathFactory

        factory = TempPathFactory.from_config(config, _ispytest=True)
        config._tmp_path_factory = factory  # type: ignore[attr-defined]

    basetemp = factory.getbasetemp()
    is_worker = is_xdist_worker(config)
    home_dir = basetemp / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    gitconfig = home_dir / ".gitconfig"
    if not gitconfig.exists():
        gitconfig.write_text(
            "[user]\n\tname = Test User\n\temail = test@example.com\n",
            encoding="utf-8",
        )
    os.environ["HOME"] = str(home_dir)

    shared = basetemp.parent if is_worker else basetemp
    config._tripwire_basetemp = shared  # type: ignore[attr-defined]
    reg = shared / ".worker_homes"
    try:
        with open(reg, "a", encoding="utf-8") as f:
            f.write(f"{home_dir}\n")
    except OSError:
        pass


def _registered_names(module: ModuleType) -> list[str]:
    """What pytest takes from a plugin module, read as pytest reads it, each name `dir()` lists
    fetched with `safe_getattr`, a module-level `__getattr__` and `__dir__` included: each
    attribute whose type is `FixtureFunctionDefinition`, whatever made it, and each `pytest_*`
    routine."""
    from _pytest.compat import safe_getattr
    from _pytest.fixtures import FixtureFunctionDefinition

    from devops_cli.config.constants import CONST_PYTEST_HOOK_PREFIX

    def registers(name: str) -> bool:
        value = safe_getattr(module, name, None)
        hook = name.startswith(CONST_PYTEST_HOOK_PREFIX) and inspect.isroutine(value)
        return hook or type(value) is FixtureFunctionDefinition

    return sorted(filter(registers, dir(module)))


def _refuse_a_test_file(name: str) -> None:
    """Fail the run on a test module or conftest under the support package, which registration
    would make a plugin of every test while the test selector takes a test module to reach
    only itself and a conftest to reach its own directory (#1312)."""
    from devops_cli.config.constants import CONST_CONFTEST_FILENAME, CONST_TEST_FILE_PREFIX

    leaf = name.rpartition(".")[2]
    if leaf.startswith(CONST_TEST_FILE_PREFIX) or leaf == Path(CONST_CONFTEST_FILENAME).stem:
        raise pytest.UsageError(
            f"{name}: a test module or conftest under the support package would register its "
            "fixtures and hooks for every test, which the test selector does not see. Move it "
            "out of the support package."
        )


def _check_registration(module: ModuleType, sees: Callable[[Path], bool]) -> None:
    """Fail the run when pytest takes a fixture or hook from `module` that `sees`, the test
    selector's reading of its source, does not find there (#1312)."""
    names = _registered_names(module)
    source = getattr(module, "__file__", None)
    if names and (source is None or not sees(Path(source))):
        found = ", ".join(f"{module.__name__}.{name}" for name in names)
        raise pytest.UsageError(
            f"{found}: pytest registers a fixture or hook that the test selector cannot find in "
            f"the source of {module.__name__}, so a narrowed run would miss the tests it reaches. "
            "Define each fixture with `pytest.fixture` in the module itself, and import no other "
            "module's fixture."
        )


def _may_hand_pytest_a_plugin(source: Path, package: str) -> bool:
    """Report whether a support module's source could give pytest a fixture or hook in a way the
    test selector cannot read: it imports pytest or another module of `package`, or answers
    attribute lookups itself with a module-level `__getattr__` or `__dir__` (#1735)."""
    from devops_cli.config.constants import CONST_PYTEST_MODULES

    def names_pytest_or_support(module: str) -> bool:
        return module.partition(".")[0] in CONST_PYTEST_MODULES or (
            module == package or module.startswith(f"{package}.")
        )

    tree = ast.parse(source.read_text(encoding="utf-8"))
    imported = [
        node.level > 0 or names_pytest_or_support(node.module or "")
        if isinstance(node, ast.ImportFrom)
        else any(names_pytest_or_support(alias.name) for alias in node.names)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    answers_lookups = any(
        isinstance(node, ast.FunctionDef) and node.name in {"__getattr__", "__dir__"}
        for node in tree.body
    )
    return any(imported) or answers_lookups


def _is_plain_helper(name: str, package: str, defines: Callable[[Path], bool]) -> bool:
    """Report whether support module `name` is a plain helper: its source defines no fixture or
    hook the test selector sees and could hand pytest none another way. Such a module loads when
    a test imports it, not at every start-up (#1735)."""
    spec = importlib.util.find_spec(name)
    source = Path(spec.origin) if spec is not None and spec.origin else None
    return (
        source is not None
        and source.suffix == ".py"
        and not defines(source)
        and not _may_hand_pytest_a_plugin(source, package)
    )


def register_support_plugins(
    pluginmanager: pytest.PytestPluginManager, package: ModuleType
) -> None:
    """Register each submodule and subpackage of `package` that could give pytest a fixture or
    hook as a pytest plugin, so a fixture or hook one defines reaches every test. A plain helper,
    which defines none the test selector sees and imports neither pytest nor another support
    module, is left for its importers to load (#1735). One registration imports and that fails to
    import fails the registration, named by `import_plugin`, and so do a test module or conftest
    under the package, and a module in which pytest finds a fixture or hook that the test
    selector's `defines_fixture_or_hook` does not, in a narrowed run as in the full one."""
    from devops_cli.core.test_selection import defines_fixture_or_hook

    prefix = f"{package.__name__}."
    for info in pkgutil.walk_packages(package.__path__, prefix):
        _refuse_a_test_file(info.name)
        if _is_plain_helper(info.name, package.__name__, defines_fixture_or_hook):
            continue
        pluginmanager.import_plugin(info.name)
        module = pluginmanager.get_plugin(info.name)
        if isinstance(module, ModuleType):
            _check_registration(module, defines_fixture_or_hook)


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config) -> None:
    """Isolate HOME, then register the support modules, so that one importing devops-cli binds
    its paths under the isolated HOME (#1311, #1312)."""
    isolate_home(config)
    register_support_plugins(config.pluginmanager, support)
