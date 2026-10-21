"""A test that hangs fails at the suite's per-test timeout, and the run carries on (#1669).

pytest-timeout bounds each test, with `timeout_method = "signal"`: a SIGALRM fails the stuck test
in its own process, so neither the run nor an xdist worker goes down with it.
"""

from __future__ import annotations

import re
import tomllib

import pytest

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from tests.support.paths import REPO_ROOT
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

pytest_plugins = ("pytester",)
pytestmark = pytest.mark.live("python")

# The inner runs' bound, and a sleep that outlives it and every handoff wait, so the sleeping test
# can only end at the timeout (tests/support/waits.py).
INNER_TIMEOUT_SECONDS = 1
HANG_SECONDS = 2 * THREAD_HANDOFF_BOUND_SECONDS

HANG_THEN_PASS = f"""
import time


def test_hangs() -> None:
    time.sleep({HANG_SECONDS})


def test_after_the_hang() -> None:
    pass
"""

TIMEOUT_REPORT = (
    f"FAILED test_hang.py::test_hangs - Failed: Timeout (>{INNER_TIMEOUT_SECONDS:.1f}s) "
    "from pytest-timeout.*"
)
# xdist's verbose line for a finished test: the worker that ran it, the progress, the outcome.
WORKER_OUTCOME = re.compile(r"\[(gw\d+)\] \[\s*\d+%\] (PASSED|FAILED) test_hang\.py::(\w+)")


@pytest.fixture
def hanging_suite(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> pytest.Pytester:
    """A suite whose first test hangs and whose second passes, under a one-second signal timeout.

    The inner runs load only the plugins they name: autoloading every installed plugin costs
    seconds and warns about pytest-asyncio's unset loop scope."""
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    pytester.makeini(f"[pytest]\ntimeout = {INNER_TIMEOUT_SECONDS}\ntimeout_method = signal\n")
    pytester.makepyfile(test_hang=HANG_THEN_PASS)
    return pytester


def test_a_hanging_test_fails_at_the_timeout_and_the_next_test_passes(
    hanging_suite: pytest.Pytester,
) -> None:
    """The sleeping test fails with pytest-timeout's report, and the test after it still runs
    and passes."""
    result = hanging_suite.runpytest_subprocess("-p", "pytest_timeout", "-p", "no:cacheprovider")

    result.stdout.fnmatch_lines([TIMEOUT_REPORT])
    assert (result.ret, result.parseoutcomes()) == (1, {"failed": 1, "passed": 1})


def test_a_hanging_test_under_xdist_fails_without_taking_its_worker_down(
    hanging_suite: pytest.Pytester,
) -> None:
    """Under `-n 2`, the worker that ran the hanging test reports pytest-timeout's failure and
    then runs the next test of the file itself, so no worker crashed and was replaced."""
    result = hanging_suite.runpytest_subprocess(
        *("-p", "pytest_timeout", "-p", "xdist", "-p", "no:cacheprovider"),
        *("-n", "2", "--dist", "loadfile", "-v"),
    )

    outcomes = WORKER_OUTCOME.findall(result.stdout.str())
    result.stdout.fnmatch_lines([TIMEOUT_REPORT])
    assert (
        result.ret,
        result.parseoutcomes(),
        [(outcome, test) for _worker, outcome, test in outcomes],
        len({worker for worker, _outcome, _test in outcomes}),
    ) == (
        1,
        {"failed": 1, "passed": 1},
        [("FAILED", "test_hangs"), ("PASSED", "test_after_the_hang")],
        1,
    )


def test_the_suite_bounds_every_test_with_a_signal_timeout_between_its_waits_and_its_run(
    request: pytest.FixtureRequest,
) -> None:
    """`[tool.pytest.ini_options]` sets a per-test `timeout` and `timeout_method = "signal"`, and
    this very session runs under them, with the plugin loaded. The bound is a hang bound: above
    the handoff bound a failing wait sits out, so such a test fails on its own assertion, and
    under half the run's timeout, so a hung test is reported by name before the whole run is
    stopped."""
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    ini = pyproject["tool"]["pytest"]["ini_options"]
    config = request.config
    bound = float(ini.get("timeout", 0))

    assert (
        ini.get("timeout_method"),
        THREAD_HANDOFF_BOUND_SECONDS < bound < DEFAULT_SUBPROCESS_TIMEOUT_SECONDS / 2,
        config.pluginmanager.hasplugin("timeout"),
        (float(config.getini("timeout")), config.getini("timeout_method")),
    ) == ("signal", True, True, (bound, "signal"))
