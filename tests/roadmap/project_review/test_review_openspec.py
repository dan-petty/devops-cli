"""The `openspec` reader of the project review catalog (#4692): the deltas of the changes that the
window archived, from `openspec show`, and the requirement totals at the base and at the head,
over the recorded git scenario `review_openspec`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli.roadmap.project_review.openspec_read import read_openspec, show_args
from devops_cli.roadmap.project_review.readers import Reads
from tests.support.fakes.git import GitFake
from tests.support.fakes.openspec import OpenSpecFake

CHANGE = "2026-10-03-add-two"


@pytest.fixture
def checkout(git_fake: GitFake, tmp_path: Path) -> Path:
    """The repository of the scenario `review_openspec`, as git answered for it."""
    git_fake.replay("review_openspec")
    return tmp_path / "specs"


def _files(root: Path) -> set[Path]:
    return {path for path in root.rglob("*")}


def test_one_archived_change_gives_its_deltas_and_the_totals_at_both_ends(
    checkout: Path, openspec_fake: OpenSpecFake
) -> None:
    deltas = [
        {"spec": "cap", "operation": "ADDED", "requirement": {"name": "Two"}},
        {"spec": "cap", "operation": "MODIFIED", "requirement": {"name": "One"}},
    ]
    seen: list[str] = []
    openspec_fake.script(
        show_args(CHANGE),
        0,
        json.dumps({"id": CHANGE, "deltas": deltas}),
        effect=lambda cwd: seen.extend(
            (cwd / "openspec/changes" / CHANGE / name).read_text(encoding="utf-8")
            for name in ("design.md", "specs/cap/spec.md")
        ),
    )
    before = _files(checkout)
    reads = Reads()

    answer = read_openspec(checkout, "v1.0.0", "v1.1.0", reads)

    assert answer == {
        "changes": [
            {
                "id": CHANGE,
                "deltas": [
                    {"spec": "cap", "operation": "ADDED", "requirement": "Two"},
                    {"spec": "cap", "operation": "MODIFIED", "requirement": "One"},
                ],
            }
        ],
        "unread": [],
        "requirements": {"base": 1, "head": 2},
    }
    shown = [call for call in openspec_fake.calls if call.argv[:1] == ("show",)]
    assert [call.argv for call in shown] == [show_args(CHANGE)]
    # A text read turns CRLF and a lone CR into one line end, and a byte that is not UTF-8 into
    # U+FFFD; the file after it keeps its own text.
    assert seen[0] == "# Design\n\nA caf\ufffd line.\nLast\n"
    assert seen[1].startswith("## ADDED Requirements")
    assert (_files(checkout), reads.counts["openspec"]) == (before, 1)


def test_a_change_that_openspec_cannot_show_is_listed_and_the_read_goes_on(
    checkout: Path, openspec_fake: OpenSpecFake
) -> None:
    """An archived proposal with no Why section fails `openspec show` (OpenSpec 2.1.0). The
    reader lists the change with the message of the tool, and the totals stay."""
    status = {
        "severity": "error",
        "code": "show_error",
        "message": "Change must have a Why section",
    }
    openspec_fake.script(show_args(CHANGE), 1, json.dumps({"status": [status]}))

    answer = read_openspec(checkout, "v1.0.0", "v1.1.0", Reads())

    assert answer == {
        "changes": [],
        "unread": [{"id": CHANGE, "reason": "Change must have a Why section"}],
        "requirements": {"base": 1, "head": 2},
    }
