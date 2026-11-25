# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests for directory-boundary pass-through, removed `-o`/`-v`/`-p`/`-u` aliases, `import`/`state`/`show`/`force-unlock`, and `--dry-run` argv/directory output, and update existing `tf` tests whose wrapper flags trailed `<directory>`
  - Verification: `$ uv run pytest -n 0 tests/commands/test_tf.py tests/commands/test_tf_dry_run.py`
- [x] 1.2 Implement `extra_args` support and `plan_tf_passthrough` / `build_tf_passthrough_cmd` in `src/devops_cli/tf/tf_plans.py`, update `src/devops_cli/commands/tf.py`, and add help strings in `src/devops_cli/lang/en/help.py`
  - Verification: `$ uv run pytest -n 0 tests/commands/test_tf.py tests/commands/test_tf_dry_run.py tests/tf/`

## 2. Documents & Checks

- [x] 2.1 Update knowledge-base markdown examples referencing `-p`, `-v`, `-o`, or trailing wrapper flags, and regenerate `docs/commands/tf.md` and `docs/CLI_REFERENCE.md`
  - Verification: `$ uv run devops docs generate && uv run devops docs check && uv run devops openspec check`
- [x] 2.2 Run local CI gate, archive the OpenSpec change, and verify clean rebase on `origin/main`
  - Verification: `$ uv run devops ci --check`
