# Task 154: Remediate DevSecOps Review Findings & Enhance Self-Improvement Loop

**Issue**: [#154](https://github.com/dan-petty/devops-cli/issues/154)
**PR**: [#155](https://github.com/dan-petty/devops-cli/pull/155)
**Status**: In Review
**Milestone**: `v0.2.16`
**Priority**: `priority/p1-high`
**Scope**: `scope/ai`

---

## 1. Description & Objectives

Address verified security and reliability findings identified in review session `20260911-060650` (`findings.json` / `review.md`). Strengthen argument injection, Rich markup injection, telemetry credential leakage, and memory boundary defenses. Update review prompts, falsification rules, the common hallucinations catalog, and documentation to improve the feedback, review, and self-improvement loop.

---

## 2. Planned Changes

1. **Security & Injection Defenses**:
   - `src/devops_cli/ai/agents/capabilities.py`: Exclude `authorization_token` from serialized model settings (CWE-200).
   - `src/devops_cli/k8s/chaos.py`: Validate `namespace` and `target_deployment` against DNS label regex before executing `kubectl` (CWE-88).
   - `src/devops_cli/k8s/logql.py`: Validate `pod` and `ns` against Kubernetes resource name regex (CWE-88).
2. **Output Formatting & Rich Markup Injection (CWE-74)**:
   - `src/devops_cli/output/console.py`: Escape user content in `print()`.
   - `src/devops_cli/output/formatters/panels.py`: Escape finding descriptions, fixes, and ArgoCD status fields.
   - `src/devops_cli/output/formatters/scalars.py`: Escape user text and URLs in `format_link()`.
   - `src/devops_cli/output/table_builder.py`: Escape table title, columns, empty messages, and cell values.
3. **Telemetry & Endpoint Hardening**:
   - `src/devops_cli/server/app.py`: Strip query strings from `url.full` telemetry attributes (CWE-200).
   - `src/devops_cli/server/routes/status.py`: Mask tool paths to `[bin]/<tool>` (CWE-200).
   - `src/devops_cli/server/routes/stream.py`: Enforce maximum WebSocket message size (1MB) (CWE-400).
4. **Memory Bounds & Error Sanitization**:
   - `src/devops_cli/ai/cache/valkey_cache.py`: Batch keys in `flush_ai_cache` to prevent memory spikes (CWE-400).
   - `src/devops_cli/pipeline/pipeline.py`: Sanitize and truncate exception messages to $\le 256$ chars (CWE-209).
   - `src/devops_cli/security/vulnerability_lookup.py`: Cap `OSVClient._cache` to 1000 items with LRU eviction (CWE-400).
   - `src/devops_cli/telemetry/metrics.py`: Cap metric names and label combinations in `InMemoryMetricsRegistry` (CWE-400).
   - `src/devops_cli/ai/review/exporter.py`: Stream `FeedbackRecord` items directly to file in `export_invalidated_feedback` (CWE-400).
5. **Test Fixtures & Assertions**:
   - `tests/test_runtime_security_and_ssrf_hardening.py`: Resolve contradictory assertion in secret sanitizer test.
   - `tests/test_embedding_config_retention.py`: Replace RFC 1918 IP with RFC 5737 TEST-NET address.
   - `tests/test_k8s.py`: Replace RFC 1918 IP with RFC 5737 TEST-NET address.
6. **Prompts, Common Hallucinations & Self-Improvement Loop**:
   - `src/devops_cli/ai/tasks/verify_finding_system.md`: Add falsification rule invalidating false CWE-400 claims on bounded local operations.
   - `src/devops_cli/ai/tasks/review.md` & `src/devops_cli/ai/tasks/review_output_instruction.md`: Clarify review guidelines regarding local files vs unbounded network streams.
   - `src/devops_cli/ai/personas/devsecops/prompt.md`: Refine resource exhaustion criteria to focus on remote untrusted payloads and $O(N^2)$ loops.
   - `src/devops_cli/ai/review/common_hallucinations.json` & `common_hallucinations.py`: Register `HALLUCINATION-LOCAL-FILE-OR-COLLECTION-CWE400`.
   - `docs/commands/review.md`: Document closed-loop feedback and self-improvement mechanism.
7. **Embedding Configuration Consolidation & User Config Protection**:
   - `config.yaml` & `config.example.yaml`: Consolidate all embedding configuration under `ai.tasks.embedding` (`model`, `ollama_urls`), removing duplicate keys under `ai.rag`.
   - `src/devops_cli/config/settings.py`: Clean `AIRAGConfig` to focus strictly on RAG parameters (chunk size, overlap, score threshold, top_k); add `timeout` to `AITaskOverride` and default `embedding` task model.
   - `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/ai/agents/embeddings.py`, `src/devops_cli/ai/benchmark/embedding_runner.py`: Resolve embedding model, endpoints, and timeouts through `tasks.embedding`.
   - `AGENTS.md`: Add explicit rule protecting user runtime `config.yaml` from being overwritten or forced to localhost.
8. **PR 155 Review Remediation & Documented Example Exclusions**:
   - `capabilities.py`: Preserved `authorization_token` in `NativeTool.get_model_settings` and `_build_mcp_tool_settings` for runtime provider authentication while keeping diagnostics redacted (Comment 1).
   - `stream.py`: Added raw UTF-8 byte measurement before decoding/parsing to enforce 1MB limit at WebSocket frame level, closing with code 1009 if exceeded (Comment 2).
   - `common_hallucinations.py`: Grounded CWE-400 guard in target source line operations (`read_text`, `open`) on local files while excluding unbounded streams (Comment 3).
   - `exporter.py`: Yielded `FeedbackRecord` items incrementally from `_extract_session_feedback_records` with 50MB file size check (Comment 4).
   - `chaos.py` & `logql.py`: Centralized Kubernetes RFC 1123 resource name validation in `core/validation.py` (Comments 5 & 6).
   - `console.py`: Added `safe: bool = False` to `print()` and print helpers, introduced `print_safe()`, and passed `safe=safe` to `render_table()` (Comment 7).
   - `pipeline.py`: Sliced to `_MAX_ERROR_LENGTH - 3` before appending `"..."` so length is strictly $\le 256$ (Comment 8).
   - `tflint.py`: Decomposed `_inspect_tf_file_fallback` with `_TfBlockContext` to track multiline HCL block context for `0.0.0.0/0` across `cidr_blocks`, `security_group`, and `ingress` (Comment 9).
   - `task.md` & `task-154`: Maintained `In Review` lifecycle status for open-PR work (Comments 10 & 11).
   - `dry_run/models.py`: Added recursive `_bound_detail_value` limiting strings to 1024, collections to 50 items, and depth to 3 levels (Comment 12).
   - `tables.py` & `table_builder.py`: Supported `safe: bool = False` in shared `render_table()` (Comment 13).
   - `conftest.py`: Removed `0.0.0.0` from `_is_loopback` and used `ipaddress.ip_address(host).is_loopback` (Comment 14).
   - `test_output.py`: Asserted that ANSI red escape sequences are absent when markup is escaped (Comment 15).
   - `reference_extractor.py`: Excluded documented example domains (RFC 2606, 6761), IPs (RFC 5737, 3849, 6890), and telephone numbers (ATIS-0300115, UK Ofcom) from threat intel lookups and network audits.
9. **Verification**:
   - Run submodule-aligned unit tests.
   - Run `uv run devops ci` to pass all 10 quality gates.
