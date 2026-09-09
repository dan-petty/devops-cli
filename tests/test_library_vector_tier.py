"""Unit tests for dedicated library vector tier (devops_libraries) and Valkey symbol store."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from devops_cli.ai.rag.library_store import LibraryVectorStore
from devops_cli.commands.ai import ai_app
from devops_cli.config.defaults import DEFAULT_RAG_LIBRARIES_COLLECTION
from devops_cli.models.library import (
    ClassSignature,
    DocChunk,
    FunctionSignature,
    LibraryContract,
    LibrarySearchResult,
    ModuleContract,
    ParameterSignature,
)

runner = CliRunner()


def _create_sample_contract() -> LibraryContract:
    """Helper to create a sample LibraryContract for testing."""
    fn_sig = FunctionSignature(
        name="get_data",
        qualname="demo_pkg.api.get_data",
        parameters=[ParameterSignature(name="query", annotation="str")],
        return_annotation="dict[str, Any]",
        docstring="Retrieve data from API.",
    )
    cls_sig = ClassSignature(
        name="DataClient",
        qualname="demo_pkg.api.DataClient",
        bases=["BaseClient"],
        docstring="Client for data access.",
        methods={"get_data": fn_sig},
        properties=["is_connected"],
    )
    mod_contract = ModuleContract(
        name="demo_pkg.api",
        docstring="API module for demo_pkg",
        all_exports=["DataClient", "get_data"],
        functions={"get_data": fn_sig},
        classes={"DataClient": cls_sig},
        constants={"VERSION": "1.0.0"},
        submodules=[],
    )
    return LibraryContract(
        package_name="demo-pkg",
        version="1.0.0",
        timestamp="2026-09-09T17:00:00Z",
        modules={"demo_pkg.api": mod_contract},
        symbols_index={
            "demo_pkg.api.get_data": "function",
            "demo_pkg.api.DataClient": "class",
            "demo_pkg.api.DataClient.get_data": "method",
        },
        total_modules=1,
        total_functions=1,
        total_classes=1,
    )


def test_library_search_result_model() -> None:
    res = LibrarySearchResult(
        symbol_name="demo_pkg.api.get_data",
        package_name="demo-pkg",
        version="1.0.0",
        kind="function",
        signature_text="def get_data(query: str) -> dict[str, Any]",
        docstring="Retrieve data from API.",
        score=0.92,
        source="library_contract",
    )
    assert res.symbol_name == "demo_pkg.api.get_data"
    assert res.package_name == "demo-pkg"
    assert res.score == 0.92
    assert res.kind == "function"


def test_default_collection_name() -> None:
    assert DEFAULT_RAG_LIBRARIES_COLLECTION == "devops_libraries"


def test_ensure_collection_created() -> None:
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection_info.return_value = None  # Collection does not exist

    store = LibraryVectorStore(qdrant_client=mock_qdrant, valkey_client=None)
    created = store.ensure_collection_exists()

    assert created is True
    mock_qdrant.create_collection.assert_called_once()
    args, kwargs = mock_qdrant.create_collection.call_args
    assert (
        kwargs.get("collection_name") == DEFAULT_RAG_LIBRARIES_COLLECTION
        or args[0] == DEFAULT_RAG_LIBRARIES_COLLECTION
    )


def test_ensure_collection_already_exists() -> None:
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection_info.return_value = {"status": "green"}

    store = LibraryVectorStore(qdrant_client=mock_qdrant, valkey_client=None)
    created = store.ensure_collection_exists()

    assert created is False
    mock_qdrant.create_collection.assert_not_called()


def test_index_contract_and_valkey_cache() -> None:
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection_info.return_value = {"status": "green"}
    mock_valkey = MagicMock()
    mock_valkey.ping.return_value = True

    mock_embedder = MagicMock()
    mock_embedder.embed_text.return_value = [0.1] * 384
    mock_embedder.embed_batch.return_value = [[0.1] * 384] * 5

    store = LibraryVectorStore(
        qdrant_client=mock_qdrant,
        valkey_client=mock_valkey,
        embedder=mock_embedder,
    )

    contract = _create_sample_contract()
    count = store.index_contract(contract)

    assert count >= 2  # at least function and class
    mock_qdrant.upsert_points.assert_called_once()
    assert mock_valkey.set.call_count >= 2  # function, class cached in Valkey


def test_lookup_symbol_valkey_hit() -> None:
    fn_sig = FunctionSignature(
        name="get_data",
        qualname="demo_pkg.api.get_data",
        parameters=[],
        return_annotation="None",
    )
    mock_valkey = MagicMock()
    mock_valkey.get.return_value = fn_sig.model_dump_json()

    store = LibraryVectorStore(qdrant_client=MagicMock(), valkey_client=mock_valkey)
    res = store.lookup_symbol("demo_pkg.api.get_data")

    assert res is not None
    assert res.name == "get_data"
    mock_valkey.get.assert_called_once()


def test_lookup_symbol_fallback_to_local_file(tmp_path: Path) -> None:
    contract = _create_sample_contract()
    pkg_file = tmp_path / "demo-pkg.json"
    pkg_file.write_text(contract.model_dump_json(), encoding="utf-8")

    mock_valkey = MagicMock()
    mock_valkey.get.return_value = None  # Cache miss in Valkey

    store = LibraryVectorStore(
        qdrant_client=MagicMock(),
        valkey_client=mock_valkey,
        local_contracts_dir=tmp_path,
    )
    res = store.lookup_symbol("demo_pkg.api.get_data")

    assert res is not None
    assert res.name == "get_data"


def test_search_library_semantic() -> None:
    mock_qdrant = MagicMock()
    mock_point = MagicMock()
    mock_point.score = 0.88
    mock_point.payload = {
        "symbol_name": "demo_pkg.api.get_data",
        "package_name": "demo-pkg",
        "version": "1.0.0",
        "kind": "function",
        "signature_text": "def get_data(query: str) -> dict[str, Any]",
        "docstring": "Retrieve data from API.",
        "source": "library_contract",
    }
    mock_qdrant.search_points.return_value = [mock_point]

    mock_embedder = MagicMock()
    mock_embedder.embed_text.return_value = [0.1] * 384

    store = LibraryVectorStore(
        qdrant_client=mock_qdrant,
        valkey_client=None,
        embedder=mock_embedder,
    )

    results = store.search("how to retrieve data from api", top_k=3)
    assert len(results) == 1
    assert results[0].symbol_name == "demo_pkg.api.get_data"
    assert results[0].score == 0.88


def test_index_doc_chunks() -> None:
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection_info.return_value = {"status": "green"}

    mock_embedder = MagicMock()
    mock_embedder.embed_batch.return_value = [[0.1] * 384]

    store = LibraryVectorStore(
        qdrant_client=mock_qdrant,
        valkey_client=None,
        embedder=mock_embedder,
    )

    chunk = DocChunk(
        chunk_id="chunk_001",
        source="docs/api.md",
        headings=["API Guide"],
        title="API Guide",
        content="Overview of the demo API.",
        token_estimate=10,
        tags=["guide"],
    )

    indexed = store.index_doc_chunks([chunk], package_name="demo-pkg")
    assert indexed == 1
    mock_qdrant.upsert_points.assert_called_once()


def test_cli_ai_ingest_index_libraries(tmp_path: Path) -> None:
    contract = _create_sample_contract()
    pkg_file = tmp_path / "demo-pkg.json"
    pkg_file.write_text(contract.model_dump_json(), encoding="utf-8")

    result = runner.invoke(
        ai_app,
        ["ingest", "index-libraries", "--dir", str(tmp_path), "--dry-run"],
    )
    assert result.exit_code == 0
    assert (
        "Indexed" in result.output
        or "demo-pkg" in result.output
        or "dry-run" in result.output.lower()
    )


def test_cli_ai_ingest_query_library_exact(tmp_path: Path) -> None:
    contract = _create_sample_contract()
    pkg_file = tmp_path / "demo-pkg.json"
    pkg_file.write_text(contract.model_dump_json(), encoding="utf-8")

    result = runner.invoke(
        ai_app,
        [
            "ingest",
            "query-library",
            "demo_pkg.api.get_data",
            "--contracts-dir",
            str(tmp_path),
            "--exact",
        ],
    )
    assert result.exit_code == 0
    assert "get_data" in result.output


def test_cli_ai_ingest_query_library_json(tmp_path: Path) -> None:
    contract = _create_sample_contract()
    pkg_file = tmp_path / "demo-pkg.json"
    pkg_file.write_text(contract.model_dump_json(), encoding="utf-8")

    result = runner.invoke(
        ai_app,
        [
            "ingest",
            "query-library",
            "demo_pkg.api.get_data",
            "--contracts-dir",
            str(tmp_path),
            "--exact",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["name"] == "get_data"
