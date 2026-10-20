# Task: Intake Retries Invalid Proposals and Exits Non-Zero on Failed Placement (#1677)

**Issue**: [#1677](https://github.com/dan-petty/devops-cli/issues/1677)
**Scope**: scope/roadmap
**Feasibility**: Verified against intake model flow, schema validation rules, and Typer CLI exit behavior.

## Description
When `devops roadmap intake` asks the analysis model for a proposal, the model may return values outside the allowed domain (e.g. an unrecognized `type/*` label like `type/perf`, or non-standard `Value` or `Effort` descriptors). Previously, any validation failure immediately skipped the candidate. Furthermore, when an inline candidate passed via `--title` and `--body-file` with `--confirm` was skipped, the CLI exited 0 as if it succeeded.

This change enhances `devops roadmap intake` with:
- **Proposal retry with feedback**: When `validate_proposal` raises `_InvalidProposal` because one or more values are off-list, `_Planner` retries once by asking the model again with the structured `problem` field attached to `ProposalRequest`.
- **System prompt guidance**: The intake system prompt instructs the model that when `problem` is present, the previous proposal had invalid values and must be corrected. Standard Conventional Commit prefixes without dedicated labels (`perf`, `build`, `ci`) are mapped to `type/infra` in `CONST_ROADMAP_CONVENTIONAL_COMMIT_TYPE_MAPPINGS`.
- **Comprehensive skip reporting**: If the second proposal also returns off-list values, the candidate is skipped with both validation problems joined in `decision.reason` and formatted in the intake run report.
- **Model call accounting**: Each proposal attempt, including retries, is tracked by `SpendMeter` as a proposal model call.
- **Non-zero exit on unplaceable title candidate**: When a new candidate specified via `--title` cannot be placed and is skipped under `--confirm`, the intake command terminates with exit code 1. A run over existing candidates preserves exit code 0.

## Acceptance Criteria
- [x] **Proposal retry on off-list value**: An off-list type, value, or effort triggers a single retry with feedback detailing which fields failed validation.
- [x] **Successful recovery**: A valid second proposal places the candidate normally.
- [x] **Combined error report on dual failure**: Two invalid proposals skip the candidate and include both failure reasons in the decision and rendered report.
- [x] **Spend accounting**: Retry attempts are counted in the proposal call spend report.
- [x] **CLI exit code**: `devops roadmap intake --title ... --confirm` exits with code 1 when the candidate is skipped, while existing issue batch runs maintain exit code 0.
