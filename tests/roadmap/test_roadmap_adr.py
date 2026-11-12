"""Tests for the ADRs that the alternatives check reads (#3505): what it keeps of an ADR file, which
files of `docs/adr/` are ADRs, which ADRs are in force, the order and the size of the ADRs, and when
a text names a tool.

The status of an ADR is its front matter (#5225): the keys of MADR 4 and the links between the
records. The roadmap is the in-memory store, which holds the files of the repository.
"""

from __future__ import annotations

import datetime
import logging

import pytest

from devops_cli.ai.context_budget import count_tokens
from devops_cli.exceptions.validation import ValidationError
from devops_cli.roadmap.adr import (
    Adr,
    AdrFrontMatter,
    AdrStatus,
    adr_of,
    fit_to_budget,
    names,
    read_adrs,
    rejects,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

ADR_DIRECTORY = "docs/adr"
FRONT_MATTER = """---
status: accepted
date: 2026-10-23
decision-makers: [owner]
issue: 1535
amends: ["0004"]
amended-by: ["0016"]
body-hash: 0f
---
"""
ADR = f"""{FRONT_MATTER}# Argo Workflows runs the jobs

The Service chose an engine.

## Considered Options

- **DBOS**: runner-up.
- **Temporal and Hatchet**: rejected. Each needs a new Postgres.

## Consequences

- Two Applications carry it.

## Status History

2026-10-28: Amended by ADR 0016, section Labels.
"""
OPTIONS = (
    "## Considered Options\n\n- **DBOS**: runner-up.\n"
    "- **Temporal and Hatchet**: rejected. Each needs a new Postgres."
)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo="example/roadmap", is_private=False)


def _seed(store: InMemoryRoadmapStore, number: int, title: str, front_matter: str = "") -> None:
    """Commit the ADR `number` with the YAML `front_matter` (no front matter when it is empty),
    `title` and one option."""
    head = f"---\n{front_matter}\n---\n" if front_matter else ""
    store.seed_file(
        f"{ADR_DIRECTORY}/{number:04d}-decision.md",
        f"{head}# {title}\n\nThe text.\n\n## Considered Options\n\n- **Tool**: chosen.\n",
    )


def test_an_adr_keeps_its_number_its_title_its_front_matter_and_its_options_section_only() -> None:
    assert adr_of("docs/adr/0008-argo-workflows.md", ADR) == Adr(
        number=8,
        title="Argo Workflows runs the jobs",
        options=OPTIONS,
        front_matter=AdrFrontMatter(
            status=AdrStatus.ACCEPTED,
            date=datetime.date(2026, 10, 23),
            decision_makers=("owner",),
            issue=1535,
            amends=("0004",),
            amended_by=("0016",),
            body_hash="0f",
        ),
    )


def test_an_adr_with_no_options_section_keeps_its_title_and_no_options() -> None:
    adr = adr_of(
        "docs/adr/0013-releases.md", "# Releases use release-please\n\n## Decision\n\nGo.\n"
    )

    assert adr == Adr(number=13, title="Releases use release-please", options="")


def test_an_adr_with_no_front_matter_has_no_status_and_is_in_force() -> None:
    adr = adr_of("docs/adr/0009-a.md", "# T\n\n[ADR 0015](0015-x.md) supersedes this ADR.\n")

    assert adr is not None
    assert (adr.front_matter, adr.in_force) == (AdrFrontMatter(), True)


@pytest.mark.parametrize(
    "front_matter",
    [
        pytest.param("status: accepted\nsuperseded_by: ['0012']", id="unknown-key"),
        pytest.param("status: superseded\nsuperseded-by: [0012]", id="a-number-not-a-string"),
        pytest.param("status: superseded\nsuperseded-by: ['12']", id="not-four-digits"),
        pytest.param("status: superseded by ADR-0012", id="unknown-status"),
        pytest.param("- accepted", id="not-a-mapping"),
    ],
)
def test_a_front_matter_that_is_not_valid_stops_the_read_and_names_the_file(
    front_matter: str,
) -> None:
    with pytest.raises(ValidationError, match=r"docs/adr/0011-old\.md"):
        adr_of("docs/adr/0011-old.md", f"---\n{front_matter}\n---\n# Old\n")


def test_an_adr_entry_gives_its_number_its_title_the_adrs_that_amend_it_and_its_options() -> None:
    adr = Adr(number=8, title="Argo Workflows", options="## Considered Options\n\n- A.")
    amended = Adr(
        number=9,
        title="Next",
        options="",
        front_matter=AdrFrontMatter(amended_by=("0010", "0021")),
    )

    assert (adr.entry, amended.entry, Adr(number=10, title="Last", options="").entry) == (
        "ADR 0008: Argo Workflows\n## Considered Options\n\n- A.",
        "ADR 0009: Next\nAmended by ADR 0010, ADR 0021.",
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


def test_only_an_accepted_adr_or_one_with_no_status_is_in_force(
    store: InMemoryRoadmapStore,
) -> None:
    _seed(store, 1, "Quiet")
    _seed(store, 2, "Accepted", "status: accepted")
    _seed(store, 3, "Proposed", "status: proposed")
    _seed(store, 4, "Rejected", "status: rejected")
    _seed(store, 5, "Deprecated", "status: deprecated")
    _seed(store, 6, "Superseded", "status: superseded\nsuperseded-by: ['0002']")

    assert [adr.number for adr in read_adrs(store)] == [2, 1]


def test_an_adr_that_another_adr_supersedes_is_left_out_from_either_side(
    store: InMemoryRoadmapStore,
) -> None:
    # ADR 1 names its successor itself, and ADR 5 names the ADR that it replaces.
    _seed(store, 1, "Old", "status: accepted\nsuperseded-by: ['0002']")
    _seed(store, 2, "Middle", "status: accepted")
    _seed(store, 4, "Replaced", "status: accepted")
    _seed(store, 5, "Newest", "status: accepted\nsupersedes: ['0004']")

    assert [adr.number for adr in read_adrs(store)] == [5, 2]


def test_an_adr_that_another_adr_amends_stays_and_its_entry_names_the_amending_adrs(
    store: InMemoryRoadmapStore,
) -> None:
    _seed(store, 4, "Gate", "status: accepted\namended-by: ['0014']")
    _seed(store, 14, "Checks", "status: accepted\namends: ['0004']")

    first, second = read_adrs(store)

    assert (first.number, second.entry.splitlines()[:2]) == (
        14,
        ["ADR 0004: Gate", "Amended by ADR 0014."],
    )


def test_a_front_matter_that_is_not_valid_stops_the_read_of_the_adrs(
    store: InMemoryRoadmapStore,
) -> None:
    _seed(store, 2, "Middle", "status: done")

    with pytest.raises(ValidationError, match=r"docs/adr/0002-decision\.md"):
        read_adrs(store)


def _entries(count: int, options: str) -> tuple[Adr, ...]:
    """`count` ADRs, the newest first, each with the same `options`."""
    return tuple(
        Adr(number=number, title=f"Decision {number}", options=options)
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
    huge = Adr(number=9, title="Huge", options="\n".join(f"- **T{n}**: no." for n in range(900)))
    small = Adr(number=8, title="Small", options="- **Tool**: chosen.")

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


# The options of ADR 0010 as the repository holds them: the chosen option and three rejected ones
# name OpenSpec (#3258, #4661).
OPENSPEC_OPTIONS = (
    "## Considered Options\n\n"
    "- **Adopt OpenSpec and delete the task files** (chosen): one planning format.\n"
    "- **Adopt OpenSpec beside the task files**: rejected. Two sources of truth.\n"
    "- **Keep the task files**: rejected. Planning stays a format every agent must learn.\n"
    "- **A forked schema with a `feasibility` artifact**: rejected. It drifts."
)


@pytest.mark.parametrize(
    ("adr", "tool_names", "rejected"),
    [
        pytest.param(
            Adr(8, "Argo Workflows runs the jobs", OPTIONS),
            ("temporalio/temporal", "Temporal"),
            True,
            id="rejected-option",
        ),
        pytest.param(
            Adr(8, "Argo Workflows runs the jobs", OPTIONS),
            ("dbos-inc/dbos-transact-py", "DBOS"),
            False,
            id="runner-up-option",
        ),
        pytest.param(
            Adr(10, "OpenSpec is the spec and change proposal layer", OPENSPEC_OPTIONS),
            ("Fission-AI/OpenSpec", "OpenSpec"),
            False,
            id="chosen-option-names-it-too",
        ),
        pytest.param(
            Adr(
                9,
                "Use **Temporal** for the jobs",
                "## Considered Options\n\n- **Temporal**: rejected for now.",
            ),
            ("temporalio/temporal", "Temporal"),
            False,
            id="title-names-it",
        ),
        pytest.param(
            Adr(
                11,
                "Releases",
                "## Considered Options\n\n- **Celery, Dramatiq and Huey**: not chosen, after a "
                "comparison.",
            ),
            ("celery/celery", "Celery"),
            True,
            id="not-chosen",
        ),
        pytest.param(
            Adr(12, "Temporal is out", "The ADR has no options."),
            ("temporalio/temporal", "Temporal"),
            False,
            id="no-option",
        ),
    ],
)
def test_an_adr_rejects_a_tool_only_when_rejected_options_alone_name_it(
    adr: Adr, tool_names: tuple[str, ...], rejected: bool
) -> None:
    assert rejects(adr, *tool_names) is rejected
