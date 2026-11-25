# Design

## Decisions
- Classify `StructuredOutputValidationError` before `AIClientError` in `_ended` (because it subclasses `AIClientError`) using prefix `schema_refusal`, `gateway_429` for `AIClientError(status=429)`, `timeout` for `timed_out` or status 408/504, and `provider` for other `AIClientError` instances, each followed by `mask_secrets(str(exc))`.
- Keep the existing `Outcome` enum (`staged`, `refused`, `degenerate`, `over_budget`, `failed`) unchanged so existing score counters and downstream readers stay stable.
- Add `case_runs: tuple[CaseRun, ...] = ()` with default empty tuple on `StageScore` so existing `StageScore(...)` calls without `case_runs` keep working, while `score_runs` populates `tuple(runs)`.
- Apply `mask_secrets` both inside `_ended` and in `render_score` / `score_json` (`score_runs` / directly constructed `CaseRun`) so no unmasked secret reaches stdout or `.data/roadmap_eval/stage/*.json`.

## Rejected alternatives
- **Add an `Outcome.INFRA` enum member**: alters the closed 5-outcome taxonomy and every summary/counter consumer.
- **Mask only in `_ended` or only at render time**: risks unmasked reasons if a `CaseRun` is constructed outside `_ended`, or before storage.
