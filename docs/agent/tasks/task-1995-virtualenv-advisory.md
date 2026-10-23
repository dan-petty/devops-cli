# Task: virtualenv 21.14.13 Fixes GHSA-cx6f-vjhg-g3cc (#1995)

**Issue**: [#1995](https://github.com/dan-petty/devops-cli/issues/1995)
**Scope**: scope/security
**Feasibility**: `uv run devops ci audit` failed on `virtualenv` 21.14.12 with GHSA-cx6f-vjhg-g3cc, fixed in 21.14.13. `uv tree --invert --package virtualenv` shows that only `pre-commit`, in the `dev` group, needs it.

## Description
`virtualenv` 21.14.9 to 21.14.12 leave the `--prompt` value unescaped in the Bash activator's `PS1`, so the shell can run it later. `uv lock --upgrade-package virtualenv` moves the lockfile to 21.14.13 and changes no other package.

## Acceptance Criteria
- [x] `uv.lock` pins `virtualenv` 21.14.13.
- [x] `uv run devops ci audit` passes.
