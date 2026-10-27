# Tasks

## 1. Failover help correction

- [x] 1.1 Add a unit test in `tests/test_ai_controller.py` verifying that `devops ai failover --help` describes route recording for virtual models and gateway fallbacks, and run `uv run devops ci test tests/test_ai_controller.py` to confirm failure.
- [x] 1.2 Update `HELP.ai.failover` in `src/devops_cli/lang/en/help.py` and verify `uv run devops ci test tests/test_ai_controller.py` passes.
- [x] 1.3 Run `uv run devops docs generate --sync-readme` and verify `uv run devops docs check` passes.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
