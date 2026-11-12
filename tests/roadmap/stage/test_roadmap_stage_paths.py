"""`devops roadmap stage`: the paths of a plan are files at the staged commit (#3010)."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stage.stage_change import (
    GroupKind,
    ProposalGate,
    StageGroup,
    check_gates,
)
from devops_cli.roadmap.stage.stage_overlap import grep_at
from devops_cli.roadmap.stage.stage_paths import (
    StagedTree,
    existing_test_problems,
    path_problems,
    record_module_tests,
)
from tests.support.builders import make_stage_proposal

# The search of a staged commit: the files that hold a literal.
Search = Callable[[str], Sequence[str]]

TREE = StagedTree(
    [
        "README.md",
        "src/devops_cli/commands/uv.py",
        "src/devops_cli/sample.py",
        "tests/fixtures/dry_run_gaps.json",
        "tests/roadmap/test_roadmap_dry_runs.py",
        "tests/security/test_scanner_tool_executor.py",
        "tests/test_sample.py",
        "docs/TESTING.md",
        "openspec/specs/config-commands/spec.md",
    ]
)


def _group(**update: object) -> StageGroup:
    """The group of the sample proposal, made light: it reads and changes files that TREE holds."""
    base = {
        "kind": "behavior",
        "reads": ["src/devops_cli/sample.py"],
        "changes": ["src/devops_cli/sample.py"],
        "creates": [],
        "test": "Write `test_the_job_keeps_the_last_comment` in `tests/test_sample.py`",
        "implementation": "Keep the last comment in `src/devops_cli/sample.py`",
        "documentation": "Change no document",
        "verify": "uv run devops ci test tests/test_sample.py",
    }
    fields = {"title": "Keep the last comment", **base, **update}
    fields.setdefault("creates_lines", {path: 10 for path in fields["creates"]})
    if not any(str(path).startswith("src/") for path in fields["changes"]):
        fields = {**fields, "kind": update.get("kind", "other"), "test": update.get("test")}
    return make_stage_proposal().groups[0].model_validate(fields)


def _problems(*groups: StageGroup, tree: StagedTree = TREE) -> list[str]:
    return path_problems(groups, tree)


# ── A path that is a file, or that a group creates ────────────────────────────


def test_a_plan_whose_paths_are_files_of_the_commit_has_no_problem() -> None:
    assert _problems(_group()) == []


def test_a_moved_test_file_is_a_problem_that_lists_the_file_with_the_same_name() -> None:
    group = _group(changes=["tests/test_scanner_tool_executor.py"])

    (problem,) = _problems(group)

    assert "`tests/test_scanner_tool_executor.py`" in problem
    assert "`tests/security/test_scanner_tool_executor.py`" in problem


def test_a_missing_path_names_the_creates_list_and_the_new_mark() -> None:
    """A stage reply lists the file in `creates`; a change folder marks it ` (new)`."""
    (problem,) = _problems(_group(reads=[], changes=["tests/test_scanner_tool_executor.py"]))

    assert "`creates`" in problem
    assert " (new)" in problem
    assert "`Changes:`" in problem
    hint = MESSAGES.roadmap.stage_path_same_name.format(
        names="`tests/security/test_scanner_tool_executor.py`"
    )
    assert problem.endswith(hint)


def test_a_path_that_a_later_group_creates_keeps_its_own_message() -> None:
    first = _group(reads=["tests/test_new.py"])
    later = _group(changes=["tests/test_new.py"], creates=["tests/test_new.py"], reads=[])

    (problem,) = _problems(first, later)

    assert "group 2" in problem
    assert "`creates`" not in problem
    assert " (new)" not in problem


def test_a_path_that_no_file_matches_by_name_says_so() -> None:
    (problem,) = _problems(_group(reads=[], changes=["src/devops_cli/commands/uv_cmd.py"]))

    assert "`src/devops_cli/commands/uv_cmd.py`" in problem
    assert "No file has this name" in problem


def test_the_problem_lists_at_most_five_files_of_the_same_name() -> None:
    names = [f"area{i}/tasks.md" for i in range(9)]
    tree = StagedTree(["README.md", *names])

    (problem,) = path_problems([_group(reads=[], changes=["tasks.md"])], tree)

    assert [name in problem for name in sorted(names)] == [True] * 5 + [False] * 4


def test_a_path_that_the_group_creates_passes() -> None:
    group = _group(changes=["tests/test_new.py"], creates=["tests/test_new.py"])

    assert _problems(group) == []


def test_a_path_that_an_earlier_group_creates_passes_in_a_later_group() -> None:
    first = _group(changes=["tests/test_new.py"], creates=["tests/test_new.py"], reads=[])
    later = _group(reads=["tests/test_new.py"], changes=["tests/test_new.py"])

    assert _problems(first, later) == []


def test_a_path_that_a_later_group_creates_is_missing_in_the_earlier_group() -> None:
    first = _group(reads=["tests/test_new.py"])
    later = _group(changes=["tests/test_new.py"], creates=["tests/test_new.py"], reads=[])

    (problem,) = _problems(first, later)

    assert "`tests/test_new.py`" in problem
    assert "group 1" in problem


def test_a_forward_read_names_the_group_that_creates_the_path_and_says_to_move_it() -> None:
    first = _group(reads=["tests/test_new.py"])
    between = _group()
    last = _group(changes=["tests/test_new.py"], creates=["tests/test_new.py"], reads=[])

    (problem,) = _problems(first, between, last)

    assert "Group 1 names `tests/test_new.py`" in problem
    assert "group 3 creates it after group 1" in problem
    assert "Move group 3 before group 1" in problem
    assert "No file has this name" not in problem
    assert "make the group that creates it list it" not in problem


def test_a_forward_read_of_a_folder_names_the_group_that_creates_a_file_in_it() -> None:
    first = _group(reads=["tests/new/"])
    later = _group(changes=["tests/new/test_new.py"], creates=["tests/new/test_new.py"], reads=[])

    (problem,) = _problems(first, later)

    assert "group 2 creates it after group 1" in problem


def test_a_path_that_no_group_creates_keeps_the_message_without_a_creating_group() -> None:
    later = _group(changes=["tests/test_other.py"], creates=["tests/test_other.py"], reads=[])

    (problem,) = _problems(_group(reads=["tests/test_new.py"]), later)

    assert "no group up to group 1 creates it" in problem
    assert "make the group that creates it list it in `creates`" in problem
    assert "Move group" not in problem


def test_a_folder_that_an_earlier_group_creates_a_file_in_passes() -> None:
    first = _group(changes=["tests/new/test_new.py"], creates=["tests/new/test_new.py"], reads=[])
    later = _group(reads=["tests/new/"], changes=["tests/new/test_new.py"])

    assert _problems(first, later) == []


# ── Where a path is named ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("update", "place"),
    [
        ({"reads": ["src/devops_cli/old.py"]}, "reads"),
        ({"changes": ["src/devops_cli/old.py"]}, "changes"),
        ({"implementation": "Keep the last comment in `src/devops_cli/old.py`"}, "task"),
        ({"test": "Write the test in `tests/old/test_old.py::test_it`"}, "task"),
        ({"documentation": "Add a section to `docs/OLD.md`"}, "task"),
        ({"verify": "uv run devops ci test tests/old/test_old.py"}, "verify"),
    ],
)
def test_a_missing_path_is_a_problem_wherever_the_group_names_it(
    update: dict[str, object], place: str
) -> None:
    (problem,) = _problems(_group(**update))

    named = next(
        value
        for value in (
            "src/devops_cli/old.py",
            "tests/old/test_old.py",
            "docs/OLD.md",
        )
        if f"`{value}`" in problem
    )
    assert named
    assert place in problem


def test_a_path_that_many_places_name_is_one_problem() -> None:
    old = "tests/old/test_old.py"
    group = _group(
        reads=[old],
        changes=[old],
        implementation=f"Change `{old}`",
        verify=f"uv run devops ci test {old}",
    )

    assert len(_problems(group, group)) == 1


def test_a_path_with_a_location_is_checked_without_it() -> None:
    group = _group(
        test="Write `tests/test_sample.py::test_it` and read `src/devops_cli/sample.py:12-20`"
    )

    assert _problems(group) == []


# ── What is a path ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "span",
    [
        "status/blocked",
        "type/bug",
        "--strict",
        "-k",
        "example.com",
        "devops_cli.config",
        "StageGroup.test",
        "uv run devops ci docs",
        "uv run devops docs generate",
        "https://example.com/docs/a.md",
        "<change>/tasks.md",
        "tests/**/*.py",
        "$HOME/notes.md",
        "/etc/hosts",
        "../outside.py",
        "--ignore=tests/old/test_old.py",
        "1.0.0",
        "DEVOPS_CLI_ROADMAP_STAGE_LIMIT",
    ],
)
def test_a_span_that_is_no_path_is_not_checked(span: str) -> None:
    assert _problems(_group(implementation=f"Use `{span}`")) == []


@pytest.mark.parametrize(
    "span", ["commands/uv_cmd.py", "src/devops_cli/new_package", "docs/missing"]
)
def test_a_name_with_a_known_suffix_or_a_top_folder_is_a_path(span: str) -> None:
    (problem,) = _problems(_group(implementation=f"Use `{span}`"))

    assert f"`{span}`" in problem


def test_a_bare_file_name_in_a_task_is_a_fixture_and_no_path() -> None:
    group = _group(test="Write `tests/test_sample.py` that writes `ruff.toml` and `uv_cmd.py`")

    assert _problems(group) == []


def test_a_bare_file_name_in_a_search_pattern_is_no_path() -> None:
    group = _group(verify="git ls-files | grep uv_cmd.py")

    assert _problems(group) == []


def test_a_bare_file_name_in_changes_is_still_checked() -> None:
    (problem,) = _problems(_group(changes=["ruff.toml"]))

    assert "`ruff.toml`" in problem


def test_a_command_in_a_span_has_its_paths_checked() -> None:
    (problem,) = _problems(_group(implementation="Run `pytest tests/old/test_old.py -x -q`"))

    assert "`tests/old/test_old.py`" in problem


def test_a_path_in_plain_text_is_not_checked() -> None:
    assert _problems(_group(implementation="Change src/devops_cli/old.py")) == []


def test_a_glob_passes_when_a_file_matches_it() -> None:
    assert _problems(_group(reads=["tests/roadmap/test_*.py"])) == []
    (problem,) = _problems(_group(reads=["tests/nothing/test_*.py"]))
    assert "`tests/nothing/test_*.py`" in problem


def test_a_folder_of_the_commit_passes() -> None:
    assert _problems(_group(reads=["tests/security/", "docs"])) == []


def test_the_files_added_to_a_tree_exist_in_it() -> None:
    group = _group(reads=["openspec/changes/1-a/tasks.md"])
    tree = TREE.with_files(["openspec/changes/1-a/tasks.md"])

    assert (len(_problems(group)), _problems(group, tree=tree)) == (1, [])


# ── A change-folder path a group never writes (#3285) ────────────────────────


def _construct(**update: object) -> StageGroup:
    """A group that skips the schema of the reply, as the replay builds one when it fails."""
    base = {
        "title": "Keep the last comment",
        "kind": GroupKind.BEHAVIOR,
        "reads": ["src/devops_cli/sample.py"],
        "changes": ["src/devops_cli/sample.py"],
        "creates": [],
        "test": "Write `test_the_job_keeps_the_last_comment` in `tests/test_sample.py`",
        "implementation": "Keep the last comment in `src/devops_cli/sample.py`",
        "documentation": "Change no document",
        "verify": "uv run devops ci test tests/test_sample.py",
    }
    return StageGroup.model_construct(**{**base, **update})


def test_a_recorded_group_that_creates_a_change_folder_path_is_reported() -> None:
    group = _construct(
        changes=["src/devops_cli/sample.py", "openspec/changes/1-a/proposal.md"],
        creates=["openspec/changes/1-a/proposal.md"],
    )

    (problem,) = _problems(group)

    assert "openspec/changes/1-a/proposal.md" in problem
    assert "must not change or create" in problem


def test_a_group_that_only_reads_a_change_folder_path_has_no_problem() -> None:
    group = _construct(reads=["src/devops_cli/sample.py", "openspec/changes/1-a/tasks.md"])
    tree = TREE.with_files(["openspec/changes/1-a/tasks.md"])

    assert _problems(group, tree=tree) == []


# ── The plans of 2026-10-31 ───────────────────────────────────────────────────

# The plan of #2260 (pull request 2975), group 1 and group 8, as the model wrote them.
PLAN_2260 = [
    _group(
        title="uv lock and uv sync dry-run request plans",
        reads=[],
        changes=["src/devops_cli/commands/uv_cmd.py", "tests/test_dry_run_uv.py"],
        test=(
            "Write a failing test in tests/test_dry_run_uv.py that calls devops uv lock --dry-run"
        ),
        implementation="In src/devops_cli/commands/uv_cmd.py, add --dry-run",
        verify="uv run pytest tests/test_dry_run_uv.py -v",
    ),
    _group(
        title="Remove 14 paths from dry_run_gaps.json and verify ratchet test",
        reads=[],
        changes=["tests/fixtures/dry_run_gaps.json"],
        kind="other",
        test=None,
        verify="uv run pytest tests/test_roadmap_dry_runs.py -v",
    ),
]

# The plan of #2162 (pull request 2979), group 2: 18 test files, 14 of them moved or gone.
_MOVED_2162 = {
    "tests/test_custom_personas.py": "tests/ai/personas/test_custom_personas.py",
    "tests/test_review_advisory_backing.py": "tests/ai/test_review_advisory_backing.py",
    "tests/test_review_deduplication.py": "tests/ai/review/test_review_deduplication.py",
    "tests/test_review_defects_comments.py": "tests/ai/review/test_review_defects_comments.py",
    "tests/test_review_defenses_and_verification.py": (
        "tests/ai/review/test_review_defenses_and_verification.py"
    ),
    "tests/test_review_history.py": "tests/ai/review/test_review_history.py",
    "tests/test_review_location_paths.py": "tests/ai/test_review_location_paths.py",
    "tests/test_review_loop_hardening.py": "tests/ai/test_review_loop_hardening.py",
    "tests/test_review_regression_harness.py": "tests/ai/review/test_review_regression_harness.py",
    "tests/test_review_taxonomy_and_severity.py": (
        "tests/ai/review/test_review_taxonomy_and_severity.py"
    ),
    "tests/test_review_verification.py": "tests/ai/test_review_verification.py",
    "tests/test_structural_positional_oracles.py": "tests/ai/test_structural_positional_oracles.py",
    "tests/test_security_kubelinter.py": "tests/security/test_security_kubelinter.py",
}
_GONE_2162 = ["tests/test_security_tflint.py"]
_KEPT_2162 = [
    "tests/ai/review/test_cited_code.py",
    "tests/commands/test_review.py",
    "tests/commands/test_review_removed_options.py",
    "tests/security/test_sarif_fuzzing.py",
]


def test_the_plan_of_2260_names_a_command_file_and_a_test_file_that_are_not_on_main() -> None:
    problems = _problems(*PLAN_2260)

    gone = [p for p in problems if "`src/devops_cli/commands/uv_cmd.py`" in p]
    moved = [p for p in problems if "`tests/test_roadmap_dry_runs.py`" in p]
    assert (len(problems), len(gone), len(moved)) == (3, 1, 1)
    assert "No file has this name" in gone[0]
    assert "`tests/roadmap/test_roadmap_dry_runs.py`" in moved[0]


def test_the_plan_of_2162_names_14_test_files_that_are_not_on_main() -> None:
    tree = StagedTree([*TREE.files, *_KEPT_2162, *_MOVED_2162.values()])
    group = _group(
        reads=[], changes=[*_KEPT_2162, *_MOVED_2162, *_GONE_2162], verify="uv run devops ci"
    )

    problems = path_problems([group], tree)

    assert len(problems) == 14
    assert all(
        f"`{real}`" in problem
        for old, real in _MOVED_2162.items()
        for problem in problems
        if f"`{old}`" in problem
    )
    assert sum("No file has this name" in problem for problem in problems) == 1


def test_the_plan_of_2116_names_one_test_file_that_moved_to_the_security_folder() -> None:
    group = _group(
        reads=[],
        changes=["tests/test_scanner_tool_executor.py"],
        verify="uv run pytest tests/test_scanner_tool_executor.py -x",
    )

    (problem,) = _problems(group)

    assert "`tests/security/test_scanner_tool_executor.py`" in problem


# ── The paths of a negative search are checked (#3263) ────────────────────────────────────


def _search(verify: str, *, creates: list[str] | None = None) -> list[str]:
    changes = ["src/devops_cli/sample.py", *(creates or [])]
    return _problems(_group(verify=verify, changes=changes, creates=creates or []))


@pytest.mark.parametrize(
    "verify",
    [
        "! git grep -n old_name src/ tests/",
        "! git grep -n old_name -- src tests",
        "! git grep -n old_name -- src/devops_cli tests/roadmap",
        "! git grep -n old_name -- docs/TESTING.md README.md",
        "! git grep -n old_name -- tests/*.py",
        "! git grep -n old_name -- .",
        "! git grep -n old_name -- ./src",
    ],
)
def test_a_negative_search_over_paths_of_the_commit_has_no_problem(verify: str) -> None:
    assert _search(verify) == []


@pytest.mark.parametrize(
    ("verify", "missing"),
    [
        ("! git grep -n hello scr/ testz/", ["scr", "testz"]),
        ("! git grep -n hello -- scr tests", ["scr"]),
        ("! git grep -n hello -- src/devops_clix", ["src/devops_clix"]),
    ],
)
def test_a_negative_search_over_a_path_that_is_not_in_the_commit_is_a_problem(
    verify: str, missing: list[str]
) -> None:
    problems = _search(verify)

    assert [path for path in missing if any(f"`{path}`" in text for text in problems)] == missing
    assert len(problems) == len(missing)


def test_a_negative_search_over_a_folder_that_the_plan_creates_has_no_problem() -> None:
    assert _search("! git grep -n x -- tests/newdir", creates=["tests/newdir/test_new.py"]) == []


def test_a_negative_search_that_the_step_refuses_is_judged_by_the_form_check_only() -> None:
    """The reader refuses the shape first, so the word `|` is no path to look up."""
    assert _search("! git grep -n x src/ | cat") == []


@pytest.mark.parametrize(
    ("verify", "missing"),
    [
        ("! git grep -n devops README.md/", "README.md"),
        ("! git grep -n x -- src/devops_cli/sample.py/", "src/devops_cli/sample.py"),
    ],
)
def test_a_trailing_slash_on_a_file_is_a_problem(verify: str, missing: str) -> None:
    problems = _search(verify)

    assert len(problems) == 1
    assert f"`{missing}`" in problems[0]


def test_a_trailing_slash_on_a_folder_is_no_problem() -> None:
    assert _search("! git grep -n x src/devops_cli/ docs/") == []


def test_the_words_of_a_refused_search_are_still_checked_as_paths() -> None:
    """The reader refuses `-O`, so the paths come from the words of the command."""
    problems = _search("! git grep -O name tests/old/test_old.py")

    assert len(problems) == 1
    assert "`tests/old/test_old.py`" in problems[0]


def test_the_words_of_a_command_that_shlex_cannot_read_are_still_checked_as_paths() -> None:
    problems = _search('uv run devops ci test tests/old/test_old.py "')

    assert len(problems) == 1
    assert "`tests/old/test_old.py`" in problems[0]


# ── A task group writes no living spec (#3295) ───────────────────────────────


@pytest.mark.parametrize(
    "path",
    ["openspec/specs/config-commands/spec.md", "openspec/specs/new-capability/spec.md"],
)
def test_a_group_that_lists_a_living_spec_is_refused(path: str) -> None:
    with pytest.raises(ValidationError) as raised:
        _group(changes=[path], creates=[path])

    assert path in str(raised.value)
    assert "only openspec archive writes living specs" in str(raised.value)


def test_a_group_that_reads_a_living_spec_passes() -> None:
    group = _group(reads=["openspec/specs/config-commands/spec.md"])

    assert _problems(group) == []


# ── A plan that changes a function must name every caller (#3307) ───────────


def _git_checkout(root: Path) -> StagedTree:
    from tests.support.roadmap_stage import run_git

    run_git(root, "init", "-q", "-b", "main")
    run_git(root, "config", "user.name", "Test")
    run_git(root, "config", "user.email", "test@example.com")
    run_git(root, "add", "-A")
    run_git(root, "commit", "-q", "-m", "init")
    return StagedTree.read(root, operation="test")


def test_a_plan_that_leaves_out_a_caller_is_refused(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "a.py").write_text("def check_proposal():\n    pass\n", encoding="utf-8")
    (src_dir / "b.py").write_text(
        "from a import check_proposal\n\ndef caller():\n    check_proposal()\n",
        encoding="utf-8",
    )
    tree = _git_checkout(tmp_path)

    group = _group(changes=["src/a.py"], test="Add `probes` to `check_proposal`")
    problems = path_problems([group], tree)

    assert any("check_proposal" in p and "src/b.py" in p for p in problems)


def test_a_plan_listing_every_caller_passes(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "a.py").write_text("def check_proposal():\n    pass\n", encoding="utf-8")
    (src_dir / "b.py").write_text(
        "from a import check_proposal\n\ndef caller():\n    check_proposal()\n",
        encoding="utf-8",
    )
    tree = _git_checkout(tmp_path)

    group = _group(
        changes=["src/a.py", "src/b.py"],
        test="Add a probes parameter to `check_proposal`",
    )
    problems = path_problems([group], tree)

    assert not any("check_proposal" in p for p in problems)


def test_caller_check_skipped_when_tree_has_no_checkout() -> None:
    tree = StagedTree(["src/a.py", "src/b.py"])
    group = _group(
        changes=["src/a.py"],
        test="Add the keyword `probes` to `check_proposal`",
    )
    problems = path_problems([group], tree)

    assert not any("check_proposal" in p for p in problems)


# Each task text of the refused replies and the archived tasks, and the names that it adds a
# parameter to (#4467, #4529). A task names a function in a clause `add ... to `name`` that says
# parameter, argument or keyword, or that adds one code span in parameter shape. A decorator, an
# option, a constant and a property are no parameter, and a clause ends at `.`, `:` or `;`.
_CHANGED_FUNCTION_CASES = [
    pytest.param("Add a probes parameter to `check_proposal`", ["check_proposal"], id="parameter"),
    pytest.param("Add `known` to `build_import_graph`", ["build_import_graph"], id="name-span"),
    pytest.param(
        "Add `sampling: CallSampling | None = None` to `_retry_chat_dispatch`",
        ["_retry_chat_dispatch"],
        id="typed-span-with-a-default",
    ),
    pytest.param(
        "In `claude.py`, add `sampling: CallSampling | None = None` to `_build_anthropic_kwargs` "
        "and `_claude_messages`",
        ["_build_anthropic_kwargs", "_claude_messages"],
        id="typed-span-to-two-functions",
    ),
    pytest.param(
        "Add the `verifier` to `plan_stage` and to the planner of `stage.py`",
        ["plan_stage"],
        id="span-after-the",
    ),
    pytest.param(
        'Add `@dry_run_class("request-plan")` to `run_benchmark`', [], id="decorator-span"
    ),
    pytest.param("Add `--take-ownership` to `_build_helm_upgrade_cmd`", [], id="option-span"),
    pytest.param(
        "Add `_criteria_section` and pass the criteria to `_tasks_file`",
        [],
        id="span-and-other-words",
    ),
    pytest.param(
        'Add `claim_texts(proposal)`, the member `CLASS_CLAIM = "class-claim"` of `ProposalGate`, '
        "and the keyword `class_text` to `check_gates`",
        ["check_gates"],
        id="keyword-at-the-end-of-a-list",
    ),
    pytest.param(
        "In `stage_change.py`, add the keyword-only argument `base_scenarios` to `check_gates` and "
        "`check_proposal` with its docstring",
        ["check_gates", "check_proposal"],
        id="argument-of-two-functions",
    ),
    pytest.param(
        'Add `REVIEW = "review"` to `FailureClass` in `src/devops_cli/roadmap/failure.py`',
        [],
        id="member-of-an-enum",
    ),
    pytest.param(
        "Add the property `added_names` to `TaskGroup` in `src/devops_cli/roadmap/step_files.py`",
        [],
        id="property-of-a-class",
    ),
    pytest.param(
        "add `constant_claims` to `StageProposal` with an empty default",
        ["StageProposal"],
        id="field-of-a-model-read-as-a-name",
    ),
    pytest.param(
        "Add `_Run.missing_check(call_site, check)`: it reads the definition, and when no command "
        "is left it appends the claim to `skipped`",
        [],
        id="list-in-the-next-clause",
    ),
    pytest.param(
        "Add the method `_repair_scope` to the run in `implement_run.py`: it takes the folder. In "
        "`_repair_after_push`, pass the same log to `_fix`",
        [],
        id="call-in-the-next-sentence",
    ),
    pytest.param(
        "Add `test_the_replay_reads_the_base_scenario_names` to `tests/x/test_y.py` for the "
        "requirement `R`: the replay passes them to `check_proposal`",
        [],
        id="test-function-of-a-test-file",
    ),
]


@pytest.mark.parametrize(("text", "functions"), _CHANGED_FUNCTION_CASES)
def test_the_caller_check_reads_only_a_parameter_that_a_task_adds(
    text: str, functions: list[str]
) -> None:
    from devops_cli.roadmap.stage.stage_paths import changed_functions

    assert changed_functions([_group(implementation=text)]) == functions


def test_a_field_of_a_model_has_no_caller_problem(tmp_path: Path) -> None:
    """The clause reads `StageProposal`, and no module defines it with `def` (#4529)."""
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "a.py").write_text("class StageProposal:\n    groups: list = []\n", encoding="utf-8")
    (src_dir / "b.py").write_text(
        "from a import StageProposal\n\nplan = StageProposal()\n", encoding="utf-8"
    )
    tree = _git_checkout(tmp_path)

    group = _group(
        changes=["src/a.py"],
        test="add `constant_claims` to `StageProposal` with an empty default",
    )
    problems = path_problems([group], tree)

    assert not any("StageProposal" in p for p in problems)


# The files under `src/` that hold the name of a function as a word, and whether each calls it
# (#4467). `asyncio.TaskGroup` and `scan_fix` were callers of the refused replies.
_CALLER_CASES = [
    pytest.param("check_proposal", "problems = check_proposal(plan)\n", True, id="call"),
    pytest.param("_fix", "self._fix(check, log)\n", True, id="call-of-a-method"),
    pytest.param("check_proposal", '"""Run check_proposal(plan) first."""\n', False, id="string"),
    pytest.param("_fix", "result = scan_fix(log)\n", False, id="longer-name"),
    pytest.param("check_proposal", "from a import check_proposal\n", False, id="import-only"),
]


@pytest.mark.parametrize(("name", "text", "calls"), _CALLER_CASES)
def test_a_caller_is_a_file_that_calls_the_function(name: str, text: str, calls: bool) -> None:
    from devops_cli.roadmap.stage.stage_paths import calling_files

    defined = f"class Run:\n    def {name}(self) -> None: ...\n"

    found = calling_files({"src/a.py": defined, "src/b.py": text}, name)

    assert found == (["src/b.py"] if calls else [])


def test_a_class_has_no_caller() -> None:
    """`TaskGroup` of `step_files.py` is a class, and `asyncio.TaskGroup()` called another one."""
    from devops_cli.roadmap.stage.stage_paths import calling_files

    modules = {
        "src/step_files.py": "class TaskGroup: ...\n",
        "src/pool.py": "async with asyncio.TaskGroup() as group: ...\n",
    }

    assert calling_files(modules, "TaskGroup") == []


# ── A plan that changes a manifest names the tests that reference it (#3972) ─


MANIFEST = "k8s/logging/networkpolicy.yaml"
MANIFEST_TEST = "tests/k8s/test_logging_policy.py"
FOLDER_ONLY_TEST = "tests/k8s/test_logging_only.py"


def _manifest_checkout(root: Path) -> Path:
    """A checkout that holds the logging perimeter and two tests of it: one that names the manifest
    and the folder in separate strings, and one that names the folder alone."""
    (root / "k8s" / "logging").mkdir(parents=True, exist_ok=True)
    (root / MANIFEST).write_text("kind: NetworkPolicy\n", encoding="utf-8")
    (root / "tests" / "k8s").mkdir(parents=True, exist_ok=True)
    (root / MANIFEST_TEST).write_text(
        'MANIFEST = "networkpolicy.yaml"\nNAMESPACE = "logging"\n', encoding="utf-8"
    )
    (root / FOLDER_ONLY_TEST).write_text('NAMESPACE = "logging"\n', encoding="utf-8")
    _git_checkout(root)
    return root


def _manifest_group(*changes: str) -> StageGroup:
    """A group that changes the paths of a manifest plan, and names no other file."""
    return _group(
        reads=[],
        changes=list(changes),
        implementation="Change the logging perimeter",
        verify="uv run devops ci docs",
    )


def test_the_record_names_the_test_that_builds_the_path_from_its_parts(tmp_path: Path) -> None:
    # Imported here: the base commit has neither function, and a module-level import would stop the
    # module at collection, before any assertion runs.
    from devops_cli.roadmap.stage.stage_paths import (
        missing_reference_problems,
        record_test_references,
    )

    root = _manifest_checkout(tmp_path)
    search = partial(grep_at, root, "HEAD", operation="test")

    references = record_test_references([_manifest_group(MANIFEST)], search)

    assert references == {MANIFEST: (MANIFEST_TEST,)}
    (problem,) = missing_reference_problems([_manifest_group(MANIFEST)], references)
    assert f"`{MANIFEST}`" in problem
    assert f"`{MANIFEST_TEST}`" in problem
    assert "`Changes:`" in problem
    assert missing_reference_problems([_manifest_group(MANIFEST, MANIFEST_TEST)], references) == []


KNOWN = ["comment-thread"]


def test_a_manifest_plan_that_omits_its_test_is_refused() -> None:
    tree = StagedTree([*TREE.files, MANIFEST, MANIFEST_TEST])
    references = {MANIFEST: (MANIFEST_TEST,)}

    omitted = check_gates(
        make_stage_proposal(groups=[_manifest_group(MANIFEST)]),
        KNOWN,
        tree,
        manifest_references=references,
        registry=(),
    )
    listed = check_gates(
        make_stage_proposal(groups=[_manifest_group(MANIFEST, MANIFEST_TEST)]),
        KNOWN,
        tree,
        manifest_references=references,
        registry=(),
    )

    (problem,) = omitted[ProposalGate.PATHS]
    assert problem == MESSAGES.roadmap.stage_problem_missing_perimeter_test.format(
        path=MANIFEST, test=MANIFEST_TEST
    )
    assert listed[ProposalGate.PATHS] == []


# ── A behavior group names the existing test of its module (#3414) ───────────

MODULE = "src/devops_cli/roadmap/stage/stage_paths.py"
MODULE_TEST = "tests/roadmap/stage/test_roadmap_stage_paths.py"
CREATED_TEST = "tests/roadmap/stage/test_stage_paths_rule.py"
OTHER_MODULE = "src/devops_cli/roadmap/step_files.py"
OTHER_TEST = "tests/roadmap/implement/test_roadmap_implement_step.py"
MESSAGES_MODULE = "src/devops_cli/lang/en/messages.py"
SAMPLE_TEST = "tests/roadmap/test_roadmap_sample.py"
# The files of the staged commit that the record reads, with their text: each test imports the
# module it tests, and the package `devops_cli.lang` imports the messages through its subpackage.
_TEXTS = {
    MODULE: "def path_problems() -> None: ...\n",
    MODULE_TEST: "from devops_cli.roadmap.stage.stage_paths import path_problems\n",
    OTHER_MODULE: "def parse_task_groups() -> None: ...\n",
    OTHER_TEST: "from devops_cli.roadmap.step_files import parse_task_groups\n",
    MESSAGES_MODULE: "MESSAGES = object()\n",
    "src/devops_cli/lang/__init__.py": "from devops_cli.lang.en import MESSAGES\n",
    "src/devops_cli/lang/en/__init__.py": "from devops_cli.lang.en.messages import MESSAGES\n",
    "src/devops_cli/lang/en/errors.py": "ERRORS = object()\n",
    "src/devops_cli/cloudflare/client.py": "class Client: ...\n",
    "src/devops_cli/github/client.py": "class Client: ...\n",
}


def _module_tree(tests: dict[str, str] | None = None) -> tuple[StagedTree, Search]:
    """The staged tree of `_TEXTS` and `tests`, a map of a test path to its text, and the search
    of that commit, as `git grep -F -w -l` gives it: the files that hold a literal as a word."""
    texts = {**_TEXTS, **(tests or {})}

    def search(literal: str) -> list[str]:
        word = re.compile(rf"(?<!\w){re.escape(literal)}(?!\w)")
        return sorted(path for path, text in texts.items() if word.search(text))

    return StagedTree([*TREE.files, *texts], reader=texts.__getitem__), search


def _module_group(**update: object) -> StageGroup:
    """A behavior group that changes `MODULE` and names only the test that it creates."""
    base = {
        "reads": [],
        "changes": [MODULE, CREATED_TEST],
        "creates": [CREATED_TEST],
        "test": f"Write `test_the_rule` in `{CREATED_TEST}`",
        "implementation": f"Refuse the group in `{MODULE}`",
        "verify": f"uv run devops ci test {CREATED_TEST}",
    }
    return _group(**{**base, **update})


def test_a_behavior_group_that_omits_the_test_of_its_module_is_refused() -> None:
    tree, search = _module_tree()
    group = _module_group()

    module_tests = record_module_tests([group], tree, search)

    assert module_tests == {MODULE: (MODULE_TEST,)}
    (problem,) = existing_test_problems([group], tree, module_tests)
    assert "Group 1" in problem
    assert f"`{MODULE}`" in problem
    assert f"`{MODULE_TEST}`" in problem


@pytest.mark.parametrize(
    "update",
    [
        {"reads": [MODULE_TEST]},
        {"changes": [MODULE, MODULE_TEST, CREATED_TEST]},
        {"test": f"Write `test_the_rule` in `{CREATED_TEST}`, as `{MODULE_TEST}` pins"},
        {"verify": f"uv run devops ci test {MODULE_TEST}"},
    ],
)
def test_a_behavior_group_that_names_the_test_of_its_module_passes(
    update: dict[str, object],
) -> None:
    tree, search = _module_tree()
    group = _module_group(**update)

    module_tests = record_module_tests([group], tree, search)

    assert existing_test_problems([group], tree, module_tests) == []


# Each test of the staged commit, and whether it is a test of the module that a group changes
# (#4467). A test of a module imports it, in any form of an import and at any depth of the test. The
# false cases come from the refused replies of the stage job: the gate asked for
# `tests/commands/test_new.py`, which holds the path of the messages module in a string, and for a
# test that carries the stem of a module in another package.
_IMPORT_CASES = [
    pytest.param(
        MODULE,
        "tests/sample/test_sample_import.py",
        "from devops_cli.roadmap.stage.stage_paths import path_problems\n",
        True,
        id="from-the-module-import-a-name",
    ),
    pytest.param(
        MODULE,
        "tests/sample/test_sample_import.py",
        "from devops_cli.roadmap.stage import stage_paths\n",
        True,
        id="from-the-package-import-the-module",
    ),
    pytest.param(
        MODULE,
        "tests/sample/test_sample_import.py",
        "import devops_cli.roadmap.stage.stage_paths as paths\n",
        True,
        id="import-the-module",
    ),
    pytest.param(
        MODULE,
        "tests/sample/test_sample_import.py",
        "def test_rule() -> None:\n    from devops_cli.roadmap.stage.stage_paths import x\n",
        True,
        id="import-in-a-test-function",
    ),
    pytest.param(
        MESSAGES_MODULE,
        "tests/sample/test_sample_import.py",
        "from devops_cli.lang import MESSAGES\n",
        True,
        id="import-a-package-that-imports-the-module",
    ),
    pytest.param(
        MESSAGES_MODULE,
        "tests/commands/test_new.py",
        'MESSAGES_FILE = "src/devops_cli/lang/en/messages.py"\n',
        False,
        id="the-path-of-the-module-in-a-string",
    ),
    pytest.param(
        MODULE,
        "tests/sample/test_sample_import.py",
        'TARGET = "devops_cli.roadmap.stage.stage_paths.path_problems"\n',
        False,
        id="the-dotted-name-in-a-string",
    ),
    pytest.param(
        MESSAGES_MODULE,
        "tests/sample/test_sample_import.py",
        "from devops_cli.lang.en.errors import ERRORS\n",
        False,
        id="import-another-module-of-the-package",
    ),
    pytest.param(
        "src/devops_cli/github/client.py",
        "tests/cloudflare/test_client.py",
        "from devops_cli.cloudflare.client import Client\n",
        False,
        id="the-stem-of-a-module-of-another-package",
    ),
    pytest.param(
        MODULE,
        "tests/sample/test_sample_import.py",
        "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n"
        "    from devops_cli.roadmap.stage.stage_paths import StagedTree\n",
        False,
        id="import-for-types-only",
    ),
]


@pytest.mark.parametrize(("module", "test", "text", "imports"), _IMPORT_CASES)
def test_the_record_holds_a_test_only_when_it_imports_the_module(
    module: str, test: str, text: str, imports: bool
) -> None:
    tree, search = _module_tree({test: text})
    group = _module_group(changes=[module, CREATED_TEST])

    record = record_module_tests([group], tree, search)

    assert (test in record.get(module, ())) is imports


FOLLOW_MODULE = "src/devops_cli/roadmap/follow.py"
FOLLOW_TEST = "tests/roadmap/test_roadmap_follow.py"
NEW_TEST = "tests/commands/test_new.py"
# The tests of the refused replies of #3049, #3076 and #4043 (#4467): the scaffold test holds the
# path of the messages module in a string, the test of `follow.py` imports that module, which shows
# the messages, and a sample test imports the messages through their package.
_MESSAGES_TESTS = {
    NEW_TEST: 'MESSAGES_FILE = "src/devops_cli/lang/en/messages.py"\n',
    FOLLOW_MODULE: "from devops_cli.lang import MESSAGES\n\ndef follow() -> None: ...\n",
    FOLLOW_TEST: "from devops_cli.roadmap.follow import follow\n",
    SAMPLE_TEST: "from devops_cli.lang import MESSAGES\n",
}


@pytest.mark.parametrize(
    ("changes", "reads", "missing"),
    [
        pytest.param([MESSAGES_MODULE], [SAMPLE_TEST], None, id="reads-a-test-of-the-package"),
        pytest.param(
            [FOLLOW_MODULE, MESSAGES_MODULE],
            [FOLLOW_TEST],
            None,
            id="reads-the-test-of-a-changed-module-that-shows-the-messages",
        ),
        pytest.param(
            [MESSAGES_MODULE], [NEW_TEST], SAMPLE_TEST, id="reads-only-a-holder-of-the-path"
        ),
        pytest.param(
            [MODULE, MESSAGES_MODULE],
            [MODULE_TEST],
            SAMPLE_TEST,
            id="reads-the-test-of-a-changed-module-that-shows-no-message",
        ),
    ],
)
def test_a_group_that_changes_the_messages_names_a_test_that_runs_them(
    changes: list[str], reads: list[str], missing: str | None
) -> None:
    """The gate asked the plans that changed the messages for `tests/commands/test_new.py`, which
    holds their path in a string and runs none of them, and refused each reply (#4467)."""
    tree, search = _module_tree(_MESSAGES_TESTS)
    group = _module_group(changes=[*changes, CREATED_TEST], reads=reads)

    problems = existing_test_problems([group], tree, record_module_tests([group], tree, search))

    if missing is None:
        assert problems == []
    else:
        (problem,) = problems
        assert f"`{MESSAGES_MODULE}`" in problem
        assert f"`{missing}`" in problem


def test_a_module_whose_only_holder_is_no_test_of_it_is_exempt() -> None:
    tree, search = _module_tree(
        {"tests/commands/test_new.py": 'MESSAGES_FILE = "src/devops_cli/lang/en/messages.py"\n'}
    )
    group = _module_group(changes=[MESSAGES_MODULE, CREATED_TEST])

    module_tests = record_module_tests([group], tree, search)

    assert module_tests == {}
    assert existing_test_problems([group], tree, module_tests) == []


def test_a_tree_that_cannot_read_its_files_records_no_test() -> None:
    """A tree of a replay case has no checkout and no reader, so the gate judges no module."""
    tree, search = _module_tree()
    group = _module_group()

    assert record_module_tests([group], StagedTree(tree.files), search) == {}


def test_grep_at_reads_a_dotted_name_as_a_fixed_string(tmp_path: Path) -> None:
    """`git grep -e` reads each dot of `devops_cli.lang.en.messages` as any sign, so the search
    found the path `src/devops_cli/lang/en/messages.py` in a string (#4467)."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_new.py").write_text(
        'MESSAGES_FILE = "src/devops_cli/lang/en/messages.py"\n', encoding="utf-8"
    )
    (tmp_path / "tests" / "test_amend.py").write_text(
        "from devops_cli.lang.en.messages import MESSAGES\n", encoding="utf-8"
    )
    _git_checkout(tmp_path)

    found = grep_at(tmp_path, "HEAD", "devops_cli.lang.en.messages", operation="test")

    assert found == ("tests/test_amend.py",)


def test_a_module_with_no_existing_test_is_exempt() -> None:
    module = "src/devops_cli/roadmap/stage/stage_untested.py"
    tree, search = _module_tree({module: "def untested() -> None: ...\n"})
    group = _module_group(changes=[module, CREATED_TEST])

    module_tests = record_module_tests([group], tree, search)

    assert module_tests == {}
    assert existing_test_problems([group], tree, module_tests) == []


def test_a_test_that_the_plan_creates_is_no_existing_test() -> None:
    tree, _search = _module_tree()
    group = _module_group()

    assert existing_test_problems([group], tree, {MODULE: (CREATED_TEST,)}) == []


def test_two_groups_that_omit_their_module_test_each_get_a_problem() -> None:
    tree, search = _module_tree()
    first = _module_group()
    second = _module_group(changes=[OTHER_MODULE, CREATED_TEST])

    module_tests = record_module_tests([first, second], tree, search)

    assert sorted(module_tests) == [MODULE, OTHER_MODULE]
    problems = existing_test_problems([first, second], tree, module_tests)
    assert len(problems) == 2
    assert "Group 1" in problems[0]
    assert f"`{MODULE_TEST}`" in problems[0]
    assert "Group 2" in problems[1]
    assert f"`{OTHER_TEST}`" in problems[1]


def test_an_other_group_that_changes_a_module_is_not_judged() -> None:
    tree, search = _module_tree()
    group = _construct(kind=GroupKind.OTHER, changes=[MODULE, CREATED_TEST], creates=[CREATED_TEST])

    assert record_module_tests([group], tree, search) == {}
    assert existing_test_problems([group], tree, {MODULE: (MODULE_TEST,)}) == []
