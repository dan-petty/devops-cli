"""The plan reader reads the weakened checks of a plan (#3490): the `## Weakened checks` section of
`proposal.md`, the tests that its entries name, and the record at a commit of the repository.

Git runs for real on a repository in `tmp_path`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from devops_cli.roadmap.plan_read import (
    PlanReadError,
    merged_recorded_tests,
    read_change,
    recorded_tests,
    weakened_checks,
)
from devops_cli.roadmap.stage.stage_change import StageProposal, WeakenedCheck, render_change
from tests.support.builders import make_stage_proposal
from tests.support.implement_step import git

CREATED = datetime(2026, 11, 5, tzinfo=UTC).date()
OPERATION = "read the record"
ENTRY = "- **`tests/a.py::test_b`**: Stopped: a wrong version. Safeguard: `test_c` holds the claim."
SECOND = (
    "- **`tests/a.py::TestD.test_e` and `tests/f/g.py::test_h`**: Stopped: two old forms. "
    "Safeguard: Stopped: is no word of the form here."
)
PROPOSAL = (
    "# Proposal\n\n## Why\n\nWhy #1.\n\n## Weakened checks\n\n{section}\n\n## Feasibility\n\n- x\n"
)


def _proposal(*lines: str) -> str:
    return PROPOSAL.format(section="\n".join(lines))


def test_each_entry_of_the_section_reads_into_its_three_fields() -> None:
    assert weakened_checks(_proposal(ENTRY, SECOND)) == [
        WeakenedCheck(
            check="`tests/a.py::test_b`",
            stopped="a wrong version.",
            safeguard="`test_c` holds the claim.",
        ),
        WeakenedCheck(
            check="`tests/a.py::TestD.test_e` and `tests/f/g.py::test_h`",
            stopped="two old forms.",
            safeguard="Stopped: is no word of the form here.",
        ),
    ]


def test_a_plan_with_no_section_has_no_entry() -> None:
    assert weakened_checks("# Proposal\n\n## Why\n\nWhy #1.\n") == []


@pytest.mark.parametrize(
    "line",
    [
        "- **`tests/a.py::test_b`**: Stopped: a wrong version.",
        "- `tests/a.py::test_b`: Stopped: a wrong version. Safeguard: a new test.",
        "`tests/a.py::test_b` goes, with no bullet.",
        "- **`tests/a.py::test_b`**: Stopped: a wrong version. Safeguard:  ",
    ],
)
def test_a_line_in_another_form_is_refused_and_named(line: str) -> None:
    with pytest.raises(PlanReadError) as caught:
        weakened_checks(_proposal(ENTRY, line))

    assert (caught.value.path, line.strip() in caught.value.reason) == ("proposal.md", True)


def test_a_check_with_no_text_is_refused_and_is_no_validation_error() -> None:
    with pytest.raises(PlanReadError) as caught:
        weakened_checks(_proposal("- ** **: Stopped: a wrong version. Safeguard: a new test."))

    assert caught.value.path == "proposal.md"


def test_read_change_gives_the_entries_of_the_section() -> None:
    files = render_change("1-sample", make_stage_proposal(), {"comment-thread"}, created=CREATED)
    files["openspec/changes/1-sample/proposal.md"] = files[
        "openspec/changes/1-sample/proposal.md"
    ].replace("## Feasibility", f"## Weakened checks\n\n{ENTRY}\n\n## Feasibility")

    assert [entry.check for entry in read_change(files).weakened_checks] == ["`tests/a.py::test_b`"]


def test_read_change_refuses_a_section_in_another_form() -> None:
    files = render_change("1-sample", make_stage_proposal(), {"comment-thread"}, created=CREATED)
    files["openspec/changes/1-sample/proposal.md"] = files[
        "openspec/changes/1-sample/proposal.md"
    ].replace("## Feasibility", "## Weakened checks\n\nThe test goes.\n\n## Feasibility")

    with pytest.raises(PlanReadError) as caught:
        read_change(files)

    assert caught.value.path == "proposal.md"


def test_the_reply_schema_of_the_stage_model_does_not_show_the_field() -> None:
    """The stage job has no writer of the section, so a key in a reply would be lost."""
    assert "weakened_checks" not in StageProposal.model_json_schema()["properties"]
    assert make_stage_proposal().weakened_checks == []


def test_the_tests_of_a_record_are_the_path_and_name_of_each_check() -> None:
    assert recorded_tests(weakened_checks(_proposal(ENTRY, SECOND))) == {
        "tests/a.py::test_b",
        "tests/a.py::TestD.test_e",
        "tests/f/g.py::test_h",
    }


@pytest.mark.parametrize(
    "check",
    ["`tests/a.py`", "`test_b`", "the claim test of tests/a.py"],
)
def test_a_check_with_no_path_and_name_records_no_test(check: str) -> None:
    entry = WeakenedCheck(check=check, stopped="a wrong version.", safeguard="a new test.")

    assert recorded_tests([entry]) == frozenset()


def test_a_name_at_the_end_of_a_sentence_keeps_no_full_stop() -> None:
    entry = WeakenedCheck(
        check="The test tests/a.py::test_b.", stopped="a wrong version.", safeguard="a new test."
    )

    assert recorded_tests([entry]) == {"tests/a.py::test_b"}


def test_the_stopped_text_and_the_safeguard_record_no_test() -> None:
    entry = WeakenedCheck(
        check="`tests/a.py::test_b`",
        stopped="a bug that tests/a.py::test_c saw too.",
        safeguard="`tests/a.py::test_d` holds it.",
    )

    assert recorded_tests([entry]) == {"tests/a.py::test_b"}


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "Person")
    git(root, "config", "user.email", "person@example.com")
    return root


def _commit(root: Path, files: dict[str, str]) -> str:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "a change")
    return git(root, "rev-parse", "HEAD")


def test_the_record_at_a_commit_is_the_text_of_that_commit(repository: Path) -> None:
    folder = "openspec/changes/7-sample"
    with_entry = _commit(repository, {f"{folder}/proposal.md": _proposal(ENTRY)})
    later = _commit(repository, {f"{folder}/proposal.md": _proposal(SECOND)})

    read = merged_recorded_tests(repository, with_entry, 7, operation=OPERATION)

    assert read == {"tests/a.py::test_b"}
    assert merged_recorded_tests(repository, later, 7, operation=OPERATION) == {
        "tests/a.py::TestD.test_e",
        "tests/f/g.py::test_h",
    }


def test_a_commit_with_no_plan_of_the_item_records_no_test(repository: Path) -> None:
    other = _commit(repository, {"openspec/changes/8-other/proposal.md": _proposal(ENTRY)})

    assert merged_recorded_tests(repository, other, 7, operation=OPERATION) == frozenset()


def test_a_plan_with_no_proposal_records_no_test(repository: Path) -> None:
    head = _commit(repository, {"openspec/changes/7-sample/tasks.md": "# Tasks\n"})

    assert merged_recorded_tests(repository, head, 7, operation=OPERATION) == frozenset()


def test_an_archived_plan_records_no_test(repository: Path) -> None:
    head = _commit(
        repository, {"openspec/changes/archive/2026-11-05-7-sample/proposal.md": _proposal(ENTRY)}
    )

    assert merged_recorded_tests(repository, head, 7, operation=OPERATION) == frozenset()


def test_a_section_in_another_form_at_a_commit_is_refused(repository: Path) -> None:
    head = _commit(
        repository, {"openspec/changes/7-sample/proposal.md": _proposal("The test goes.")}
    )

    with pytest.raises(PlanReadError) as caught:
        merged_recorded_tests(repository, head, 7, operation=OPERATION)

    assert "The test goes." in caught.value.reason
