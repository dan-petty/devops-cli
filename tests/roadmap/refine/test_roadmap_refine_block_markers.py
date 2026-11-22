"""Refine finds its own section again after each write (#6627, #6736).

A marker of refine bounds its section only where CommonMark reads the marker as an HTML block of
its own, or as the last line of a comment that the marker ends. CommonMark reads all text after an
open fenced code block or an open HTML block as part of that block. So refine closes such a block at
the end of its own text, and at the end of the text of a person that its section follows. The next
round then replaces the section, adds no second one, and reads the item as unchanged. A block that a
person leaves open above the section ends at its first job block marker line, so a read still finds
the section. A marker that a person quotes stays in the text of the person.

The roadmap is the in-memory store, the model edge is the fake, and git is the fake of the refine
support module.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
)
from devops_cli.roadmap.body_hash import body_hashes, extract_section_and_outside, is_unchanged
from devops_cli.roadmap.refine.refine import RefinementProposal
from devops_cli.roadmap.stores.store import RefineRecordKey
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import READY, refine_round, require_item, seed_with_body

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake

pytestmark = pytest.mark.usefixtures("keyring_store")

_PERSON = "## Problem\nPerson text."
# A problem statement whose code fence the model does not close.
_OPEN_FENCE = "The run fails with:\n```\nTraceback (most recent call last):\n"


def _rounds(
    store: InMemoryRoadmapStore, source: Path, number: int, count: int
) -> tuple[list[tuple[int, bool, bool]], list[str]]:
    """Run `count` rounds of refine. For each round: the start markers in the body, whether a
    read finds the section, and whether the next round reads the item as unchanged; and the body
    after each round."""
    seen = []
    bodies = []
    for _ in range(count):
        refine_round(store, source)
        body = store.read_issue_body(number)
        bodies.append(body)
        seen.append(
            (
                body.count(CONST_ROADMAP_REFINE_START_MARKER),
                extract_section_and_outside(body)[1] is not None,
                is_unchanged(require_item(store, number), body),
            )
        )
    return seen, bodies


@pytest.mark.parametrize(
    ("body", "proposal", "head"),
    [
        pytest.param(
            _PERSON,
            READY.model_copy(update={"problem_statement": _OPEN_FENCE}),
            f"{_PERSON}\n\n",
            id="fence-in-the-model-text",
        ),
        pytest.param(
            f"{_PERSON}\n\n```\nAn open fence of a person.\n",
            READY,
            f"{_PERSON}\n\n```\nAn open fence of a person.\n```\n\n",
            id="person-fence",
        ),
        pytest.param(
            f"{_PERSON}\n\n<pre>\nAn open pre block of a person.\n",
            READY,
            f"{_PERSON}\n\n<pre>\nAn open pre block of a person.\n</pre>\n\n",
            id="person-pre",
        ),
    ],
)
def test_an_open_block_leaves_one_section_and_an_unchanged_item_over_three_rounds(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
    body: str,
    proposal: RefinementProposal,
    head: str,
) -> None:
    """Each round leaves one section that a read finds, the item reads as unchanged, so only the
    first round asks the model and the body does not change after it. The first round writes
    `head` before the start marker: the text of the person, the close of the block that the person
    left open on a line of its own, and a blank line."""
    number = seed_with_body(store, body)
    model_fake.answer(proposal)

    seen, bodies = _rounds(store, git_repo, number, 3)

    first = bodies[0]
    assert (
        seen,
        len(model_fake.calls),
        first[: first.find(CONST_ROADMAP_REFINE_START_MARKER)],
        bodies[1:],
    ) == ([(1, True, True)] * 3, 1, head, [first, first])


_QUOTED_PAIR = (
    f"A person writes `{CONST_ROADMAP_REFINE_START_MARKER}` and "
    f"`{CONST_ROADMAP_REFINE_END_MARKER}`, with the design text between them.\n\n"
    f"```\n{CONST_ROADMAP_REFINE_START_MARKER}\nA quoted section.\n"
    f"{CONST_ROADMAP_REFINE_END_MARKER}\n```"
)


def test_a_body_that_quotes_both_markers_keeps_them_and_gets_the_section_at_the_end(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A body quotes both markers in code spans and in a fenced code block, and holds no section:
    the write keeps every character of the quote and adds the section after it."""
    number = seed_with_body(store, _QUOTED_PAIR)
    model_fake.answer(READY)

    refine_round(store, git_repo)

    body = store.read_issue_body(number)
    outside, section = extract_section_and_outside(body)
    assert (
        body.startswith(f"{_QUOTED_PAIR}\n\n{CONST_ROADMAP_REFINE_START_MARKER}\n"),
        outside.strip(),
        section is not None and "## Proposed design" in section,
    ) == (True, _QUOTED_PAIR, True)


# A section of an earlier round of refine, at the end of the body.
_OLD_SECTION = (
    f"{CONST_ROADMAP_REFINE_START_MARKER}\n<!-- checked-at: sha=abc -->\n"
    f"## Proposed design\nAn old design.\n{CONST_ROADMAP_REFINE_END_MARKER}"
)


def test_an_open_comment_above_the_section_leaves_one_section_over_three_rounds(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """An earlier round of refine wrote and recorded a section, and then a person opens a comment
    above it. CommonMark ends that comment at the start marker of the section, so the start marker
    still bounds the section. The first round replaces the section and closes the comment of the
    person on a line of its own. Each round leaves one section, and only the first round asks the
    model."""
    earlier = f"{_PERSON}\n\n{_OLD_SECTION}"
    number = seed_with_body(store, earlier)
    body_hash, section_hash = body_hashes(earlier)
    store.set_marks(
        require_item(store, number),
        {RefineRecordKey.BODY_HASH: body_hash, RefineRecordKey.SECTION_HASH: section_hash},
    )
    store.write_issue_body(
        number, f"{_PERSON}\n\n<!-- An open comment of a person.\n\n{_OLD_SECTION}"
    )
    model_fake.answer(READY)

    seen, bodies = _rounds(store, git_repo, number, 3)

    first = bodies[0]
    assert (
        seen,
        len(model_fake.calls),
        first[: first.find(CONST_ROADMAP_REFINE_START_MARKER)],
        "An old design." in first,
        bodies[1:],
    ) == (
        [(1, True, True)] * 3,
        1,
        f"{_PERSON}\n\n<!-- An open comment of a person.\n-->\n\n",
        False,
        [first, first],
    )


@pytest.mark.parametrize(
    "opened",
    [
        pytest.param("```\nAn open fence of a person.", id="fence"),
        pytest.param("<pre>\nAn open pre block of a person.", id="pre"),
    ],
)
def test_a_block_that_a_person_opens_above_the_section_leaves_one_section_over_three_rounds(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, opened: str
) -> None:
    """An earlier round of refine wrote and recorded a section, and then a person opens a code
    fence or a `<pre>` block above it and does not close it. The block runs to the end of the body,
    and the start marker of the section ends it for a read (#6736). So each round finds the section,
    leaves one section in the body, and does not change the body after the first round."""
    earlier = f"{_PERSON}\n\n{_OLD_SECTION}"
    number = seed_with_body(store, earlier)
    body_hash, section_hash = body_hashes(earlier)
    store.set_marks(
        require_item(store, number),
        {RefineRecordKey.BODY_HASH: body_hash, RefineRecordKey.SECTION_HASH: section_hash},
    )
    store.write_issue_body(number, f"{_PERSON}\n\n{opened}\n\n{_OLD_SECTION}")
    model_fake.answer(READY)

    seen, bodies = _rounds(store, git_repo, number, 3)

    assert ([(count, found) for count, found, _ in seen], bodies[1:]) == (
        [(1, True)] * 3,
        [bodies[0], bodies[0]],
    )
