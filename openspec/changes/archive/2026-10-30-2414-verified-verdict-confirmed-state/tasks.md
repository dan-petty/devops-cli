# Tasks

## 1. Lifecycle state transitions and models

- [x] 1.1 Write failing unit tests for `can_transition(FindingState.CONFIRMED, FindingState.OPEN)` and `SavedFinding` state fields. Verify with `uv run pytest tests/test_review_state.py`.
- [x] 1.2 Add `FindingState.OPEN` to `_VALID_TRANSITIONS[FindingState.CONFIRMED]` in `src/devops_cli/review/state.py`. Verify with `uv run pytest tests/test_review_state.py`.
- [x] 1.3 Add `state: FindingState` and `confirmed_by: str | None` fields to `SavedFinding` in `src/devops_cli/ai/review_schema.py`. Verify with `uv run pytest tests/test_resource_schemas.py`.

## 2. Adjudication verdict updates and mirroring

- [x] 2.1 Write failing unit tests for `apply_verdict` updating `state` and `confirmed_by` on human VERIFIED/MITIGATED and UNVERIFIED/INVALIDATED verdicts, and session mirroring. Verify with `uv run pytest tests/test_review_adjudication.py`.
- [x] 2.2 Update `apply_verdict` in `src/devops_cli/ai/review/verdicts.py` to set `state` and `confirmed_by` on human verdicts for findings with fingerprint v2, and reset on UNVERIFIED/INVALIDATED. Verify with `uv run pytest tests/test_review_adjudication.py`.
- [x] 2.3 Include `"state"` and `"confirmed_by"` in `_VERDICT_FIELDS` in `src/devops_cli/ai/review/adjudication.py`. Verify with `uv run pytest tests/test_review_adjudication.py`.
- [x] 2.4 Update `_sanitize_admitted_candidate` in `src/devops_cli/ai/review/pipeline.py` to copy `admitted.state` and `admitted.confirmed_by` to `sf`. Verify with `uv run pytest tests/test_review_adjudication.py`.

## 3. CLI reader and documentation

- [x] 3.1 Write failing test asserting `devops review findings --details` outputs finding lifecycle state for CONFIRMED findings. Verify with `uv run pytest tests/test_review.py`.
- [x] 3.2 Update `_build_finding_panel_lines` in `src/devops_cli/commands/review.py` to display finding lifecycle state and confirmed_by in detail panels. Verify with `uv run pytest tests/test_review.py`.
- [x] 3.3 Regenerate documentation with `uv run devops docs generate --sync-readme`. Verify with `git diff --exit-code docs/`.

## Workflow follow-up

- Archive the change after the project's review requirements are satisfied.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
