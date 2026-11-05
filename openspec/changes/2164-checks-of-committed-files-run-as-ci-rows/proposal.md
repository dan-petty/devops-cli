# Proposal

## Why

Issue #2164: some pytest tests check committed files and the configuration of tools. They start ruff, ast-grep, `kubectl kustomize` or a fresh Python interpreter, or they parse every file under `tests/`. The rule of 2026-10-24 (ADR 0007 as #2143 amends it) says that a check of committed files is a row of `devops ci`, and that a test of `src/` starts no program. These checks also cost time in every pytest run, because each xdist worker repeats them.

## What Changes

- `devops ci` gets a package of check modules, `tests/gate/`, one module for each row. A runner (`tests/gate/runner.py`) calls the functions named `check_*` of a package, with `pytest.mark.parametrize` marks and `tmp_path`, and prints the failures.
- The `lint` row also runs the Ruff configuration check (`tests/gate/ruff_config.py`): the resolved settings of Ruff, the walk of Ruff against the files that git tracks, and a probe of the two caps.
- The `constructs` row also runs `ast-grep test --skip-snapshot-tests` and the construct gate check (`tests/gate/construct_gate.py`): one scan of a scratch project that holds one violation of each rule in its tree and in the other tree, and the checks of the committed files (`sgconfig.yml`, the rules and their cases, the scan command of the row and of the hook, the ignore files, the ban of the address APIs).
- Four new rows: `k8s` (the 45 tests that read a `kubectl kustomize` render, now 81 cases that share each render), `test-tree` (the six invariants that parse `tests/`, with their self-tests), `startup-imports` (the 55 probes of the startup budget) and `swallowed-failures` (the ratchet).
- Each pytest file keeps the cases that test the logic of a check with canned input or a small tree, and no case starts a program. The pytest cases that started ruff, ast-grep, git, kubectl or an interpreter to check a committed file go. `trees.py` loses the two fixtures that nothing reads.
- The `startup-imports` row drops the test that ran the budget under CPU load: the module counts do not depend on load, and the test started eight busy processes.
- The row commands are observable through `devops ci --only <row>`, so the change carries a spec delta, `ci-gate-rows`.
- The documents that named the old tests change: `CONTRIBUTING.md`, `docs/SDLC.md` and `docs/TESTING.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `ci-gate-rows`: which checks of committed files and tool configuration run as rows of `devops ci`.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/commands/ci.py` (rows), `src/devops_cli/lang/en/messages.py` (row titles), `src/devops_cli/roadmap/runner_tools.py` (the programs that the rows need).
- New: `tests/gate/` (`runner.py`, `ruff_config.py`, `ruff_selection.py`, `construct_gate.py`, `k8s.py`, `k8s_render.py`, `k8s_checks/`, `tree.py`, `tree_checks/`, `startup_imports.py`, `swallowed_failures.py`).
- Tests that lose cases or move them into the rows: `tests/commands/test_ruff_complexity_cap.py`, `tests/commands/test_net_construct_rules.py`, `tests/commands/test_cli_startup_imports.py`, `tests/commands/test_test_selection.py`, `tests/invariants/test_architectural_invariants.py`, `tests/invariants/test_k8s_argocd_apps.py`, `tests/invariants/test_k8s_manifests.py`, `tests/commands/k8s/`, `tests/k8s/test_k8s_argocd_overrides.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/config/test_k8s_devops_runtime.py`, `tests/tools_lock/test_k8s_argo_workflows.py`, `tests/server/routes/test_k8s_roadmap_service.py`; deleted: `tests/core/test_k8s_runner.py`, `tests/k8s/test_k8s_job_admission_policy.py`, `tests/invariants/test_test_module_independence.py`, `tests/invariants/test_swallowed_failures_ratchet.py`.
- Documents: `CONTRIBUTING.md`, `docs/SDLC.md`, `docs/TESTING.md`.

## Acceptance

- No pytest test starts ruff, ast-grep, kubectl or a fresh interpreter to check a committed file or a configuration: groups 1 to 6.
- Each check runs as a row and fails on the input that failed its test: the pull request comment shows one failing case for each row.
- The rows are in the table of `devops ci`: group 7. The help of `devops ci` and the generated references list commands, and they have never listed rows (the `git` and `test-settings` rows are not in them either); `devops ci --only <wrong>` lists the valid row names.
- The time of each CI job before and after, and the pytest figure, are in the pull request comment.
- `uv run devops ci` passes: task 8.2.

## Feasibility

Checked on 2026-11-04 at `origin/main` (1ad0e59a).

- The premise holds, and the paths of the issue are stale. `git grep -n 'subprocess.run' -- tests` and the lists of `tests/k8s_manifests.py` users show the tests that start `kubectl kustomize`: 13 files and 45 tests. The ruff and ast-grep tests are in `tests/commands/test_ruff_complexity_cap.py` and `tests/commands/test_net_construct_rules.py`. The startup file is `tests/commands/test_cli_startup_imports.py`, as #2369 says.
- `uv run ast-grep test --skip-snapshot-tests` runs the 19 rule tests in under a second. `ruff check --config pyproject.toml --show-settings` runs in 0.05 s. A scan of a scratch project with 42 files runs in under a second.
- `ruff`, `ast-grep` and Python come from `uv sync`. `kubectl` is on the GitHub runner image: the Argo CD gate and the `Image Pins` job of `ci.yml` use it. The image of the roadmap Job holds no `kubectl` (`NOT_IN_RUNNER`), and the Job runs the scoped tests and hooks, not the rows, so it never runs the `k8s` row. The reason in `NOT_IN_RUNNER` says so.
- `tests/support/bootstrap.py` imports at the start of every pytest process each support module that imports pytest or another support module. The check modules therefore live in `tests/gate/`, which the bootstrap does not walk. `tests/invariants/test_source_tree.py` lists `gate` as a reserved directory.
- Measured on one host at a load of 8 to 26: the 55 probes of the startup row take 57 to 71 s of CPU time (53 to 64 s user), against 76 to 129 s of CPU time for the 57 tests of the old file. The goal of #2369, at most half of the old CPU time by a cut of the import of `main` or of the work of the help, is not reached: the row moves the cost and runs it four at a time. The change files one item for it (see Workflow follow-up).
- AGENTS.md rule 5 allows 5 minutes for a job. The new rows run in the `Static Analysis` job (`--skip test,outdated,actionlint`). The startup row runs four probes at a time. The times of the job before and after are in the pull request comment.

## Existing Tool Considered

`devops ci` rows, ruff, `ast-grep test`, `kubectl kustomize` and `pytest` itself cover the need, as the issue says. The runner `tests/gate/runner.py` is 120 lines. It expands the `pytest.mark.parametrize` marks with the public mark API of pytest (`Mark`, `ParameterSet`) and the fixture `tmp_path`, so the 45 moved checks keep their asserts, their names and their cases. Rejected: `pytest` run as a row over the moved files. The acceptance criterion forbids a pytest test that starts `kubectl`, and a pytest row would repeat the render for each worker. The runner has no plugin system, no fixture scope and no report; each of those the checks do not use. The change deletes the pytest copies of the checks.

## Workflow follow-up

- The startup budget costs 57 to 71 s of CPU time and does not reach the half of the old figure: a cut of the import of `devops_cli.main` or of the work of the help is a separate item, #3550.
