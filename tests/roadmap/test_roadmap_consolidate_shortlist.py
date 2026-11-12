"""The shortlists of the consolidation job (#1127): evidence from tools, the contest rule and the
text that is embedded. No test calls a model, a network or a cluster."""

from __future__ import annotations

from collections.abc import Sequence

from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_END_MARKER,
    CONST_ROADMAP_ALTERNATIVES_START_MARKER,
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
)
from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_CONSOLIDATE_COMMON_CITATION,
    DEFAULT_ROADMAP_CONSOLIDATE_MEMBERS,
)
from devops_cli.roadmap.consolidate_shortlist import (
    Evidence,
    Member,
    Shortlist,
    Signal,
    assign_groups,
    consolidation_groups,
    embed_issues,
    read_blockers,
    shortlists,
)
from devops_cli.roadmap.stores.store import GitHubState, IssueRecord
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

PRIORITY = ("priority/p2-medium",)


def issue(
    number: int, body: str = "", *, parent: int | None = None, blocked_by: int = 0
) -> IssueRecord:
    return IssueRecord(
        number=number,
        title=f"Item {number}",
        url=f"https://github.com/example/roadmap/issues/{number}",
        body=body,
        parent=parent,
        blocked_by=blocked_by,
    )


def apart(numbers: Sequence[int]) -> dict[int, list[float]]:
    """A vector for each number that is at a right angle to the others: no item is nearer."""
    width = max(numbers) + 1
    return {n: [1.0 if place == n else 0.0 for place in range(width)] for n in numbers}


def members(lists: Sequence[Shortlist], anchor: int) -> dict[int, tuple[Evidence, ...]]:
    found = next((s for s in lists if s.anchor == anchor), None)
    return {} if found is None else {m.number: m.evidence for m in found.members}


def signals(lists: Sequence[Shortlist], anchor: int, member: int) -> set[Signal]:
    return {e.signal for e in members(lists, anchor).get(member, ())}


class Embedder:
    """A fake embedder that counts its calls and the texts it embeds."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(len(text)), 1.0] for text in texts]


# ── Citations ──


def test_a_shared_path_puts_each_issue_on_the_shortlist_of_the_other() -> None:
    issues = [
        issue(1, "See src/devops_cli/roadmap/stores/store.py:100 for the read."),
        issue(2, "The write is in `src/devops_cli/roadmap/stores/store.py`."),
        issue(3, "Nothing is cited."),
    ]
    lists = shortlists(issues, apart([1, 2, 3]), {})
    assert Signal.PATH in signals(lists, 1, 2)
    assert Signal.PATH in signals(lists, 2, 1)
    assert Signal.PATH not in signals(lists, 1, 3)
    shown = [e.detail for e in members(lists, 1)[2] if e.signal is Signal.PATH]
    assert shown == ["src/devops_cli/roadmap/stores/store.py"]


def test_a_shared_path_and_identifier_is_the_strongest_citation() -> None:
    issues = [
        issue(1, "src/a.py has `parse_row` wrong."),
        issue(2, "src/a.py has `parse_row` wrong too."),
        issue(3, "src/a.py is slow."),
        issue(4, "`parse_row` is slow."),
    ]
    lists = shortlists(issues, apart([1, 2, 3, 4]), {})
    assert Signal.PATH_AND_IDENTIFIER in signals(lists, 1, 2)
    assert Signal.PATH_AND_IDENTIFIER not in signals(lists, 1, 3)
    assert {Signal.PATH} <= signals(lists, 1, 3)
    assert {Signal.IDENTIFIER} <= signals(lists, 1, 4)
    best = [m.number for m in next(s for s in lists if s.anchor == 1).members][:3]
    assert best == [2, 3, 4]


def test_a_citation_that_many_issues_share_shows_no_shared_cause() -> None:
    count = DEFAULT_ROADMAP_CONSOLIDATE_COMMON_CITATION + 1
    numbers = list(range(1, count + 1))
    issues = [issue(n, "Read docs/COMMON.md and `Thing`.") for n in numbers]
    lists = shortlists(issues, apart(numbers), {})
    shared = {Signal.PATH, Signal.IDENTIFIER, Signal.PATH_AND_IDENTIFIER}
    assert all(
        not shared & {e.signal for e in ev}
        for s in lists
        for ev in members(lists, s.anchor).values()
    )


def test_a_section_that_a_job_writes_shows_no_shared_citation() -> None:
    section = "Fix `parse_row` in src/x.py:3."
    alternatives = (
        f"{CONST_ROADMAP_ALTERNATIVES_START_MARKER}\nSee src/y.py\n"
        f"{CONST_ROADMAP_ALTERNATIVES_END_MARKER}"
    )
    issues = [
        issue(1, f"{refined('Slow.', section)}\n{alternatives}"),
        issue(2, f"{refined('Wrong.', section)}\n{alternatives}"),
    ]
    lists = shortlists(issues, apart([1, 2]), {})
    assert signals(lists, 1, 2) == {Signal.EMBEDDING}


def test_a_version_is_no_file() -> None:
    issues = [issue(1, "It landed in v0.2.26 of the tool."), issue(2, "Since v0.2.26 it fails.")]
    assert Signal.PATH not in signals(shortlists(issues, apart([1, 2]), {}), 1, 2)


# ── Links ──


def test_a_relation_line_links_the_issues_it_names() -> None:
    body = "- Depends on #2 and #3.\n- **Related**: #4\n- Merged into #5\nSee #6."
    issues = [issue(n, body if n == 1 else "") for n in range(1, 7)]
    lists = shortlists(issues, apart(range(1, 7)), {})
    assert [signals(lists, 1, n) & {Signal.LINK} for n in (2, 3, 4, 5, 6)] == [
        {Signal.LINK},
        {Signal.LINK},
        {Signal.LINK},
        {Signal.LINK},
        set(),
    ]
    assert Signal.LINK in signals(lists, 2, 1)
    assert members(lists, 1)[2][0].detail == "#1 Depends on #2"


def test_a_nested_list_under_a_relation_line_counts_for_it() -> None:
    body = "- Related:\n  - #2 (the first);\n  - #3\n\n- Plan:\n  - #4"
    issues = [issue(n, body if n == 1 else "") for n in range(1, 5)]
    lists = shortlists(issues, apart(range(1, 5)), {})
    assert [Signal.LINK in signals(lists, 1, n) for n in (2, 3, 4)] == [True, True, False]


def test_a_split_line_and_the_dependencies_section_link() -> None:
    issues = [
        issue(1, "Split from #2 (part 2 of 4)."),
        issue(2),
        issue(3, "## Dependencies\n#2, #4\n\n## Next\n#5"),
        issue(4),
        issue(5),
    ]
    lists = shortlists(issues, apart(range(1, 6)), {})
    assert Signal.LINK in signals(lists, 1, 2)
    assert [Signal.LINK in signals(lists, 3, n) for n in (2, 4, 5)] == [True, True, False]


def test_a_blocker_and_a_parent_link() -> None:
    issues = [issue(1, blocked_by=1), issue(2), issue(3, parent=2), issue(4)]
    lists = shortlists(issues, apart([1, 2, 3, 4]), {1: [4]})
    assert members(lists, 1)[4][0].detail == "#1 is blocked by #4"
    assert Signal.LINK in signals(lists, 4, 1)
    assert members(lists, 2)[3][0].detail == "#2 has the sub-issue #3"
    assert Signal.LINK not in signals(lists, 1, 2)


def test_a_link_to_an_issue_that_is_not_open_names_no_member() -> None:
    issues = [issue(1, "- Depends on #99"), issue(2, "- Related #1")]
    lists = shortlists(issues, apart([1, 2]), {1: [99]})
    assert set(members(lists, 1)) == {2}
    assert signals(lists, 1, 2) == {Signal.EMBEDDING, Signal.LINK}


def test_blockers_are_read_for_the_issues_that_count_one() -> None:
    store = InMemoryRoadmapStore(repo="example/roadmap")
    first = store.seed_issue("first", labels=PRIORITY)
    second = store.seed_issue("second", labels=PRIORITY)
    free = store.seed_issue("free", labels=PRIORITY)
    store.seed_blocked_by(second, first)
    assert read_blockers(store, store.issues()) == {second: [first]}
    assert free not in read_blockers(store, store.issues())


# ── Embeddings ──


def test_the_nearest_items_by_embedding_are_members_with_their_rank() -> None:
    numbers = list(range(1, 10))
    issues = [issue(n) for n in numbers]
    vectors = {n: [1.0, float(n)] for n in numbers}
    lists = shortlists(issues, vectors, {})
    nearest_five = next(s for s in lists if s.anchor == 5).members
    assert [(m.number, m.evidence[0].rank) for m in nearest_five] == [
        (6, 1),
        (4, 2),
        (7, 3),
        (8, 4),
        (9, 5),
    ]


def test_a_shortlist_keeps_the_members_with_the_strongest_evidence() -> None:
    count = DEFAULT_ROADMAP_CONSOLIDATE_MEMBERS + 4
    numbers = list(range(1, count + 1))
    linked = " ".join(f"#{n}" for n in range(6, count + 1))
    issues = [issue(1, f"- Related: {linked}")] + [issue(n) for n in numbers[1:]]
    lists = shortlists(issues, apart(numbers), {})
    kept = [m.number for m in next(s for s in lists if s.anchor == 1).members]
    assert kept == [*range(6, count + 1), 2]


def test_an_issue_with_no_other_issue_has_no_shortlist() -> None:
    assert shortlists([issue(1, "src/x.py")], apart([1]), {}) == []


# ── Groups ──


def member(number: int, signal: Signal, rank: int | None = None) -> Member:
    return Member(number=number, evidence=(Evidence(signal=signal, detail="x", rank=rank),))


def test_the_stronger_evidence_wins_a_contested_item() -> None:
    lists = [
        Shortlist(anchor=4, members=(member(7, Signal.EMBEDDING, 1),)),
        Shortlist(anchor=9, members=(member(7, Signal.PATH_AND_IDENTIFIER),)),
    ]
    groups = assign_groups(lists)
    assert [(g.anchor, [m.number for m in g.members]) for g in groups] == [(9, [7])]


def test_a_tie_goes_to_the_lower_anchor_number() -> None:
    lists = [
        Shortlist(anchor=9, members=(member(7, Signal.PATH),)),
        Shortlist(anchor=4, members=(member(7, Signal.PATH),)),
    ]
    assert [(g.anchor, [m.number for m in g.members]) for g in assign_groups(lists)] == [(4, [7])]


def test_a_nearer_embedding_rank_is_stronger() -> None:
    lists = [
        Shortlist(anchor=2, members=(member(7, Signal.EMBEDDING, 3),)),
        Shortlist(anchor=3, members=(member(7, Signal.EMBEDDING, 1),)),
    ]
    assert [g.anchor for g in assign_groups(lists)] == [3]


def test_a_pair_is_one_group_and_a_member_anchors_none() -> None:
    lists = [
        Shortlist(anchor=1, members=(member(2, Signal.PATH), member(3, Signal.IDENTIFIER))),
        Shortlist(anchor=2, members=(member(1, Signal.PATH), member(4, Signal.PATH))),
        Shortlist(anchor=3, members=(member(5, Signal.LINK),)),
    ]
    groups = assign_groups(lists)
    assert [(g.anchor, [m.number for m in g.members]) for g in groups] == [(1, [2, 3])]


def test_an_anchor_whose_members_are_all_taken_has_no_group() -> None:
    lists = [
        Shortlist(anchor=8, members=(member(2, Signal.PATH),)),
        Shortlist(anchor=5, members=(member(2, Signal.PATH_AND_IDENTIFIER),)),
    ]
    assert [g.anchor for g in assign_groups(lists)] == [5]


def test_a_group_does_not_take_the_shortlist_of_its_member() -> None:
    issues = [issue(1, "src/a.py"), issue(2, "src/a.py src/b.py"), issue(3, "src/b.py")]
    lists = shortlists(issues, {1: [1.0, 0.0, 0.0], 2: [0.0, 1.0, 0.0], 3: [0.0, 0.0, 1.0]}, {})
    groups = assign_groups(lists)
    assert [(g.anchor, [m.number for m in g.members]) for g in groups] == [(1, [2, 3])]


def test_equal_input_gives_equal_groups() -> None:
    issues = [issue(n, f"src/{n % 3}.py `name{n % 2}`") for n in range(1, 9)]
    vectors = {n: [float(n % 4), float(n % 5), 1.0] for n in range(1, 9)}
    first = assign_groups(shortlists(issues, vectors, {}))
    again = assign_groups(shortlists(list(reversed(issues)), vectors, {}))
    assert first == again


# ── The embedded text ──


def refined(body: str, section: str) -> str:
    return (
        f"{body}\n{CONST_ROADMAP_REFINE_START_MARKER}\n{section}\n{CONST_ROADMAP_REFINE_END_MARKER}"
    )


def test_a_section_that_a_job_writes_is_no_part_of_the_embedded_text() -> None:
    embedder = Embedder()
    embed_issues([issue(1, "one")], embedder)
    embed_issues([issue(1, refined("one", "## Proposed design"))], embedder)
    assert embedder.calls == [["Item 1\n\none"], ["Item 1\n\none"]]


def test_issues_with_the_same_text_are_embedded_once() -> None:
    twin = issue(2, "one").model_copy(update={"title": "Item 1"})
    embedder = Embedder()
    vectors = embed_issues([issue(1, "one"), twin], embedder)
    assert (embedder.calls, vectors) == ([["Item 1\n\none"]], {1: [11.0, 1.0], 2: [11.0, 1.0]})


# ── The whole read ──


def test_the_groups_of_a_store_come_from_its_open_items_and_call_no_model() -> None:
    store = InMemoryRoadmapStore(repo="example/roadmap")
    first = store.seed_issue("first", body="It is in `src/a.py`.", labels=PRIORITY)
    second = store.seed_issue("second", body="It is in `src/a.py`.", labels=PRIORITY)
    store.seed_issue("closed", body="src/a.py", labels=PRIORITY, state=GitHubState.CLOSED)
    store.seed_issue("a candidate", body="src/a.py")
    store.seed_issue("a pull request", body="src/a.py", labels=PRIORITY, pull_request=True)
    third = store.seed_issue("third", labels=PRIORITY)
    store.seed_blocked_by(third, first)
    embedder = Embedder()
    groups = consolidation_groups(store, embedder)
    assert [(g.anchor, [m.number for m in g.members]) for g in groups] == [(first, [second, third])]
    assert len(embedder.calls) == 1
    assert len(embedder.calls[0]) == 3
    assert store.job_writes() == []
