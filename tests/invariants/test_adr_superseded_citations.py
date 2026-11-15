"""Code, tests and workflows cite the ADR in force (#5238).

An ADR that a later record supersedes keeps its history in `docs/adr/`, the archived change
folders and `CHANGELOG.md`. A citation outside those places is a rule that the reader follows, so
it names the record in force.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from devops_cli.roadmap.adr import AdrStatus, adr_of
from tests.support.paths import REPO_ROOT

_ADR = re.compile(r"ADR[ -]?0*(?P<number>\d{1,4})\b")
_SCANNED = ("src", "tests", ".github")
# `test_docs_adr_records.py` writes temporary records with arbitrary numbers, and
# `test_roadmap_adr.py` records the warning of the oldest records; neither cites a rule.
_SKIPPED = (
    "openspec/changes/archive",
    "CHANGELOG.md",
    "docs/adr",
    "tests/docs/test_docs_adr_records.py",
    "tests/roadmap/test_roadmap_adr.py",
)


def _superseded_numbers() -> set[int]:
    numbers: set[int] = set()
    for path in sorted((REPO_ROOT / "docs/adr").glob("*.md")):
        adr = adr_of(path.name, path.read_text(encoding="utf-8"))
        if adr is not None and adr.front_matter.status is AdrStatus.SUPERSEDED:
            numbers.add(adr.number)
    return numbers


def _paths() -> Iterator[tuple[Path, str]]:
    for root in _SCANNED:
        for path in sorted((REPO_ROOT / root).rglob("*")):
            relative = path.relative_to(REPO_ROOT).as_posix()
            if (
                path.is_file()
                and path.suffix in {".py", ".md", ".yml", ".yaml"}
                and not relative.startswith(_SKIPPED)
            ):
                yield path, relative


def _citations() -> list[str]:
    superseded = _superseded_numbers()
    return [
        f"{relative}:{number}: {match.group(0)}"
        for path, relative in _paths()
        for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1)
        for match in _ADR.finditer(line)
        if int(match.group("number")) in superseded
    ]


def test_code_tests_and_workflows_cite_no_superseded_adr() -> None:
    assert _citations() == []
