# Proposal

## Why

`devops openspec new` prints "Created <folder> on branch <branch>", and the branch is a name that the command computes from the issue title. It creates, switches to and reads no branch, so a checkout on another branch reads a false fact, and the folder slug can differ from the worktree branch slug (#4593).

## What Changes

- `ScaffoldResult` holds `current_branch`, the branch of the checkout, or None when HEAD is detached.
- The folder slug comes from the branch of the checkout when that branch is `<type>/<issue>-<slug>` for the same issue; otherwise from the title.
- The output names the branch of the checkout, or `HEAD detached`, and calls the computed name a suggestion when the checkout is not on it.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `openspec-scaffold`: The output names the branch of the checkout, and the folder takes its slug.

## Impact

- Code: `src/devops_cli/openspec/scaffold.py`, `src/devops_cli/commands/openspec.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/openspec/test_openspec_new.py`

## Feasibility

- `current_branch` and `parse_branch` already exist.
- The command already prints from `MESSAGES.openspec`.
- Verification commands: `uv run devops ci test tests/openspec/test_openspec_new.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

GitPython can report the branch, but the project removed it for one git seam. The change reuses `current_branch` and `parse_branch`.
