# Proposal

## Why

Issue #2585: the 1,000-character body limit of CONTRIBUTING.md section 4 is enforced only by a reviewer. 119 of 188 recent squash commits exceed it. Agents run `devops pr check-readiness` before `devops pr ready`, so a WARNING advisory there reaches the writer at the right time without blocking the merge.

## What Changes

- Add a WARNING advisory in `assess_merge_readiness` when the PR body, with trailer lines removed, exceeds 1,000 characters.
- Add a constant `PR_BODY_MAX_LENGTH` and a trailer-stripping helper in `merge_readiness.py`.
- Update CONTRIBUTING.md section 4 to name the advisory from `devops pr check-readiness` in place of the reviewer check.
- Add a table test covering the threshold, the trigger, trailer exclusion, and exit-code invariance.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-merge-readiness`: body-length-advisory-threshold, body-length-advisory-trigger, trailer-exclusion, advisory-does-not-block

## Impact

- Code: `src/devops_cli/github/merge_readiness.py`
- Documents: `CONTRIBUTING.md`
- Tests: `tests/test_merge_readiness.py`

## Feasibility

- The `pr_data` dict passed to `assess_merge_readiness` holds the body under the "body" key, confirmed by the function signature in `src/devops_cli/github/merge_readiness.py` and the issue body.
- `AdvisoryLevel.WARNING`, the `Advisory` NamedTuple, and `_Verdict.warn()` already exist in `src/devops_cli/github/merge_readiness.py`, so no new mechanism is needed.
- The trailer prefixes (Closes, Change:, Fail-to-pass:, Co-authored-by:, Signed-off-by:) are a closed set named in the issue and in `.github/pull_request_template.md`.
- First check: run `uv run devops ci test tests/test_merge_readiness.py` to confirm the new test fails before the implementation.
- Second check: run `uv run devops docs check` to confirm CONTRIBUTING.md still resolves its command references.

## Existing Tool Considered

No open tool checks the length of a pull request body. The Semantic PR title action checks only the title. commitlint checks commits, but the squash merge discards branch commits. markdownlint checks line lengths, not a total. Cost of building: about 20 lines in the verdict module and one table test, about 40k tokens to build and 5k a year to keep, under one hour of elapsed time.
