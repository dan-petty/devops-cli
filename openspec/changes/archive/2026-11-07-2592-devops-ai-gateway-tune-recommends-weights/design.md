# Design

## Decisions

- **Delete the recommendation, do not mark it informational.** The gateway routes with `least-busy` and reads no weight, so a weight is not a setting that the reader can apply. The measurements (engine, GPUs, capacity, cost, capabilities) stay.
- **Keep `current_weight` of `DeploymentTune`.** It is the `weight` that the gateway lists for a deployment, not a recommendation. The run record keeps it as `setup.pool[].weight`, and `test_a_gateway_tune_is_kept_with_its_pool` pins that. The table does not show it.
- **Keep `ai.gateway_concurrency`.** The RAG embedder and indexer read it (`rag/embeddings.py:1158`, `rag/indexer.py:421`). The tune command stops reading it.
- **Delete `ai.gateway_weights`.** Only `tune_cmd` read it. `AIConfig` has `extra="forbid"`, so a config file that still holds it fails to load with the error of a refused key. That error names the unset command. This is the pre-1.0 way: no shim.
- **Use `ai.gateway_concurrency` as the example of a mapping setting in the config tests and specs.** It has the same type, `dict[str, int]`, as `ai.gateway_weights` had. This keeps the tests that cover dotted keys in a mapping.
- **Delete the five constants with their last reader.** Group 3 does it after group 2 removes the readers.

## Rejected alternatives

- **Keep the columns and mark them informational.** The reader can not apply the value, and the footer would still imply an action. Evidence: `k8s/llm/gateway/config.yaml:216` and the LiteLLM routing page.
- **Delete `ai.gateway_concurrency` as well.** Rejected: `git grep -n gateway_concurrency -- src` shows two live readers in `src/devops_cli/ai/rag/`. A deletion would change the embedding batch size.
- **Keep the weight functions for the `embedding` group, which uses `simple-shuffle`.** Rejected: the tune sweep posts to `/chat/completions` (`gateway_bench.py:51`), so it can not measure an embedding group.
- **Add `ai.gateway_weights` to `CONST_REMOVED_CONFIG_KEYS`.** Rejected: the table names a release, and a release does not exist yet. The error works without one.
