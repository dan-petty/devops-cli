# Design

## Context

See proposal.md for motivation. `FindingState.CONFIRMED` and `Finding.confirmed_by` exist in `src/devops_cli/review/finding.py` and `src/devops_cli/review/state.py`. However, session storage relies on `SavedFinding` in `src/devops_cli/ai/review_schema.py`, which currently omits these lifecycle fields. In addition, `_VALID_TRANSITIONS` permits CONFIRMED findings to transition only to FIXED, preventing adjudicators from overturning a verdict back to OPEN.

## Goals / Non-Goals

**Goals:**
- Store finding lifecycle state (`FindingState`) and confirmation adjudicator (`confirmed_by`) on `SavedFinding`.
- Update finding state to CONFIRMED when a person records a VERIFIED or MITIGATED verdict on an admitted finding with a fingerprint v2.
- Reset finding state to OPEN and clear `confirmed_by` when a later verdict invalidates or resets the finding.
- Allow CONFIRMED to transition to OPEN in `_VALID_TRANSITIONS`.
- Mirror `state` and `confirmed_by` between `findings.json` and `candidates.json`.
- Display finding state in `devops review findings --details`.

**Non-Goals:**
- Machine-originated verdicts setting CONFIRMED: only human verdicts or replayed observations confirm findings.
- Custom state values beyond canonical `FindingState` enum members.

## Decisions

### Decision: Add `state` and `confirmed_by` directly to `SavedFinding`
- **Choice**: Add `state: FindingState = FindingState.OPEN` and `confirmed_by: str | None = None` to `SavedFinding` in `src/devops_cli/ai/review_schema.py`.
- **Alternative considered**: Store state in `findings.sarif` property bags.
  - *Evidence for rejection*: `SavedFinding` is the authoritative session payload persisted in `findings.json` and `candidates.json` read by `devops review verify` and `devops review findings`.

### Decision: Allow transition from CONFIRMED to OPEN
- **Choice**: Add `FindingState.OPEN` to `_VALID_TRANSITIONS[FindingState.CONFIRMED]` in `src/devops_cli/review/state.py`.
- **Alternative considered**: Disallow overturning a CONFIRMED finding.
  - *Evidence for rejection*: A human reviewer can re-evaluate and mark a previously verified finding as `INVALIDATED` or `UNVERIFIED`. Refusing the transition would break `devops review verify`.

### Decision: Update state in `apply_verdict`
- **Choice**: In `src/devops_cli/ai/review/verdicts.py`, check if the finding has a valid fingerprint v2 and `by == "human"`. Set `state = FindingState.CONFIRMED` and `confirmed_by = "human"` on VERIFIED/MITIGATED. Set `state = FindingState.OPEN` and `confirmed_by = None` on UNVERIFIED/INVALIDATED.
- **Alternative considered**: Adding a separate command to change lifecycle state.
  - *Evidence for rejection*: `apply_verdict` is the unified entrypoint for adjudication across `devops review verify`. Automatic alignment avoids state drift between verdict status and lifecycle state.

### Decision: Include state fields in adjudication mirroring
- **Choice**: Add `"state"` and `"confirmed_by"` to `_VERDICT_FIELDS` in `src/devops_cli/ai/review/adjudication.py`.
- **Alternative considered**: Only writing state to `findings.json`.
  - *Evidence for rejection*: Adjudication mirrors verdicts between `candidates.json` and `findings.json`. Omitting state fields would cause the two files to diverge.

## Risks / Trade-offs

- [Risk] Historical sessions lack `state` and `confirmed_by` in their JSON files.
  → Mitigation: `SavedFinding` assigns defaults `FindingState.OPEN` and `None`. A pre-validation normalizer handles string values gracefully.
- [Risk] Invariant checks fail if `state == CONFIRMED` without `confirmed_by`.
  → Mitigation: `_validate_finding_state_fields` and `assert_finding_state_invariants` require non-empty `confirmed_by` for CONFIRMED findings; `apply_verdict` sets both atomically.
