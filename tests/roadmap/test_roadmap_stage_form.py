"""`devops roadmap stage`: a plan gives a verify command and test paths in the project form (#3015)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.roadmap.stage_change import StageGroup, StageProposal, check_proposal
from devops_cli.roadmap.stage_form import form_problems
from devops_cli.roadmap.stage_overlap import Overlap
from devops_cli.roadmap.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal
from tests.support.paths import REPO_ROOT

CODE = "src/devops_cli/roadmap/stage.py"
MIRRORED = "tests/roadmap/test_stage.py"
FLAT = "tests/test_stage.py"
VERIFY_PROBLEM = (
    "Group 1 gives the `verify` command `uv run pytest tests/roadmap/test_stage.py`. A `verify` "
    "command starts with `uv run devops`, such as `uv run devops ci test "
    "tests/roadmap/test_feature.py`, or is a `! git grep -n <name>` check that a name is gone. "
    "Give a command of one of these forms."
)


def _plan(*changes: str, creates: tuple[str, ...] = (), verify: str | None = None) -> StageProposal:
    """The sample proposal, with one group that changes `changes` and creates `creates`."""
    base = make_stage_proposal().groups[0].model_dump()
    update: dict[str, Any] = {
        "reads": [],
        "changes": list(changes),
        "creates": list(creates),
        "creates_lines": {path: 10 for path in creates},
    }
    sourced = any(path.startswith("src/") for path in changes)
    if not sourced:
        update |= {"kind": "other", "test": None}
    if verify is not None:
        update["verify"] = verify
    group = StageGroup.model_validate({**base, **update})
    return make_stage_proposal(
        groups=[group], **({} if sourced else {"skip_specs": True, "specs": []})
    )


def _problems(proposal: StageProposal) -> list[str]:
    """What `check_proposal` finds in a plan whose files all exist or are created by it."""
    group = proposal.groups[0]
    tree = StagedTree([*group.changes, "src/devops_cli/sample.py", "tests/test_sample.py"])
    return check_proposal(proposal, ["comment-thread"], tree)


def test_a_pytest_verify_command_is_refused_with_the_form_to_use() -> None:
    plan = _plan(CODE, MIRRORED, creates=(MIRRORED,), verify=f"uv run pytest {MIRRORED}")

    assert _problems(plan) == [VERIFY_PROBLEM]


@pytest.mark.parametrize(
    "verify",
    [
        f"uv run devops ci test {MIRRORED}",
        "uv run devops ci",
        "uv run devops openspec check",
        "uv run devops docs check",
        "uv run devops k8s image-pins",
        "! git grep -n -w old_name src/ tests/",
    ],
)
def test_a_devops_command_or_a_negative_search_is_a_verify_command(verify: str) -> None:
    plan = _plan(CODE, MIRRORED, creates=(MIRRORED,), verify=verify)

    assert _problems(plan) == []


@pytest.mark.parametrize(
    ("verify", "reason"),
    [
        ("! git grep -n name", "it gives no path"),
        ("! git grep -n name src/ | cat", "the word `|` is not a path of the checkout"),
        ("! git grep -n name src/ ; rm -rf tests/", "the word `;` is not a path of the checkout"),
        (
            "! git grep -O name src/",
            "the option `-O` is not allowed (the options are -n -I -F -i -w -l -c -q)",
        ),
        ("! rm -rf src/", "it does not start with `! git grep`"),
        ("! git log", "it does not start with `! git grep`"),
        ("uv run devops 'ci", "it is not a valid command line"),
    ],
)
def test_a_verify_command_that_the_step_refuses_gets_the_reason_of_the_step(
    verify: str, reason: str
) -> None:
    plan = _plan(CODE, MIRRORED, creates=(MIRRORED,), verify=verify)

    assert _problems(plan) == [
        f"Group 1 gives the `verify` command `{verify}`, and the step cannot run it: {reason}. "
        "Give `uv run devops <command>` or `! git grep -n <name> src/ tests/`."
    ]


@pytest.mark.parametrize(
    "verify", ["devops ci test tests/roadmap/test_stage.py", "uv run devopsx", "pytest -x"]
)
def test_a_command_that_is_not_uv_run_devops_is_refused(verify: str) -> None:
    plan = _plan(CODE, MIRRORED, creates=(MIRRORED,), verify=verify)

    (problem,) = _problems(plan)
    assert f"`{verify}`" in problem


def test_a_flat_new_test_path_is_refused_with_the_mirror_directory() -> None:
    plan = _plan(CODE, FLAT, creates=(FLAT,))

    (problem,) = _problems(plan)
    assert problem == (
        f"Group 1 creates `{FLAT}`, and the directory `tests` does not mirror the code that the "
        "plan changes. A new test goes in `tests/roadmap` or `tests/invariants`. Move it there."
    )


def test_a_new_test_in_the_mirror_directory_or_in_invariants_is_accepted() -> None:
    invariant = "tests/invariants/test_source_tree.py"
    plan = _plan(CODE, MIRRORED, invariant, creates=(MIRRORED, invariant))

    assert _problems(plan) == []


def test_a_new_test_is_checked_against_the_code_of_every_group() -> None:
    other = "src/devops_cli/ai/review/pipeline.py"
    new = "tests/ai/review/test_pipeline.py"
    plan = _plan(CODE, other, new, creates=(new,))

    assert _problems(plan) == []


def test_a_new_test_in_the_wrong_package_directory_is_refused() -> None:
    wrong = "tests/ai/test_stage.py"
    plan = _plan(CODE, wrong, creates=(wrong,))

    (problem,) = _problems(plan)
    assert f"`{wrong}`" in problem
    assert "`tests/roadmap`" in problem


def test_a_top_level_module_has_the_tests_directory_as_its_mirror() -> None:
    plan = _plan("src/devops_cli/sample.py", FLAT, creates=(FLAT,))

    assert _problems(plan) == []


def test_a_plan_with_no_source_path_refuses_a_flat_test_and_accepts_a_nested_one() -> None:
    flat = _plan(FLAT, creates=(FLAT,), verify="uv run devops ci test tests/test_stage.py")
    nested = _plan(MIRRORED, creates=(MIRRORED,), verify=f"uv run devops ci test {MIRRORED}")

    assert len(_problems(flat)) == 1
    assert _problems(nested) == []


@pytest.mark.parametrize(
    "path", ["tests/conftest.py", "tests/fixtures/stage/plan.json", "tests/support/builders.py"]
)
def test_a_new_file_under_tests_that_is_no_test_module_is_not_judged(path: str) -> None:
    plan = _plan(CODE, path, creates=(path,))

    assert _problems(plan) == []


def test_a_test_that_already_exists_is_not_judged() -> None:
    plan = _plan(CODE, FLAT)

    assert _problems(plan) == []


# ── A task holds more than one word (#3255) ───────────────────────────────────

SENTENCE = "Add a test in tests/roadmap/test_roadmap_stage_form.py for a bare filename task"


def _group(**update: Any) -> StageGroup:
    base = make_stage_proposal().groups[0].model_dump()
    return StageGroup.model_validate({**base, **update})


@pytest.mark.parametrize(
    "text",
    [
        "src/devops_cli/roadmap/stage_form.py",
        "Refactor",
        "`tests/roadmap/test_stage.py`",
        "a.py",
        "`uv run devops ci`",
    ],
)
def test_a_bare_first_task_is_refused_and_names_the_group(text: str) -> None:
    (problem,) = form_problems([_group(title="Keep the comment", test=text)])

    assert problem.startswith("Group 1 (Keep the comment) has the test task")
    assert text in problem
    assert "one word" in problem


@pytest.mark.parametrize("part", ["implementation", "documentation"])
def test_a_bare_work_or_document_task_is_refused_with_its_part(part: str) -> None:
    (problem,) = form_problems([_group(**{part: "stage_form.py"})])

    assert f"has the {part} task" in problem


def test_a_task_with_a_verb_and_an_object_is_accepted() -> None:
    group = _group(test=SENTENCE, implementation="Add `form_problems`", documentation="Document it")

    assert form_problems([group]) == []


def test_a_bare_task_reaches_the_model_through_check_proposal() -> None:
    plan = _plan(CODE, MIRRORED, creates=(MIRRORED,))
    plan.groups[0].test = "tests/roadmap/test_stage.py"

    assert any("one word" in problem for problem in _problems(plan))


# ── The examples of the prompt and of the rules ───────────────────────────────

_TEST_PATH = re.compile(r"tests/[\w/<>-]*test_[\w<>-]*\.py")
_PROMPT = "roadmap_stage_change.md"


def _example_paths(text: str) -> list[str]:
    return _TEST_PATH.findall(text)


def _mirrored(path: str) -> bool:
    """Whether the folder of `path` sits under `tests/` and mirrors a package of `src/devops_cli`."""
    folder = Path(path).parent
    package = REPO_ROOT / "src" / "devops_cli" / folder.relative_to("tests")
    return folder != Path("tests") and package.is_dir()


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(load_task_prompt(_PROMPT), id="prompt"),
        pytest.param((REPO_ROOT / "openspec" / "config.yaml").read_text("utf-8"), id="config"),
    ],
)
def test_every_example_test_path_of_the_prompt_and_the_config_is_mirrored(text: str) -> None:
    paths = _example_paths(text)

    assert paths
    assert [path for path in paths if not _mirrored(path)] == []


# ── The open pull requests that change a cited path (#3252) ──────────────────

_OVERLAP = Overlap(
    number=3173,
    title="docs(openspec): plan #3173 the telemetry page",
    state="open",
    plan=True,
    paths=("docs/TELEMETRY.md",),
)
_DEPENDENCY_PROBLEM = (
    "The open pull request #3173 changes `docs/TELEMETRY.md`, and no entry of `dependencies` "
    "names it. Add an entry that names #3173 and `docs/TELEMETRY.md`, or show in that entry why "
    "the overlap is no dependency."
)


def _overlap_problems(plan: StageProposal) -> list[str]:
    """What `check_proposal` finds in a plan whose files exist, against one overlap."""
    group = plan.groups[0]
    tree = StagedTree([*group.changes, "src/devops_cli/sample.py", "tests/test_sample.py"])
    return check_proposal(plan, ["comment-thread"], tree, overlaps=[_OVERLAP])


def test_an_overlap_with_no_dependency_is_refused_and_named() -> None:
    plan = _plan(CODE, MIRRORED, creates=(MIRRORED,))

    assert _overlap_problems(plan) == [_DEPENDENCY_PROBLEM]


def test_a_dependency_that_names_the_overlap_is_accepted() -> None:
    plan = _plan(CODE, MIRRORED, creates=(MIRRORED,)).model_copy(
        update={"dependencies": ["#3173 changes `docs/TELEMETRY.md`, so this plan waits for it."]}
    )

    assert _overlap_problems(plan) == []
