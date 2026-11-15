"""Tests of the issue drafts that the agent audit files through roadmap intake (#2346).

The audit files one issue for each group that the model made. The child `devops roadmap intake` is
the process edge, which `process_fake` answers, so no test starts a real program, reaches GitHub or
needs a roadmap.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Sequence

    from devops_cli.ai.agent_audit.finding import Finding
    from devops_cli.ai.agent_audit.grouping import FindingGroup
    from tests.support.fakes.process import ProcessCall, ProcessFake

# The group that the model made of the failures of the fixture sessions, and another group.
_GROUP = "Test runs that fail on a changed workspace"
_OTHER_GROUP = "A uv warning about the project environment"
# A group name that is longer than the summary of a title may be.
_LONG_GROUP = (
    "The agent sessions of this repository met a test run that failed on a changed workspace"
)
# A failure of a test run, as a signature reduces the line that the shell tool printed.
_SIGNATURE = "uv run devops ci test <path> | exit 1: failed <path>"
# A token of a group name, which no title and no body may hold.
_TOKEN = "ghp_1234567890abcdefghij"


def _finding(signature: str = _SIGNATURE, *, sessions: int = 3, recurrences: int = 4) -> Finding:
    """One finding, as `finding.py` gives it to the model stage and to the drafts."""
    from devops_cli.ai.agent_audit.finding import Finding

    return Finding(
        signature=signature,
        sessions=sessions,
        recurrences=recurrences,
        elapsed_seconds=0.0,
        pointers=(),
    )


def _group(name: str = _GROUP, *, signature: str = _SIGNATURE) -> FindingGroup:
    """One group of the report: `name`, with the one finding of `signature`."""
    from devops_cli.ai.agent_audit.grouping import FindingGroup

    return FindingGroup(name=name, findings=(_finding(signature),))


def _is_intake(call: ProcessCall) -> bool:
    """Whether `call` starts the intake command of the interpreter that runs the audit."""
    return call.argv[1:6] == ("-P", "-m", "devops_cli.entry", "roadmap", "intake")


def _option(argv: Sequence[str], name: str) -> str:
    """The word after the option `name` in `argv`."""
    return argv[argv.index(name) + 1]


def _titled(call: ProcessCall, name: str) -> bool:
    """Whether `call` files a draft whose title holds `name`."""
    return "--title" in call.argv and name in _option(call.argv, "--title")


def test_confirm_files_one_draft_for_each_group(process_fake: ProcessFake) -> None:
    """The audit files one issue for each group, through `devops roadmap intake --confirm`, and it
    reports the number of each filed issue (#2346)."""
    from devops_cli.ai.agent_audit.filing import drafts_of, file_drafts
    from tests.support.fakes.process import ProcessAnswer

    process_fake.answer(
        lambda call: _titled(call, _GROUP),
        ProcessAnswer(returncode=0, stdout="Filed #41.\n"),
    )
    process_fake.answer(
        lambda call: _titled(call, _OTHER_GROUP),
        ProcessAnswer(returncode=0, stdout="Filed #42.\n"),
    )

    filed = file_drafts(
        drafts_of([_group(), _group(_OTHER_GROUP, signature="uv run ruff check <path>")])
    )

    calls = [call for call in process_fake.calls if _is_intake(call)]
    assert len(calls) == 2
    assert [each.number for each in filed] == [41, 42]
    assert _GROUP in filed[0].title
    assert _OTHER_GROUP in filed[1].title
    assert all(each.title.startswith("fix(ai): ") for each in filed)
    assert all("--confirm" in call.argv for call in calls)


def test_the_body_file_of_a_draft_holds_its_body(process_fake: ProcessFake) -> None:
    """The audit gives intake a body file that holds the draft body, so the filed issue holds the
    sections of the group (#2346)."""
    from devops_cli.ai.agent_audit.filing import drafts_of, file_drafts
    from tests.support.fakes.process import ProcessAnswer

    written: list[str] = []

    def answer(call: ProcessCall) -> ProcessAnswer:
        written.append(Path(_option(call.argv, "--body-file")).read_text(encoding="utf-8"))
        return ProcessAnswer(returncode=0, stdout="Filed #41.\n")

    process_fake.answer(_is_intake, answer)

    file_drafts(drafts_of([_group()]))

    assert len(written) == 1
    assert "### Problem Description" in written[0]
    assert _GROUP in written[0]
    assert _SIGNATURE in written[0]


def test_a_draft_that_intake_does_not_file_stops_the_audit(process_fake: ProcessFake) -> None:
    """A run of intake that fails raises the filing error with the title of the draft and the line
    that intake printed, and the audit files no later draft (#2346)."""
    from devops_cli.ai.agent_audit.filing import drafts_of, file_drafts
    from devops_cli.exceptions import AgentAuditFilingError
    from tests.support.fakes.process import ProcessAnswer

    process_fake.answer(
        _is_intake,
        ProcessAnswer(returncode=1, stderr="fatal: could not read the roadmap\n"),
    )

    with pytest.raises(AgentAuditFilingError, match=_GROUP):
        file_drafts(
            drafts_of([_group(), _group(_OTHER_GROUP, signature="uv run ruff check <path>")])
        )

    assert len([call for call in process_fake.calls if _is_intake(call)]) == 1


def test_a_draft_whose_intake_prints_no_number_is_reported_without_one(
    process_fake: ProcessFake,
) -> None:
    """A run of intake that ends without filing an issue, as one does for a candidate that it skips,
    reports its draft with no number and stops no later draft (#2346)."""
    from devops_cli.ai.agent_audit.filing import drafts_of, file_drafts
    from tests.support.fakes.process import ProcessAnswer

    process_fake.answer(
        _is_intake, ProcessAnswer(returncode=0, stdout="Intake placed 0 item(s).\n")
    )

    filed = file_drafts(drafts_of([_group()]))

    assert [each.number for each in filed] == [None]
    assert _GROUP in filed[0].title


def test_the_title_of_a_long_group_name_is_a_short_commit_title() -> None:
    """The title of a draft is a Conventional Commit title of the scope `ai`, which intake accepts,
    and a group name that is too long for its summary is shortened at a word boundary (#2346)."""
    from devops_cli.ai.agent_audit.filing import draft_title
    from devops_cli.roadmap.commit_title import commit_summary
    from devops_cli.roadmap.pull_form import SUMMARY_MAX_CHARS, summary_length, title_problems

    title = draft_title(_LONG_GROUP)

    assert title.startswith("fix(ai): ")
    assert summary_length(commit_summary(title)) <= SUMMARY_MAX_CHARS
    assert title_problems(title) == []
    assert title.startswith("fix(ai): The agent sessions of this repository")


def test_a_secret_of_a_group_name_reaches_no_title_and_no_body() -> None:
    """A token of a group name reaches no title and no body of a draft, so the audit files no secret
    (AGENTS.md rule 10)."""
    from devops_cli.ai.agent_audit.filing import drafts_of

    (draft,) = drafts_of([_group(f"the {_TOKEN} token")])

    assert _TOKEN not in draft.title
    assert "<masked-github-token>" in draft.title
    assert _TOKEN not in draft.body
    assert "<masked-github-token>" in draft.body


def test_the_drafts_are_filed_in_the_named_checkout(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """The audit files the drafts in the checkout that it read, so intake reads the roadmap of that
    repository and not of the working directory (#2346)."""
    from devops_cli.ai.agent_audit.filing import drafts_of, file_drafts

    file_drafts(drafts_of([_group()]), cwd=tmp_path)

    assert [call.cwd for call in process_fake.calls if _is_intake(call)] == [tmp_path]
