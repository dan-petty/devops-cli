"""The decision records of `docs/adr/` keep the rules of `docs/adr/README.md` (#5225).

Each record has the front matter of MADR 4 with a status, a date and the roles that decided it. A
supersession or an amendment links both records, each to the other. An accepted record keeps the
hash of its body, so an edit of the body in place fails here. A record after ADR 0025 keeps the
limits of length. The index of the README is the one that `devops docs generate` writes.
"""

from __future__ import annotations

from devops_cli.docs.adr_records import read_record_texts, record_problems, sync_index
from tests.support.paths import REPO_ROOT

ADR_DIRECTORY = REPO_ROOT / "docs" / "adr"
README = ADR_DIRECTORY / "README.md"


def test_each_record_keeps_the_rules_of_the_decision_records() -> None:
    assert record_problems(read_record_texts(ADR_DIRECTORY)) == []


def test_the_index_of_the_readme_is_the_generated_index() -> None:
    page = README.read_text(encoding="utf-8")

    assert sync_index(page, read_record_texts(ADR_DIRECTORY)) == page
