# Proposal

## Why

Issue #2162 identifies 18 review and scanner test files that cover no unique source line beyond what other files cover. Line coverage alone cannot prove a file is redundant. Mutation testing determines whether each file kills a unique mutant, so redundant files can be deleted or merged.

## What Changes

- Run mutation testing on the 18 review and scanner test files to identify which kill a unique mutant
- Delete test files that kill no unique mutant, or merge their distinct case into the covering file
- Record the mutants each file kills and the mutants that survive without it
- Verify CI passes and line coverage stays the same or rises
- Add a spec requirement to ci-test-selection for redundant test file elimination
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-test-selection`: redundant-test-file-elimination

## Impact

- Documents: `openspec/changes/2162-mutation-review-scanner/mutation-report.md`, `openspec/changes/2162-mutation-review-scanner/tasks.md`
- Tests: `tests/ai/review/test_cited_code.py`, `tests/commands/test_review.py`, `tests/commands/test_review_removed_options.py`, `tests/test_custom_personas.py`, `tests/test_review_advisory_backing.py`, `tests/test_review_deduplication.py`, `tests/test_review_defects_comments.py`, `tests/test_review_defenses_and_verification.py`, `tests/test_review_history.py`, `tests/test_review_location_paths.py`, `tests/test_review_loop_hardening.py`, `tests/test_review_regression_harness.py`, `tests/test_review_taxonomy_and_severity.py`, `tests/test_review_verification.py`, `tests/test_structural_positional_oracles.py`, `tests/test_security_kubelinter.py`, `tests/test_security_tflint.py`, `tests/security/test_sarif_fuzzing.py`

## Feasibility

- The 18 test files exist in the repository, confirmed by the directory tree showing tests/ai/review/test_cited_code.py, tests/commands/test_review.py, tests/commands/test_review_removed_options.py, tests/security/test_sarif_fuzzing.py, and the others.
- The coverage audit data in .data/agent/scratch/audit-coverage/unique-lines-nobaseline.json and subsumption.json confirms the line overlap percentages stated in the issue table.
- The mutation testing command `uv run devops ci mutate` exists, confirmed by the issue evidence citing its --help output.
- The pytest_add_cli_args_test_selection setting at pyproject.toml:266 supports the --ignore= flag needed to exclude a file from the suite.
- First checks: (1) `uv run devops ci mutate --help` to confirm the command and its arguments, (2) `uv run pytest tests/ai/review/test_cited_code.py -v` to confirm the file runs and passes, (3) `uv run devops ci mutate` on a small source file to confirm the mutation run completes.

## Existing Tool Considered

mutmut, accessed through `uv run devops ci mutate`, is the open, maintained mutation testing tool that covers the need. The change uses this existing tool and builds no new mutation testing code. The internal code the change deletes is the set of redundant test files identified by the mutation report, drawn from the 18 files listed in the issue table.
