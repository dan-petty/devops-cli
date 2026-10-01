# Task: Keep a Reply's Structured Output When Its Prose Contains Brackets (#786)

**Issue**: [#786](https://github.com/dan-petty/devops-cli/issues/786)
**Status**: Done
**Milestone**: v0.2.24
**Priority**: priority/p0-critical
**Scope**: scope/ai

## Description
95ed4cc (#675) made `repair_json_string` parse the whole reply first and accept any non-empty list that parse returned. json-repair reads bracketed prose, such as `[OWASP A03](https://…)`, `items[0]` or `request.args["id"]`, as list items beside the answer, so such a reply came back as a list like `[["OWASP A03"], {"findings": [...]}]`. `parse_review_response` returned None for it, so every finding of that persona was lost. The agent loop parses each structured reply the same way and saw a schema failure.

json-repair's own parser also drops a string's trailing newline, so a fenced `write_file` call lost its content's final newline when its strings held raw newlines or bracketed prose came before it.

A lone fenced block that holds an object or a list of objects is now the answer. It is decoded with the standard JSON decoder from its opening fence, so a fence on a line of its own inside one of its strings cannot cut it short. Otherwise the whole reply is repaired as before, and a list of the values json-repair read from bracketed prose yields its one object or list of objects. A fence opens at the start of a line and closes on a line of its own.

## Acceptance Criteria
- [x] Each row of the issue's table yields its three findings through `parse_review_response` and through `fix_llm_response(..., schema=ReviewResult)`.
- [x] A `fix` holding a fenced python block keeps every finding and the whole fix, with escaped or raw newlines, with or without a link before the block.
- [x] A json block followed by a python example block parses the json block.
- [x] Bare objects, bare lists of findings, and truncated or single-quoted replies still parse.
- [x] A fenced `write_file` call whose content holds a fence arrives whole, final newline included.
- [x] A reply that an unclosed `[` in its prose turns into fragments yields its finding or None, not an empty review.
- [x] 16 of the 30 new test cases fail on 07a52ef; the rest pin behaviour that was already right.

## Deliverables
- [x] `src/devops_cli/ai/response_repair.py`
- [x] `tests/test_ai_fixer.py`
