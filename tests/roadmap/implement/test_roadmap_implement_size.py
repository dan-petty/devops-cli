"""The size of a runner Job follows the plan (#3193): the table of sizes, the count of the files
of a plan, the worker count that equals the CPU limit, and the memory limit that equals the memory
request of the row (#7422)."""

from __future__ import annotations

import pytest

from devops_cli.config import settings
from devops_cli.roadmap.implement.implement_size import (
    RUNNER_SIZES,
    SMALL_PLAN_MAX_FILES,
    WORKERS_VARIABLE,
    plan_file_count,
    runner_size,
)

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

    assert (few.cpu, few.memory, many.cpu, many.memory) == ("1", "5Gi", "4", "11Gi")


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
        "  - Verification: `$ uv run devops ci test tests/test_a.py`\n"
        "- [ ] 1.2 Change `src/devops_cli/a.py` again, set `roadmap.implement.max_parallel_jobs`, "
        "read `PYTEST_XDIST_AUTO_NUM_WORKERS` and `devops_cli.roadmap.implement.implement_size`\n"
        "- [ ] 1.3 Document it in `k8s/README.md` and `CONTEXT.md`\n"
    )

    assert plan_file_count(tasks) == 4


def test_a_plan_that_names_no_file_has_zero_files() -> None:
    assert plan_file_count("# Tasks\n") == 0


def test_the_worker_count_of_each_row_is_its_cpu_limit() -> None:
    for row in RUNNER_SIZES:
        resources = row.resources()
        assert (
            row.env,
            resources["requests"]["cpu"],
            resources["limits"]["cpu"],
        ) == ({WORKERS_VARIABLE: row.cpu}, row.cpu, row.cpu)


def test_the_memory_limit_of_each_row_equals_its_memory_request() -> None:
    """The scheduler places a Job by its request, so a Job that may grow past the request takes
    memory from the other pods of the node (#7422)."""
    assert [row.resources() for row in RUNNER_SIZES] == [
        {
            "requests": {"cpu": "1", "memory": "5Gi"},
            "limits": {"cpu": "1", "memory": "5Gi"},
        },
        {
            "requests": {"cpu": "4", "memory": "11Gi"},
            "limits": {"cpu": "4", "memory": "11Gi"},
        },
    ]


def test_each_row_cites_its_measured_sample_and_its_peak_is_at_most_80_percent_of_the_memory() -> (
    None
):
    """The highest peak is at most 80 % of the limit: the room of T1 in the Kubernetes guideline."""
    for row in RUNNER_SIZES:
        assert (bool(row.sample), row.peak_bytes <= 0.8 * _gibibytes(row.memory)) == (True, True)


def test_the_table_has_more_cpu_and_memory_in_each_row_than_in_the_one_before() -> None:
    cpus = [int(row.cpu) for row in RUNNER_SIZES]
    memory = [_gibibytes(row.memory) for row in RUNNER_SIZES]

    assert (cpus, memory) == (sorted(set(cpus)), sorted(set(memory)))


PARALLEL_VARIABLE = "DEVOPS_CLI_ROADMAP_IMPLEMENT_MAX_PARALLEL_JOBS"


def _parallel_limit() -> int:
    settings.reset_settings_cache()
    return settings.load_settings().roadmap.implement.max_parallel_jobs


def test_the_parallel_limit_defaults_to_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PARALLEL_VARIABLE, raising=False)
    assert _parallel_limit() == 1
    monkeypatch.setenv(PARALLEL_VARIABLE, "3")
    assert _parallel_limit() == 3
