"""One public function builds the Qdrant client, the embedder and the collection names (#1329).

Qdrant and the embedder come from their seams, so each test installs the fake of the edge and
no test patches a devops_cli name.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.rag.indexer import RagComponents, resolve_rag_components
from devops_cli.config.settings import Settings, load_settings
from devops_cli.exceptions import ConfigurationError

pytestmark = pytest.mark.usefixtures("keyring_store")

_CONFIGURED_QDRANT = "qdrant:\n  url: http://localhost:6333\n"


def _unconfigure_qdrant(config: Path) -> None:
    """Remove the address of Qdrant from the config file of the test."""
    config.write_text(config.read_text(encoding="utf-8").replace(_CONFIGURED_QDRANT, ""))


def test_the_components_are_the_clients_of_the_seams(qdrant: Any, embedder: Any) -> None:
    components = resolve_rag_components()

    assert isinstance(components, RagComponents)
    assert (components.qdrant is qdrant, components.embedder is embedder) == (True, True)


def test_the_collections_take_the_default_prefix(qdrant: Any, embedder: Any) -> None:
    components = resolve_rag_components()

    assert (components.code_collection, components.docs_collection) == (
        "devops_code",
        "devops_docs",
    )


def test_the_collections_take_the_configured_prefix(
    qdrant: Any, embedder: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_QDRANT_COLLECTION_PREFIX", "team")

    components = resolve_rag_components()

    assert (components.code_collection, components.docs_collection) == ("team_code", "team_docs")


def test_an_empty_prefix_gives_the_default_names(qdrant: Any, embedder: Any) -> None:
    settings = load_settings()
    settings.qdrant.collection_prefix = ""

    components = resolve_rag_components(settings)

    assert (components.code_collection, components.docs_collection) == (
        "devops_code",
        "devops_docs",
    )


def test_the_components_follow_the_settings_that_the_caller_gives(
    embedder: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The client has the address and the timeout of the given settings, not the loaded ones."""
    monkeypatch.setenv("DEVOPS_CLI_QDRANT_COLLECTION_PREFIX", "loaded")
    given = Settings.model_validate(
        {"qdrant": {"url": "http://127.0.0.1:6334", "collection_prefix": "given", "timeout": 42}}
    )

    components = resolve_rag_components(given)

    assert (
        components.qdrant.base_url,
        components.qdrant.timeout,
        components.code_collection,
    ) == ("http://127.0.0.1:6334", 42.0, "given_code")


def test_a_missing_qdrant_address_names_the_setting(
    embedder: Any, isolate_devops_cli_config: Path
) -> None:
    _unconfigure_qdrant(isolate_devops_cli_config)

    with pytest.raises(ConfigurationError) as refused:
        resolve_rag_components()

    assert (str(refused.value), refused.value.details.get("key")) == (
        "No Qdrant vector store URL configured. Run: devops config set qdrant.url <url>",
        "qdrant.url",
    )
