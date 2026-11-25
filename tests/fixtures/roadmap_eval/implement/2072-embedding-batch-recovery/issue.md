## Friction

The embedding batch size of the direct Ollama path has one-way and wrong transitions. `_embed_ollama` (`src/devops_cli/ai/rag/embeddings.py`) fixes `chunk_batch_size` once per call, and every slow batch in that call halves the size again, although none was sent at the reduced size. The increase fires on any batch at or under 2.0 s, with no cooldown and no margin below the threshold. #430 also left a backward-compatible alias, `_halve_batch_size`, which the project's no-shim rule forbids.

## Evidence

Checked on main on 2026-10-24: `_halve_batch_size` (`embeddings.py:531`), `_record_batch_latency` (`:535`) and the per-call `chunk_batch_size` in `_embed_ollama` (`:951-960`) are all present. This is PR1 of tracking issue #596.

## Proposed remedy

- Pass the size that each batch was sent at into `_record_batch_latency` and the timeout path, and skip a decrease when the sent size is larger than the current one.
- Add a cooldown and a margin below the threshold before any increase.
- Delete `_halve_batch_size` and migrate its tests.
- Test it through `_embed_ollama` with the shared HTTP fake and two workers.


Source: https://github.com/dan-petty/devops-cli/issues/596
