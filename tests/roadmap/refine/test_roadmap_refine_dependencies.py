"""The blockers of a Dependencies section, and the mentions that name no dependency (#6451).

Each issue reference of the section names a blocker, also in prose, unless the text names a link
and no blocker: a block that starts with `None` or `No`, the references after a link word such as
`Part of`, `Child 2 of`, `Tracker`, `Related` or `Source`, a sentence with a reverse phrase such as
`#N needs this item`, a block whose issue merges in either order, and a reference in parentheses
with other words, such as the tracker of the hold line `- #N (hold: ... of #M)`. The start or the
end marker of a job block ends the section (#6613).
"""

from __future__ import annotations

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_END_MARKER,
    CONST_ROADMAP_ALTERNATIVES_START_MARKER,
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
)
from devops_cli.roadmap.refine.refine import body_dependencies

# The hold line that the freeze of #6519 writes as the first item of a Dependencies section.
HOLD = (
    "- #6521 (hold: incremental work on the stage, implement and fix-checks jobs waits for the "
    "re-architecture of #6519)"
)


def _alternatives_block(lacks: str) -> str:
    """A short copy of the block that the alternatives job writes, whose Lacks list holds `lacks`."""
    return (
        f"{CONST_ROADMAP_ALTERNATIVES_START_MARKER}\n"
        "Alternatives check of 2026-11-21: build.\n\n"
        f"Lacks:\n- {lacks}\n"
        f"{CONST_ROADMAP_ALTERNATIVES_END_MARKER}\n"
    )


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


def test_body_dependencies_keeps_a_blocker_written_in_prose() -> None:
    """A blocker that a person writes in prose still names a dependency: a paragraph that starts
    with `#N` and goes on, the openers `Depends on`, `Blocked by` and `Waits for`, a merge order
    in a sentence of a block that opens with other words, a sibling child that a quoted title
    names with its number, and the number of a quoted title (#6451)."""
    assert body_dependencies(
        "## Dependencies\n\n#5421 (merged first).\n\nDepends on #5380 (the step budget).\n\n"
        "#4847; #4798 with the fixable check of its scope comment, merged first.\n\n"
        "Blocked by #12.\n\nWaits for #13.\n\n"
        "Open the pull request after the pull request of #5234 merges.\n\n"
        "Issue #5451 sets the forms. Start this item after #5451 merges.\n\n"
        "#4970 (the rerank route). The stop test of #4968 must pass first.\n\n"
        '- Child 2 of #4742: "feat(k8s): apply store buckets" (#4756).\n'
        '- "feat(roadmap): a title" (#123)\n'
    ) == [5421, 5380, 4847, 4798, 12, 13, 5234, 5451, 5451, 4970, 4968, 4756, 123]


def test_body_dependencies_names_no_link_in_a_list_item_or_a_blocker_line() -> None:
    """A list item or a sentence that names a reverse link, a parent or an issue that merges in
    either order names no dependency, a block that starts with `None` names none, a tracker of an
    owner decision names none, and a `Merge first` line names its blocker and not the parent of
    that blocker (#6451)."""
    assert body_dependencies(
        "## Dependencies\n\n- #3803 waits for this item.\n- #4517 is the parent tracker.\n"
        "- #6347 (open): changes `_verdict_of` too. Rebase before the second of the two merges.\n"
        "- #5135 comes after this item.\n\nMerge first: #4835, child 8 of #4833.\n\n"
        "#5131 (the fixture). This item blocks #5134 step 6.\n\n"
        "It does not wait for #5343, because the Dockerfile does not change.\n\n"
        "None. #4385, #4386 and #5168 use these records.\n\n"
        "#5327, #5328 and #5330; owner decisions 2, 3 in #5311. Part of the plan #5311.\n"
    ) == [4835, 5131, 5327, 5328, 5330]


def test_the_hold_line_names_its_hold_issue_and_not_the_tracker() -> None:
    """The hold line of the freeze, the first item of the Dependencies section, names the hold
    issue as a blocker, so a person lifts every hold when that issue closes. The tracker that its
    parentheses name, and a `None.`, a related or a reverse line after it, name no dependency
    (#6519, #6521)."""
    assert (
        body_dependencies(f"### Dependencies\n\n{HOLD}\n"),
        body_dependencies(f"### Dependencies\n\n{HOLD}\n\nNone.\n"),
        body_dependencies(f"### Dependencies\n\n{HOLD}\n- #4847: the prerequisite\n"),
        body_dependencies(f"### Dependencies\n\n{HOLD}\nRelated: #4408\n"),
        body_dependencies(f"### Dependencies\n\n{HOLD}\n#4691 needs this item.\n"),
    ) == ([6521], [6521], [6521, 4847], [6521], [6521])


@pytest.mark.parametrize(
    ("body", "blockers"),
    [
        pytest.param(
            "## Dependencies\n\nNone.\n"
            + _alternatives_block("Two-container template integration that #5506 adds"),
            [],
            id="alternatives-after-section",
        ),
        pytest.param(
            f"Body\n\n{CONST_ROADMAP_REFINE_START_MARKER}\n## Proposed design\n\n"
            f"### Dependencies\n- #4989\n{CONST_ROADMAP_REFINE_END_MARKER}\n\n"
            + _alternatives_block("A tool that #5506 adds"),
            [4989],
            id="refine-part-then-alternatives",
        ),
        pytest.param(
            f"Body\n\n{CONST_ROADMAP_REFINE_START_MARKER}\n## Proposed design\n\n"
            f"### Dependencies\n- #4989\n{CONST_ROADMAP_REFINE_END_MARKER}\n\n"
            "Depends on #8888.\n",
            [4989],
            id="refine-part-then-person-text",
        ),
        pytest.param(
            _alternatives_block("A tool that #5506 adds") + "\n## Dependencies\n\n- #4989\n",
            [4989],
            id="section-after-alternatives",
        ),
        pytest.param(
            "## Dependencies\n\n"
            f"The job writes `{CONST_ROADMAP_ALTERNATIVES_START_MARKER}` after this section.\n\n"
            "- #4989\n",
            [4989],
            id="marker-in-code-span",
        ),
        pytest.param(
            "## Dependencies\n- #4989\n<!-- note\n" + _alternatives_block("A tool that #5506 adds"),
            [4989],
            id="comment-open-above-alternatives",
        ),
        pytest.param(
            f"Body\n\n```\nAn open fence.\n\n{CONST_ROADMAP_REFINE_START_MARKER}\n"
            f"## Proposed design\n\n### Dependencies\n- #4989\n{CONST_ROADMAP_REFINE_END_MARKER}\n\n"
            + _alternatives_block("A tool that #5506 adds"),
            [4989],
            id="fence-open-above-the-refine-block",
        ),
    ],
)
def test_a_job_block_marker_ends_the_dependencies_section(body: str, blockers: list[int]) -> None:
    """The Dependencies section ends at the start or the end marker of a job block, so the Lacks
    list of an alternatives block after it names no blocker. The `### Dependencies` part of the
    refine block ends at the refine end marker, also when no other job block follows it, a heading
    after an alternatives block still starts a section, and a marker in a code span ends no section
    (#6613). A comment that a person leaves open ends at the start marker, so that marker ends the
    section too, and a fence that a person leaves open ends at the first job block marker, so the
    refine block after it names its blockers (#6736)."""
    assert body_dependencies(body) == blockers
