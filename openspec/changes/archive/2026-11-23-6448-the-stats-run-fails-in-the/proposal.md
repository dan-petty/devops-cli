# Proposal: #6448

## Why

The mutants tree runs tests in a copied tree.
Tests that look for the nearest `.git` find the parent checkout outside allowed roots.
The host path guard stops the test.
Initializing the mutants root as a Git repository stops the upward search.

## What Changes

- Add `prepare_mutants_tree` in `src/devops_cli/ci/mutate.py` to initialize a Git repository at `mutants/.git`.
- Call `prepare_mutants_tree` in `devops ci mutate` before running mutmut.
- Add unit tests verifying mutants root preparation and repository resolution.

## Capabilities

### Modified
- `ci-test-selection`: `devops ci mutate` prepares the mutants directory as a Git repository before mutmut starts.

## Impact

Tests running in the mutants tree find `.git` in the mutants root and stay within allowed paths.

## Feasibility

Verified against `_resolve_git_dir` and `_repository`.
The presence of `.git` in `mutants/` stops upward directory traversal.

## Existing Tool Considered

Git is the repository tool in use.
`git init -q` initializes the repository without custom tools.
Cost to build: 15 lines of code.
