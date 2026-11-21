# Tasks

## 1. The plain publish

Kind: behavior.

- [x] 1.1 Write failing tests: a patch in a fixed format that no diff setting changes; a patch up to a commit; two commits of the bot on a base other than the old tip; a new branch only where none is; the new tree read from its objects; a second publish of the same tree with no push; the delete of a branch that `publish` made; the plain clone of the issue branch, with no refused setting
  - Verification: `$ uv run devops ci test tests/roadmap/phases`
- [x] 1.2 Write the patch with fixed format flags, apply the patches with `git apply --index` in a new repository, clone the issue branch plainly (`phases/checkout.py`), and move fix-checks onto them with no URL carry and no `--source`
  - Verification: `$ uv run devops ci test tests/roadmap/phases tests/roadmap/steps/test_roadmap_step_fix_checks.py tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py tests/commands/test_roadmap_step_fix_checks.py`

## 2. Documents

Kind: other.

- [x] 2.1 State the plain flow in ADR 0030, and regenerate the documentation
  - Verification: `$ uv run devops ci docs`
