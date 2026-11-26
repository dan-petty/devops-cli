"""The entry of the brain index that the alternatives block and the job record of an issue give
(#4676).

The alternatives check keeps its result in the block of the body and in the keys
`alternatives.*` of the job record. They are the durable copy of the brain index (ADR 0023
section 3), so the entry of an issue is read from them with no request and no model call. The
block has two forms: the one of the check alone, and the one with the links of the reference step
(#4672), whose record also holds `alternatives.refs`. Each test writes its own body and record.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from devops_cli.roadmap.brain_entries import (
    BrainEntry,
    checked_entry,
    entry_of,
    reference_key_id,
    tool_key_id,
)
from devops_cli.roadmap.stores.store import (
    AlternativesRecordKey,
    GitHubState,
    IssueRecord,
    Verdict,
)

CHECKED_AT = "2026-11-26T05:10:18.933054+00:00"
TOOL_URL = "https://github.com/acme/widget-kit"
TOOL_ID = "github.com/acme/widget-kit"
BODY_HASH = "4f1def9ae48b73c8d8ab397cc1fec530873cd1e665e28b1cef32eb51326702a5"
ADR_HASH = "40ed395d9640dde04e935ead0df8cfdcd916f82b2bf6cb8a9083bbf04661378b"

START = "<!-- devops-roadmap-alternatives:start -->"
END = "<!-- devops-roadmap-alternatives:end -->"

# The block of a check with a tool, as the check alone writes it.
CHECK_BLOCK = f"""{START}
Alternatives check of 2026-11-26: covers.
Tool: Widget Kit (fork) ({TOOL_URL}), MIT License, last activity 2026-10-12, maintained.
Reason: The tool builds each widget of the item.

Covers:
- Widgets with a frame

Lacks:
- Widgets with no frame
{END}"""

# The same check with the links of the reference step (#4672): two more sections.
REFERENCE_BLOCK = f"""{START}
Alternatives check of 2026-11-26: covers.
Tool: Widget Kit (fork) ({TOOL_URL}), MIT License, last activity 2026-10-12, maintained.
Reason: The tool builds each widget of the item.

Covers:
- Widgets with a frame

Lacks:
- Widgets with no frame

Reference implementations:
- https://github.com/Acme/Frames/blob/0123abc/src/frame.py#L1-L9
- https://github.com/acme/panels/blob/4567def/panel.py#L3
- https://github.com/acme/frames/blob/0123abc/tests/test_frame.py#L5
- https://github.com/acme/grids/blob/89ab012/grid.py#L1
- https://github.com/acme/tiles/blob/cdef345/tile.py#L2

Official documentation:
- https://docs.example.com/widgets
{END}"""

REFERENCE_LINKS = (
    "https://github.com/Acme/Frames/blob/0123abc/src/frame.py#L1-L9 "
    "https://github.com/acme/panels/blob/4567def/panel.py#L3 "
    "https://github.com/acme/frames/blob/0123abc/tests/test_frame.py#L5 "
    "https://github.com/acme/grids/blob/89ab012/grid.py#L1 "
    "https://github.com/acme/tiles/blob/cdef345/tile.py#L2 "
    "https://docs.example.com/widgets"
)


def _record(**changes: str | None) -> dict[str, str | None]:
    """The record of a check with a tool, with `changes` in place of its values."""
    record: dict[str, str | None] = {
        "alternatives.checked_at": CHECKED_AT,
        "alternatives.body_hash": BODY_HASH,
        "alternatives.verdict": "covers",
        "alternatives.tool": TOOL_URL,
        "alternatives.tool_id": TOOL_ID,
        "alternatives.adr_hash": ADR_HASH,
    }
    return record | {f"alternatives.{name}": value for name, value in changes.items()}


def _entry(**changes: object) -> BrainEntry:
    """The entry of the check with a tool, with `changes` in place of its values."""
    fields: dict[str, object] = {
        "number": 7,
        "state": GitHubState.OPEN,
        "verdict": Verdict.COVERS,
        "checked_at": datetime(2026, 11, 26, 5, 10, 18, 933054, tzinfo=UTC),
        "body_hash": BODY_HASH,
        "adr_hash": ADR_HASH,
        "tool_id": TOOL_ID,
        "tool_url": TOOL_URL,
        "tool_name": "Widget Kit (fork)",
        "refs": (),
        "uses": (),
    }
    return BrainEntry(**(fields | changes))  # type: ignore[arg-type]


def test_an_issue_with_a_block_and_a_recorded_check_gives_its_entry() -> None:
    """The record gives the verdict, the canonical tool id, the hashes and the time of the check,
    the block gives the name that the check wrote for the tool, and the issue gives its state."""
    issue = IssueRecord(
        number=7,
        title="Build widgets",
        url="https://github.com/acme/widgets/issues/7",
        body=f"The item needs widgets.\n\n{CHECK_BLOCK}",
        state=GitHubState.CLOSED,
        job_record={
            AlternativesRecordKey.CHECKED_AT: CHECKED_AT,
            AlternativesRecordKey.BODY_HASH: BODY_HASH,
            AlternativesRecordKey.VERDICT: "covers",
            AlternativesRecordKey.TOOL: TOOL_URL,
            AlternativesRecordKey.TOOL_ID: TOOL_ID,
            AlternativesRecordKey.ADR_HASH: ADR_HASH,
        },
    )

    assert entry_of(issue) == _entry(state=GitHubState.CLOSED)


def test_a_check_with_five_reference_links_keeps_the_repositories_of_three() -> None:
    """The record of the reference step holds its links in `alternatives.refs`. The entry keeps
    the repository of each link to a GitHub repository, each one time, and at most 3: the two
    links to `acme/frames` are one reference, and the documentation link names no repository."""
    entry = checked_entry(
        7,
        GitHubState.OPEN,
        f"The item needs widgets.\n\n{REFERENCE_BLOCK}",
        _record(refs=REFERENCE_LINKS),
    )

    assert entry == _entry(
        refs=(
            "https://github.com/acme/frames",
            "https://github.com/acme/panels",
            "https://github.com/acme/grids",
        )
    )


def test_the_block_of_the_reference_step_reads_as_the_block_of_the_check_alone() -> None:
    """The two sections of the reference step change no field that the block gives: with the
    same record, both forms of the block give the same entry."""
    entries = [
        checked_entry(7, GitHubState.OPEN, f"Text.\n\n{block}\n\nMore text.", _record())
        for block in (CHECK_BLOCK, REFERENCE_BLOCK)
    ]

    assert entries == [_entry(), _entry()]


@pytest.mark.parametrize(
    "skip_line",
    [
        pytest.param("Class: docs, no search.", id="the-check-alone"),
        pytest.param("Class: docs, no model call.", id="with-the-reference-step"),
    ],
)
def test_a_skip_class_block_of_either_form_gives_an_entry_with_no_tool(skip_line: str) -> None:
    """A skip class names no tool and reads no ADR: the entry holds the verdict and no tool id."""
    block = (
        f"{START}\nAlternatives check of 2026-11-26: not-applicable.\n{skip_line}\n"
        f"Tool: none found.\n{END}"
    )
    record = _record(verdict="not-applicable", tool=None, tool_id=None, adr_hash=None)

    assert checked_entry(7, GitHubState.OPEN, block, record) == _entry(
        verdict=Verdict.NOT_APPLICABLE, adr_hash="", tool_id="", tool_url="", tool_name=""
    )


def test_a_check_that_recorded_no_tool_id_takes_the_canonical_id_of_its_tool_url() -> None:
    """A check from before the canonical id recorded only the URL of its tool: the entry takes
    the canonical id of that URL, the package URL of a PyPI page."""
    block = CHECK_BLOCK.replace(TOOL_URL, "https://pypi.org/project/Widget_Kit")
    record = _record(tool="https://pypi.org/project/Widget_Kit", tool_id=None)

    assert checked_entry(7, GitHubState.OPEN, block, record) == _entry(
        tool_id="pkg:pypi/widget-kit", tool_url="https://pypi.org/project/Widget_Kit"
    )


def test_the_entry_names_at_most_ten_used_entries() -> None:
    """`alternatives.brain_used` names the entries that the check used; the entry keeps 10."""
    used = " ".join(f"item:{number}" for number in range(1, 13))

    entry = checked_entry(7, GitHubState.OPEN, CHECK_BLOCK, _record(brain_used=used))

    assert entry == _entry(uses=tuple(f"item:{number}" for number in range(1, 11)))


@pytest.mark.parametrize(
    ("body", "record"),
    [
        pytest.param("A person deleted the block.", _record(), id="no-block"),
        pytest.param(CHECK_BLOCK, _record(verdict=None), id="no-verdict"),
        pytest.param(CHECK_BLOCK, _record(verdict="maybe"), id="an-unknown-verdict"),
        pytest.param(CHECK_BLOCK, _record(checked_at=None), id="no-check-time"),
        pytest.param(CHECK_BLOCK, _record(checked_at="yesterday"), id="a-time-that-is-no-time"),
        pytest.param(f"`{START}` and `{END}` in a sentence.", _record(), id="quoted-markers"),
    ],
)
def test_an_issue_with_no_block_or_no_recorded_check_gives_no_entry(
    body: str, record: dict[str, str | None]
) -> None:
    """A record with no block is no check, since a person deleted the block, and a block with no
    recorded verdict and time is no check either."""
    assert checked_entry(7, GitHubState.OPEN, body, record) is None


def test_a_pull_request_gives_no_entry() -> None:
    """The listing holds pull requests too. A pull request holds no check of the job."""
    pull = IssueRecord(
        number=8,
        title="feat: build widgets",
        url="https://github.com/acme/widgets/pull/8",
        body=CHECK_BLOCK,
        pull_request=True,
        job_record={
            AlternativesRecordKey.CHECKED_AT: CHECKED_AT,
            AlternativesRecordKey.VERDICT: "covers",
        },
    )

    assert entry_of(pull) is None


def test_the_key_id_of_a_tool_and_of_a_reference_is_16_hex_of_its_sha256() -> None:
    """The key of a tool holds a hash of its canonical id, and the key of a reference a hash of
    its repository URL (ADR 0023 section 6), so no key holds a `/` or a glob character."""
    url = "https://github.com/acme/frames"

    assert (tool_key_id(TOOL_ID), reference_key_id(url)) == (
        hashlib.sha256(TOOL_ID.encode()).hexdigest()[:16],
        hashlib.sha256(url.encode()).hexdigest()[:16],
    )
