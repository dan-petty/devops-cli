# Task 875: One JSON Repair Seam Counting Repairs Per Entry Point

**Issue**: [#875](https://github.com/dan-petty/devops-cli/issues/875)
**Status**: Done
**Feasibility**: Verified against `src/devops_cli/ai/response_repair.py`, `src/devops_cli/core/serialization.py`, `src/devops_cli/ai/client/structured.py`, and `src/devops_cli/telemetry/instruments.py` that routing all three JSON repair entry points (`repair_json_string`, `extract_json_block`, and `_parse_json_payload`) through `repair_json(text, *, source)` eliminates ad-hoc `{...}`/`[...]` slicing in `extract_json_block`, preserves top-level lists on unclosed markdown fences, and counts repairs via `devops_cli_ai_json_repairs_total` labeled by `source`.

## Deliverables

- [x] Implement `repair_json(text, *, source, max_length=None)` in `src/devops_cli/ai/response_repair.py` that attempts strict `json.loads` first, falls back to fenced block decoding and `json_repair.loads`, and emits `AI_JSON_REPAIRS_TOTAL` (`devops_cli_ai_json_repairs_total`) with `{"source": source}` whenever `json-repair` repairs a payload.
- [x] Route `repair_json_string`, `extract_json_block` (`src/devops_cli/core/serialization.py`), and `_parse_json_payload` (`src/devops_cli/ai/client/structured.py`) through `repair_json` using constants `CONST_JSON_REPAIR_SOURCE_REPAIR_JSON_STRING`, `CONST_JSON_REPAIR_SOURCE_EXTRACT_JSON_BLOCK`, and `CONST_JSON_REPAIR_SOURCE_CHAT_STRUCTURED` in `src/devops_cli/config/constants.py`, replacing `CONST_METRIC_AI_STRUCTURED_REPAIR_SUCCESS` and leaving `src/devops_cli/ai/response_repair.py` as the sole module importing `json_repair`.
- [x] Remove `{...}`-then-`[...]` substring slicing from `extract_json_block` so replies with unclosed ` ```json ` fences holding a one-item list of objects return the list rather than the inner dictionary.
- [x] Add unit tests in `tests/test_consolidation_serialization.py` verifying the unclosed-fence one-item list fixture, bracketed-prose replies, and per-entry-point `devops_cli_ai_json_repairs_total` counts.
- Pending a person: Replaying the 69 verifier cache entries of S5 to S8 with the new parser changes the parsed shape of `llm_82417aa8…` only.
