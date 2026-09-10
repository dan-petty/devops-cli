"""Unit tests for dedicated library vector tier (devops_libraries) and Valkey symbol store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
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
    mock_qdrant.ensure_collection.assert_called_once()
    args, kwargs = mock_qdrant.ensure_collection.call_args
    assert kwargs.get("name") == DEFAULT_RAG_LIBRARIES_COLLECTION or (
        args and args[0] == DEFAULT_RAG_LIBRARIES_COLLECTION
    )


def test_ensure_collection_created_fallback_create_collection() -> None:
    mock_qdrant = MagicMock(spec=["get_collection_info", "create_collection"])
    mock_qdrant.get_collection_info.return_value = None

    store = LibraryVectorStore(qdrant_client=mock_qdrant, valkey_client=None)
    created = store.ensure_collection_exists()

    assert created is True
    mock_qdrant.create_collection.assert_called_once()
    args, kwargs = mock_qdrant.create_collection.call_args
    assert kwargs.get("collection_name") == DEFAULT_RAG_LIBRARIES_COLLECTION or (
        args and args[0] == DEFAULT_RAG_LIBRARIES_COLLECTION
    )


def test_ensure_collection_already_exists() -> None:
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection_info.return_value = {"status": "green"}

    store = LibraryVectorStore(qdrant_client=mock_qdrant, valkey_client=None)
    created = store.ensure_collection_exists()

    assert created is False
    mock_qdrant.ensure_collection.assert_not_called()
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

    assert count >= 3  # function, class, and method
    mock_qdrant.upsert_points.assert_called_once()
    assert mock_valkey.set.call_count >= 3  # function, class, and method cached in Valkey


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


def test_index_contract_indexes_methods() -> None:
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection_info.return_value = {"status": "green"}
    mock_valkey = MagicMock()

    store = LibraryVectorStore(
        qdrant_client=mock_qdrant,
        valkey_client=mock_valkey,
    )

    contract = _create_sample_contract()
    points_meta, texts, cache_entries = store._collect_contract_items(contract)

    kinds = {item["kind"] for item in points_meta}
    assert "function" in kinds
    assert "class" in kinds
    assert "method" in kinds

    method_items = [item for item in points_meta if item["kind"] == "method"]
    assert len(method_items) >= 1
    assert any("get_data" in item["symbol_name"] for item in method_items)

    cached_keys = [k for k, _ in cache_entries]
    assert any("get_data" in k for k in cached_keys)


def test_load_local_contracts_skips_invalid_json(tmp_path: Path) -> None:
    from devops_cli.commands.ai_ingest import _load_local_contracts

    valid_contract = _create_sample_contract()
    valid_file = tmp_path / "valid.json"
    valid_file.write_text(valid_contract.model_dump_json(), encoding="utf-8")

    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{invalid json here", encoding="utf-8")

    empty_file = tmp_path / "empty.json"
    empty_file.write_text("{}", encoding="utf-8")

    loaded = _load_local_contracts(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].package_name == "demo-pkg"


def test_build_runtime_vector_store_dry_run(tmp_path: Path) -> None:
    from devops_cli.commands.ai_ingest import _build_runtime_vector_store

    store = _build_runtime_vector_store(tmp_path, dry_run=True)
    assert store.qdrant_client is None
    assert store.valkey_client is None
    assert store.embedder is None


def test_build_runtime_vector_store_with_mocked_clients(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.commands import ai_ingest

    mock_valkey = MagicMock()
    mock_qdrant = MagicMock()
    mock_embedder = MagicMock()

    monkeypatch.setattr(ai_ingest, "_resolve_runtime_valkey_client", lambda: mock_valkey)
    monkeypatch.setattr(
        ai_ingest,
        "_resolve_runtime_qdrant_and_embedder",
        lambda: (mock_qdrant, mock_embedder),
    )

    store = ai_ingest._build_runtime_vector_store(tmp_path, semantic_needed=True, dry_run=False)
    assert store.valkey_client is mock_valkey
    assert store.qdrant_client is mock_qdrant
    assert store.embedder is mock_embedder


def test_cli_ai_ingest_index_libraries_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.commands import ai_ingest

    contract = _create_sample_contract()
    pkg_file = tmp_path / "demo-pkg.json"
    pkg_file.write_text(contract.model_dump_json(), encoding="utf-8")

    mock_store = MagicMock()
    monkeypatch.setattr(
        ai_ingest,
        "_build_runtime_vector_store",
        lambda *args, **kwargs: mock_store,
    )

    result = runner.invoke(
        ai_app,
        ["ingest", "index-libraries", "--dir", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "demo-pkg" in result.output
    mock_store.index_contract.assert_called_once()


def test_cli_ai_ingest_query_library_semantic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.commands import ai_ingest

    mock_store = MagicMock()
    mock_res = LibrarySearchResult(
        symbol_name="demo_pkg.api.get_data",
        package_name="demo-pkg",
        version="1.0.0",
        kind="function",
        signature_text="def get_data(query: str) -> dict[str, Any]",
        score=0.95,
        source="library_contract",
    )
    mock_store.search.return_value = [mock_res]
    monkeypatch.setattr(
        ai_ingest,
        "_build_runtime_vector_store",
        lambda *args, **kwargs: mock_store,
    )

    result = runner.invoke(
        ai_app,
        ["ingest", "query-library", "how to get data", "--contracts-dir", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "demo_pkg.api.get_data" in result.output
    assert "0.950" in result.output
    mock_store.search.assert_called_once_with("how to get data", package=None, top_k=5)


def test_discover_submodules_skips_private_and_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression test for Issue #84: ensure _discover_submodules skips __main__ and private submodules."""
    from types import ModuleType

    from devops_cli.ai.library.introspector import _discover_submodules

    dummy_root = ModuleType("dummy_pkg")
    dummy_root.__path__ = ["/dummy/path"]  # type: ignore[attr-defined]

    dummy_modules = [
        (None, "dummy_pkg.sub", False),
        (None, "dummy_pkg.__main__", False),
        (None, "dummy_pkg._private", False),
        (None, "dummy_pkg._internal.deep", False),
    ]

    imported_names: list[str] = []

    def mock_iter_modules(path: Any, prefix: str = "") -> list[Any]:
        return dummy_modules

    def mock_import(name: str) -> ModuleType:
        imported_names.append(name)
        return ModuleType(name)

    monkeypatch.setattr("pkgutil.iter_modules", mock_iter_modules)
    monkeypatch.setattr("importlib.import_module", mock_import)

    discovered = _discover_submodules(dummy_root, max_depth=1)
    assert len(discovered) == 1
    assert discovered[0].__name__ == "dummy_pkg.sub"
    assert "dummy_pkg.__main__" not in imported_names
    assert "dummy_pkg._private" not in imported_names


def test_index_doc_chunks_namespaced_point_ids() -> None:
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection_info.return_value = {"status": "green"}
    store = LibraryVectorStore(qdrant_client=mock_qdrant)
    chunk = DocChunk(
        chunk_id="intro_001",
        title="Introduction",
        content="Welcome to the library docs.",
        source="https://docs.example.com",
    )
    count = store.index_doc_chunks([chunk], package_name="demo-pkg")
    assert count == 1
    mock_qdrant.upsert_points.assert_called_once()
    called_points = mock_qdrant.upsert_points.call_args[1]["points"]
    assert called_points[0]["id"] == "demo-pkg:intro_001"


def test_valkey_symbol_cache_namespacing() -> None:
    mock_valkey = MagicMock()
    mock_valkey.get.return_value = None
    store = LibraryVectorStore(valkey_client=mock_valkey)
    store.lookup_symbol("fetch_data", package="my_lib")
    first_call_key = mock_valkey.get.call_args_list[0][0][0]
    assert first_call_key == "symbol:my_lib:fetch_data"
