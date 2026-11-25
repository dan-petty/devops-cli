## ADDED Requirements

### Requirement: Failed case keeps masked reason class and message
`stage_eval_run._ended` SHALL keep the masked error message in `CaseRun.reason`, classifying `StructuredOutputValidationError` as `schema_refusal`, `AIClientError` with status 429 as `gateway_429`, `AIClientError` with `timed_out` or status 408 or 504 as `timeout`, and other `AIClientError` as `provider`.

#### Scenario: Infrastructure and schema classes are separated with masked messages
- **WHEN** `_ended` handles a masked `AIClientError` with status 429, status 500, or `timed_out=True`, or a `StructuredOutputValidationError` with `error_types=('missing',)`
- **THEN** the returned reason starts with `gateway_429`, `provider`, `timeout`, or `schema_refusal`, holds the masked message, and calls `mask_secrets`

### Requirement: Live text, JSON, and stored stage eval reports include each case
`render_score`, `score_json`, and the stored `.data/roadmap_eval/stage/` JSON file SHALL include every `CaseRun` with its `outcome` and masked `reason` (passing `reason` through `mask_secrets` before writing).

#### Scenario: Text, JSON, and stored reports carry masked per-case outcome and reason
- **WHEN** `render_score`, `score_json`, or `devops roadmap eval stage` writes a `StageScore` holding a `CaseRun` whose `outcome` is `failed`
- **THEN** the text output lists a line with the case name, `failed`, and the masked reason, and both `--json` output and the stored file hold matching `case_runs` entries with secrets masked by `mask_secrets`
