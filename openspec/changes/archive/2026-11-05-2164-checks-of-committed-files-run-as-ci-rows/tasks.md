# Tasks

## 1. Run the checks of the caps and the construct gate in the rows of their tools

- [x] 1.1 Give `lint` the Ruff configuration check (`tests/gate/ruff_config.py`) and `constructs` `ast-grep test` and the construct gate check (`tests/gate/construct_gate.py`) as `also_cmds`
  - Verification: `uv run pytest tests/commands/test_net_construct_rules.py tests/commands/test_ci_gate_rows.py -n 0`
- [x] 1.2 Cut from `tests/commands/test_ruff_complexity_cap.py` and `tests/commands/test_net_construct_rules.py` the cases that start ruff or ast-grep, and keep the cases of the logic with canned settings
  - Verification: `uv run pytest tests/commands/test_ruff_complexity_cap.py tests/commands/test_net_construct_rules.py -n 0`
- [x] 1.3 Move the construct gate escapes of `tests/invariants/test_architectural_invariants.py` to `tests/invariants/test_construct_gate_check.py`, over a tree and a list of tracked files, with no git
  - Verification: `uv run pytest tests/invariants/test_construct_gate_check.py tests/invariants/test_architectural_invariants.py -n 0`
- [x] 1.4 Run both modules by hand: `uv run python -c "import sys; from tests.gate.ruff_config import main; sys.exit(main())"` and the same for `construct_gate`
  - Verification: `uv run devops ci --check --only lint,constructs`

## 2. Run the kustomize checks as the k8s row

- [x] 2.1 Move the 45 tests that read a `kubectl kustomize` render of a committed directory to `tests/gate/k8s_checks/` as `check_*` functions, with `tests/gate/k8s_render.py` and the runner `tests/gate/runner.py`; delete `tests/core/test_k8s_runner.py` and `tests/k8s/test_k8s_job_admission_policy.py`
  - Verification: `uv run python -c "import sys; from tests.gate.k8s import main; sys.exit(main())"`
- [x] 2.2 Add the row `k8s`, and give `NOT_IN_RUNNER` the reason of `kubectl`
  - Verification: `uv run pytest tests/commands/test_ci_gate_rows.py tests/roadmap/test_roadmap_runner_tools.py -n 0`

## 3. Run the invariants over the Python files as the test-tree row

- [x] 3.1 Move the six invariants that parse `tests/`, with their self-tests, to `tests/gate/tree_checks/`; delete `tests/invariants/test_test_module_independence.py`; remove the two fixtures that nothing reads from `tests/support/trees.py`; remove the test of selection that read the deleted module from `tests/commands/test_test_selection.py`
  - Verification: `uv run python -c "import sys; from tests.gate.tree import main; sys.exit(main())"`
- [x] 3.2 Add the row `test-tree`, and reserve `tests/gate` in `tests/invariants/test_source_tree.py`
  - Verification: `uv run pytest tests/invariants/test_source_tree.py tests/commands/test_ci_gate_rows.py -n 0`

## 4. Run the startup budget as a row

- [x] 4.1 Move the 55 probes of `tests/commands/test_cli_startup_imports.py` to `tests/gate/startup_imports.py`, four at a time, with the four limits, the control, the ten slowest imports in a failure and the CPU time in the output; keep the AST test and give the logic of the row its own cases
  - Verification: `uv run pytest tests/commands/test_cli_startup_imports.py -n 0`
- [x] 4.2 Add the row `startup-imports`
  - Verification: `uv run python -c "import sys; from tests.gate.startup_imports import main; sys.exit(main())"`

## 5. Run the swallowed-failures ratchet as a row

- [x] 5.1 Move `tests/invariants/test_swallowed_failures_ratchet.py` to `tests/gate/swallowed_failures.py` with a `main` that checks and lowers; keep the cases of its logic in `tests/invariants/test_swallowed_failures_check.py`
  - Verification: `uv run pytest tests/invariants/test_swallowed_failures_check.py -n 0`
- [x] 5.2 Add the row `swallowed-failures`
  - Verification: `uv run python -c "import sys; from tests.gate.swallowed_failures import main; sys.exit(main())"`

## 6. Check that no pytest test starts the tools

- [x] 6.1 Show one failing case for each row in the pull request comment
  - Verification: `uv run devops ci --check --only lint,constructs,k8s,test-tree,startup-imports,swallowed-failures`
- [x] 6.2 Show that no test of the files in the table starts ruff, ast-grep or a fresh interpreter, and that no test reads a render of a committed directory
  - Verification: `! git grep -n -E 'tests\.k8s_manifests|"ast-grep", "(test|scan)"' -- tests`

## 7. Update the documents

- [x] 7.1 Name the rows and `tests/gate/` in `docs/TESTING.md`, and the new places of the checks in `CONTRIBUTING.md` and `docs/SDLC.md`; regenerate the references
  - Verification: `uv run devops docs check`

## 8. Finish

- [x] 8.1 Show the time of each CI job and the figure of the pytest run before and after, in the pull request comment
  - Verification: `uv run devops ci job-time --help`
- [x] 8.2 Run the whole gate
  - Verification: `uv run devops ci`
