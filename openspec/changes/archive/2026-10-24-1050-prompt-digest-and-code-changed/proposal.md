# Proposal

## Why

Issue #1050: `ReviewProfiler.build()` calculates `review_prompt_digest()` when a review ends.
When prompt files change while a review runs, the profile records the digest of the changed prompts.
The profile does not record that the prompts changed during the run.
Also, `devops review corpus score` accepts sessions that have `code_changed_during_run: true`.
Benchmark arms must compare runs that used unchanging code and prompts.

## What Changes

- Calculate `review_prompt_digest()` in `ReviewProfiler.__init__` and store the initial value.
- Record the initial `prompt_digest` value in `ReviewProfile` during `build()`.
- Calculate `review_prompt_digest()` again in `ReviewProfiler.build()` and set `code_changed_during_run: true` if the digest changed.
- Update `score_corpus_runs` to raise `ValidationError` when any profile has `code_changed_during_run: true`.
- Update field comments, documentation, and warning messages to state that `code_changed_during_run` includes prompt changes.
- Add tests for start-time digest recording, prompt modifications during runs, and benchmark arm rejection.
- The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/review/profile.py`: `ReviewProfiler` calculates `prompt_digest` at initialization and flags prompt changes in `build()`.
- `src/devops_cli/ai/review/defects.py`: `score_corpus_runs` raises `ValidationError` for sessions with `code_changed_during_run: true`.
- `src/devops_cli/lang/en/messages.py`: Warning message notes prompt changes alongside source checkout changes.
- `docs/SELF_IMPROVEMENT.md`: Document start-time prompt digest recording and arm rejection for changed code or prompts.
- `tests/test_review_profile.py`: Add tests for prompt change detection during review runs.
- `tests/test_review_defects.py`: Add tests for rejecting sessions with changed code or prompts in benchmark arms.

## Feasibility

- Premise confirmed against `src/devops_cli/ai/review/profile.py` and `src/devops_cli/ai/review/defects.py`.
- `ReviewProfiler` already computes `tools_lock_digest` and `own_source_state` at start.
- `ReviewProfile` already contains the `code_changed_during_run` field.
- `score_corpus_runs` already raises `ValidationError` for differing prompt digests.
- `commands/review.py` already handles `ValidationError` from `score_corpus_runs` and exits with code 1.

## Existing Tool Considered

Existing review profiler and defect corpus scoring mechanisms in `devops-cli` cover these workflows.
We use the existing `code_changed_during_run` field and `ValidationError` exceptions.
No third-party library is required.
