## ADDED Requirements

### Requirement: The repair scope takes the failed files that the change causes
A failed file outside the plan SHALL be in the repair scope when the branch changes it, when it uses a function, class or method whose definition the branch changes, when it is a test that imports a module that the branch changes, or when it is a snapshot test whose snapshot differs while the branch changes a source module. A failed file that the default branch changed after the branch point SHALL NOT be in the scope.

#### Scenario: A caller of a changed function outside the plan is repaired
- **WHEN** the plan adds the keyword-only argument `in_runner` to `_run_pr_review_workflow`, and the log names `FAILED tests/git/test_review_worktree_regression.py::test_run_pr_review_workflow_partial_context - TypeError: _run_pr_review_workflow() missing 1 required keyword-only argument: 'in_runner'`, a file that the plan does not list and that calls the function
- **THEN** the step gives the file to `run_fix_step`, which may change it, and pushes the repair

#### Scenario: A failed file that main changed stops as main skew
- **WHEN** the failed file is a caller of a changed function, and the default branch changed the file after the branch point
- **THEN** the step stops with 0 model requests, and the reason names the file and main skew

#### Scenario: A log that names no file of the checkout stops
- **WHEN** the log names no failed file that the checkout tracks, such as the end of an ignore of a scanner
- **THEN** the step stops with 0 model requests, and the reason says that the log names no path of the plan and no file that the change causes

### Requirement: A comment names the files of a pushed repair
After the push of a repair, the step SHALL upsert its marked comment for the check. The comment SHALL name each file that tier 1 wrote, or each failed file outside the plan that the model fix could change, with its reason.

#### Scenario: Tier 1 names the files that it wrote
- **WHEN** tier 1 writes `docs/MCP_TOOLS.md` and a snapshot again and pushes the repair
- **THEN** the comment of the step names both files

#### Scenario: Tier 2 names the files that the change causes
- **WHEN** the model fix repairs a caller outside the plan and the step pushes the repair
- **THEN** the comment of the step names the file and the changed name that it uses

## MODIFIED Requirements

### Requirement: Tier 1 resolves deterministic check failures with zero model calls
When a check failure is classified as `lint`, the step SHALL run `ruff check --fix` and `ruff format` on the changed files. Whatever the class of the check, a docs failure SHALL get `devops docs generate`, a lockfile failure `uv lock`, and a failed snapshot test the snapshot update of the toolchain and `devops docs generate`. The step SHALL run the check again locally, and when it passes, push the repair with zero model requests.

#### Scenario: Tier 1 fixes a lint failure with 0 model requests
- **WHEN** a pull request check fails on code formatting or lint errors
- **THEN** the step runs the lint fixers and pushes the repair with 0 model requests

#### Scenario: Tier 1 fixes a docs failure
- **WHEN** a pull request check fails because documentation is out of sync
- **THEN** the step regenerates the documentation and pushes the repair

#### Scenario: Tier 1 fixes a lockfile failure
- **WHEN** a pull request check fails because uv.lock is not updated
- **THEN** the step updates the lockfile and pushes the repair

#### Scenario: A lockfile failure in a test check gets uv lock
- **WHEN** `uv sync --locked` fails in the check `Tests & Coverage`, whose class is test
- **THEN** tier 1 runs `uv lock` and `uv lock --check`, commits `uv.lock`, and makes no model request

#### Scenario: Tier 1 writes a snapshot and the documents again
- **WHEN** the log of `Tests & Coverage (shard 3 of 4)` holds `FAILED tests/ai/mcp/test_mcp_tool_listing.py::test_the_tool_listing_matches_the_snapshot - assert [+ received] == [- snapshot]`
- **THEN** tier 1 runs `uv run pytest -n 0 --snapshot-update tests/ai/mcp/test_mcp_tool_listing.py` and `uv run devops docs generate`, then `uv run devops ci test tests/ai/mcp/test_mcp_tool_listing.py` and `uv run devops ci docs`, commits the snapshot and the document, and makes no model request

### Requirement: Tier 2 repairs failures within plan scope using a model
When Tier 1 does not resolve the failure, the step SHALL inspect the failed log against the repair scope of the item: the paths of the plan, and the failed files that the change of the branch causes. When the log names no path within the scope, the step SHALL stop with zero model calls, with a reason that names each failed file and why. When the log names a path in scope, the step SHALL invoke `run_fix_step`, which MAY change the failed files that the change causes.

#### Scenario: A log outside the plan scope stops with 0 model requests
- **WHEN** the failed check log names only files outside the plan scope that the change of the branch does not cause
- **THEN** the step stops with 0 model requests, and the reason names each file

#### Scenario: A log within plan scope runs a fix step
- **WHEN** the failed check log names a path within the plan scope
- **THEN** the step invokes `run_fix_step`
