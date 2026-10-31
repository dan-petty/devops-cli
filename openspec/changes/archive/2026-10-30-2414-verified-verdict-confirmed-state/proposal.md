# Proposal

## Why

Issue #2414: A person's VERIFIED or MITIGATED verdict on an admitted finding does not set the finding's stored state to CONFIRMED. CONTEXT.md and the review redesign (#1137, child P2-10, #877) state that a valid verdict sets CONFIRMED. The session files hold no state field, and `apply_verdict` updates no state.

## What Changes

- Add `state` (default `FindingState.OPEN`) and `confirmed_by` (default `None`) fields to `SavedFinding`.
- Update `apply_verdict` so a person's VERIFIED or MITIGATED verdict on an admitted finding with a fingerprint v2 sets `state` to `FindingState.CONFIRMED` and `confirmed_by` to `"human"`.
- Update `apply_verdict` so a later verdict of UNVERIFIED or INVALIDATED on a CONFIRMED finding resets `state` to `FindingState.OPEN` and clears `confirmed_by`.
- Allow the transition from `FindingState.CONFIRMED` to `FindingState.OPEN` in `_VALID_TRANSITIONS` in `src/devops_cli/review/state.py`.
- Include `state` and `confirmed_by` in `_VERDICT_FIELDS` in `src/devops_cli/ai/review/adjudication.py` so mirroring keeps `findings.json` and `candidates.json` in step.
- Update `_build_finding_panel_lines` in `src/devops_cli/commands/review.py` to display the finding's state in `devops review findings --details`.
- This change fits one pull request.

## Capabilities

### New Capabilities
- `review-finding-state`: Stores and transitions review finding lifecycle states when human verdicts are recorded.

### Modified Capabilities

## Impact

- `src/devops_cli/ai/review_schema.py`: `SavedFinding` model fields.
- `src/devops_cli/ai/review/verdicts.py`: `apply_verdict` logic.
- `src/devops_cli/review/state.py`: `_VALID_TRANSITIONS` table.
- `src/devops_cli/ai/review/adjudication.py`: `_VERDICT_FIELDS` set.
- `src/devops_cli/commands/review.py`: `devops review findings --details` display.
- `tests/test_review_adjudication.py`, `tests/test_review.py`: unit tests.

## Feasibility

Checked on `origin/main` at commit 6c502854:

- `FindingState.CONFIRMED` and `Finding.confirmed_by` exist in `src/devops_cli/review/state.py` and `src/devops_cli/review/finding.py`.
- `SavedFinding` in `src/devops_cli/ai/review_schema.py` lacks `state` and `confirmed_by`.
- `_VALID_TRANSITIONS` in `src/devops_cli/review/state.py:27-36` allows CONFIRMED to transition only to FIXED, which rejects changing an overturned human verdict back to OPEN.
- `apply_verdict` in `src/devops_cli/ai/review/verdicts.py` updates `status`, `verified`, and `verified_by`, but does not touch `state` or `confirmed_by`.
- The premise is confirmed by code inspection and existing test output.

## Existing Tool Considered

SARIF 2.1.0 does not specify a CONFIRMED state for findings. The repository already contains `FindingState.CONFIRMED` and `FindingState.OPEN` in `src/devops_cli/review/state.py`. This change uses existing domain models and extends `SavedFinding` and `apply_verdict` with no new dependencies or outside tools. The change deletes no internal code.
