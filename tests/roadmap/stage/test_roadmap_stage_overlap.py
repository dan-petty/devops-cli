"""`devops roadmap stage`: the open pull requests and metric senders of a context (#3252). A pull
request gives its title only when an author that the jobs trust opened it (`roadmap/trust.py`)."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from devops_cli.roadmap.stage.stage_overlap import (
    OpenPull,
    OpenPulls,
    cited_instruments,
    metric_senders,
    open_pulls,
    overlaps,
)

_INSTRUMENT = "devops_cli_github_requests_total"
_APP_SLUG = "devops-cli-service"
_TITLE_LEFT_OUT = "(title left out: an account with no write access opened the item)"
_PERSON: Mapping[str, Any] = {
    "authorAssociation": "OWNER",
    "author": {"__typename": "User", "login": "a-person"},
}


class FakeReads:
    """A GraphQL client that answers its pages in order and records each request."""

    def __init__(self, pages: Sequence[Sequence[Mapping[str, Any]]]) -> None:
        self._pages = list(pages)
        self.calls: list[Mapping[str, Any]] = []

    def graphql(self, query: str, variables: Mapping[str, Any] | None = None) -> Any:
        self.calls.append({"query": query, "variables": dict(variables or {})})
        number = len(self.calls)
        return {
            "data": {
                "repository": {
                    "pullRequests": {
                        "nodes": list(self._pages[number - 1]),
                        "pageInfo": {
                            "hasNextPage": number < len(self._pages),
                            "endCursor": f"cursor-{number}",
                        },
                    }
                }
            }
        }


def _pull(
    number: int,
    title: str,
    *files: str,
    state: str = "OPEN",
    author: Mapping[str, Any] | None = _PERSON,
) -> dict[str, Any]:
    """One pull request node of the GraphQL read. `author` holds the `authorAssociation` and the
    `author` object that GitHub gives: a person with write access unless it is given, and None
    for a node with no author fields."""
    return {
        "number": number,
        "title": title,
        "state": state,
        "files": {"nodes": [{"path": path} for path in files]},
        **(author or {}),
    }


def _bot(login: str, typename: str = "Bot") -> dict[str, Any]:
    """The author fields of an account that GitHub gives the association CONTRIBUTOR."""
    return {"authorAssociation": "CONTRIBUTOR", "author": {"__typename": typename, "login": login}}


@pytest.fixture
def app_slug(config: Callable[..., Path]) -> str:
    """The slug of the Service App, so that the login of its bot is `<slug>[bot]`."""
    config(service={"github_app": {"slug": _APP_SLUG}})
    return _APP_SLUG


def test_metric_senders_lists_each_other_file_that_holds_a_cited_instrument() -> None:
    files = {
        _INSTRUMENT: ["src/devops_cli/telemetry/instruments.py", "docs/TELEMETRY.md"],
    }

    senders = metric_senders([_INSTRUMENT], lambda name: files[name])

    assert senders == {
        _INSTRUMENT: ("docs/TELEMETRY.md", "src/devops_cli/telemetry/instruments.py")
    }


def test_metric_senders_ignores_a_name_that_no_instrument_holds() -> None:
    assert metric_senders(["devops_cli_dashboard_panel"], lambda name: ["docs/panel.md"]) == {}


def test_cited_instruments_keeps_the_names_that_instruments_holds() -> None:
    text = f"The panel reads `{_INSTRUMENT}` and `devops_cli_dashboard_panel`."

    assert cited_instruments(text) == [_INSTRUMENT]


def test_a_pull_that_changes_a_cited_path_is_one_overlap() -> None:
    reads = FakeReads([[_pull(3173, "feat(telemetry): add a panel", "docs/TELEMETRY.md")]])

    read = open_pulls(reads, "example/roadmap")
    found = overlaps(read.pulls, ["docs/TELEMETRY.md", "src/devops_cli/stage.py"])

    assert read.requests == 1
    assert [(entry.number, entry.title, entry.state, entry.paths) for entry in found] == [
        (3173, "feat(telemetry): add a panel", "open", ("docs/TELEMETRY.md",))
    ]


def test_a_pull_that_changes_no_cited_path_is_no_overlap() -> None:
    reads = FakeReads([[_pull(3173, "feat(telemetry): add a panel", "docs/TELEMETRY.md")]])

    read = open_pulls(reads, "example/roadmap")

    assert overlaps(read.pulls, ["src/devops_cli/roadmap/stage/stage.py"]) == ()


def test_a_plan_pull_request_carries_the_plan_mark() -> None:
    reads = FakeReads(
        [
            [
                _pull(
                    3252,
                    "docs(spec): plan #3252 stage context",
                    "src/devops_cli/roadmap/stage/stage_overlap.py",
                ),
                _pull(
                    3251,
                    "docs(openspec): plan #3251 legacy stage context",
                    "src/devops_cli/roadmap/stage/stage_overlap.py",
                ),
                _pull(
                    3253, "feat(roadmap): stage context", "src/devops_cli/roadmap/stage/stage.py"
                ),
            ]
        ]
    )

    read = open_pulls(reads, "example/roadmap")

    assert [pull.plan for pull in read.pulls] == [True, True, False]
    assert overlaps(read.pulls, ["src/devops_cli/roadmap/stage/stage_overlap.py"])[0].plan is True


def test_a_pull_request_of_an_outside_account_keeps_its_plan_mark_and_gives_no_title() -> None:
    stranger = {
        "authorAssociation": "NONE",
        "author": {"__typename": "User", "login": "a-stranger"},
    }
    reads = FakeReads(
        [[_pull(9, "docs(spec): plan #9 of an outside account", "src/app.py", author=stranger)]]
    )

    read = open_pulls(reads, "example/roadmap")

    assert (read.pulls, read.requests) == (
        (OpenPull(9, _TITLE_LEFT_OUT, "open", ("src/app.py",), plan=True),),
        1,
    )
    assert [overlap.entry() for overlap in overlaps(read.pulls, ["src/app.py"])] == [
        {
            "number": 9,
            "title": _TITLE_LEFT_OUT,
            "state": "open",
            "plan": True,
            "paths": ["src/app.py"],
        }
    ]


def test_a_pull_request_whose_author_github_does_not_give_has_no_title() -> None:
    reads = FakeReads(
        [
            [
                _pull(9, "fix: a change of an outside account", "src/app.py", author=None),
                _pull(10, "fix: a deleted account", author={"authorAssociation": "NONE"}),
            ]
        ]
    )

    read = open_pulls(reads, "example/roadmap")

    assert [pull.title for pull in read.pulls] == [_TITLE_LEFT_OUT, _TITLE_LEFT_OUT]


@pytest.mark.parametrize(
    ("author", "title"),
    [
        (_bot(_APP_SLUG), "docs(spec): plan #7"),
        (_bot(f"{_APP_SLUG}[bot]"), "docs(spec): plan #7"),
        (_bot("github-actions"), "docs(spec): plan #7"),
        (_bot("dependabot"), _TITLE_LEFT_OUT),
        (_bot(f"{_APP_SLUG}x"), _TITLE_LEFT_OUT),
        (_bot(_APP_SLUG, typename="User"), _TITLE_LEFT_OUT),
        (_bot("github-actions", typename="User"), _TITLE_LEFT_OUT),
        (_bot("github-actions[bot]", typename="User"), _TITLE_LEFT_OUT),
    ],
)
def test_a_pull_request_of_the_two_trusted_bots_keeps_its_title_and_no_other_account_does(
    app_slug: str, author: Mapping[str, Any], title: str
) -> None:
    reads = FakeReads([[_pull(7, "docs(spec): plan #7", "src/app.py", author=author)]])

    read = open_pulls(reads, "example/roadmap")

    assert [(pull.title, pull.plan) for pull in read.pulls] == [(title, True)]


def test_the_read_asks_github_for_the_author_of_each_pull_request_in_the_same_request() -> None:
    reads = FakeReads([[_pull(1, "fix: one", "src/app.py")]])

    open_pulls(reads, "example/roadmap")

    (call,) = reads.calls
    asked = " ".join(call["query"].split())
    assert ("authorAssociation" in asked, "author { __typename login }" in asked) == (True, True)


def test_150_open_pull_requests_cost_two_requests_and_no_other_request() -> None:
    first = [
        _pull(number, f"fix(roadmap): item {number}", f"src/file_{number}.py")
        for number in range(1, 101)
    ]
    second = [
        _pull(number, f"fix(roadmap): item {number}", f"src/file_{number}.py")
        for number in range(101, 151)
    ]
    reads = FakeReads([first, second])

    read = open_pulls(reads, "example/roadmap")

    assert read.requests == 2
    assert len(reads.calls) == 2
    assert len(read.pulls) == 150
    assert [call["variables"]["cursor"] for call in reads.calls] == [None, "cursor-1"]


def test_a_repository_name_that_is_no_owner_and_name_reads_nothing() -> None:
    reads = FakeReads([])

    assert open_pulls(reads, "roadmap") == OpenPulls((), 0)
    assert reads.calls == []
