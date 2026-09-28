# Task 437: Lossless Structured Error Reflection for Schema Retries

**Issue**: [#437](https://github.com/dan-petty/devops-cli/issues/437)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Enhances Pydantic schema validation error feedback by preserving up to 5 field paths with type violations and prescriptive fix hints, enabling single-turn model self-correction.

#### Key Deliverables:
- [x] **Constants Centralization**: Declared `CONST_MAX_SCHEMA_REFLECTION_ERRORS = 5`, `CONST_MAX_INPUT_VALUE_REPR_LENGTH = 60`, and `CONST_SCHEMA_FIX_HINT_TEMPLATES` in `src/devops_cli/config/constants.py` and re-exported in `src/devops_cli/config/__init__.py`.
- [x] **Lossless Schema Reflection Engine**: Implemented `src/devops_cli/ai/schema_reflection.py` with typed models `SchemaViolation` and `SchemaReflectionReport`, dot-and-bracket path formatting `format_field_path(loc)`, table-driven fix hint synthesis `synthesize_fix_hint(error_dict)`, `extract_schema_reflection(exc, max_errors=5)`, and `build_schema_reflection_message(error_source, max_errors=5)`.
- [x] **Structured Client Reflection Integration**: Updated `src/devops_cli/ai/client/structured.py` with `format_schema_validation_error` and `_build_reflection_message`, bounding single-error summary length $\le 256$ chars while providing prescriptive multi-field fix hints in retry prompts.
- [x] **Universal Response Repair Enrichment**: Extended `FormattedLLMResponse` in `src/devops_cli/ai/response_repair.py` with `validation_error: str | None` and `schema_reflection: Any | None`. Decomposed parsing pipelines into pure helpers (`_try_model_validate`, `_try_python_validate`, `_try_json_validate`, `_parse_schema_model`, `_build_extracted_tool_calls`, `_resolve_schema_parsed_model`), dropping complexity to $M \le 4$.
- [x] **Agent Schema Validation Retries**: Added `_handle_schema_validation_retry` in `src/devops_cli/ai/agents/runner.py` and wired into `Agent.run` in `src/devops_cli/ai/agents/agent.py` to trigger structured reflection retry turns when schema validation fails.
- [x] **Unit & Integration Test Coverage**: Added comprehensive test suite `tests/test_schema_reflection.py` with structural tuple equality assertions covering path formatting, fix hint synthesis, error extraction, bounded truncation, prompt formatting, and repair integration.
- [x] **Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$**.
- [x] **100% passing across Gated CI validation suite (`uv run devops ci`)**.

---

## 2. Verification Results

- `uv run pytest tests/test_schema_reflection.py -v`: 10 passed in 21.98s
- `uv run pytest tests/test_ai_client_structured.py tests/test_pydantic_agent.py -v`: 45 passed in 25.80s
- `uv run pytest tests/test_architectural_invariants.py -v`: 13 passed in 29.95s
- `uv run devops scan complexity src/devops_cli/ai/schema_reflection.py`: Compliant ($M \le 10$, depth $\le 5$)
- `uv run devops scan complexity tests/test_schema_reflection.py`: Compliant ($M \le 10$, depth $\le 5$)
- `uv run devops scan complexity src/devops_cli/ai/client/structured.py`: Compliant ($M \le 10$, depth $\le 5$)
- `uv run devops ci`: All Gated CI Quality Gates passing
