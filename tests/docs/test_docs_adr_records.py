"""The rules of the decision records of `docs/adr/` (#5225): the body hash that freezes an accepted
record, the index that `devops docs generate` writes into `docs/adr/README.md`, and the problems
that `tests/invariants/test_adr_records.py` reads for the records of the repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.docs.adr_records import (
    ADR_INDEX_END,
    ADR_INDEX_PAGE,
    ADR_INDEX_START,
    body_hash,
    record_problems,
    render_index,
    sync_index,
)
from devops_cli.docs.generator import DocGenerator

BODY = """# Labels hold the fields

Labels hold the fields of an [item](https://example.com/item).

## Considered Options

- **Board fields**: rejected, because the App cannot read them.
"""
HISTORY = "\n## Status History\n\n2026-11-12: Fact out of date: the board (#1).\n"


def _record(front_matter: str, body: str = BODY, history: str = "") -> str:
    return f"---\n{front_matter}\n---\n{body}{history}"


def _accepted(*links: str, body: str = BODY, status: str = "accepted") -> str:
    """An accepted record with the right body hash and the front matter lines `links`."""
    keys = "\n".join((f"status: {status}", "date: 2026-11-12", "decision-makers: [owner]", *links))
    return _record(f"{keys}\nbody-hash: {body_hash(body)}", body)


def test_the_body_hash_leaves_out_the_front_matter_the_status_history_and_link_targets() -> None:
    moved = BODY.replace("https://example.com/item", "https://example.com/moved")

    assert {
        body_hash(BODY),
        body_hash(_record("status: accepted", BODY, HISTORY)),
        body_hash(_record("status: superseded", moved, HISTORY + "2026-11-13: More.\n")),
    } == {body_hash(BODY)}


@pytest.mark.parametrize(
    "edit",
    [
        pytest.param(("Labels hold", "Labels keep"), id="a-word"),
        pytest.param(("rejected, because", "chosen, because"), id="an-option"),
        pytest.param(("[item]", "[record]"), id="a-link-text"),
        pytest.param(("# Labels", "## Labels"), id="a-heading-level"),
    ],
)
def test_the_body_hash_changes_when_the_body_changes(edit: tuple[str, str]) -> None:
    assert body_hash(BODY.replace(*edit)) != body_hash(BODY)


def test_the_records_of_the_repository_have_no_problem_when_they_keep_the_rules() -> None:
    texts = {
        "0001-old.md": _accepted("superseded-by: ['0002']", status="superseded"),
        "0002-new.md": _accepted("supersedes: ['0001']", "amended-by: ['0003']"),
        "0003-change.md": _accepted("amends: ['0002']"),
        "0004-draft.md": _record("status: proposed\ndate: 2026-11-12\ndecision-makers: [owner]"),
    }

    assert record_problems(texts) == []


@pytest.mark.parametrize(
    ("texts", "problem"),
    [
        pytest.param(
            {"0001-a.md": BODY},
            "0001-a.md: the front matter has no status.",
            id="no-front-matter",
        ),
        pytest.param(
            {"0001-a.md": _record("date: 2026-11-12\ndecision-makers: [owner]")},
            "0001-a.md: the front matter has no status.",
            id="no-status",
        ),
        pytest.param(
            {"0001-a.md": _record("status: proposed\ndecision-makers: [owner]")},
            "0001-a.md: the front matter has no date.",
            id="no-date",
        ),
        pytest.param(
            {"0001-a.md": _record("status: proposed\ndate: 2026-11-12\ndecision-makers: [Ann]")},
            "0001-a.md: decision-makers holds a name that is not a role: Ann.",
            id="a-person",
        ),
        pytest.param(
            {"0001-a.md": _accepted("superseded-by: ['0002']"), "0002-b.md": _accepted()},
            "0001-a.md: superseded-by names ADR 0002, and ADR 0002 has no supersedes link back.",
            id="one-way-supersession",
        ),
        pytest.param(
            {"0001-a.md": _accepted(), "0002-b.md": _accepted("supersedes: ['0001']")},
            "0002-b.md: supersedes names ADR 0001, and ADR 0001 has no superseded-by link back.",
            id="one-way-from-the-new-record",
        ),
        pytest.param(
            {"0001-a.md": _accepted("amended-by: ['0002']"), "0002-b.md": _accepted()},
            "0001-a.md: amended-by names ADR 0002, and ADR 0002 has no amends link back.",
            id="one-way-amendment",
        ),
        pytest.param(
            {"0001-a.md": _accepted("amends: ['0009']")},
            "0001-a.md: amends names ADR 0009, which does not exist.",
            id="a-missing-record",
        ),
        pytest.param(
            {"0001-a.md": _accepted(status="superseded")},
            "0001-a.md: the status is superseded, and superseded-by names no record.",
            id="superseded-with-no-successor",
        ),
        pytest.param(
            {"0001-a.md": _accepted("superseded-by: ['0002']"), "0002-b.md": _accepted()},
            "0001-a.md: superseded-by names a record, and the status is accepted.",
            id="a-successor-and-in-force",
        ),
        pytest.param(
            {"0001-a.md": _record("status: accepted\ndate: 2026-11-12\ndecision-makers: [owner]")},
            "0001-a.md: the front matter has no body-hash: the hash of the body is",
            id="no-body-hash",
        ),
        pytest.param(
            {"0001-a.md": _accepted().replace("Labels hold the fields of", "Labels keep")},
            f"0001-a.md: the body changed after acceptance: its hash is "
            f"{body_hash(BODY.replace('Labels hold the fields of', 'Labels keep'))}.",
            id="an-edit-of-an-accepted-body",
        ),
        pytest.param(
            {"0001-a.md": _record("status: accepted\nsuperseded_by: ['0002']")},
            "0001-a.md: the front matter is not valid",
            id="not-valid",
        ),
    ],
)
def test_a_record_that_breaks_a_rule_is_a_problem(texts: dict[str, str], problem: str) -> None:
    assert [found for found in record_problems(texts) if found.startswith(problem)] != []


def test_a_new_record_over_the_limits_of_length_is_a_problem() -> None:
    title = "# " + " ".join(["Word"] * 11)
    body = f"{title}\n\n" + " ".join(["text"] * 1001) + "\n"
    name = "0026-" + "-".join(["slug"] * 13) + ".md"

    assert record_problems({name: _accepted(body=body)}) == [
        f"{name}: the body has 1001 words, more than 1000.",
        f"{name}: the title has 11 words, more than 10.",
        f"{name}: the slug has 64 characters, more than 60.",
    ]


def test_a_record_written_before_the_rules_has_no_limit_of_length() -> None:
    body = "# " + " ".join(["Word"] * 11) + "\n\n" + " ".join(["text"] * 1001) + "\n"

    assert record_problems({"0025-" + "-".join(["slug"] * 13) + ".md": _accepted(body=body)}) == []


INDEX_TEXTS = {
    "0001-old.md": _accepted("superseded-by: ['0002']", status="superseded"),
    "0002-new.md": _accepted("supersedes: ['0001']", "amended-by: ['0003']").replace(
        "# Labels hold the fields", "# Labels | hold the fields"
    ),
    "0003-change.md": _accepted("amends: ['0002']"),
}
INDEX = """| Record | Title | Status | Date | Links |
| :--- | :--- | :--- | :--- | :--- |
| [0001](0001-old.md) | Labels hold the fields | superseded | 2026-11-12 | superseded by 0002 |
| [0002](0002-new.md) | Labels \\| hold the fields | accepted | 2026-11-12 | supersedes 0001; amended by 0003 |
| [0003](0003-change.md) | Labels hold the fields | accepted | 2026-11-12 | amends 0002 |"""


def test_the_index_has_a_row_for_each_record_with_its_status_and_its_links() -> None:
    assert render_index({**INDEX_TEXTS, "README.md": "# Decisions\n"}) == INDEX


def test_the_readme_gets_the_index_between_its_markers() -> None:
    page = f"# Decisions\n\n{ADR_INDEX_START}\nold\n{ADR_INDEX_END}\n\nMore.\n"

    assert sync_index(page, INDEX_TEXTS) == (
        f"# Decisions\n\n{ADR_INDEX_START}\n\n{INDEX}\n\n{ADR_INDEX_END}\n\nMore.\n"
    )


def test_a_page_with_no_index_markers_is_not_synced() -> None:
    assert sync_index("# Decisions\n", INDEX_TEXTS) is None


def test_devops_docs_generate_writes_the_index_of_the_records(tmp_path: Path) -> None:
    directory = tmp_path / "docs" / "adr"
    directory.mkdir(parents=True)
    for name, text in INDEX_TEXTS.items():
        (directory / name).write_text(text, encoding="utf-8")
    (directory / "README.md").write_text(
        f"# Decisions\n\n{ADR_INDEX_START}\n{ADR_INDEX_END}\n", encoding="utf-8"
    )

    assert DocGenerator(tmp_path).synced_blocks() == {
        ADR_INDEX_PAGE: f"# Decisions\n\n{ADR_INDEX_START}\n\n{INDEX}\n\n{ADR_INDEX_END}\n"
    }
