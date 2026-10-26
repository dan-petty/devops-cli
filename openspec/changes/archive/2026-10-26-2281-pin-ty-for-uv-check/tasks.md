# Tasks

## 1. Failing test

- [x] Add `test_ci_uv_check_type_checks_with_the_ty_the_lockfile_pins` to `tests/test_ci.py`: the `dev` group pins `ty` and `uv.lock` holds the same version
  - Verification: `uv run devops ci test tests/test_ci.py -k type_checks_with_the_ty`

## 2. Pin ty

- [x] Add `ty==0.0.92` to the `dev` group of `pyproject.toml` and run `uv lock`
  - Verification: `uv lock --check`
- [x] Confirm that `uv check` passes with the locked `ty`
  - Verification: `uv check`
- [x] Add a `ty` row to the pinned-tool table of `src/devops_cli/ai/knowledge_base/devops_cli/python_packages.md`
  - Verification: `uv run devops ci test tests/test_kb.py`

## 3. Verification and static checks

- [x] Verify the fail-to-pass check run passes against the base
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] Verify the full static checks pass
  - Verification: `uv run devops ci`

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
