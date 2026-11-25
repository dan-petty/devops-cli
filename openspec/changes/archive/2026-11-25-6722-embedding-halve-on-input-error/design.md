# Design

## Decisions
- Add a keyword-only `can_subdivide: bool = False` flag to `EmbeddingsError.__init__` so the error producer preserves whether batch halving can isolate a per-text cause without changing `EmbeddingsError.status`, `is_transient`, or `details`.
- `_reply_vectors` sets `can_subdivide=True` when an HTTP 200 reply returns fewer or empty vectors. Other `EmbeddingsError` instances (such as HTTP 404, 401, 403, 5xx, or unknown `EmbeddingsError` raised with `status=None`) keep `can_subdivide=False`.
- `_try_query_candidate_nodes` sets `can_subdivide=True` on the combined `EmbeddingsError` when any failed node attempt hit a timeout (`httpx2.TimeoutException` or `TimeoutError`), `is_input_refused_error(exc)` (`400`, `413`, `422`), or `isinstance(exc, EmbeddingsError) and exc.can_subdivide`.
- `_embed_batch_with_subdivision` retries halves only when `is_input_refused_error(exc) or exc.can_subdivide`; checking `is_input_refused_error(exc)` directly also keeps callers or tests that raise `EmbeddingsError(..., status=400/413/422)` directly working.

## Rejected alternatives
- **Check only `EmbeddingsError.status in {400, 413, 422}`**: drops timeout halving (`ReadTimeout` has `status=None`, breaking `test_parallel_batches_that_time_out_on_an_ollama_node_halve_the_batch_size_once`) and malformed-reply halving (`status=None`).
- **Check `exc.is_transient`**: halves on `ConnectError` (`status=None`, `is_transient=True`) and HTTP 5xx (`status >= 500`, `is_transient=True`), repeating node-wide failures 2n-1 times.
- **Inspect English message substrings for vector mismatches**: couples flow control to error prose strings instead of explicit producer metadata.
