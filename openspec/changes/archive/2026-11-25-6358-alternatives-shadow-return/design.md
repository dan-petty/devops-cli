# Design

## Decisions
1. Remove `or band is Band.CONTINUE` from line 1349 of `_OutputChecker.check` in `src/devops_cli/roadmap/alternatives.py`, leaving `if self.returns > 0: return None`.
2. Keep `Mode.ON` gated at line 1351 (`if self.chain is not None and self.chain.mode is Mode.ON:`), where only `Band.REVIEW` retries and `Band.CONTINUE` still returns `None`.
3. Add a parametrized test covering `"job_verdict"`, `"no_search"`, and `"skip_only"` across `"shadow"`, `"on"`, and `"off"` modes when `FAILED_REASON` equals the refusal code.

## Rejected alternatives
- Checking `band is Band.CONTINUE` inside a separate `Mode.SHADOW` branch: duplicates the `Mode.OFF` fallback already below the `Mode.ON` block.
