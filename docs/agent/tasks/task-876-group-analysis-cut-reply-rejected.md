# Task: Group-Analysis Reply Cut at Token Cap Is Rejected, Not Shown (#876)

**Issue**: [#876](https://github.com/dan-petty/devops-cli/issues/876)
**Scope**: scope/review
**Feasibility**: Verified against `_execute_single_group_job` in `src/devops_cli/review/analysis.py`, `LLMResponse.finish_reason`, and offline fake client unit tests in `tests/test_review_group_analysis.py`.

## Description

When an LLM response is truncated at its token ceiling (`finish_reason == CONST_FINISH_REASON_LENGTH`), json-repair fallback could previously parse the partial response into an incomplete `GroupAnalysisOutput`, passing G10 checks and surfacing a truncated explanation in review reports. Group analysis explanation is all-or-nothing and should not be retried with the same prompt (which would hit the same cap). This task ensures that any group-analysis model reply whose provider reports `length` is rejected immediately prior to parsing, marked with reason `reply-truncated`, not retried, tracked in `AnalysisReport.rejections`, and rendered in markdown with its rejection notice rather than partial explanation text.

## Acceptance Criteria

- [x] A group-analysis reply whose provider reports `length` is never parsed or shown. Its record is `rejected` with `reply-truncated`, and `analysis.json`'s `rejections` counts it.
- [x] A cut reply is not retried, so the client receives one call per group.
- [x] A reply with any other finish reason (e.g. `stop`) is handled and verified as normal.
- Pending a person: The first branch review after the change records on the issue how many groups were rejected as `reply-truncated`, with the report stage's `finish_reasons` from `profile.json`.
- [x] Tests run offline with a fake client returning `LLMResponse`: no network, no model; each test runs under 1 s.
- [x] `changelog.d/876.md` records the change; `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes.

## Deliverables

- [x] Declared constants `CONST_ANALYSIS_REJECTION_REPLY_TRUNCATED`, `CONST_ANALYSIS_REJECTION_SCHEMA_VALIDATION_FAILED`, and `CONST_ANALYSIS_REJECTION_MODEL_CALL_ERROR` in `src/devops_cli/config/constants.py`.
- [x] Checked `finish_reason == CONST_FINISH_REASON_LENGTH` on `LLMResponse` before parsing in `_execute_single_group_job` (`src/devops_cli/review/analysis.py`).
- [x] Introduced helper `_rejected_group_record` to maintain cyclomatic complexity $M \le 4$ and indentation depth $\le 2$.
- [x] Added unit tests in `tests/test_review_group_analysis.py` covering truncated responses, normal control responses, markdown rendering, and multi-group isolation with offline fake client.
- [x] Added changelog fragment `changelog.d/876.md` under `### Fixed`.
