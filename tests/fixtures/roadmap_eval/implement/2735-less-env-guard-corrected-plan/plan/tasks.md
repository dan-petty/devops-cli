# Tasks

## 1. Add LESS to the denied patterns and test it

Reads: none. Changes: `src/devops_cli/config/constants.py`, `tests/core/test_subprocess_env_boundary.py`.

- [ ] 1.1 Write a test that calls build_subprocess_env with env={"LESS": "+!x\n"} and asserts SecurityError is raised with the message "Prohibited dangerous environment variable override: 'LESS'". Add a second case with isolate_env=False. Add a third case asserting env={"LESSOPEN": "|x %s"} still raises SecurityError, and verify that `uv run devops ci test tests/core/test_subprocess_env_boundary.py` fails on the base
- [ ] 1.2 Add the string "LESS" to the tuple CONST_CODE_LOADING_ENV_PATTERNS in src/devops_cli/config/constants.py, beside the existing entries LESSOPEN and LESSCLOSE, and verify that `uv run devops ci test tests/core/test_subprocess_env_boundary.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
