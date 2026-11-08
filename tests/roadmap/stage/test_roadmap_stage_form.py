"""`devops roadmap stage`: a plan gives a verify command and test paths in the project form (#3015)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.roadmap.stage.stage_change import (
    STAGE_EVAL_REPLAY,
    STAGE_EVAL_TRIGGER_PATHS,
    StageGroup,
    StageProposal,
    StageRequirement,
    StageScenario,
    StageSpec,
    check_proposal,
)
from devops_cli.roadmap.stage.stage_form import (
    form_problems,
    negative_search_parts,
    record_search_evidence,
    search_problems,
)
from devops_cli.roadmap.stage.stage_overlap import Overlap
from devops_cli.roadmap.stage.stage_paths import StagedTree
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

PLAN_CHECK_FILE = "src/devops_cli/roadmap/stage/stage_change.py"
SELF_ACCEPTANCE = "`StageProposal` gets no problem from `content_problems`"


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
        if all(path.startswith("tests/") for path in changes):
            update["implementation"] = "Update `test_stage` for the changes."
    elif PLAN_CHECK_FILE in changes:
        # A plan that changes the plan check gives the test that accepts its own plan (#3404).
        update["test"] = f"{base['test']}, and the plan's own {SELF_ACCEPTANCE}"
    prompt_file = any(
        path.startswith("src/devops_cli/ai/tasks/roadmap_stage_") and path.endswith(".md")
        for path in changes
    )
    if prompt_file:
        update["reads"] = ["tests/roadmap/stage/test_roadmap_stage_prompt_rules.py"]
        if verify is None:
            update["verify"] = (
                "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py"
            )
    if verify is not None:
        update["verify"] = verify
    group = StageGroup.model_validate({**base, **update})
    return make_stage_proposal(
        groups=[group],
        what_changes=[f"`{path}` changes." for path in changes],
        **({} if sourced else {"skip_specs": True, "specs": []}),
    )


def _problems(proposal: StageProposal) -> list[str]:
    """What `check_proposal` finds in a plan whose files all exist or are created by it."""
    group = proposal.groups[0]
    tree = StagedTree(
        [*group.changes, *group.reads, "src/devops_cli/sample.py", "tests/test_sample.py"]
    )
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
        "src/devops_cli/roadmap/stage/stage_form.py",
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


# ── The evidence of a negative search (#3410) ────────────────────────────────

NO_HIT = "! git grep -n -F devops_cli.roadmap.stage_missing src/ tests/"
BARE = "! git grep -n -F devops_cli.roadmap.stage src/ tests/"
DOTTED = "! git grep -n -F devops_cli.roadmap.stage_ src/ tests/"
STAGE_PACKAGE = "src/devops_cli/roadmap/stage/ready.py"


def _search_group(verify: str, *, creates: tuple[str, ...] = ()) -> StageGroup:
    return _group(
        title="Move the stage modules",
        kind="other",
        test=None,
        reads=[],
        changes=[CODE, *creates],
        creates=list(creates),
        creates_lines={path: 5 for path in creates},
        verify=verify,
    )


def test_negative_search_parts_reads_the_literal_and_the_paths() -> None:
    found = negative_search_parts(DOTTED)

    assert found is not None
    assert (found.literals, found.paths) == (("devops_cli.roadmap.stage_",), ("src/", "tests/"))


@pytest.mark.parametrize("command", ["uv run devops ci", "! git grep -n", "!"])
def test_negative_search_parts_gives_no_literal_for_another_command(command: str) -> None:
    assert negative_search_parts(command) is None


def test_record_search_evidence_calls_the_search_once_for_each_literal() -> None:
    seen: list[str] = []

    def search(literal: str) -> tuple[str, ...]:
        seen.append(literal)
        return ("src/b.py", "src/a.py", "src/a.py", "")

    evidence = record_search_evidence(
        [_search_group(DOTTED), _search_group(BARE), _search_group(DOTTED)], search
    )

    assert seen == ["devops_cli.roadmap.stage_", "devops_cli.roadmap.stage"]
    assert evidence == {
        "devops_cli.roadmap.stage_": ("src/a.py", "src/b.py"),
        "devops_cli.roadmap.stage": ("src/a.py", "src/b.py"),
    }


def test_search_problems_refuses_a_literal_with_no_hit() -> None:
    (problem,) = search_problems([_search_group(NO_HIT)], {"devops_cli.roadmap.stage_": ()})

    assert "already passes before the change and proves nothing" in problem
    assert NO_HIT in problem


def test_search_problems_refuses_a_literal_that_a_created_source_path_keeps() -> None:
    (problem,) = search_problems(
        [_search_group(BARE, creates=(STAGE_PACKAGE,))],
        {"devops_cli.roadmap.stage": ("src/devops_cli/roadmap/stage.py",)},
    )

    assert "can never pass on the produced tree" in problem
    assert STAGE_PACKAGE in problem


def test_search_problems_accepts_a_recorded_hit_that_survives_the_change() -> None:
    groups = [_search_group(DOTTED, creates=(STAGE_PACKAGE,))]

    assert search_problems(groups, {"devops_cli.roadmap.stage_": ("src/a.py",)}) == []


def test_search_problems_records_no_hit_only_when_the_caller_gives_evidence() -> None:
    groups = [_search_group(NO_HIT)]

    assert search_problems(groups) == []


E_TWO = (
    "! git grep -n -e devops_cli.roadmap.stage_ -e devops_cli.roadmap.stage_missing -- src/ tests/"
)


def test_each_e_literal_has_its_own_hit_check() -> None:
    evidence = {"devops_cli.roadmap.stage_": ("src/a.py",), "devops_cli.roadmap.stage_missing": ()}

    (problem,) = search_problems([_search_group(E_TWO)], evidence)

    assert "already passes before the change and proves nothing" in problem
    assert "devops_cli.roadmap.stage_missing" in problem


def test_record_search_evidence_records_each_e_literal() -> None:
    seen: list[str] = []

    def search(literal: str) -> tuple[str, ...]:
        seen.append(literal)
        return ("src/a.py",) if literal == "devops_cli.roadmap.stage_" else ()

    evidence = record_search_evidence([_search_group(E_TWO)], search)

    assert seen == ["devops_cli.roadmap.stage_", "devops_cli.roadmap.stage_missing"]
    assert evidence == {
        "devops_cli.roadmap.stage_": ("src/a.py",),
        "devops_cli.roadmap.stage_missing": (),
    }


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


# ── The issue that a plan needs first (#3224) ────────────────────────────────

ISSUE_ENTRY = "#3201: the check command"
OVERLAP_ENTRY = "an open pull request changes src/devops_cli/roadmap/plan_check.py"
OTHER_ENTRY = "a metric name and its other files"


def test_the_issue_form_gives_its_number() -> None:
    from devops_cli.roadmap.stage.stage_change import issue_dependencies

    assert issue_dependencies([ISSUE_ENTRY, OVERLAP_ENTRY]) == [3201]


def test_an_entry_with_no_issue_form_is_skipped() -> None:
    from devops_cli.roadmap.stage.stage_change import issue_dependencies

    assert issue_dependencies([OTHER_ENTRY]) == []


# ── A plan that changes a stage trigger path runs the eval replay (#3331) ─────

_REPLAY_SCORE = "the score before and after the change"


def _with_task(plan: StageProposal, text: str) -> StageProposal:
    """The plan, with its one group task written as `text`."""
    group = plan.groups[0].model_copy(update={"implementation": text})
    return plan.model_copy(update={"groups": [group]})


@pytest.mark.parametrize("path", STAGE_EVAL_TRIGGER_PATHS)
def test_a_plan_that_changes_a_trigger_path_with_no_replay_task_is_refused(path: str) -> None:
    (problem,) = _problems(_plan(path))

    assert f"`{path}`" in problem
    assert STAGE_EVAL_REPLAY in problem


def test_a_plan_that_changes_the_prompt_with_no_replay_task_is_refused() -> None:
    prompt = "src/devops_cli/ai/tasks/roadmap_stage_change.md"

    (problem,) = _problems(_plan(prompt))

    assert f"`{prompt}`" in problem
    assert "must run" in problem


def test_a_replay_task_without_the_score_is_refused() -> None:
    plan = _with_task(
        _plan("src/devops_cli/roadmap/stage/stage_change.py"),
        f"Run `{STAGE_EVAL_REPLAY}` before the merge.",
    )

    (problem,) = _problems(plan)

    assert "score" in problem
    assert "before and after" in problem


def test_a_replay_task_with_the_score_passes() -> None:
    path = "src/devops_cli/ai/tasks/roadmap_stage_change.md"
    plan = _with_task(
        _plan(path),
        f"Run `{STAGE_EVAL_REPLAY}` and state {_REPLAY_SCORE}.",
    )

    assert _problems(plan) == []


def test_a_plan_that_changes_no_trigger_path_has_no_replay_problem() -> None:
    plan = _plan(CODE)

    assert _problems(plan) == []


def test_a_spec_naming_a_missing_test_file_is_refused() -> None:
    spec = StageSpec(
        capability="comment-thread",
        added=[
            StageRequirement(
                name="A requirement",
                text="The system SHALL test `tests/test_missing_example.py`.",
                scenarios=[
                    StageScenario(
                        name="A scenario",
                        when="A condition holds.",
                        then="The system SHALL pass.",
                    )
                ],
            )
        ],
    )
    plan = make_stage_proposal(specs=[spec])
    tree = StagedTree(["src/devops_cli/sample.py", "tests/test_sample.py"])
    problems = check_proposal(plan, ["comment-thread"], tree)
    assert any("tests/test_missing_example.py" in p for p in problems)


def test_a_changed_docstring_naming_a_missing_test_file_is_refused() -> None:
    group = make_stage_proposal().groups[0]
    plan = make_stage_proposal(groups=[group])
    source = 'def helper():\n    """See `tests/test_missing_example.py`."""\n    pass\n'
    read_text = {"src/devops_cli/sample.py": source}.get
    tree = StagedTree(["src/devops_cli/sample.py", "tests/test_sample.py"])
    problems = check_proposal(plan, ["comment-thread"], tree, read_text=read_text)
    assert any("tests/test_missing_example.py" in p for p in problems)


def test_a_changed_source_with_syntax_error_is_ignored() -> None:
    group = make_stage_proposal().groups[0]
    plan = make_stage_proposal(groups=[group])
    read_text = {"src/devops_cli/sample.py": "def broken_syntax(:\n"}.get
    tree = StagedTree(["src/devops_cli/sample.py", "tests/test_sample.py"])
    problems = check_proposal(plan, ["comment-thread"], tree, read_text=read_text)
    assert not any("stage_problem_missing_test_file" in p for p in problems)


def test_a_changed_docstring_naming_an_existing_test_file_passes() -> None:
    group = make_stage_proposal().groups[0]
    plan = make_stage_proposal(groups=[group])
    read_text = {
        "src/devops_cli/sample.py": '"""See `tests/roadmap/test_roadmap_limit_classes.py`."""\n'
    }.get
    tree = StagedTree(["src/devops_cli/sample.py", "tests/roadmap/test_roadmap_limit_classes.py"])
    problems = check_proposal(plan, ["comment-thread"], tree, read_text=read_text)
    assert not any("tests/roadmap/test_roadmap_limit_classes.py" in p for p in problems)


def test_an_other_group_that_changes_a_case_path_is_refused_with_the_manifest_kind() -> None:
    case = "tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml"
    group = StageGroup.model_validate(
        {
            **make_stage_proposal().groups[0].model_dump(),
            "kind": "other",
            "changes": [case],
            "creates": [],
            "creates_lines": {},
            "test": None,
            "verify": "uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py",
        }
    )

    (problem,) = form_problems([group])
    assert "manifest" in problem
    assert f"`{case}`" in problem
    assert "other" in problem


def test_a_manifest_verify_that_is_not_a_case_of_the_group_is_refused() -> None:
    case = "tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml"
    group = StageGroup.model_validate(
        {
            **make_stage_proposal().groups[0].model_dump(),
            "kind": "manifest",
            "changes": [case],
            "creates": [],
            "creates_lines": {},
            "test": f"Add the promtool cases to `{case}`",
            "verify": "uv run devops ci mutate tests/prometheus",
        }
    )

    (problem,) = form_problems([group])
    assert "manifest" in problem
    assert "`uv run devops ci mutate tests/prometheus`" in problem
    assert "uv run devops ci test" in problem


def test_a_manifest_verify_that_runs_a_path_of_the_group_is_accepted() -> None:
    case = "tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml"
    test_file = "tests/prometheus/test_k8s_monitoring_alerting.py"
    group = StageGroup.model_validate(
        {
            **make_stage_proposal().groups[0].model_dump(),
            "kind": "manifest",
            "changes": [case, test_file],
            "creates": [],
            "creates_lines": {},
            "test": f"Add the promtool cases to `{case}`",
            "verify": f"uv run devops ci test {test_file}",
        }
    )

    assert form_problems([group]) == []
