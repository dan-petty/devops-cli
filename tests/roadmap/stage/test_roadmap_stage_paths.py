"""`devops roadmap stage`: the paths of a plan are files at the staged commit (#3010)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stage.stage_change import GroupKind, StageGroup
from devops_cli.roadmap.stage.stage_paths import StagedTree, path_problems
from tests.support.builders import make_stage_proposal

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
        "uv run devops docs generate --sync-readme",
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
