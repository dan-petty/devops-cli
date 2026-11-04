"""The verification pass of the stage job: its input, its findings and the quote rule (#3153)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS,
    CONST_ROADMAP_STAGE_VERIFY_MAX_FILES,
)
from devops_cli.roadmap.stage_eval_cases import DefectType
from devops_cli.roadmap.stage_verify import (
    OPEN_TYPES,
    PLAN_NEEDS_FIX_LABEL,
    RETURN_TYPES,
    Finding,
    Verification,
    VerificationInput,
    findings_section,
    open_findings,
    open_findings_section,
    return_problem,
    returning,
)

PLAN = {
    "summary": "Stop the job dropping a comment",
    "why": "The job drops the last comment of a thread.",
    "groups": [
        {
            "title": "Keep the last comment",
            "reads": ["src/a.py"],
            "changes": ["src/a.py", "tests/test_a.py", "../outside.py"],
        },
        {"title": "Second", "reads": ["docs/guide.md"], "changes": ["src/a.py", "src/b.py"]},
    ],
}


def _input(root: Path | None = None, plan: dict[str, object] | None = None) -> VerificationInput:
    return VerificationInput.of(
        number=7,
        title="fix(roadmap): the job drops a comment",
        body="The job drops the last comment.\nIt happens on a long thread.",
        plan=plan or PLAN,
        source=root or Path("/nonexistent"),
    )


def _finding(kind: DefectType, quote: str = "") -> Finding:
    return Finding(type=kind, where="group 1", problem="The plan is wrong.", quote=quote)


def test_the_prompt_names_the_nine_types_and_no_other() -> None:
    line = next(
        line
        for line in load_task_prompt("roadmap_stage_verify.md").splitlines()
        if "nine types" in line
    )

    named = set(re.findall(r"`([a-z_]+)`", line))

    assert named == {kind.value for kind in DefectType}


def test_the_missing_path_type_names_a_needed_file_that_the_plan_does_not_change() -> None:
    line = next(
        line
        for line in load_task_prompt("roadmap_stage_verify.md").splitlines()
        if line.startswith("- `missing_path`")
    )

    assert "does not exist" in line
    assert "needs a file that the plan does not change" in line


def test_a_finding_with_a_type_outside_the_nine_is_refused() -> None:
    with pytest.raises(ValidationError, match="type"):
        Verification.model_validate(
            {"findings": [{"type": "style", "where": "x", "problem": "y", "quote": ""}]}
        )


def test_the_return_types_are_the_three_that_the_issue_names() -> None:
    assert RETURN_TYPES == {
        DefectType.MISSING_PATH,
        DefectType.FALSE_PREMISE,
        DefectType.IGNORES_EXISTING_CODE,
    }


def test_the_cited_files_are_the_existing_files_of_reads_and_changes_in_plan_order(
    tmp_path: Path,
) -> None:
    root = tmp_path / "checkout"
    for name in ("src/a.py", "docs/guide.md", "src/b.py"):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(f"text of {name}\n", encoding="utf-8")
    (tmp_path / "outside.py").write_text("secret\n", encoding="utf-8")

    given = _input(root)

    assert list(given.files) == ["src/a.py", "docs/guide.md", "src/b.py"]
    assert given.files["src/a.py"] == "text of src/a.py\n"


def test_a_long_cited_file_is_cut_to_the_cap(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("word " * 20000, encoding="utf-8")

    given = _input(tmp_path)

    kept = given.files["src/a.py"]
    assert 0 < len(kept) < len("word " * 20000)
    assert len(kept) < CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS * 8


def test_only_the_files_up_to_the_cap_are_read(tmp_path: Path) -> None:
    names = [f"src/f{index}.py" for index in range(CONST_ROADMAP_STAGE_VERIFY_MAX_FILES + 5)]
    (tmp_path / "src").mkdir()
    for name in names:
        (tmp_path / name).write_text("x = 1\n", encoding="utf-8")
    plan = {"groups": [{"reads": names, "changes": names}]}

    given = _input(tmp_path, plan)

    assert list(given.files) == names[:CONST_ROADMAP_STAGE_VERIFY_MAX_FILES]


def test_a_secret_in_a_cited_file_is_masked(tmp_path: Path) -> None:
    token = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text(f'TOKEN = "{token}"\n', encoding="utf-8")

    given = _input(tmp_path)

    assert token not in given.files["src/a.py"]


def test_the_payload_holds_the_issue_the_plan_and_the_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")

    payload = _input(tmp_path).payload()

    assert set(payload) == {"number", "title", "body", "plan", "files"}
    assert (payload["number"], payload["plan"], payload["files"]) == (
        7,
        PLAN,
        {"src/a.py": "x = 1\n"},
    )


def test_a_quote_of_the_issue_the_plan_or_a_file_is_in_the_input(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def keep(comments):\n    return 1\n", encoding="utf-8")

    given = _input(tmp_path)

    assert [
        given.contains(quote)
        for quote in (
            "It happens   on a long thread.",
            "The job drops the last comment of a thread.",
            "def keep(comments):\n    return 1",
            "text that no part holds",
            "",
            "   ",
        )
    ] == [True, True, True, False, False, False]


def test_a_return_type_with_a_quote_in_the_input_returns_the_plan() -> None:
    given = _input()
    findings = [
        _finding(DefectType.FALSE_PREMISE, "The job drops the last comment"),
        _finding(DefectType.MISSING_PATH, "invented quote"),
        _finding(DefectType.CONTRIVED_TEST, "The job drops the last comment"),
        _finding(DefectType.IGNORES_EXISTING_CODE),
    ]

    assert returning(findings, given) == [findings[0]]


def test_the_open_types_add_the_spec_delta_to_the_return_types() -> None:
    assert OPEN_TYPES == RETURN_TYPES | {DefectType.SPEC_DELTA_WRONG}
    assert PLAN_NEEDS_FIX_LABEL == "plan/needs-fix"


def test_an_open_finding_is_a_listed_type_or_a_placeholder_with_a_quote_in_the_input() -> None:
    given = _input(
        plan={"groups": [{"title": "placeholder"}, {"title": "The job drops a comment"}]}
    )
    findings = [
        _finding(DefectType.SPEC_DELTA_WRONG, "The job drops the last comment"),
        _finding(DefectType.OTHER, "placeholder"),
        _finding(DefectType.MISSING_PATH, "invented quote"),
        _finding(DefectType.TASK_ORDER, "The job drops the last comment"),
        _finding(DefectType.OTHER),
    ]

    assert open_findings(findings, given) == [findings[0], findings[1]]


def test_the_open_findings_section_lists_each_open_finding_first() -> None:
    finding = _finding(DefectType.OTHER, "placeholder")

    section = open_findings_section([finding])

    assert PLAN_NEEDS_FIX_LABEL in section
    assert "placeholder" in section
    assert open_findings_section([]) == ""


def test_the_problem_that_goes_back_to_the_planner_names_each_finding() -> None:
    problem = return_problem([_finding(DefectType.FALSE_PREMISE, "The job drops the last comment")])

    assert "false_premise" in problem
    assert "group 1" in problem
    assert "The job drops the last comment" in problem


def test_the_findings_section_is_empty_without_findings() -> None:
    assert findings_section([]) == ""


def test_the_findings_section_puts_each_finding_on_one_line_without_a_ping() -> None:
    finding = Finding(
        type=DefectType.CONTRIVED_TEST,
        where="group 2",
        problem="The test\nasks @octocat to read https://example.com/x.",
        quote="a  quote",
    )

    section = findings_section([finding])

    (line,) = [line for line in section.splitlines() if "contrived_test" in line]
    assert "@octocat" not in line.replace("`@octocat`", "")
    assert "group 2" in line
    assert "\n" not in line
