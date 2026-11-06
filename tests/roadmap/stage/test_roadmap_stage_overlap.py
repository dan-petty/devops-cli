"""`devops roadmap stage`: the open pull requests and metric senders of a context (#3252)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from devops_cli.roadmap.stage.stage_overlap import (
    OpenPulls,
    cited_instruments,
    metric_senders,
    open_pulls,
    overlaps,
)

_INSTRUMENT = "devops_cli_github_requests_total"


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


def _pull(number: int, title: str, *files: str, state: str = "OPEN") -> dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "state": state,
        "files": {"nodes": [{"path": path} for path in files]},
    }


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
                    "docs(openspec): plan #3252 stage context",
                    "src/devops_cli/roadmap/stage/stage_overlap.py",
                ),
                _pull(
                    3253, "feat(roadmap): stage context", "src/devops_cli/roadmap/stage/stage.py"
                ),
            ]
        ]
    )

    read = open_pulls(reads, "example/roadmap")

    assert [pull.plan for pull in read.pulls] == [True, False]
    assert overlaps(read.pulls, ["src/devops_cli/roadmap/stage/stage_overlap.py"])[0].plan is True


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
