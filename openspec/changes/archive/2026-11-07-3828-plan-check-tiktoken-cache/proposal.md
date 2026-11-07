# Proposal

## Why

The `Plan Check` job of `.github/workflows/pr-title.yml` fails on the GitHub runner for each plan pull request, before it judges the plan. `count_tokens` in `src/devops_cli/ai/context_budget.py` loads the tiktoken encoding from the cache directory and raises `TokenCountError` when that directory is empty. A clean runner has no cache, and the job sets none up. #3828 gives the job the cache.

## What Changes

- The job `plan-check` gets the step `Prepare the tiktoken cache`. It copies the committed `tests/fixtures/tiktoken/o200k_base.tiktoken` and `cl100k_base.tiktoken` into `${{ runner.temp }}/tiktoken-cache`. It names each file with the SHA-1 of its blob URL, as `tests/conftest.py` does.
- The step `Check the Plan` sets `TIKTOKEN_CACHE_DIR` to that directory.
- `tests/invariants/test_workflow_contracts.py` fails when the job has no preparation step, when the step comes after the command, or when the two steps name different directories.
- `count_tokens` is not changed. It keeps raising `TokenCountError` for a missing cache, and `tests/ai/test_context_budget.py` already asserts that.
- The change alters no behavior that a consumer observes: it edits a CI workflow and a test. It has no spec delta and sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Workflows: `.github/workflows/pr-title.yml`
- Tests: `tests/invariants/test_workflow_contracts.py`

## Feasibility

- The cause was confirmed in the code. `_get_tiktoken_encoding` raises when the cache directory is missing or empty, and `count_tokens` then raises `TokenCountError` with the message of the job log.
- The job has no step that fills the cache: `.github/workflows/pr-title.yml` sets no `TIKTOKEN_CACHE_DIR` for `plan-check`.
- The fix was run by hand. The script of the new step, run with bash, wrote two files named `fb374d419588a4632f3f557e76b4b70aebbca790` and `9b5ad71b2ce5302211f9c61530b329a4922fc6a4`. With `TIKTOKEN_CACHE_DIR` set to that directory, `count_tokens` returned a count. With an empty directory, it raised `TokenCountError`.
- The fixtures are in the repository, and the job checks out the whole history, so the files are on the runner.

## Existing Tool Considered

- `tiktoken` reads a cache directory and does not download a file for an empty one in this job. The change adds no tool.
- `actions/cache` was rejected. A clean runner has no cache to restore, so the first run still fails.
- A download from the OpenAI blob store was rejected. It adds a network path and an unpinned remote input to the check.
- The committed fixtures are pinned by the commit, need no network, and the Docker images and the tests already use them. The change deletes no code.
