"""Dedicated library vector tier and Valkey symbol cache store."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, cast

from devops_cli.config.defaults import (
    DEFAULT_DRY_RUN_EMBEDDING_DIMENSION,
    DEFAULT_QDRANT_DISTANCE,
    DEFAULT_RAG_LIBRARIES_COLLECTION,
    DEFAULT_VALKEY_SYMBOL_TTL_SECONDS,
)
from devops_cli.models.library import (
    ClassSignature,
    DocChunk,
    FunctionSignature,
    LibraryContract,
    LibrarySearchResult,
    ModuleContract,
)

logger = logging.getLogger(__name__)


def _format_fn_signature(fn: FunctionSignature) -> str:
    """Format a FunctionSignature model into Pythonic signature string."""
    params = [f"{p.name}: {p.annotation}" if p.annotation else p.name for p in fn.parameters]
    return f"def {fn.name}({', '.join(params)}) -> {fn.return_annotation}"


def _format_class_signature(cls: ClassSignature) -> str:
    """Format a ClassSignature model into Pythonic class header string."""
    bases_str = f"({', '.join(cls.bases)})" if cls.bases else ""
    return f"class {cls.name}{bases_str}"


def _parse_cached_symbol(raw: str) -> FunctionSignature | ClassSignature | None:
    """Parse JSON string from Valkey cache into FunctionSignature or ClassSignature."""
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        if "parameters" in data:
            return FunctionSignature.model_validate(data)
        if "methods" in data or "bases" in data:
            return ClassSignature.model_validate(data)
    except Exception as exc:
        logger.debug("Failed to deserialize cached symbol JSON: %s", exc)
    return None


def _find_function_match(
    functions: dict[str, FunctionSignature], symbol: str
) -> FunctionSignature | None:
    """Find matching function signature by exact key, qualname, or short name."""
    if symbol in functions:
        return functions[symbol]
    for fn in functions.values():
        if fn.qualname == symbol or fn.name == symbol:
            return fn
    return None


def _find_method_in_class(cls: ClassSignature, symbol: str) -> FunctionSignature | None:
    """Find matching method signature inside a ClassSignature."""
    if symbol in cls.methods:
        return cls.methods[symbol]
    for m in cls.methods.values():
        if m.qualname == symbol or m.name == symbol:
            return m
    return None


def _find_class_match(
    classes: dict[str, ClassSignature], symbol: str
) -> FunctionSignature | ClassSignature | None:
    """Find matching class or class method signature by qualname or short name."""
    if symbol in classes:
        return classes[symbol]
    for cls in classes.values():
        if cls.qualname == symbol or cls.name == symbol:
            return cls
        method_match = _find_method_in_class(cls, symbol)
        if method_match is not None:
            return method_match
    return None


def _search_module_symbols(
    mod: ModuleContract, symbol: str
) -> FunctionSignature | ClassSignature | None:
    """Find matching function, class, or method signature in a module contract."""
    return _find_function_match(mod.functions, symbol) or _find_class_match(mod.classes, symbol)


def _search_contract_modules(
    contract: LibraryContract, symbol: str
) -> FunctionSignature | ClassSignature | None:
    """Search all modules in a LibraryContract for matching symbol."""
    for mod in contract.modules.values():
        match = _search_module_symbols(mod, symbol)
        if match is not None:
            return match
    return None


def _collect_function_item(
    fn: FunctionSignature, package_name: str, version: str, kind: str = "function"
) -> tuple[dict[str, Any], str, list[tuple[str, str]]]:
    """Extract point metadata, embedding text, and cache tuples for a function or method."""
    sig = _format_fn_signature(fn)
    text = f"{sig}\n\n{fn.docstring or ''}"
    meta = {
        "symbol_name": fn.qualname,
        "package_name": package_name,
        "version": version,
        "kind": kind,
        "signature_text": sig,
        "docstring": fn.docstring,
        "source": "library_contract",
    }
    json_str = fn.model_dump_json()
    cache = [
        (f"symbol:{package_name}:{fn.qualname}", json_str),
        (f"symbol:{fn.qualname}", json_str),
    ]
    return meta, text, cache


def _collect_class_item(
    cls: ClassSignature, package_name: str, version: str
) -> tuple[dict[str, Any], str, list[tuple[str, str]]]:
    """Extract point metadata, embedding text, and cache tuples for a class."""
    cls_sig = _format_class_signature(cls)
    text = f"{cls_sig}\n\n{cls.docstring or ''}"
    meta = {
        "symbol_name": cls.qualname,
        "package_name": package_name,
        "version": version,
        "kind": "class",
        "signature_text": cls_sig,
        "docstring": cls.docstring,
        "source": "library_contract",
    }
    json_str = cls.model_dump_json()
    cache = [
        (f"symbol:{package_name}:{cls.qualname}", json_str),
        (f"symbol:{cls.qualname}", json_str),
    ]
    return meta, text, cache


class LibraryVectorStore:
    """Segregated vector index and in-memory symbol cache for library contracts."""

    def __init__(
        self,
        qdrant_client: Any = None,
        valkey_client: Any = None,
        embedder: Any = None,
        collection_name: str = DEFAULT_RAG_LIBRARIES_COLLECTION,
        local_contracts_dir: Path | None = None,
    ) -> None:
        self.qdrant_client = qdrant_client
        self.valkey_client = valkey_client
        self.embedder = embedder
        self.collection_name = collection_name
        self.local_contracts_dir = local_contracts_dir or Path(".data/libraries")

    def _resolve_dimension(self) -> int:
        """Resolve vector dimension from embedder or fallback default."""
        if self.embedder is not None:
            if hasattr(self.embedder, "dimension"):
                return int(self.embedder.dimension)
            if hasattr(self.embedder, "embed_text"):
                vec = self.embedder.embed_text("probe")
                if isinstance(vec, list) and vec:
                    return len(vec)
        return DEFAULT_DRY_RUN_EMBEDDING_DIMENSION

    def ensure_collection_exists(self) -> bool:
        """Ensure devops_libraries collection exists in Qdrant, creating it if absent."""
        if self.qdrant_client is None:
            return False
        info = self.qdrant_client.get_collection_info(self.collection_name)
        if info:
            return False

        dim = self._resolve_dimension()
        if hasattr(self.qdrant_client, "ensure_collection"):
            self.qdrant_client.ensure_collection(
                name=self.collection_name,
                vector_size=dim,
                distance=DEFAULT_QDRANT_DISTANCE,
            )
        elif hasattr(self.qdrant_client, "create_collection"):
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vector_size=dim,
                distance=DEFAULT_QDRANT_DISTANCE,
            )
        return True

    def _embed_single_text(self, text: str) -> list[float]:
        """Embed a single text string using configured embedder."""
        if self.embedder is None:
            return [0.0] * DEFAULT_DRY_RUN_EMBEDDING_DIMENSION
        if hasattr(self.embedder, "embed_text"):
            return cast(list[float], self.embedder.embed_text(text))
        if hasattr(self.embedder, "embed_query"):
            return cast(list[float], self.embedder.embed_query(text))
        if hasattr(self.embedder, "embed_texts"):
            res = cast(list[list[float]], self.embedder.embed_texts([text]))
            return res[0] if res else [0.0] * DEFAULT_DRY_RUN_EMBEDDING_DIMENSION
        return [0.0] * DEFAULT_DRY_RUN_EMBEDDING_DIMENSION

    def _embed_many_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple text strings using batch embedder."""
        if not texts:
            return []
        if self.embedder is None:
            return [[0.0] * DEFAULT_DRY_RUN_EMBEDDING_DIMENSION for _ in texts]
        if hasattr(self.embedder, "embed_batch"):
            return cast(list[list[float]], self.embedder.embed_batch(texts))
        if hasattr(self.embedder, "embed_texts"):
            return cast(list[list[float]], self.embedder.embed_texts(texts))
        if hasattr(self.embedder, "embed_text"):
            return [cast(list[float], self.embedder.embed_text(t)) for t in texts]
        return [[0.0] * DEFAULT_DRY_RUN_EMBEDDING_DIMENSION for _ in texts]

    def _cache_symbol_in_valkey(self, key: str, payload_json: str) -> None:
        """Write serialized symbol JSON to Valkey with standard TTL."""
        if self.valkey_client is None:
            return
        try:
            self.valkey_client.set(key, payload_json, ttl=DEFAULT_VALKEY_SYMBOL_TTL_SECONDS)
        except Exception as exc:
            logger.debug("Failed to cache symbol '%s' in Valkey: %s", key, exc)

    def _collect_contract_items(
        self, contract: LibraryContract
    ) -> tuple[list[dict[str, Any]], list[str], list[tuple[str, str]]]:
        """Extract points, text descriptions, and cache entries from a LibraryContract."""
        points_meta: list[dict[str, Any]] = []
        texts: list[str] = []
        cache_entries: list[tuple[str, str]] = []

        for mod in contract.modules.values():
            for fn in mod.functions.values():
                meta, text, cache = _collect_function_item(
                    fn, contract.package_name, contract.version, "function"
                )
                points_meta.append(meta)
                texts.append(text)
                cache_entries.extend(cache)

            for cls in mod.classes.values():
                meta, text, cache = _collect_class_item(
                    cls, contract.package_name, contract.version
                )
                points_meta.append(meta)
                texts.append(text)
                cache_entries.extend(cache)

                for method in cls.methods.values():
                    m_meta, m_text, m_cache = _collect_function_item(
                        method, contract.package_name, contract.version, "method"
                    )
                    points_meta.append(m_meta)
                    texts.append(m_text)
                    cache_entries.extend(m_cache)

        return points_meta, texts, cache_entries

    def index_contract(self, contract: LibraryContract) -> int:
        """Embed API symbols from LibraryContract, upsert to Qdrant, and cache in Valkey."""
        self.ensure_collection_exists()
        points_meta, texts, cache_entries = self._collect_contract_items(contract)
        if not points_meta:
            return 0

        vectors = self._embed_many_texts(texts)
        points = [
            {"id": meta["symbol_name"], "vector": vec, "payload": meta}
            for meta, vec in zip(points_meta, vectors, strict=False)
        ]

        if self.qdrant_client is not None:
            self.qdrant_client.upsert_points(name=self.collection_name, points=points)

        for cache_key, json_str in cache_entries:
            self._cache_symbol_in_valkey(cache_key, json_str)

        return len(points)

    def index_doc_chunks(self, chunks: list[DocChunk], package_name: str) -> int:
        """Embed and upsert documentation chunks into devops_libraries collection."""
        if not chunks or self.qdrant_client is None:
            return 0
        self.ensure_collection_exists()

        texts = [f"{c.title}\n\n{c.content}" for c in chunks]
        vectors = self._embed_many_texts(texts)
        points = [
            {
                "id": f"{package_name}:{chunk.chunk_id}",
                "vector": vec,
                "payload": {
                    "symbol_name": chunk.title,
                    "package_name": package_name,
                    "version": "",
                    "kind": "doc_chunk",
                    "signature_text": chunk.title,
                    "docstring": chunk.content,
                    "headings": chunk.headings,
                    "source": chunk.source,
                },
            }
            for chunk, vec in zip(chunks, vectors, strict=False)
        ]
        self.qdrant_client.upsert_points(name=self.collection_name, points=points)
        return len(points)

    def _lookup_local_fallback(
        self, symbol: str, package: str | None = None
    ) -> FunctionSignature | ClassSignature | None:
        """Look up symbol in local JSON contracts directory."""
        if not self.local_contracts_dir or not self.local_contracts_dir.exists():
            return None

        candidate_files = (
            [self.local_contracts_dir / f"{package}.json"]
            if package
            else list(self.local_contracts_dir.glob("*.json"))
        )

        for filepath in candidate_files:
            if not filepath.is_file():
                continue
            try:
                contract = LibraryContract.model_validate_json(filepath.read_text(encoding="utf-8"))
                match = _search_contract_modules(contract, symbol)
                if match is not None:
                    json_str = match.model_dump_json()
                    self._cache_symbol_in_valkey(
                        f"symbol:{contract.package_name}:{symbol}", json_str
                    )
                    self._cache_symbol_in_valkey(f"symbol:{symbol}", json_str)
                    return match
            except Exception as exc:
                logger.debug("Failed parsing contract file %s: %s", filepath, exc)
        return None

    def lookup_symbol(
        self, symbol: str, package: str | None = None
    ) -> FunctionSignature | ClassSignature | None:
        """Retrieve symbol signature from Valkey L1 cache, falling back to local contracts."""
        if self.valkey_client is not None:
            try:
                raw = None
                if package:
                    raw = self.valkey_client.get(f"symbol:{package}:{symbol}")
                if raw is None:
                    raw = self.valkey_client.get(f"symbol:{symbol}")
                if raw is None:
                    raw = self.valkey_client.get(symbol)
                if raw:
                    parsed = _parse_cached_symbol(raw)
                    if parsed is not None:
                        return parsed
            except Exception as exc:
                logger.debug("Valkey lookup failed for '%s': %s", symbol, exc)

        return self._lookup_local_fallback(symbol, package=package)

    def search(
        self, query: str, package: str | None = None, top_k: int = 5
    ) -> list[LibrarySearchResult]:
        """Perform semantic similarity search over library symbols and documentation."""
        if self.qdrant_client is None:
            return []

        query_vec = self._embed_single_text(query)
        filter_payload = {"package_name": package} if package else None

        hits = self.qdrant_client.search_points(
            name=self.collection_name,
            query_vector=query_vec,
            limit=top_k,
            filter_payload=filter_payload,
        )

        results: list[LibrarySearchResult] = []
        for hit in hits:
            score = getattr(hit, "score", None)
            if score is None and isinstance(hit, dict):
                score = hit.get("score", 0.0)
            payload = getattr(hit, "payload", None)
            if payload is None and isinstance(hit, dict):
                payload = hit.get("payload", {})
            payload = payload or {}

            results.append(
                LibrarySearchResult(
                    symbol_name=payload.get("symbol_name", ""),
                    package_name=payload.get("package_name", ""),
                    version=payload.get("version", ""),
                    kind=payload.get("kind", "function"),
                    signature_text=payload.get("signature_text", ""),
                    docstring=payload.get("docstring"),
                    score=float(score or 0.0),
                    source=payload.get("source", "library_contract"),
                )
            )
        return results
