# Proposal: #6324

## Why
`devops roadmap eval stage` keeps each case's ending reason in `CaseRun.reason`, but `render_score` and `score_json` drop `case_runs` from text, `--json`, and stored reports under `.data/roadmap_eval/stage/`. In addition, `_ended` records only `type(exc).__name__` for non-tool failures, hiding whether a case failed due to gateway rate limiting (429), timeout, provider error, or structured output validation refusal.

## What Changes
- Classify failed exceptions in `_ended` (`src/devops_cli/roadmap/stage/stage_eval_run.py`) into `schema_refusal`, `gateway_429`, `timeout`, or `provider` with the masked exception message (falling back to masked message / exception type for other errors).
- Record `case_runs` on `StageScore` in `src/devops_cli/roadmap/stage/stage_eval_score.py`.
- Include per-case `outcome` and `mask_secrets(reason)` in `render_score` and `score_json` (`case_runs`) in `src/devops_cli/roadmap/stage/stage_eval_render.py` and message templates in `src/devops_cli/lang/en/messages.py`.
- Update `docs/ROADMAP_WORKFLOW.md` if needed and update/add unit and CLI tests in `tests/roadmap/stage/test_roadmap_stage_eval_run.py` and `tests/roadmap/stage/test_roadmap_stage_eval_command.py`.

## Capabilities
- `roadmap-stage-eval`: Include each live case's outcome and masked failure/end reason in text, `--json`, and stored reports without changing `Outcome` members.

## Impact
- Makes failed live stage eval runs directly diagnosable without guessing whether a failure was infrastructure (429/timeout/provider) or model schema refusal, while never leaking unmasked secrets into stored reports.

## Feasibility
- Confirmed on `origin/main` (`4046839ec`): `stage_eval_run._ended` (`lines 150-159`) returns bare `type(exc).__name__`, `StageScore` (`stage_eval_score.py:53-64`) omits `case_runs`, and `render_score`/`score_json` (`stage_eval_render.py:100-162`) omit per-case outcomes and reasons. `AIClientError` already exposes `.status` and `.timed_out`, and `StructuredOutputValidationError` subclasses it.

## Existing Tool Considered
No external library formats this repository's internal `StageScore` reports or failure taxonomy (alternatives check verdict `none`). Reuses `mask_secrets` and existing `AIClientError` attributes; ~80 lines across 4 modules.
