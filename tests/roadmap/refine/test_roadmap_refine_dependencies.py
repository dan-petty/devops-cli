"""The blocker lines of a Dependencies section, and the mentions that name no dependency (#6451).

A line names blockers when it starts with a blocker opener (`Merge first`, `Depends on`, `Blocked
by`, `Waits for`, `Wait for`), or when its first word is an issue reference and it is the first
text of a list item or a paragraph outside a list. A line with a reverse phrase, such as `needs
this item`, names no blocker, and a reference that follows `of` names a parent. A parent, a child,
a related issue and the source line of intake name no dependency.
"""

from __future__ import annotations

import pytest

from devops_cli.roadmap.refine.refine import body_dependencies


def test_body_dependencies_names_only_a_blocker_line() -> None:
    """A Dependencies section names a dependency only on a blocker line: `None.` and a
    `Source: #N` paragraph name none, a parent, a child, a related issue, a reverse link and a
    sentence that mentions an issue name none, a list item and a `Merge first` line name one, and
    a paragraph of issue references names each (#6451)."""
    assert (
        body_dependencies("## Dependencies\n\nNone.\n\nSource: #4989\n"),
        body_dependencies(
            "## Dependencies\n\nPart of #5014\n\nChild 5 of #4893\n\nRelated: #4408\n\n"
            "#4691 needs this item\n\nThis item blocks #5134 step 6\n"
        ),
        body_dependencies("## Dependencies\n\n- #4989\n\nMerge first: #5134\n"),
        body_dependencies("## Dependencies\n\n#2, #4\n"),
    ) == ([], [], [4989, 5134], [2, 4])


@pytest.mark.parametrize(
    ("section", "blockers"),
    [
        pytest.param(
            "#4847; #4798 with the fixable check of its scope comment, merged first.",
            [4847, 4798],
            id="4867-prose-paragraph",
        ),
        pytest.param("#5421 (merged first).", [5421], id="5430-merged-first-note"),
        pytest.param(
            "#4991: the exporter CPU limits must go up first.\n\nSource: #4989",
            [4991],
            id="4993-prose-and-source",
        ),
        pytest.param(
            "#4884, #4889, #3917. The scheduled reindex waits for #4566.",
            [4884, 4889, 3917, 4566],
            id="4921-references-then-prose",
        ),
        pytest.param("Depends on #5380 (the step budget).", [5380], id="5379-depends-on"),
        pytest.param(
            "Depends on #5356. The acceptance needs the running server.\n\n"
            "It does not wait for #5343, because the Dockerfile does not change.",
            [5356],
            id="5348-depends-on-and-a-sentence",
        ),
        pytest.param(
            "- #3741 (the gateway database backup sets the pattern).\n"
            "- #3803 (move the database to a worker node) waits for this item.\n"
            "- Tracker: #4742 (child 8).",
            [3741],
            id="4765-reverse-list-item",
        ),
        pytest.param("Merge first: #4835, child 8 of #4833.", [4835], id="4848-child-of-parent"),
        pytest.param(
            "#4550 puts the dependencies of the catalog first. #4691 needs this item.",
            [4550],
            id="4814-blocker-then-reverse-sentence",
        ),
        pytest.param(
            "- #4612 must merge first; #4598 waits for this item.",
            [4612],
            id="blocker-and-reverse-clause-in-one-item",
        ),
        pytest.param("None.\n\nSource: #4989", [], id="5001-source-after-none"),
        pytest.param("- Part of #5014 (track the Service step jobs).", [], id="5026-part-of"),
    ],
)
def test_body_dependencies_reads_the_blockers_of_real_bodies(
    section: str, blockers: list[int]
) -> None:
    """Short copies of the Dependencies sections of open items give their blockers: a paragraph
    or a list item that opens with `#N` and goes on in prose, and a `Depends on` line, keep every
    reference; a reverse link, a parent after `of`, a tracker and the source line keep none
    (#6451)."""
    assert body_dependencies(f"### Dependencies\n\n{section}\n") == blockers


@pytest.mark.parametrize(
    ("line", "blockers"),
    [
        pytest.param("Blocked by #12 and #13.", [12, 13], id="blocked-by"),
        pytest.param("waits for #12.", [12], id="waits-for-lower-case"),
        pytest.param("Wait for #12 to merge.", [12], id="wait-for"),
        pytest.param("MERGE FIRST: #12", [12], id="merge-first-upper-case"),
        pytest.param("#12 depends on this item.", [], id="depends-on-this-item"),
        pytest.param("#12 is Blocked By This Item.", [], id="blocked-by-this-item"),
        pytest.param("Depends on #12, part of #4833.", [12], id="part-of-parent"),
    ],
)
def test_body_dependencies_reads_openers_and_reverse_phrases_in_any_case(
    line: str, blockers: list[int]
) -> None:
    """Each blocker opener names the references of its line in any case, a reverse phrase in any
    case names none, and a reference after `of` is a parent (#6451)."""
    assert body_dependencies(f"## Dependencies\n\n{line}\n") == blockers
