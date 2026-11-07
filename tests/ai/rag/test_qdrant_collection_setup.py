"""A new Qdrant collection is created with scalar quantization unless the caller opts out.

The real client sends its requests to a loopback server that records them.
"""

from __future__ import annotations

from typing import Any

import pytest
from qdrant_client import QdrantClient as NativeQdrantClient
from qdrant_client import models as qmodels

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


def _index_fields(served: ServedQdrant) -> list[str]:
    """The fields that the client asked for a payload index on, in order."""
    return [
        body["field_name"]
        for method, path, body in served.bodies
        if method == "PUT" and "/index" in path
    ]


def test_a_new_collection_gets_both_payload_indexes() -> None:
    with serving_qdrant() as served:
        QdrantClient(served.url, api_key="test-key", timeout=5.0).ensure_collection("docs", 4)

    assert _index_fields(served) == ["project_name", "file_path"]


def test_an_existing_collection_without_payload_indexes_gets_both_on_the_next_run() -> None:
    native = NativeQdrantClient(location=":memory:")
    native.create_collection(
        "docs", vectors_config=qmodels.VectorParams(size=4, distance=qmodels.Distance.COSINE)
    )
    with serving_qdrant() as served:
        served.collection_info = native.get_collection("docs").model_dump(mode="json")
        QdrantClient(served.url, api_key="test-key", timeout=5.0).ensure_collection("docs", 4)

    assert (_index_fields(served), [b for b in served.bodies if "/index" not in b[1]]) == (
        ["project_name", "file_path"],
        [],
    )
