# Tasks

## 1. Pin the lockfile bucket to CONST_LOCKFILE_NAMES

Reads: `src/devops_cli/ai/review/pipeline.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/security/osv_scanner.py`, `tests/security/test_review_pipeline_go.py`. Changes: `src/devops_cli/ai/review/pipeline.py`, `tests/security/test_review_pipeline_go.py`.

- [ ] 1.1 Add `test_classify_scanner_files_keeps_unknown_lock_names_out` to `tests/security/test_review_pipeline_go.py`: write `uv.lock`, `rules.lock` and `tools.lock` under `tmp_path`, call `classify_scanner_files` with them, and assert that the bucket holds `uv.lock` and holds neither `rules.lock` nor `tools.lock`. It fails against the suffix rule
  - Verification: `uv run devops ci test tests/security/test_review_pipeline_go.py` fails on the base
- [ ] 1.2 In `classify_scanner_files`, build the lockfile bucket from files whose name is in `CONST_LOCKFILE_NAMES`, and drop the `.lock` and `.lockb` suffix branch. In `_lockfiles_beside`, keep a file only when its name is in `CONST_LOCKFILE_NAMES`. Keep the fixture-path exclusion
  - Verification: `uv run devops ci test tests/security/test_review_pipeline_go.py` passes

## Criteria

- Group 1: ### Requirement: Known lockfile names only The scanner file classification SHALL place a file in the lockfile bucket only when its name is in CONST_LOCKFILE_NAMES.
- Group 1: ### Requirement: osv-scanner gets only real lockfiles The review pipeline MUST pass only files in the lockfile bucket to osv-scanner as --lockfile arguments.
- Group 1: ### Requirement: Regression test pins rules.lock exclusion The test suite SHALL pin that a file named rules.lock is not classified as a lockfile.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
