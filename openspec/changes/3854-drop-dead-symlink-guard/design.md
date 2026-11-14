# Design

## Context

`_is_safe_workspace_path` takes a path, optionally resolved, and asks `is_safe_subpath`. Each caller resolves the path before the call, so `Path.is_symlink()` is false at the check.

## Goals

- Delete the dead branch.
- Keep the workspace boundary and the link behavior.

## Decisions

- **Keep `is_safe_subpath`.** The resolved target is the boundary test, and a link out of the workspace resolves outside it.
- **Keep the existing tests.** They already prove a link inside the workspace is readable and a link outside it is denied.

## Risks

- A future caller that passes an unresolved path would now be judged by its unresolved location, which starts inside the workspace. The function is private, and every caller resolves the path.

## Tests

- `unittest security tests` of `tests/security/test_builtin_tools.py` pass unchanged.
