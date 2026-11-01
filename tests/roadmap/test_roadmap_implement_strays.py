"""The stray files of an implement step (#3092): a file that the agent left in the checkout and
that its group does not name. `stray_files` decides from the names that git lists; the replay tests
below run a step with a stub model that writes such a file.
"""

from __future__ import annotations

import pytest

from devops_cli.roadmap.implement_strays import stray_files
from devops_cli.roadmap.step_files import parse_task_groups

CHANGE = "openspec/changes/1-sample-change"
GROUP = parse_task_groups(
    "## 1. The group\n\n"
    "Reads: none. Changes: `src/sample.py`, `tests/test_sample.py` (new).\n\n"
    "- [ ] 1.1 Add the test `tests/test_sample.py`\n"
    "  - Verification: `uv run devops ci test tests/test_sample.py`\n"
    "- [ ] 1.2 Write `docs/NOTES.md`\n"
)[0]


def _strays(*names: str) -> list[str]:
    return stray_files(names, GROUP, CHANGE)


@pytest.mark.parametrize(
    "name", ["tmp_test_x.py", "test_cwd_issue.py", "scripts/probe.py", "tests/sub/test_other.py"]
)
def test_a_file_that_the_group_does_not_name_is_a_stray_file(name: str) -> None:
    assert _strays(name) == [name]


@pytest.mark.parametrize(
    "name",
    [
        "src/sample.py",
        "tests/test_sample.py",
        "docs/NOTES.md",
        f"{CHANGE}/notes.md",
        f"{CHANGE}/specs/sample/spec.md",
        "tests/test_sample_more.py",
    ],
)
def test_a_file_that_the_group_allows_is_kept(name: str) -> None:
    assert _strays(name) == []


def test_a_test_file_is_kept_only_in_the_directory_of_a_named_test_file() -> None:
    assert _strays("tests/test_more.py", "tests/conftest.py", "src/test_more.py") == [
        "tests/conftest.py",
        "src/test_more.py",
    ]


def test_the_stray_files_come_back_in_the_order_git_listed_them() -> None:
    assert _strays("b_tmp.py", "src/sample.py", "a_tmp.py") == ["b_tmp.py", "a_tmp.py"]


def test_a_name_with_a_dot_folder_is_compared_as_a_normal_path() -> None:
    assert _strays("./src/sample.py", "docs/../src/sample.py") == []
