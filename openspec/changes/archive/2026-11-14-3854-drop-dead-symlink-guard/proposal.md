# Proposal

## Why

`_is_safe_workspace_path` in `src/devops_cli/ai/tools/builtin_tools.py` returns `False` when `target.is_symlink()`. No caller reaches that branch: every caller resolves the path first, and a resolved path is never a symlink. The branch is dead, and it suggests a protection that the code does not give (#3854).

## What Changes

- `_is_safe_workspace_path` decides only by `is_safe_subpath`.
- The link-out-of-workspace denial stays, because the resolved target lies outside the root.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/tools/builtin_tools.py`
- Tests: `tests/security/test_builtin_tools.py` already covers a link inside the workspace and a link out of it.

## Feasibility

- The two lines are the whole change.
- Verification commands: `uv run devops ci test tests/security/test_builtin_tools.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

No outside tool applies to a refactor that deletes dead code.
