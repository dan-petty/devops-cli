"""The providers of one run of the reference step (#4672): the two GitHub providers, and an
optional provider only for a public repository whose server answers at the start.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from devops_cli.roadmap.references.providers import (
    Hit,
    HitKind,
    SearchKind,
    open_providers,
    repositories_query,
)
from devops_cli.roadmap.references.step import ReferenceRequest, open_reference_step
from devops_cli.telemetry.instruments import BRAIN_REFERENCES_TOTAL
from tests.support.fakes.reference_provider import FakeReferenceProvider
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

if TYPE_CHECKING:
    from tests.support.fakes.otlp import FakeCollector

REPO = "example/roadmap"
NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
GITHUB = ["github-code", "github-repository"]


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=REPO, is_private=False)


def _optional(*, down: bool = False) -> FakeReferenceProvider:
    return FakeReferenceProvider("mcp-code", SearchKind.CODE, down=down)


def test_a_public_repository_with_no_optional_server_gets_the_two_github_providers(
    store: InMemoryRoadmapStore,
) -> None:
    with open_providers(store, private=False) as providers:
        names = [provider.name for provider in providers]
        kinds = [provider.kind for provider in providers]

    assert (names, kinds) == (GITHUB, [SearchKind.CODE, SearchKind.FACT])


def test_an_optional_provider_that_is_down_at_the_start_leaves_the_list_of_the_run(
    store: InMemoryRoadmapStore, otlp: FakeCollector, caplog: pytest.LogCaptureFixture
) -> None:
    down = _optional(down=True)

    with open_providers(store, private=False, optional=[down]) as providers:
        names = [provider.name for provider in providers]

    assert (names, down.connected, down.closed, otlp.points(BRAIN_REFERENCES_TOTAL.name)) == (
        GITHUB,
        False,
        False,
        [({"provider": "mcp-code", "result": "unavailable"}, 1.0)],
    )
    assert "mcp-code is down at the start" in caplog.text


def test_a_private_repository_gets_the_two_github_providers_only(
    store: InMemoryRoadmapStore,
) -> None:
    optional = _optional()

    with open_providers(store, private=True, optional=[optional]) as providers:
        names = [provider.name for provider in providers]

    assert (names, optional.connected) == (GITHUB, False)


def test_a_connected_optional_provider_takes_each_second_query_and_is_closed_at_the_end(
    store: InMemoryRoadmapStore,
) -> None:
    optional = _optional()
    optional.answer(
        "beta two", Hit("mcp-code", HitKind.CODE, "beta two", "example/agent", "src/agent.py")
    )
    request = ReferenceRequest(
        number=7,
        title="Run an agent",
        text="Use `alpha one`, `beta two` and `gamma three`.",
        repo=REPO,
        now=NOW,
    )

    with open_reference_step(store, mode="on", private=False, optional=[optional]) as step:
        names = [provider.name for provider in step.providers]
        step.run(store, request)
        open_during_the_run = optional.connected and not optional.closed

    assert (
        names,
        open_during_the_run,
        optional.closed,
        store.code_searches,
        optional.queries,
        store.repository_searches,
    ) == (
        [*GITHUB, "mcp-code"],
        True,
        True,
        ["alpha one", "gamma three"],
        ["beta two"],
        [repositories_query(["example/agent"])],
    )


def test_mode_off_opens_no_provider(store: InMemoryRoadmapStore) -> None:
    optional = _optional()

    with open_reference_step(store, mode="off", private=False, optional=[optional]) as step:
        providers = step.providers

    assert (providers, optional.connected) == ((), False)


def test_the_repository_query_names_each_repository_and_no_other_text() -> None:
    assert repositories_query(["example/agent", "not a name", "Example/App"]) == (
        "repo:example/agent repo:Example/App fork:true"
    )
