"""Refine finds its own section again after each write (#6627).

A marker of refine bounds its section only where CommonMark reads the marker as an HTML block of
its own. CommonMark reads all text after an open fenced code block or an open HTML block as part of
that block. So refine closes such a block at the end of its own text, and at the end of the text of
a person that its section follows. The next round then replaces the section, adds no second one,
and reads the item as unchanged. A marker that a person quotes stays in the text of the person.

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
from devops_cli.roadmap.body_hash import extract_section_and_outside, is_unchanged
from devops_cli.roadmap.refine.refine import RefinementProposal
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
) -> list[tuple[int, bool, bool]]:
    """Run `count` rounds of refine. For each round: the start markers in the body, whether a
    read finds the section, and whether the next round reads the item as unchanged."""
    seen = []
    for _ in range(count):
        refine_round(store, source)
        body = store.read_issue_body(number)
        seen.append(
            (
                body.count(CONST_ROADMAP_REFINE_START_MARKER),
                extract_section_and_outside(body)[1] is not None,
                is_unchanged(require_item(store, number), body),
            )
        )
    return seen


@pytest.mark.parametrize(
    ("body", "proposal"),
    [
        pytest.param(
            _PERSON,
            READY.model_copy(update={"problem_statement": _OPEN_FENCE}),
            id="fence-in-the-model-text",
        ),
        pytest.param(f"{_PERSON}\n\n```\nAn open fence of a person.\n", READY, id="person-fence"),
        pytest.param(
            f"{_PERSON}\n\n<pre>\nAn open pre block of a person.\n", READY, id="person-pre"
        ),
    ],
)
def test_an_open_block_leaves_one_section_and_an_unchanged_item_over_three_rounds(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
    body: str,
    proposal: RefinementProposal,
) -> None:
    """Each round leaves one section that a read finds, the item reads as unchanged, so only the
    first round asks the model, and the text of the person stays at the start of the body."""
    number = seed_with_body(store, body)
    model_fake.answer(proposal)

    seen = _rounds(store, git_repo, number, 3)

    assert (
        seen,
        len(model_fake.calls),
        store.read_issue_body(number).startswith(body.rstrip()),
    ) == ([(1, True, True)] * 3, 1, True)


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
