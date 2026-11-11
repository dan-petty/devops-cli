"""`record_module_tests` lists the tests of a module nearest first (#4519).

The problem of the `paths` gate names the first test of the record, so the first test must be the
test that a reader of the module expects: the mirror test, then a direct importer, then a test in
the mirror folder, then a test that reaches the module through a package.
"""

from __future__ import annotations

import re

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stage.stage_change import StageGroup
from devops_cli.roadmap.stage.stage_paths import (
    StagedTree,
    existing_test_problems,
    record_module_tests,
)

MESSAGES_MODULE = "src/devops_cli/lang/en/messages.py"
STAGE_MODULE = "src/devops_cli/roadmap/stage/stage_paths.py"
STEP_MODULE = "src/devops_cli/roadmap/step_files.py"
MIRROR_TEST = "tests/lang/en/test_messages.py"
FAR_TEST = "tests/ai/mcp/test_ai_benchmark_mcp_tool.py"
PACKAGE_IMPORT = "from devops_cli.lang import MESSAGES\n"
DIRECT_IMPORT = "from devops_cli.lang.en.messages import MESSAGES\n"
_SOURCES = {
    MESSAGES_MODULE: "MESSAGES = object()\n",
    "src/devops_cli/lang/__init__.py": "from devops_cli.lang.en import MESSAGES\n",
    "src/devops_cli/lang/en/__init__.py": "from devops_cli.lang.en.messages import MESSAGES\n",
    STAGE_MODULE: "def path_problems() -> None: ...\n",
    STEP_MODULE: "def parse_task_groups() -> None: ...\n",
}


def _record(
    module: str, tests: dict[str, str], *, also: dict[str, str] | None = None
) -> dict[str, tuple[str, ...]]:
    """The record of `module`, which a behavior group changes, in a tree of `tests`. `also` maps
    another module that the group changes to its text."""
    texts = {**_SOURCES, **(also or {}), **tests}

    def search(literal: str) -> list[str]:
        word = re.compile(rf"(?<!\w){re.escape(literal)}(?!\w)")
        return sorted(path for path, text in texts.items() if word.search(text))

    group = StageGroup.model_validate(
        {
            "title": "Order the tests",
            "kind": "behavior",
            "reads": [],
            "changes": [module, *(also or {})],
            "creates": [],
            "creates_lines": {},
            "test": "Write `test_the_order` in `tests/new/test_order.py`",
            "implementation": f"Order the record in `{module}`",
            "documentation": None,
            "verify": "uv run devops ci test tests/new/test_order.py",
        }
    )
    tree = StagedTree(list(texts), reader=texts.__getitem__)
    return record_module_tests([group], tree, search)


def test_the_mirror_test_comes_first() -> None:
    record = _record(MESSAGES_MODULE, {FAR_TEST: PACKAGE_IMPORT, MIRROR_TEST: PACKAGE_IMPORT})

    assert record[MESSAGES_MODULE] == (MIRROR_TEST, FAR_TEST)


def test_a_direct_import_beats_a_package_import() -> None:
    first = "tests/aaa/test_package_import.py"
    second = "tests/zzz/test_direct_import.py"

    record = _record(MESSAGES_MODULE, {first: PACKAGE_IMPORT, second: DIRECT_IMPORT})

    assert record[MESSAGES_MODULE] == (second, first)


def test_a_test_in_the_mirror_folder_beats_a_package_import() -> None:
    near = "tests/lang/en/test_other.py"

    record = _record(MESSAGES_MODULE, {FAR_TEST: PACKAGE_IMPORT, near: PACKAGE_IMPORT})

    assert record[MESSAGES_MODULE] == (near, FAR_TEST)


def test_package_importers_keep_path_order_and_none_is_lost() -> None:
    tests = {f"tests/{name}/test_{name}.py": PACKAGE_IMPORT for name in ("zeta", "alpha", "mid")}

    record = _record(MESSAGES_MODULE, tests)

    assert record[MESSAGES_MODULE] == tuple(sorted(tests))


def test_a_test_of_another_changed_module_ranks_last() -> None:
    own = "tests/zzz/test_own.py"
    other = "tests/aaa/test_other.py"
    tests = {
        own: "from devops_cli.roadmap.stage.stage_paths import path_problems\n",
        other: "from devops_cli.roadmap.step_files import parse_task_groups\n",
    }
    importer = {STEP_MODULE: "from devops_cli.roadmap.stage.stage_paths import path_problems\n"}

    record = _record(STAGE_MODULE, tests, also=importer)

    assert record[STAGE_MODULE] == (own, other)


def test_the_problem_names_the_mirror_test_only() -> None:
    record = _record(MESSAGES_MODULE, {FAR_TEST: PACKAGE_IMPORT, MIRROR_TEST: PACKAGE_IMPORT})
    group = StageGroup.model_validate(
        {
            "title": "Order the tests",
            "kind": "behavior",
            "reads": [],
            "changes": [MESSAGES_MODULE, "tests/new/test_order.py"],
            "creates": ["tests/new/test_order.py"],
            "creates_lines": {"tests/new/test_order.py": 10},
            "test": "Write `test_the_order` in `tests/new/test_order.py`",
            "implementation": f"Change `{MESSAGES_MODULE}`",
            "documentation": None,
            "verify": "uv run devops ci test tests/new/test_order.py",
        }
    )
    tree = StagedTree([MESSAGES_MODULE, MIRROR_TEST, FAR_TEST])

    (problem,) = existing_test_problems([group], tree, record)

    assert f"`{MIRROR_TEST}`" in problem
    assert FAR_TEST not in problem
    assert (
        MESSAGES.roadmap.stage_problem_missing_module_test.format(
            group=1, path=MESSAGES_MODULE, test=MIRROR_TEST
        )
        == problem
    )


def test_a_module_at_the_top_of_the_package_has_no_mirror_rank() -> None:
    top = "src/devops_cli/sample.py"
    import_top = "from devops_cli.sample import run\n"
    tests = {"tests/test_sample.py": import_top, "tests/aaa/test_first.py": import_top}

    record = _record(top, tests, also={top: "def run() -> None: ...\n"})

    assert record[top] == ("tests/aaa/test_first.py", "tests/test_sample.py")
