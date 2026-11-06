"""Tests for the ADRs that the alternatives check reads (#3505): what it keeps of an ADR file, which
files of `docs/adr/` are ADRs, which ADRs are in force, the order and the size of the ADRs, and when
a text names a tool.

The roadmap is the in-memory store, which holds the files of the repository.
"""

from __future__ import annotations

import logging

import pytest

from devops_cli.ai.context_budget import count_tokens
from devops_cli.roadmap.adr import Adr, adr_of, fit_to_budget, names, read_adrs
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore

ADR_DIRECTORY = "docs/adr"
ADR = """# Argo Workflows runs the jobs

Amended on 2026-10-28 by [ADR 0016](0016-labels.md). Labels hold the fields.

ADR 0008 amends ADR 0004.

The Service chose an engine.

## Considered Options

- **DBOS**: runner-up.
- **Temporal and Hatchet**: rejected. Each needs a new Postgres.

## Consequences

- Two Applications carry it.
"""
STATUS = "Amended on 2026-10-28 by ADR 0016. Labels hold the fields.\nADR 0008 amends ADR 0004."
OPTIONS = (
    "## Considered Options\n\n- **DBOS**: runner-up.\n"
    "- **Temporal and Hatchet**: rejected. Each needs a new Postgres."
)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo="example/roadmap", is_private=False)


def _seed(store: InMemoryRoadmapStore, number: int, title: str, *notes: str) -> None:
    """Commit the ADR `number` with `title`, the paragraphs `notes` under it and one option."""
    paragraphs = "\n\n".join(notes)
    store.seed_file(
        f"{ADR_DIRECTORY}/{number:04d}-decision.md",
        f"# {title}\n\n{paragraphs}\n\nThe text.\n\n## Considered Options\n\n- **Tool**: chosen.\n",
    )


def test_an_adr_keeps_its_number_its_title_its_status_and_its_options_section_only() -> None:
    assert adr_of("docs/adr/0008-argo-workflows.md", ADR) == Adr(
        number=8, title="Argo Workflows runs the jobs", options=OPTIONS, status=STATUS
    )


def test_an_adr_with_no_options_section_keeps_its_title_and_no_options() -> None:
    adr = adr_of(
        "docs/adr/0013-releases.md", "# Releases use release-please\n\n## Decision\n\nGo.\n"
    )

    assert adr == Adr(number=13, title="Releases use release-please", options="", status="")


@pytest.mark.parametrize(
    ("text", "status"),
    [
        pytest.param(
            "# T\n\n[ADR 0015](0015-x.md) supersedes this ADR.\n\nThe text.\n",
            "ADR 0015 supersedes this ADR.",
            id="a-link-is-its-text",
        ),
        pytest.param(
            "# T\n\nThe webhook clause is superseded by ADR 0017.\n\nAmended by ADR 0016.\n\nText.\n",
            "The webhook clause is superseded by ADR 0017.\nAmended by ADR 0016.",
            id="two-paragraphs",
        ),
        pytest.param(
            "# T\n\nThe text of the decision.\n\nAmended by ADR 0016.\n",
            "",
            id="a-note-after-the-body-is-no-status",
        ),
        pytest.param(
            "# T\n\nIt replaces an older text and amends the old design.\n\nMore.\n",
            "",
            id="a-sentence-with-no-adr-is-no-status",
        ),
        pytest.param(
            "# T\n\n## Considered Options\n\n- A.\n\nAmended by ADR 0016.\n",
            "",
            id="a-note-under-a-heading-is-no-status",
        ),
    ],
)
def test_the_status_of_an_adr_is_the_paragraphs_under_its_title_that_name_another_adr(
    text: str, status: str
) -> None:
    adr = adr_of("docs/adr/0009-a.md", text)

    assert adr is not None
    assert adr.status == status


def test_an_adr_entry_gives_its_number_as_four_digits_its_title_its_status_and_its_options() -> (
    None
):
    adr = Adr(number=8, title="Argo Workflows", options="## Considered Options\n\n- A.", status="")
    noted = Adr(number=9, title="Next", options="", status="ADR 0010 amends ADR 0004.")

    assert (adr.entry, noted.entry, Adr(number=10, title="Last", options="", status="").entry) == (
        "ADR 0008: Argo Workflows\n## Considered Options\n\n- A.",
        "ADR 0009: Next\nADR 0010 amends ADR 0004.",
        "ADR 0010: Last",
    )


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
        pytest.param("docs/adr/0001-blank-title.md", "# \n\nThe text.\n", id="blank-h1"),
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


def test_an_adr_that_a_later_adr_supersedes_is_left_out_from_either_side(
    store: InMemoryRoadmapStore,
) -> None:
    # ADR 2 says so in its own note, and ADR 5 says so in the note of the ADR that replaces it.
    _seed(store, 1, "Old", "[ADR 0002](0002-x.md) supersedes this ADR.")
    _seed(store, 2, "Middle", "ADR 0002 supersedes ADR 0001.")
    _seed(store, 3, "Quiet")
    _seed(store, 4, "Replaced", "No note here.")
    _seed(store, 5, "Newest", "ADR 0005 supersedes [ADR 0004](0004-x.md).")

    assert [adr.number for adr in read_adrs(store)] == [5, 3, 2]


def test_an_adr_that_a_later_adr_supersedes_in_part_or_amends_stays(
    store: InMemoryRoadmapStore,
) -> None:
    _seed(store, 3, "Polling", "The webhook clause is superseded on 2026-10-29 by ADR 0017.")
    _seed(store, 4, "Gate", "Amended on 2026-10-24 by ADR 0014.")
    _seed(store, 14, "Checks", "ADR 0014 amends [ADR 0004](0004-x.md).")
    _seed(store, 17, "Webhooks", "This ADR supersedes the webhook clause of [ADR 0003](x.md).")

    assert [adr.number for adr in read_adrs(store)] == [17, 14, 4, 3]


def test_an_adr_does_not_supersede_an_adr_of_a_higher_number(store: InMemoryRoadmapStore) -> None:
    _seed(store, 1, "First", "ADR 0001 supersedes ADR 0002.")
    _seed(store, 2, "Second", "The text.")

    assert [adr.number for adr in read_adrs(store)] == [2, 1]


def test_the_status_of_a_superseding_adr_reaches_its_entry(store: InMemoryRoadmapStore) -> None:
    _seed(store, 12, "Release-please", "ADR 0012 supersedes ADR 0011.")
    _seed(store, 11, "Towncrier", "[ADR 0012](0012-x.md) supersedes this ADR.")

    (adr,) = read_adrs(store)

    assert adr.entry.splitlines()[:2] == [
        "ADR 0012: Release-please",
        "ADR 0012 supersedes ADR 0011.",
    ]


def _entries(count: int, options: str) -> tuple[Adr, ...]:
    """`count` ADRs, the newest first, each with the same `options`."""
    return tuple(
        Adr(number=number, title=f"Decision {number}", options=options, status="")
        for number in range(count, 0, -1)
    )


def test_adrs_that_fit_the_cap_are_all_kept_and_log_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    adrs = _entries(3, "- **Tool**: chosen.")

    with caplog.at_level(logging.WARNING):
        kept = fit_to_budget(adrs, max_tokens=500)

    assert (kept, caplog.records) == (adrs, [])


def test_adrs_over_the_cap_keep_whole_entries_newest_first_and_log_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    options = "\n".join(f"- **Tool {n}**: rejected, for a reason." for n in range(40))
    adrs = _entries(5, options)
    cap = 2 * count_tokens(adrs[0].entry) + 20

    with caplog.at_level(logging.WARNING):
        kept = fit_to_budget(adrs, max_tokens=cap)

    assert (
        [adr.number for adr in kept],
        count_tokens("\n\n".join(adr.entry for adr in kept)) <= cap,
        [record.getMessage() for record in caplog.records],
    ) == (
        [5, 4],
        True,
        [
            f"The ADRs of the repository do not fit the cap of {cap} tokens: the alternatives "
            "check leaves out ADR 0003, ADR 0002, ADR 0001."
        ],
    )


def test_an_entry_that_is_over_the_cap_alone_is_left_out_and_a_smaller_older_one_stays(
    caplog: pytest.LogCaptureFixture,
) -> None:
    huge = Adr(
        number=9, title="Huge", options="\n".join(f"- **T{n}**: no." for n in range(900)), status=""
    )
    small = Adr(number=8, title="Small", options="- **Tool**: chosen.", status="")

    with caplog.at_level(logging.WARNING):
        kept = fit_to_budget((huge, small), max_tokens=200)

    assert ([adr.number for adr in kept], len(caplog.records)) == ([8], 1)


@pytest.mark.parametrize(
    ("text", "tool_names", "named"),
    [
        pytest.param("The dashboard shows Grafana panels", ("grafana/grafana",), False, id="bare"),
        pytest.param("The `grafana` panels", ("grafana/grafana",), True, id="code-span"),
        pytest.param("see [Grafana](https://x.test/g)", ("grafana/grafana",), True, id="link-text"),
        pytest.param("see [docs](https://x.test/grafana)", ("grafana",), True, id="link-target"),
        pytest.param(
            "- **Temporal and Hatchet**: rejected.", ("temporalio/temporal",), True, id="bold"
        ),
        pytest.param(
            "Temporal and Hatchet: rejected.", ("temporalio/temporal",), False, id="plain"
        ),
        pytest.param(
            "the Argo Workflows controller", ("argoproj/argo-workflows",), True, id="words"
        ),
        pytest.param("it uses argo_workflows here", ("argo-workflows",), True, id="underscore"),
        pytest.param(
            "DBOS Transact in-process", ("dbos-inc/dbos-transact-py",), False, id="suffix"
        ),
        pytest.param(
            "DBOS Transact in-process",
            ("dbos-inc/dbos-transact-py", "DBOS Transact"),
            True,
            id="display-name",
        ),
        pytest.param("use release-please", ("googleapis/release-please",), True, id="two-words"),
        pytest.param("Run example/scanner now.", ("example/scanner",), True, id="owner-name"),
        pytest.param(
            "see https://github.com/example/scanner.", ("example/scanner",), True, id="url"
        ),
        pytest.param("Run the scanner now.", ("example/scanner",), False, id="bare-name-of-a-repo"),
        pytest.param("add pytest-cov", ("pytest-dev/pytest",), False, id="longer-name"),
        pytest.param("add `pytest-cov`", ("pytest-dev/pytest",), False, id="longer-name-in-code"),
        pytest.param("the `scanners` run", ("example/scanner",), False, id="part-of-a-word"),
        pytest.param("a `rescanner`", ("scanner",), False, id="end-of-a-word"),
        pytest.param("```\njust build\n```", ("casey/just",), False, id="fence-is-bare"),
        pytest.param("A line\n![logo](x.png) and `scanner`", ("scanner",), True, id="line-image"),
        pytest.param("nothing here", ("example/scanner",), False, id="absent"),
        pytest.param("anything", ("",), False, id="empty-name"),
        pytest.param("The `scanner` runs", (), False, id="no-name"),
    ],
)
def test_a_text_names_a_tool_by_its_names_in_the_forms_that_say_so(
    text: str, tool_names: tuple[str, ...], named: bool
) -> None:
    assert names(text, *tool_names) is named


@pytest.mark.parametrize(
    ("text", "tool"),
    [
        pytest.param("This task adds a check.", "go-task/task", id="task"),
        pytest.param("just add it", "casey/just", id="just"),
        pytest.param("Send requests to the API", "psf/requests", id="requests"),
        pytest.param("build the image", "pypa/build", id="build"),
        pytest.param("a rich comment", "Textualize/rich", id="rich"),
        pytest.param("act on it", "nektos/act", id="act"),
    ],
)
def test_a_common_word_in_plain_prose_does_not_name_a_tool_of_that_name(
    text: str, tool: str
) -> None:
    assert names(text, tool) is False


@pytest.mark.parametrize(
    ("text", "tool"),
    [
        pytest.param("Run `just` for the build.", "casey/just", id="code-span"),
        pytest.param("Use [just](https://just.systems) here.", "casey/just", id="link"),
        pytest.param("Use casey/just here.", "casey/just", id="owner-name"),
    ],
)
def test_a_common_word_in_a_code_span_a_link_or_the_owner_name_form_names_the_tool(
    text: str, tool: str
) -> None:
    assert names(text, tool) is True
