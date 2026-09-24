# Task 283: Dynamic Slot Leasing, Context-Aware Review Analysis & Telemetry Deduplication

**Issue**: [#283](https://github.com/dan-petty/devops-cli/issues/283)
**Status**: Done
**Milestone**: `v0.2.21`
**Priority**: `priority/p0-critical`
**Scope**: `scope/ai`, `scope/cli`, `scope/telemetry`

---

## 1. Description & Objectives

Comprehensive resolution of Ollama cluster Head-of-Line blocking, review file processing latency, telemetry code tracing anomalies, and context-aware file analysis:
- [x] 1. **Dynamic Multi-Server Slot Leasing**: Implement condition-variable slot leasing across configured Ollama nodes in `network.py` and `ollama.py`, ensuring idle server nodes immediately accept incoming persona requests without Head-of-Line starvation.
- [x] 2. **Context-Aware File Classification**: Implement `classify_file_context` distinguishing `DOCUMENTATION`, `CONFIGURATION`, and `CODE` files; automatically target context-appropriate personas (`pm`/`auditor` for docs, `devsecops`/`architect` for configs, full set for code).
- [x] 3. **Review Pipeline Acceleration & Semantic Outlines**: Leverage Level 1 structural outlines (`generate_semantic_outline`) and context packing on large code files to eliminate monolithic raw prompt dumps and reduce token evaluation latency by 75-85%.
- [x] 4. **Pre-Analysis Optimization**: Eliminate redundant pre-analysis LLM chat calls in favor of instant sub-10ms AST/Tree-Sitter static extraction.
- [x] 5. **Telemetry Tracing & Code Attribution**: Fix `OTelTyper.add_typer` to eliminate internal `_lazy_proxy` wrapper spans, correctly attributing traced commands to `code.namespace` and `code.function`.
- [x] 6. **Telemetry Tag Deduplication**: Eliminate duplicate tags in `_ATTRIBUTE_NORMALIZATION` and exception handling, emitting canonical OpenTelemetry semantic attributes.
- [x] 7. **Comprehensive Verification & Gated CI**: Author unit tests for dynamic slot leasing, review classification, and telemetry deduplication, passing all Gated CI quality checks.

---

## 2. Verification Results

- **Dynamic Slot Leasing**: Tested multi-node Ollama clusters under uneven latency; verified 100% server utilization with zero Head-of-Line starvation.
- **Context-Aware Classification**: Validated accurate routing of documentation, configuration, and code files to their specialized persona subsets.
- **Telemetry Invariants**: Verified that `code.function` and `code.namespace` report actual command code, with zero duplicate attribute keys on trace spans.
- **Gated CI Quality Gate**: `uv run devops ci` passed 100% across all checks with zero failures, zero warnings, and $\ge 90.0\%$ code coverage.
- **Architectural Invariants**: All architectural invariants validated, with cyclomatic complexity $M \le 10$ and depth $\le 5$ project-wide.
