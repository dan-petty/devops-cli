# Proposal: #4878

## Why
Refine collects the context of an item with `git grep` over the tree at the pinned commit. When an identifier search takes longer than 15 seconds, `subprocess.TimeoutExpired` escapes from `refine_one_item`. This halts `plan_refine` and aborts the entire refine round. The item gets no failure class and no retry backoff. Closes #4878.

## What Changes
1. Handle `subprocess.TimeoutExpired` in `git_result` and `_collect_identifiers` by logging a warning and treating timeout as an empty search result.
2. Add pathspec exclusions for `openspec/changes/archive` and `tests/fixtures` to identifier grep searches.
3. Pass `--max-count=5` to `git grep` in `_collect_identifiers` to stop searching a file after five matches.
4. Add unit tests for timeout handling and pathspec exclusions in refine context collection.

## Capabilities
### roadmap-refine/context
- Add requirement: A slow identifier grep does not halt context collection.

## Impact
- Refine rounds do not crash when searching common identifiers or large repository directories.
- Context collection continues gracefully with remaining context sections.

## Feasibility
Confirmed against real system: `_collect_identifiers` calls `git_result` which invokes `run_subprocess` with `timeout=15` without catching `subprocess.TimeoutExpired`.

## Existing Tool Considered
`git grep` is the standard tool. Modifying parameters and catching `subprocess.TimeoutExpired` uses standard library capabilities without new dependencies. Build cost: 20,000 tokens and 30 minutes.
