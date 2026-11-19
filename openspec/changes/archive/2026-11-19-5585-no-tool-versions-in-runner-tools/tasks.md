# Tasks

## 1. The check of the runner image compares no copied version (behavior)

- [x] 1.1 Write the failing tests in `tests/roadmap/test_roadmap_runner_tools.py`: a tool that `Dockerfile` or `tools.lock` pins passes on any version that its command prints, and the check runs only its version command; a dev dependency fails with the message `runner_tool_other_version` when it prints another version than its installed distribution; `main` prints `All <n> runner tools are on PATH and run.`. Delete the tests that compare pins or read `tools.lock`, and the tests of the link check of a tool of the lock.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py`
- [x] 1.2 In `src/devops_cli/roadmap/runner_tools.py`, delete `UV_VERSION`, `GH_VERSION`, `NODE_MAJOR`, `ACTIONLINT_VERSION`, `RunnerTool.pin`, the Python pin, `_pin_failure`, `TOOLS_DIR`, `TOOLS_BIN_DIR`, `USER_DATA_ROOT_VARIABLE`, the `IMAGE_PIN` and `TOOLS_LOCK` branches of `expected_text`, and the imports of `DEFAULT_PYTHON_VERSION` and `load_tools_lock`. In `src/devops_cli/lang/en/messages.py`, delete `runner_tool_off_pin`, rename `runner_tool_version` to `runner_tool_other_version`, and change `runner_tools_ready`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py tests/invariants/test_runner_hooks.py tests/roadmap/stage/test_roadmap_stage_context.py`
- [x] 1.3 Lower the count of `tests/roadmap/test_roadmap_runner_tools.py` in `tests/gate/tree_checks/config_reads.toml` to the tests that still read a committed file.
  - Verification: `$ uv run devops ci --check --only test-tree`

## 2. Renovate writes no tool version into src

- [x] 2.1 In `.github/renovate.json`, delete the custom managers of `UV_VERSION` and `NODE_MAJOR`, remove the runner tools table from the descriptions of the `uv` and `node` groups and of the `src/devops_cli/**` rule, and delete the rule of the group `gh`, which matches no dependency.
  - Verification: `$ ! git grep -n -E 'runner_tools|runner tools table|cli/cli' -- .github/renovate.json`
- [x] 2.2 Confirm that no Python file under `src/` holds a copy of the uv, gh, Node or actionlint version.
  - Verification: `$ ! git grep -n -E '^(UV|GH|ACTIONLINT)_VERSION|NODE_MAJOR' -- src`

## 3. Documents

- [x] 3.1 Describe the presence check in the comment of the smoke step of `Dockerfile` and in `docs/CLUSTER.md`, and the managers and groups in `docs/SDLC.md`.
  - Verification: `$ uv run devops ci --check --only docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
