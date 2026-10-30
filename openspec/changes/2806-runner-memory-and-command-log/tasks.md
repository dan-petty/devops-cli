# Tasks

## 1. The memory limit and the worker bound of the runner Job

- [x] Write failing tests in `tests/test_k8s_runner.py`: the memory limit of the runner is 8 Gi and its request is 4 Gi; `PYTEST_XDIST_AUTO_NUM_WORKERS` equals the CPU limit; the Job that the template makes passes the admission policy.
  - Verification: `uv run devops ci test tests/test_k8s_runner.py tests/test_k8s_job_admission_policy.py`
- [x] Change `k8s/devops/cronjob-runner.yaml`: memory limit 8 Gi, the worker variable, and the comments. Change `k8s/README.md` and `docs/ROUTINE_TASKS.md` where they state the numbers.
  - Verification: `uv run devops ci test tests/test_k8s_runner.py tests/test_k8s_job_admission_policy.py`

## 2. The shell takes the worker bound

- [x] Write the failing tests in `tests/test_roadmap_implement_step.py`: the shell environment holds the variable of the process, and holds none when the process has none.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py`
- [x] Change `shell_environment` in `src/devops_cli/roadmap/implement_step.py`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py`

## 3. The tool log names the command

- [x] Write the failing tests in `tests/test_roadmap_implement_tool_log.py`: the start line comes before the call runs; a long command is cut; a secret is masked; a control character stays on one line; an unknown first word shows as `other`; a call with no command writes no start line. Update the tests that read all lines.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_tool_log.py`
- [x] Change `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/lang/en/messages.py` and `src/devops_cli/config/constants.py`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_tool_log.py tests/test_roadmap_implement_step.py`

## 4. Review findings

- [x] Write the failing test in `tests/test_subprocess_env_boundary.py` and add `PYTEST_XDIST_AUTO_NUM_WORKERS` to `DEFAULT_ALLOWED_ENV_VARS`, so that the `pytest` of `devops ci` gets the bound.
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py`
- [x] Write the failing tests for `name=value`, free text and flag arguments in `tests/test_roadmap_implement_tool_log.py`, and mask them in `logged_command`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_tool_log.py`
- [x] Lower the memory limit to 8 Gi so that it fits the smallest node, and name the unproven command in the proposal.
  - Verification: `uv run devops ci test tests/test_k8s_runner.py tests/test_k8s_job_admission_policy.py`
- [x] Fix the statements about the variables of the shell in the spec of `roadmap-implement-job`, `k8s/README.md` and `docs/ROUTINE_TASKS.md`.
  - Verification: `uv run devops openspec check`

## 5. The documentation

- [ ] Regenerate the documentation.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 6. Archive

- [ ] Archive the change.
  - Verification: `uv run devops openspec archive 2806-runner-memory-and-command-log`
