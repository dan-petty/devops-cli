# Design

## Decisions

- **One rule for each site.** A count of events becomes a counter. A duration or a size for each event becomes a histogram. A value that holds the state at one time, which the next value replaces, becomes a gauge. A name is deleted when it repeats a declared instrument, or when its value repeats each time the same data is read again.
- **Each text counts once.** `embed_texts` adds one lookup for each text that it gets: a hit from the memory cache, a hit from Valkey, or a miss. The counter adds a value only for a result that has texts, so a batch of 3 hits from memory and 2 misses sends the points `{result="hit", tier="memory"} 3` and `{result="miss"} 2`, one time each.
- **`result` and `tier` are two labels.** The issue asks for a counter by result (hit or miss). The Valkey hits had their own gauge, so a hit keeps its tier as a second label, and the hit share is `result="hit"` over all lookups.
- **The hit-share panel follows the response-cache panel.** It divides the hits of the last hour by the lookups of the last hour, and `or <lookups> * 0` shows 0 for an hour with lookups and no hits.
- **`emit()` is the one writer.** The client's `increment_counter`, `record_gauge` and `record_histogram` stay public, because `emit()` in another module calls them. The check finds every call of a metric method by its attribute name and allows only the calls in `emit()` and the calls on `GLOBAL_METRICS`, the Prometheus registry of the Service.
- **Only declared instruments are emitted.** The check reads each module that imports `emit` from `devops_cli.telemetry.instruments`, and refuses an `emit()` whose first argument is not a name that the module imports from there and that `INSTRUMENTS` holds.

## Call sites

Paths are under `src/devops_cli/`. The line numbers are those of `origin/main` at bb46660c.

| Site | Old name | Class | New instrument |
| :--- | :--- | :--- | :--- |
| `commands/telemetry.py:287` | `devops_cli.test_counter` | counter | `devops_cli_telemetry_tests_total` |
| `commands/sandbox.py:647` | `devops_cli.sandbox.metrics_invoked` | delete | Repeats the subcommand histogram of `devops sandbox metrics`. In a dry run the client sent nothing, so its `dry_run` label never left the process. |
| `commands/ci.py:557`, `:577`, `:947` | `ci.step_pass` | counter | `devops_cli_ci_checks_total`, by `step` and `outcome` (`pass` or `fail`) |
| `commands/ci.py:625` | `ci.gate_slot_wait_seconds` | histogram | `devops_cli_ci_gate_slot_wait_seconds` |
| `core/cli.py:28`, `:53`, `:71` | `devops_cli_subcommand_seconds` | histogram | `devops_cli_subcommand_duration_seconds`, by `command` and `status` |
| `sandbox/engine.py:605` | `devops_cli.sandbox.metrics_collected` | delete | One collection is one run of `devops sandbox metrics`, which the subcommand histogram counts. The health of the sandbox is in the report. |
| `sandbox/engine.py:670`, `:677` | `devops.sandbox.logs.lines`, `devops.sandbox.logs.panics` | delete | A second read of the same log counts the same lines and panics again, and the `instance_id` label has no bound. |
| `core/process.py:577`, `:729`, `:1128` | `devops_cli_subprocess_seconds` | histogram | `devops_cli_subprocess_duration_seconds`, by `bin` and `status` |
| `k8s/security_stream.py:207` | `devops_cli_k8s_security_alerts_total` | delete | The stream reads the last lines of the Falco log (`--tail`), so a second read counts the same alerts again. |
| `commands/ai.py:833` | `ai.prewarm.success` | counter | `devops_cli_ai_prewarms_total`, by `model`, `evict` and `outcome` (`ok` or `failed`) |
| `ai/gateway.py:503` | `ai.gateway.latency_ms` | histogram | `devops_cli_ai_gateway_probe_duration_seconds` |
| `ai/gateway.py:504` | `ai.gateway.healthy` | gauge | `devops_cli_ai_gateway_healthy` |
| `ai/gateway.py:541` | `ai.gateway.failover_events` | counter | `devops_cli_ai_gateway_failovers_total`, by `virtual_model` and `simulate` |
| `ai/capability.py:136`, `:151` | `ai.failover.capability_override`, `ai.failover.capability_rejection` | counter | `devops_cli_ai_capability_gate_total`, by `role`, `model` and `decision` (`override` or `rejection`) |
| `commands/test_cmd.py:525`, `:526`, `:532` | `test.profile_memory.invocations`, `.duration_seconds`, `.peak_kb` | delete | The run and its time repeat the subcommand histogram. The peak is in the report, and the `target` label is a path that a person types, with no bound. |
| `security/vulnerability_lookup.py:255`, `:313` | `devops_cli_vulnerability_lookups_total` | counter | `devops_cli_vulnerability_lookups_total`, by `source`, `status` and `batch` |
| `security/vulnerability_lookup.py:547`, `:557`, `:573`, `:584` | `devops_cli_threat_intel_lookups_total` | counter | `devops_cli_threat_intel_lookups_total`, by `source`, `status` and `cached` |
| `ai/client/structured.py:325`, `:335` | `ai.client.structured_success`, `ai.client.structured_validation_failure` | counter | `devops_cli_ai_structured_attempts_total`, by `model` and `outcome` (`valid` or `invalid`) |
| `ai/client/structured.py:261` | `ai.client.structured_retry_count` | delete | A retry follows each invalid attempt except the last, so the attempts counter gives it. |
| `ai/rag/embeddings.py:497`, `:531` | `rag.embedding.batch_size` | gauge | `devops_cli_rag_embedding_batch_size` |
| `ai/rag/embeddings.py:498`, `:532` | `rag.embedding.aimd_action` | counter | `devops_cli_rag_embedding_batch_resizes_total`, by `action` |
| `ai/rag/embeddings.py:617`, `:857`, `:858` | `devops_cli_embedding_valkey_hits_total`, `devops_cli_embedding_cache_hits_total`, `devops_cli_embedding_cache_misses_total` | counter | `devops_cli_embedding_cache_lookups_total`, by `result` and `tier` |
| `ai/rag/embeddings.py:859` | `devops_cli_embedding_cache_size` | gauge | `devops_cli_embedding_cache_size` |
| `ai/rag/drift.py:349` | `devops_cli_rag_drift_detected_total` | gauge | `devops_cli_rag_drift_detected`, by `project`. The value is 1 or 0 for the last check, a state, so the name loses `_total`. |
| `ai/rag/drift.py:354` | `devops_cli_rag_drift_score` | gauge | `devops_cli_rag_drift_score`, by `project` |
| `ai/rag/qdrant.py:542` | `qdrant.search_hits_count` | delete | The `db.response.returned_points` attribute of the search span holds it, and the investigations counter tells a retrieval that found context from one that did not. |
| `ai/client/unified.py:453` | `devops_cli_llm_inference_seconds` | histogram | `devops_cli_ai_chat_duration_seconds`, by `provider` and `model` |
| `ai/rag/indexer.py:985`, `:986` | `rag.indexed_files`, `rag.total_chunks` | delete | The root span of the index run holds both. `devops_cli_rag_points` holds the size of each collection. |
| `ai/rag/investigator.py:190` | `ai.rag.investigation.stopped` | counter | `devops_cli_rag_stops_total` |
| `ai/rag/investigator.py:384` | `ai.rag.investigation.duration_ms` | delete | Repeats `devops_cli_rag_query_duration_ms{stage="total"}`. |
| `ai/rag/investigator.py:386`, `:390` | `ai.rag.investigation.empty`, `ai.rag.investigation.hits` | counter | `devops_cli_rag_investigations_total`, by `outcome` (`found` or `empty`). The count of results stays on the span as `rag.results_count`. |

Totals: 24 sites become counters, 9 become histograms, 6 become gauges, and 13 are deleted. The three sites in `telemetry/tracer.py` are the definitions that this change deletes.

## Rejected alternatives

- **Keep `record_metric` as the private path of gauges.** The issue's first answer was to keep it for `emit()`. Since #1253, `emit()` calls the client's `record_gauge`, and nothing else calls the module function. The update of 2026-10-08 on the issue proposes to delete it, and this change does.
- **Declare every old name as it is.** Names such as `ci.step_pass` and `ai.gateway.latency_ms` break the rule that `CONTRIBUTING.md` sets for a metric (`devops_cli_<name>`, `_total` only on a counter), and several are counts that a gauge loses. No dashboard reads any of them, so a new name costs no reader.
- **Name the chat duration `gen_ai.client.operation.duration`.** The GenAI conventions define it, but the AI instruments of devops-cli (`devops_cli_ai_requests_total`, `devops_cli_ai_tokens_total`) use `devops_cli_` names, and the dashboard tests read only `devops_cli_` series. To move the AI metrics to the conventions is a change of its own.
- **Check the metric writes at run time.** A run-time check sees only the paths that a test runs. The AST check reads every module under `src/devops_cli/`.
- **Make the client's metric methods private.** `emit()` lives in another module, so it would call private methods across modules. The check by attribute name keeps the methods public and still finds every other caller.
