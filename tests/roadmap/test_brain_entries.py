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
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

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


def _entry(**changes: Any) -> BrainEntry:
    """The entry of the check with a tool, with `changes` in place of its values."""
    fields: dict[str, Any] = {
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
    return BrainEntry(**(fields | changes))


def _checked_issue(association: str | None, login: str | None) -> IssueRecord:
    """A closed issue of an author with the relation `association` and the login `login`, with
    the block and the record of the check with a tool."""
    return IssueRecord(
        number=7,
        title="Build widgets",
        url="https://github.com/acme/widgets/issues/7",
        body=f"The item needs widgets.\n\n{CHECK_BLOCK}",
        state=GitHubState.CLOSED,
        author_association=association,
        author_login=login,
        job_record={
            AlternativesRecordKey.CHECKED_AT: CHECKED_AT,
            AlternativesRecordKey.BODY_HASH: BODY_HASH,
            AlternativesRecordKey.VERDICT: "covers",
            AlternativesRecordKey.TOOL: TOOL_URL,
            AlternativesRecordKey.TOOL_ID: TOOL_ID,
            AlternativesRecordKey.ADR_HASH: ADR_HASH,
        },
    )


@pytest.mark.parametrize(
    ("association", "login"),
    [
        pytest.param("OWNER", "octocat", id="the-owner"),
        pytest.param("COLLABORATOR", "hubot", id="a-collaborator"),
        pytest.param("CONTRIBUTOR", "github-actions[bot]", id="the-bot-of-the-workflows"),
    ],
)
def test_an_issue_with_a_block_and_a_recorded_check_gives_its_entry(
    association: str, login: str
) -> None:
    """The record gives the verdict, the canonical tool id, the hashes and the time of the check,
    the block gives the name that the check wrote for the tool, and the issue gives its state.
    The author of the issue is one that the jobs trust."""
    assert entry_of(_checked_issue(association, login)) == _entry(state=GitHubState.CLOSED)


@pytest.mark.parametrize(
    ("association", "login"),
    [
        pytest.param("NONE", "outsider", id="an-outside-account"),
        pytest.param("CONTRIBUTOR", "outsider", id="a-contributor"),
        pytest.param("CONTRIBUTOR", "github-actions-x[bot]", id="a-bot-with-a-similar-login"),
        pytest.param(None, None, id="no-author"),
    ],
)
def test_a_block_and_a_record_in_the_issue_of_an_untrusted_author_give_no_entry(
    association: str | None, login: str | None
) -> None:
    """The repository is public, and the body of an issue holds its record. An account with no
    write access can write a block and a record of its own. The job checks only the items of
    trusted authors, so such a block is no check of the job, and the issue gives no entry."""
    assert entry_of(_checked_issue(association, login)) is None


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


def test_a_recorded_time_with_no_zone_is_a_time_in_utc() -> None:
    """A record that a person wrote can hold a time with no zone. The entry reads it as UTC, so
    it compares with the time of each other check."""
    record = _record(checked_at="2026-11-26T05:10:18.933054")

    assert checked_entry(7, GitHubState.OPEN, CHECK_BLOCK, record) == _entry()


# Strings that the URL parser refuses: a name in brackets, a template, an open bracket and a
# full-width colon in the host.
NOT_A_URL = [
    pytest.param("https://[cluster-ip]:6443/healthz", id="a-name-in-brackets"),
    pytest.param("http://[{host}]:{port}", id="a-template"),
    pytest.param("https://[::1", id="an-open-bracket"),
    pytest.param("https://example.com\uff1a8080", id="a-full-width-colon"),
]


@pytest.mark.parametrize("text", NOT_A_URL)
def test_a_tool_url_that_is_no_url_is_its_own_tool_id(text: str) -> None:
    """A record holds a tool URL that the URL parser refuses, and no canonical id. The entry
    takes the string as its tool id, and the read raises nothing."""
    block = CHECK_BLOCK.replace(TOOL_URL, text)

    assert checked_entry(7, GitHubState.OPEN, block, _record(tool=text, tool_id=None)) == _entry(
        tool_id=text, tool_url=text
    )


@pytest.mark.parametrize("text", NOT_A_URL)
def test_a_reference_link_that_is_no_url_is_no_reference(text: str) -> None:
    """`alternatives.refs` holds a string that the URL parser refuses between two links. The
    entry keeps the repositories of the two links, and the read raises nothing."""
    links = (
        f"https://github.com/acme/frames/blob/0123abc/a.py {text} https://github.com/acme/panels"
    )

    assert checked_entry(7, GitHubState.OPEN, CHECK_BLOCK, _record(refs=links)) == _entry(
        refs=("https://github.com/acme/frames", "https://github.com/acme/panels")
    )


@pytest.mark.parametrize(
    "page",
    [
        pytest.param("https://pypi.org/project/ /", id="a-space"),
        pytest.param("https://pypi.org/project/..", id="two-dots"),
        pytest.param("https://pypi.org/project/widget@kit", id="a-name-with-an-at-sign"),
        pytest.param("https://pypi.org/project/\ud800", id="a-lone-surrogate"),
    ],
)
def test_a_pypi_page_whose_name_is_no_package_name_is_its_own_tool_id(page: str) -> None:
    """The tool URL is a page of PyPI whose last part is no name of a package. It names no
    package URL, so the entry takes the string as its tool id, and the read raises nothing."""
    block = CHECK_BLOCK.replace(TOOL_URL, page)

    assert checked_entry(7, GitHubState.OPEN, block, _record(tool=page, tool_id=None)) == _entry(
        tool_id=page, tool_url=page
    )


# Each code point, a lone surrogate too: the JSON of a record can hold each of them.
_TEXT = st.text(st.characters(exclude_categories=()), max_size=24)
_URL = st.builds(
    "https://{}/{}/{}".format,
    st.sampled_from(["github.com", "pypi.org/project", "example.com", "[::1", "[name]:6443"]),
    _TEXT,
    _TEXT,
)
_VALUE = st.one_of(st.none(), _TEXT, _URL)


@given(
    tool=_VALUE,
    tool_id=_VALUE,
    refs=st.lists(st.one_of(_TEXT, _URL), max_size=5).map(" ".join),
    used=_TEXT,
    checked_at=st.one_of(st.just(CHECKED_AT), _TEXT),
    verdict=st.one_of(st.sampled_from(["covers", "partly", "none", "in-use"]), _TEXT),
    hashes=_VALUE,
)
def test_no_value_of_a_record_makes_the_read_of_an_entry_raise(
    tool: str | None,
    tool_id: str | None,
    refs: str,
    used: str,
    checked_at: str,
    verdict: str,
    hashes: str | None,
) -> None:
    """A person can write a record by hand, so each value is open text. For each text, the read
    gives an entry or none and raises nothing, the entry keeps at most 3 references and 10 used
    entries, and the tool and each reference have a key id of 16 hex characters."""
    record = _record(
        tool=tool,
        tool_id=tool_id,
        refs=refs,
        brain_used=used,
        checked_at=checked_at,
        verdict=verdict,
        body_hash=hashes,
        adr_hash=hashes,
    )
    block = CHECK_BLOCK.replace(TOOL_URL, tool or "")

    entry = checked_entry(7, GitHubState.OPEN, block, record)

    if entry is not None:
        key_ids = [tool_key_id(entry.tool_id), *map(reference_key_id, entry.refs)]
        assert (
            len(entry.refs) <= 3,
            len(entry.uses) <= 10,
            [key_id for key_id in key_ids if len(key_id) != 16 or not set(key_id) <= _HEX],
        ) == (True, True, [])


_HEX = frozenset("0123456789abcdef")


def test_a_tool_id_that_is_no_unicode_text_has_a_key_id() -> None:
    """The JSON of a record can hold a lone surrogate, which is no text that UTF-8 encodes. The
    entry keeps the value, and the key id of the tool is still 16 hex characters."""
    entry = checked_entry(7, GitHubState.OPEN, CHECK_BLOCK, _record(tool_id="tool-\ud800"))
    assert entry is not None

    key_id = tool_key_id(entry.tool_id)
    assert (entry.tool_id, len(key_id), set(key_id) <= set("0123456789abcdef")) == (
        "tool-\ud800",
        16,
        True,
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
        pytest.param(f"Text.\n\n{START}\nAlternatives check", _record(), id="a-start-marker-only"),
        pytest.param(f"Text.\n\n{END}\n", _record(), id="an-end-marker-only"),
        pytest.param(f"{END}\nText.\n{START}", _record(), id="the-markers-in-the-wrong-order"),
        pytest.param("", _record(), id="an-empty-body"),
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
