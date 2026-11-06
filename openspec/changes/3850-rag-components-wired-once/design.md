# Design

## Context

See proposal.md for the motivation and the scope (#3850, item 1 of #1329).

## Decisions

### 1. One function in `ai/rag/indexer.py`

- **Decision**: `resolve_rag_components(settings=None) -> RagComponents` sits next to `resolve_qdrant_client`, which already resolves the client from the settings. `RagComponents` is a `NamedTuple`, so a command unpacks it as before.
- **Alternative considered**: a new module `ai/rag/components.py`.
  - *Rejected*: `indexer.py` already owns the client resolution and the collection defaults. A module of one function adds an import and no clarity.
- **Alternative considered**: let each caller keep its code and share only the collection-name rule.
  - *Rejected*: the investigator skipped the Qdrant and embedder seams because it built the classes. Only one function that every caller uses keeps all callers on the seams.

### 2. The function reads the settings it is given

- **Decision**: `resolve_qdrant_client` takes `settings`, and `resolve_rag_components` passes its own. The investigator holds settings that a caller may pass in (`investigate_rag_context(settings=...)`), and the client must use them.
- **Alternative considered**: load the settings again inside the function.
  - *Rejected*: the investigator would then build a client from other settings than the ones it checked for `qdrant.url`.

### 3. A missing address is an error, not a printed message

- **Decision**: `resolve_qdrant_client` already raises `ConfigurationError` with the message. The commands let it pass to the one error report of the CLI. The investigator checks `qdrant.url` itself and skips the investigation silently, as before.
- **Alternative considered**: keep a `print_error` and `typer.Exit(1)` in a command helper.
  - *Rejected*: it is a second error path for the same failure, and the helper is the code this change removes.

### 4. The library store builder stays in `ai/rag/library_store.py`

- **Decision**: `build_library_vector_store` is next to `LibraryVectorStore`. It degrades to the local contracts when Qdrant is not configured or does not answer, and it catches `DevOpsCLIError` only. The old helper caught `Exception`.
- **Alternative considered**: keep `except Exception`.
  - *Rejected*: it swallows a programming error. Every failure that configuration or the network can cause is a `DevOpsCLIError`.
