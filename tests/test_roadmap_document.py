"""Reading a hand-written `docs/ROADMAP.md` as entries and matrix rows, and linking entries (#739)."""

from __future__ import annotations

from devops_cli.roadmap.document import (
    linked_issues,
    normalize_title,
    parse_roadmap,
    titles_index,
)
from devops_cli.roadmap.store import IssueRecord

DOCUMENT = """# Roadmap

### Foundations (v0.0.1 – v0.1.9 - Completed)
- [x] **Runtime Core**: shipped.

### Current (v0.2.25 - Active Release)
- [ ] **Two Issues and a PR (P1 - High, Issues #287, #289, PR #288)**:
  - *Context*: sub-bullets belong to the entry.

  - *More*: so do lines after a blank line, while they are indented.
- [ ] **Deterministic Test Selection (P1 - High)** — index landed in #446:
- [ ] **A Fleet Daemon (`devops gh pm daemon`) (P0 - Critical, Overlaps #741)**:

#### Self-Evolving Systems (v0.5.x)
- **A Theme**: not an entry.

---
- [ ] **After the Themes (P2 - Medium)**:

| Priority Category | Feature / Focus | Value | Effort | Status |
|---|---|---|---|---|
| **Quick Wins** | Gate Cache \\| Tree | High | Low | 📋 Scheduled (P1) |
|  | Shipped | High | Low | ✅ Completed |
|  | Installers | Low | High | ❌ Rejected (native) |
"""


def test_entries_carry_their_heading_tags_section_and_release() -> None:
    entries = parse_roadmap(DOCUMENT).entries
    assert [
        (e.line, e.title, e.done, e.priority, e.issues, e.overlaps, e.release) for e in entries
    ] == [
        (4, "Runtime Core", True, None, (), (), None),
        (7, "Two Issues and a PR", False, "P1", (287, 289), (), "v0.2.25"),
        (11, "Deterministic Test Selection", False, "P1", (), (), "v0.2.25"),
        (12, "A Fleet Daemon (`devops gh pm daemon`)", False, "P0", (), (741,), "v0.2.25"),
        (18, "After the Themes", False, "P2", (), (), None),
    ]


def test_an_entry_holds_its_indented_lines_and_a_theme_heading_names_no_release() -> None:
    entries = parse_roadmap(DOCUMENT).entries
    assert (len(entries[1].text.splitlines()), entries[4].section) == (
        4,
        "Self-Evolving Systems (v0.5.x)",
    )


def test_matrix_rows_are_read_by_their_column_names() -> None:
    rows = parse_roadmap(DOCUMENT).matrix
    assert [(r.line, r.feature, r.value, r.effort, r.open, r.rejected) for r in rows] == [
        (22, "Gate Cache \\| Tree", "High", "Low", True, False),
        (23, "Shipped", "High", "Low", False, False),
        (24, "Installers", "Low", "High", False, True),
    ]


def test_titles_compare_without_a_conventional_commit_prefix_case_or_spacing() -> None:
    assert (
        normalize_title("feat(github)!:  Roadmap   VIEW "),
        normalize_title("Roadmap view"),
        normalize_title("Metric Provenance: radon"),
    ) == ("roadmap view", "roadmap view", "metric provenance: radon")


def test_an_entry_links_by_heading_or_by_exactly_one_title_match() -> None:
    issues = [
        IssueRecord(number=1, title="feat(ci): deterministic test selection", url="u"),
        IssueRecord(number=2, title="fix(ai): after the themes", url="u"),
        IssueRecord(number=3, title="docs(ai): After the Themes", url="u"),
        IssueRecord(number=4, title="feat: a fleet daemon", url="u", pull_request=True),
    ]
    titles = titles_index(issues)
    entries = parse_roadmap(DOCUMENT).entries
    assert [linked_issues(entry, titles) for entry in entries[1:]] == [(287, 289), (1,), (), ()]
