# Proposal: #6116

## Why

The fix-checks job (mode `on`) stopped on both of its runs since 0.169.3 with `Failed check log is outside plan scope`, so it graded 0 of 2 (#6116). In both cases the change of the plan caused the failure, in a file that the plan does not list:

- Pull request #6114 (#3827): the plan adds the keyword-only argument `in_runner` to `_run_pr_review_workflow`. Two tests in `tests/git/test_review_worktree_regression.py` call the function without it and fail with a `TypeError`.
- Pull request #6041 (#3771): the plan adds an option to `devops ai rag drift`, so the MCP tool listing changes. The snapshot test `tests/ai/mcp/test_mcp_tool_listing.py` and the `docs` row fail, because nobody wrote the snapshot and the generated documents again.

Tier 1 had no fixer for a snapshot, and the scope check read only the paths that the plan names.

## What Changes

- The scope check of the step takes a file outside the plan when the change of the branch causes its failure: the file uses a function, class or method whose definition the branch changes; the file is a test that imports a module that the branch changes; the file is a snapshot test whose snapshot differs while the branch changes a source module; or the branch changes the file. The model fix may change these files, the fix group names them, and a comment on the pull request names each file with its reason.
- A failure that the change does not cause still stops the round, and the reason names each file and why: a file that the default branch changed after the branch point is main skew, and a log that names no file of the checkout (such as an expired ignore) names no path.
- Tier 1 writes the snapshot of each test whose snapshot differs again with the snapshot update of the toolchain (`uv run pytest -n 0 --snapshot-update <tests>` for devops-cli), then the documents with `devops docs generate`, and runs the tests and `devops ci docs` again. It makes no model request, and its comment names the files that it wrote.
- The behavior of the step is observable (its result, its reason and its comment), so the change has a delta of `roadmap-fix-checks`.

The change fits one pull request.

## Capabilities

- `roadmap-fix-checks`: the tier 1 and tier 2 requirements change.

## Impact

- `src/devops_cli/roadmap/steps/fix_checks.py`, `fix_checks_repair.py` and the new `fix_checks_cause.py`.
- `src/devops_cli/roadmap/implement/implement_step.py`: a fix request carries the extra paths, and the outside-plan check of a fix step allows them. The implement job gives no extra path, so its repair loop does not change.
- `src/devops_cli/roadmap/toolchains.py`: a preset names its snapshot update command.
- `src/devops_cli/lang/en/messages.py`: one message for the fix group.
- No prompt under `src/devops_cli/ai/tasks/` changes.

## Feasibility

- The live record of item #3827 holds `fix_checks.key` `30271ea…:Tests & Coverage (shard 4 of 4)` with `fix_checks.result` `stopped`, and the record of #3771 holds `80e783a…:Tests & Coverage (shard 3 of 4)` with `stopped` (`devops gh api repos/dan-petty/devops-cli/issues/<n>`).
- The job log of that shard of #6114 holds `FAILED tests/git/test_review_worktree_regression.py::test_run_pr_review_workflow_partial_context - TypeError: _run_pr_review_workflow() missing 1 required keyword-only argument: 'in_runner'`. The log of #6041 holds `FAILED tests/ai/mcp/test_mcp_tool_listing.py::test_the_tool_listing_matches_the_snapshot - assert [+ received] == [- snapshot]`, the assertion text of syrupy 7.0.2.
- The two pull requests were repaired by hand with the same fixes: `in_runner=False` in the two calls, and `uv run pytest tests/ai/mcp/test_mcp_tool_listing.py --snapshot-update -n 0` plus `uv run devops docs generate`. Their checks then passed.
- syrupy 7.0.2 has no option `--snapshot-file-lock` (#5146), so the update runs with `-n 0`, in one process.

## Existing Tool Considered

- Snapshots: syrupy's own `--snapshot-update` writes the snapshots again; the change builds no snapshot writer.
- Documents: `devops docs generate`, the project command.
- Changed definitions: the standard library `ast` compares each function, class and method at the branch point and at the head. The `symbols` module of `devops_cli.ai.analyze` gives only added and removed names, not changed ones, so it does not cover a changed signature.
- References and imports: `ast` reads the names and the imports of the failed file. A whole-repository reference search (`git grep`) is not needed, because only the files that the log names are judged.
- Main skew: `git merge-base` and `git diff --name-only` give the files that the default branch changed after the branch point.
- No import graph library is a dependency (grimp, import-linter), and the direct imports of the failed test are enough for the two cases, so the change adds none.
- The change deletes no internal code. The written cost of the build: about 60,000 tokens and 2 hours, and the tests hold it.
