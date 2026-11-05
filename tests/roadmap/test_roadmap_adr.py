"""Tests for the ADRs that the alternatives check reads (#3505): what it keeps of an ADR file, which
files of `docs/adr/` are ADRs, the order of the ADRs, and when a text names a tool.

The roadmap is the in-memory store, which holds the files of the repository.
"""

from __future__ import annotations

import pytest

from devops_cli.roadmap.adr import Adr, adr_of, names, read_adrs
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore

ADR_DIRECTORY = "docs/adr"
ADR = """# Argo Workflows runs the jobs

Amended on 2026-10-28 by another ADR.

The Service chose an engine.

## Considered Options

- **DBOS**: runner-up.
- **Temporal and Hatchet**: rejected. Each needs a new Postgres.

## Consequences

- Two Applications carry it.
"""
OPTIONS = (
    "## Considered Options\n\n- **DBOS**: runner-up.\n"
    "- **Temporal and Hatchet**: rejected. Each needs a new Postgres."
)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo="example/roadmap", is_private=False)


def test_an_adr_keeps_its_number_its_title_and_its_options_section_only() -> None:
    assert adr_of("docs/adr/0008-argo-workflows.md", ADR) == Adr(
        number=8, title="Argo Workflows runs the jobs", options=OPTIONS
    )


def test_an_adr_with_no_options_section_keeps_its_title_and_no_options() -> None:
    adr = adr_of(
        "docs/adr/0013-releases.md", "# Releases use release-please\n\n## Decision\n\nGo.\n"
    )

    assert adr == Adr(number=13, title="Releases use release-please", options="")


@pytest.mark.parametrize(
    ("path", "text"),
    [
        pytest.param("docs/adr/README.md", ADR, id="readme"),
        pytest.param("docs/adr/0001.md", ADR, id="no-name-after-the-number"),
        pytest.param("docs/adr/001-short.md", ADR, id="three-digits"),
        pytest.param("docs/adr/0001-notes.txt", ADR, id="not-markdown"),
        pytest.param(
            "docs/adr/0001-no-title.md", "No heading.\n\n## Considered Options\n", id="no-h1"
        ),
    ],
)
def test_a_file_that_is_no_adr_gives_none(path: str, text: str) -> None:
    assert adr_of(path, text) is None


def test_the_adrs_of_a_repository_come_newest_first_and_leave_out_a_file_that_is_no_adr(
    store: InMemoryRoadmapStore,
) -> None:
    store.seed_file(f"{ADR_DIRECTORY}/0007-first.md", "# First\n\n## Considered Options\n\n- A.\n")
    store.seed_file(f"{ADR_DIRECTORY}/0009-third.md", "# Third\n")
    store.seed_file(f"{ADR_DIRECTORY}/0008-second.md", "# Second\n")
    store.seed_file(f"{ADR_DIRECTORY}/README.md", "# Decisions\n")

    assert [(adr.number, adr.title) for adr in read_adrs(store)] == [
        (9, "Third"),
        (8, "Second"),
        (7, "First"),
    ]


def test_a_repository_with_no_adr_directory_has_no_adr(store: InMemoryRoadmapStore) -> None:
    store.seed_file("README.md", "# Project\n")

    assert read_adrs(store) == ()


def test_an_adr_entry_gives_its_number_as_four_digits_its_title_and_its_options() -> None:
    adr = Adr(number=8, title="Argo Workflows", options="## Considered Options\n\n- A.")

    assert (adr.entry, Adr(number=9, title="Next", options="").entry) == (
        "ADR 0008: Argo Workflows\n## Considered Options\n\n- A.",
        "ADR 0009: Next",
    )


@pytest.mark.parametrize(
    ("text", "name", "named"),
    [
        pytest.param("The dashboard shows Grafana panels", "grafana", True, id="prose-no-case"),
        pytest.param("the Argo Workflows controller", "argo-workflows", True, id="words"),
        pytest.param("it uses argo_workflows here", "argo-workflows", True, id="underscore"),
        pytest.param(
            "the notifications-engine's NewAPI", "notifications-engine", True, id="possessive"
        ),
        pytest.param("Run example/scanner on each file.", "example/scanner", True, id="owner-name"),
        pytest.param(
            "Run the scanner on each file.", "example/scanner", True, id="name-of-owner-name"
        ),
        pytest.param("see https://github.com/example/scanner.", "scanner", True, id="url-and-stop"),
        pytest.param("add pytest-cov", "pytest", False, id="longer-name-with-hyphen"),
        pytest.param("the scanners run", "scanner", False, id="part-of-a-word"),
        pytest.param("a rescanner", "scanner", False, id="end-of-a-word"),
        pytest.param("py_pytest", "pytest", False, id="underscore-before"),
        pytest.param("nothing here", "scanner", False, id="absent"),
        pytest.param("anything", "", False, id="empty-name"),
    ],
)
def test_a_text_names_a_tool_by_its_name_as_a_whole_word(text: str, name: str, named: bool) -> None:
    assert names(text, name) is named
