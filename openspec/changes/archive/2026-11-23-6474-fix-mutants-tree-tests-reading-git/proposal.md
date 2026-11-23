# Proposal: #6474

## Why
Tests in the prepared mutants tree fail when they read Git tracking or generated source files.
The tests need a hermetic Git fixture or exclusion from the mutation test selection.

## What Changes
Add a shared `git_repo` fixture with a recorded commit that starts no real Git process.
Add `tests/git/test_git_repo_fixture.py` to verify the fixture.
Exclude tests from the mutation selection in `pyproject.toml` with documented reasons.

## Capabilities
Tests can read Git tracking without starting real Git subprocesses.
Mutation testing runs without failures from tests that read checkout state or generated source.

## Impact
No production code changes.
Improves test hermeticity and enables mutation testing in prepared trees.

## Feasibility
Confirmed via `uv run devops ci test tests/git/test_git_repo_fixture.py`.
The tests pass cleanly without real Git commands.

## Existing Tool Considered
`pytest` fixture system and existing `git_fake` process double are reused.
Cost to implement: 30 lines of test helper code and configuration updates.
