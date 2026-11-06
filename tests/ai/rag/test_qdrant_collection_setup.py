"""A new Qdrant collection is created with scalar quantization unless the caller opts out.

The real client sends its requests to a loopback server that records them.
"""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.ai.rag.qdrant import QdrantClient
from tests.support.fakes.qdrant import ServedQdrant, serving_qdrant

pytestmark = [
    pytest.mark.usefixtures("keyring_store"),
    pytest.mark.filterwarnings("ignore:Api key is used with an insecure connection"),
]


def _created(served: ServedQdrant) -> dict[str, Any]:
    """The JSON body of the request that created the collection."""
    ((_, path, body),) = (
        entry for entry in served.bodies if entry[0] == "PUT" and "/index" not in entry[1]
    )
    assert path.split("?")[0] == "/collections/docs"
    return body  # type: ignore[no-any-return]


def test_new_collections_are_created_with_int8_quantization_held_in_ram() -> None:
    """Quantization stores vectors as int8, held in RAM for fast scoring."""
    with serving_qdrant() as served:
        QdrantClient(served.url, api_key="test-key", timeout=5.0).ensure_collection("docs", 768)

    body = _created(served)
    assert (body["vectors"]["size"], body["quantization_config"]) == (
        768,
        {"scalar": {"type": "int8", "quantile": 0.99, "always_ram": True}},
    )


def test_quantization_can_be_disabled() -> None:
    """Opting out stores full-precision vectors."""
    with serving_qdrant() as served:
        client = QdrantClient(served.url, api_key="test-key", timeout=5.0)
        client.ensure_collection("docs", 768, quantize=False)

    assert _created(served).get("quantization_config") is None
