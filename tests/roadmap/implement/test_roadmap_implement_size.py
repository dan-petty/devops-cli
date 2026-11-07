"""The size of a runner Job follows the plan (#3193): the table of sizes, the count of the files
of a plan, the worker count that equals the CPU limit, and the setting of the memory limit."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.config import settings
from devops_cli.exceptions import ConfigurationError
from devops_cli.roadmap.implement.implement_size import (
    RUNNER_SIZES,
    SMALL_PLAN_MAX_FILES,
    WORKERS_VARIABLE,
    plan_file_count,
    runner_size,
)

VARIABLE = "DEVOPS_CLI_ROADMAP_IMPLEMENT_MAX_MEMORY_LIMIT"
GIB = 1024**3


def _gibibytes(quantity: str) -> int:
    assert quantity.endswith("Gi")
    return int(quantity.removesuffix("Gi")) * GIB


def _tasks(*paths: str) -> str:
    """A `tasks.md` that names each path in a task of its own."""
    lines = ["# Tasks", "", "## 1. The work", "", "Kind: behavior", ""]
    lines += [f"- [ ] 1.{number} Change `{path}`" for number, path in enumerate(paths, start=1)]
    return "\n".join(lines) + "\n"


def test_a_plan_with_few_files_gets_a_smaller_request_than_a_plan_with_many() -> None:
    few = runner_size(plan_file_count(_tasks(*(f"src/a{n}.py" for n in range(3)))))
    many = runner_size(plan_file_count(_tasks(*(f"src/a{n}.py" for n in range(12)))))

    assert (few.cpu, few.memory, many.cpu, many.memory) == ("1", "2Gi", "4", "6Gi")


@pytest.mark.parametrize(
    ("files", "row"),
    [(0, 0), (1, 0), (SMALL_PLAN_MAX_FILES, 0), (SMALL_PLAN_MAX_FILES + 1, 1), (60, 1)],
)
def test_the_small_row_holds_up_to_ten_files_and_the_large_row_the_rest(
    files: int, row: int
) -> None:
    assert (SMALL_PLAN_MAX_FILES, runner_size(files)) == (10, RUNNER_SIZES[row])


def test_a_file_is_counted_once_and_a_command_or_a_setting_is_no_file() -> None:
    tasks = (
        "# Tasks\n\n## 1. The work\n\n"
        "- [ ] 1.1 Change `src/devops_cli/a.py` and `tests/test_a.py`\n"
        "  - Verification: `uv run devops ci test tests/test_a.py`\n"
        "- [ ] 1.2 Change `src/devops_cli/a.py` again, set `roadmap.implement.max_memory_limit`, "
        "read `PYTEST_XDIST_AUTO_NUM_WORKERS` and `devops_cli.roadmap.implement.implement_size`\n"
        "- [ ] 1.3 Document it in `k8s/README.md` and `CONTEXT.md`\n"
    )

    assert plan_file_count(tasks) == 4


def test_a_plan_that_names_no_file_has_zero_files() -> None:
    assert plan_file_count("# Tasks\n") == 0


def test_the_worker_count_of_each_row_is_its_cpu_limit() -> None:
    for row in RUNNER_SIZES:
        resources = row.resources("8Gi")
        assert (
            row.env,
            resources["requests"]["cpu"],
            resources["limits"]["cpu"],
        ) == ({WORKERS_VARIABLE: row.cpu}, row.cpu, row.cpu)


def test_the_memory_limit_is_the_argument_and_the_request_is_the_row() -> None:
    resources = RUNNER_SIZES[0].resources("12Gi")

    assert resources == {
        "requests": {"cpu": "1", "memory": "2Gi"},
        "limits": {"cpu": "1", "memory": "12Gi"},
    }


def test_each_row_cites_its_measured_sample_and_its_request_is_above_the_peak() -> None:
    for row in RUNNER_SIZES:
        assert (bool(row.sample), row.peak_bytes < _gibibytes(row.memory)) == (True, True)


def test_the_table_has_more_cpu_and_memory_in_each_row_than_in_the_one_before() -> None:
    cpus = [int(row.cpu) for row in RUNNER_SIZES]
    memory = [_gibibytes(row.memory) for row in RUNNER_SIZES]

    assert (cpus, memory) == (sorted(set(cpus)), sorted(set(memory)))


@pytest.fixture
def clean_setting(config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(VARIABLE, raising=False)
    config()


def _limit() -> str:
    settings.reset_settings_cache()
    return settings.load_settings().roadmap.implement.max_memory_limit


@pytest.mark.usefixtures("clean_setting")
def test_the_memory_limit_is_8gi_when_the_setting_is_not_set() -> None:
    assert _limit() == "8Gi"


@pytest.mark.usefixtures("clean_setting")
def test_a_variable_raises_the_memory_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE, "12Gi")

    assert _limit() == "12Gi"


@pytest.mark.usefixtures("clean_setting")
def test_the_largest_request_is_a_valid_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE, RUNNER_SIZES[-1].memory)

    assert _limit() == RUNNER_SIZES[-1].memory


@pytest.mark.usefixtures("clean_setting")
@pytest.mark.parametrize("value", ["5Gi", "8G", "8192Mi", "8", "0Gi", "08Gi", "8.5Gi", "eight"])
def test_a_limit_below_the_largest_request_or_in_another_form_is_refused(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(VARIABLE, value)

    with pytest.raises(ConfigurationError, match="max_memory_limit"):
        _limit()
