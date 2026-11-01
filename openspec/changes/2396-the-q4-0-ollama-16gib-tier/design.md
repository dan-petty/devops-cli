# Design

## Decisions

- **Set `q8_0` on `ollama-16gib` and keep the value on the other eight tiers.** Ollama gives `OLLAMA_KV_CACHE_TYPE` to `llama-server` for every model on the tier, also for the embedding model. One value on all nine tiers means that every tier that the gateway sends embeddings to makes the same vectors. `q8_0` is the value of eight tiers, so only one tier changes. `f16` would change eight tiers and cost memory on all of them.
- **The requirement names `q8_0`, not "the same value".** The issue asks for `q8_0` on every tier. A requirement that says "the same value" would pass with a different value on all nine tiers, but it would also hide the memory that each tier is sized for. The requirement fixes the value; a later change of all tiers edits the requirement with it.
- **The requirement covers all nine tiers, not only the tiers that serve embeddings.** The gateway embedding groups can change. A tier that serves no embeddings today may serve them after a routing change, and a mix of values brings the defect back.
- **No new test.** The owner rule of 2026-11-01 is: tests are for new code functionality, and every other change has a command that verifies it. This change flips one value in a manifest. Task 1.4 gives the commands: a `git grep` that prints nothing, a count that must print 9, and the manifest tests that already exist. An earlier implement run wrote two new test files for this value, and the static check stopped it. No test file is in the scope of this change.
- **The header comment keeps the old measurement and marks it.** The 13 GB figure is a `q4_0` measurement (#2822). The text says so and gives the estimate for `q8_0` as an estimate. A reader then does not take the estimate for a measurement.

## Rejected alternatives

- **Remove `ollama-16gib-fast` from the embedding group of `k8s/llm/gateway/config.yaml`.** Rejected: the issue scopes the fix to the KV cache type, and the deployment is a valid order 2 fallback. Removing it also leaves the cause, which is a different cache type on one tier, in place for any other model.
- **Record the producing tier with each vector in Qdrant.** Rejected: the refined design of #2396 puts it out of scope. It is a separate item.
- **Keep `q4_0` on the 16 GiB tier to save memory and lower the context.** Rejected: the memory fits (see "Feasibility" in `proposal.md`: 15196 MiB of 16303 MiB in the worst case for the chat model alone), and a lower context would remove the 131072 window that #2822 raised and that the gateway config declares for `gpt-oss:20b`.
