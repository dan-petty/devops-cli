# Proposal

## Why
Issue `#6358`: In `shadow` mode, `alternatives.reply_fixable` alters job behavior, contrary to `openspec/specs/roadmap-alternatives/spec.md` ("record its band with no change to the job behavior"). In `_OutputChecker.check` (`src/devops_cli/roadmap/alternatives.py:1349`), `if self.returns > 0 or band is Band.CONTINUE: return None` runs before the `self.chain.mode is Mode.ON` branch. When a refusal has `code` in `("job_verdict", "no_search", "skip_only")` matching `earlier_code`, the rule outputs `Band.CONTINUE` and `shadow` suppresses the one return that `off` gives.

## What Changes
- Remove `or band is Band.CONTINUE` from the pre-mode guard in `_OutputChecker.check` (`src/devops_cli/roadmap/alternatives.py`). `Mode.ON` already returns `None` when `band is not Band.REVIEW`.
- Add parametrized tests in `tests/roadmap/test_roadmap_alternatives_reply_fixable.py` covering `job_verdict`, `no_search`, and `skip_only` with matching `earlier_code` in `shadow`, `on`, and `off` modes.

## Capabilities

### Modified Capabilities
- `roadmap-alternatives`: add a scenario under `Shadow mode records the band only` confirming `shadow` keeps the `off`-path return when `band` is `continue`.

## Impact
- `src/devops_cli/roadmap/alternatives.py`
- `tests/roadmap/test_roadmap_alternatives_reply_fixable.py`
