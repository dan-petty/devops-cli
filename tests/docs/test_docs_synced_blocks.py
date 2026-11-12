"""`devops docs generate` writes the generated block of a hand-written page (#5165).

The job success page holds the grade table of `roadmap/job_grade.py` between its markers, so
`devops docs check` fails when the table of the code and the page differ.
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.docs.generator import JOB_SUCCESS_PAGE, DocGenerator
from devops_cli.roadmap.job_grade import (
    GRADE_TABLE_END,
    GRADE_TABLE_START,
    render_grade_table,
)


def _page(root: Path, text: str) -> Path:
    page = root / "docs" / JOB_SUCCESS_PAGE
    page.parent.mkdir(parents=True)
    page.write_text(text, encoding="utf-8")
    return page


def test_the_job_success_page_gets_the_grade_table(tmp_path: Path) -> None:
    """The generator gives the page with the table of the code between its markers."""
    _page(tmp_path, f"# Success\n\n{GRADE_TABLE_START}\nold\n{GRADE_TABLE_END}\n")

    assert DocGenerator(tmp_path).synced_blocks() == {
        JOB_SUCCESS_PAGE: (
            f"# Success\n\n{GRADE_TABLE_START}\n\n{render_grade_table()}\n\n{GRADE_TABLE_END}\n"
        )
    }


def test_a_stale_grade_table_fails_the_docs_check(tmp_path: Path) -> None:
    """A page whose table is not the table of the code is out of date."""
    page = _page(tmp_path, f"# Success\n\n{GRADE_TABLE_START}\nold\n{GRADE_TABLE_END}\n")
    generator = DocGenerator(tmp_path)

    ok, errors = generator.check_docs(
        tmp_path / "docs", check_readme_table=False, docs=generator.synced_blocks()
    )

    assert (ok, errors) == (
        False,
        [f"Out-of-date documentation file: {page} differs from generated content."],
    )


def test_a_page_with_no_markers_is_not_synced(tmp_path: Path) -> None:
    """A page with no markers gives no generated block."""
    _page(tmp_path, "# Success\n")

    assert DocGenerator(tmp_path).synced_blocks() == {}
