# Proposal

## Why

Issue #2949 reports that a single failed alternatives check fails the whole round. After three failed rounds the row is suspended. On 2026-10-30 one item (UnexpectedModelBehavior on #1127) suspended the row for the entire repository. One bad item should not block the other items.

## What Changes

- Per-item error isolation: a failed check is caught and recorded, the round continues with the remaining items.
- Failure record in the item's job record: the item number, the error class, and the time of the failure.
- Retry delay: a failed item is skipped until roadmap.alternatives.retry_days (3 by default) has elapsed.
- Row failure condition: the row fails and counts toward the 3-round suspension only when zero items were checked.
- Stop reason format: uses the tool-call retry reasons of #2875 and the readable provider text of #2922.
- Documentation: k8s/README.md line 610 and docs/TELEMETRY.md line 83 are updated to the new behavior.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-alternatives`: partial-failure-isolation, total-failure-still-fails, retry-delay

## Impact

- Code: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/rows.py`
- Documents: `k8s/README.md`, `docs/TELEMETRY.md`

## Feasibility

- The current behavior is confirmed at k8s/README.md:610: 'If the check of an item fails, the row writes the other checks and fails, naming the item.'
- The 3-round suspension and the row scheduling are described at k8s/README.md:610 and in the model lane description in CONTEXT.md.
- The stop reason format is documented in openspec/changes/archive/2026-10-30-2562-refine-warning-reasons/design.md:13 (bounded_text, AIClientError.reason).
- The UnexpectedModelBehavior error class is documented at docs/ERRORS.md:125 and in openspec/changes/archive/2026-10-28-2398-refine-investigates-questions/design.md:39.
- The metric devops_cli_roadmap_alternatives_total is documented at docs/TELEMETRY.md:83.
- First checks the implementation runs: `uv run devops ci test tests/test_roadmap_alternatives.py` to verify the new per-item isolation, then `uv run devops ci` for the full suite.

## Existing Tool Considered

No open, maintained tool covers this need. The fix modifies the project's own alternatives row code in the roadmap service. The written cost is the tokens to build the per-item error isolation, the retry scheduling, the stop reason formatting, and the tests, plus the elapsed time to pass `uv run devops ci`. No internal code is deleted; the existing failure path is replaced by the per-item isolation.
