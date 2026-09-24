# Task 128: Streaming Reasoning Think Token Parser & Bounded Stream Sanitizer

**Issue**: [#128](https://github.com/dan-petty/devops-cli/issues/128)
**Status**: Done
**Milestone**: `v0.2.19`
**Priority**: `priority/p2-medium`
**Scope**: `scope/ai`

---

## 1. Description & Objectives

Frontier reasoning models and local thinking models (such as DeepSeek-R1, QwQ, Gemma) emit `<think>...</think>` tokens in streaming SSE responses. Currently, thinking blocks can leak into raw review comments or markdown reports if not cleanly separated from final response payloads. Additionally, unbounded SSE streams can cause memory exhaustion without strict `MAX_STREAM_BYTES` (50MB) guards.

Objectives:
1. **Standardized Streaming Token Processor**: Implement a robust streaming token processor / sanitizer in `devops_cli.ai.client.streaming` that cleanly extracts reasoning tokens into a structured reasoning scratchpad buffer while streaming sanitized markdown to callers.
2. **Multi-Provider Thinking Tag Extraction**: Support clean thinking extraction across Ollama (including inline `<think>` tags and discrete `message.thinking` fields), Anthropic (SSE `thinking_delta`), and OpenAI-compatible endpoints (`reasoning_content`, `reasoning`, and inline `<think>` blocks).
3. **Bounded Stream Guard & Transport Safety**: Enforce strict `MAX_STREAM_BYTES` (50MB) boundary guards counting raw line payload sizes before extraction and resilient SSE line reading with bounded error truncation ($\le 256$ chars).
4. **Zero Leakage Invariant**: Guarantee that downstream review reports, PR comments, and markdown artifacts receive strictly clean text without raw `<think>` tokens.
5. **Comprehensive Testing**: Authored unit tests in `tests/test_ai_streaming.py` with $\ge 90\%$ code coverage, $M \le 10$, and nesting depth $< 6$.

---

## 2. Key Deliverables

- `src/devops_cli/ai/client/streaming.py`: Standardized `StreamingTokenProcessor`, `StreamingReasoningSanitizer`, bounded stream iterator with raw-line size guards and error truncation, and normalized provider chunk extraction.
- `src/devops_cli/ai/client/__init__.py`: Export standardized streaming processor and utilities.
- `src/devops_cli/ai/client/unified.py`: Integrated streaming reasoning processor into `chat_messages_stream` and `chat_stream`.
- `src/devops_cli/ai/thinking_stream.py`: Harmonized `ThinkingStreamProcessor` with updated extractor capabilities.
- `tests/test_ai_streaming.py`: Unit test suite covering multi-provider streams (Ollama, Claude, OpenAI), split token boundaries, scratchpad accumulation, dynamic byte truncation, and transport error bounds.

---

## 3. Verification & Invariant Results

- **Unit Test Suite**: `uv run pytest tests/test_ai_streaming.py` passes 36/36 tests covering multi-provider streams (Ollama, Claude, OpenAI), split token boundaries, scratchpad accumulation, dynamic byte truncation, and transport error bounds.
- **Architectural Invariants**: `uv run pytest tests/test_architectural_invariants.py` passes 8/8 tests.
- **Documentation Integrity**: `uv run pytest tests/test_docs.py` passes 21/21 tests.
- **Complexity Analysis**: `uv run devops scan complexity tests/test_ai_streaming.py` and `src/devops_cli/ai/client/streaming.py` confirm 100% compliance with $M \le 10$ and depth $\le 5$ ceilings.
