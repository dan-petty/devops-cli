# Task: Brackets in a Reply's Prose Cost It Its Structured Output (#786)

**Issue**: [#786](https://github.com/dan-petty/devops-cli/issues/786)
**Status**: Done
**Milestone**: v0.2.24
**Priority**: priority/p0-critical
**Scope**: scope/ai

## Description
95ed4cc (#675), the #656 fix, made `repair_json_string` parse a whole reply before its fenced blocks. json-repair turns bracketed prose into list items, so a reply citing `[OWASP A03](…)` or `items[0]` before its ```json block, or `request.args["id"]` after it, came back as a list such as `[["OWASP A03"], {"findings": [...]}]`. `parse_review_response` could not read it, and every finding in the reply was dropped. The agent loop takes the same path for every structured output.

## Acceptance Criteria
- [x] Fenced blocks are tried before the whole reply again. Each block's value is decoded with `json.JSONDecoder.raw_decode`, which reads string values whole, so a fence nested in a string value never ends the block (the #656 case).
- [x] Only a block that needs repair is cut, at a closing line that holds nothing but the backticks; a ```python line no longer closes it.
- [x] Repairing the whole reply remains the last resort, for unfenced or malformed replies.
- [x] Tests cover each row of the issue's table through `parse_review_response`, nested fences inside a string value, a json block followed by a python example block, a fenced `write_file` tool call, a malformed block between bracketed prose, and a bare JSON reply.

## Deliverables
- [x] `src/devops_cli/ai/response_repair.py`
- [x] `tests/test_response_repair_fences.py`
- [x] `CHANGELOG.md`
- [x] `docs/ROADMAP.md`

## Verification
- `tests/test_response_repair_fences.py`: 7 of its 9 tests failed before the fix; all pass after it, together with the #656 regressions in `tests/test_batch_2_review_defects.py`.
- The 26 test files that touch response repair, tool-call extraction, review parsing or agents: 531 passed.
