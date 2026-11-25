# Tasks

## 1. Behavior

- [x] 1.1 Write failing offline tests for `PlanDriftResult`, unlocked/saved-plan `read_plan_drift` flags, `checks` (`fail`/`error`/`unknown`), plan errors, exit codes `0`/`1`/`2` (including check precedence over drift and `--format json`), and `--help` text in `tests/tf/test_tf_analysis.py`
  - Verification: `$ uv run pytest -n 0 tests/tf/test_tf_analysis.py`
- [x] 1.2 Add `PlanDriftResult` in `src/devops_cli/models/tf.py`, update `read_plan_drift`/`parse_plan_checks`/`detect_drift` in `src/devops_cli/tf/analysis.py`, update `tf_drift` and messages in `src/devops_cli/commands/tf.py` and `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run pytest -n 0 --cov=src tests/tf/test_tf_analysis.py tests/commands/test_tf.py tests/commands/test_tf_dry_run.py`

## 2. Documents

- [x] 2.1 Regenerate command documentation (`docs/commands/tf.md`) and run local checks
  - Verification: `$ uv run devops docs generate && uv run devops docs check && uv run devops openspec check`
