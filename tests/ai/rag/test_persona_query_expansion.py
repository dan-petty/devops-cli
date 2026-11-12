"""A persona search adds the terms of its persona to the query."""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.ai.personas import Persona
from devops_cli.ai.rag.retriever import SemanticRetriever

pytestmark = pytest.mark.usefixtures("keyring_store")

_QUERY = "retry policy"


@pytest.mark.parametrize(
    ("persona", "expanded"),
    [
        (Persona.DEVSECOPS, f"{_QUERY} security auth secrets token validation permissions"),
        (Persona.ARCHITECT, f"{_QUERY} architecture design patterns interfaces abstractions"),
        (Persona.PM, f"{_QUERY} requirements api specification contract docs"),
        (Persona.AUDITOR, f"{_QUERY} compliance logging error handling telemetry reliability"),
        (Persona.QA, f"{_QUERY} tests fixtures mocks assertions coverage"),
        (Persona.CHALLENGER, f"{_QUERY} decision rationale trade-offs alternatives failure modes"),
        ("security-lead", _QUERY),
    ],
)
def test_a_persona_search_embeds_the_terms_of_its_persona(
    qdrant: Any, embedder: Any, persona: str, expanded: str
) -> None:
    SemanticRetriever(qdrant=qdrant, embedder=embedder).retrieve_context_for_persona(
        _QUERY, persona=persona
    )

    assert embedder.recorded_texts == [(expanded, True)]
