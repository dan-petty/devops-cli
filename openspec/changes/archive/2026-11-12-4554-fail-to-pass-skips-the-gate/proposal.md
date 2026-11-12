# Proposal: #4554

## Why
`devops ci fail-to-pass` reads only `tests/**/test_*.py` files (#4554). A fix of a manifest proves itself with a case of a gate check in `tests/gate/k8s_checks/`, which the `k8s` row of `devops ci` runs. The command does not run gate checks. Thus it exits 1 for each manifest fix, also when the changed check fails on the base and passes on the head. AGENTS.md rule 4 tells each fix pull request to cite this run, so PR #4514 and PR #4551 wrote their `k8s` row runs by hand. The workflow also does not start for a change to a gate check, and its comment says that only `src/` can make a test fail on base.

## What Changes
- `devops ci fail-to-pass` also lists the added or changed modules of `tests/gate/<row>_checks/`. For each row of these modules, it runs `tests.gate.<row>` on the base tree with the tests of the head, and on the head tree. Then it compares the failed cases of the two runs.
- A case of a changed check module that fails on the base and does not fail on the head proves the fix, when the two runs count the same cases.
- A base failure in a check module that the fix does not change refuses the replay. A row run that writes no case summary, or that exits with a status other than 0 or 1, could not run and refuses the replay.
- The command is satisfied when the test replay or the gate replay proves the fix, and no replay refuses. The test replay of a fix that changes no gate check is the same as before.
- The dry run lists the gate row runs.
- `.github/workflows/fail-to-pass.yml` also starts for a change under `tests/gate/*_checks/`, and its comment says that a changed gate check can fail on the base.
- CONTRIBUTING.md, the help of the command, the generated README and CLI reference, and the Purpose of the `ci-fail-to-pass` spec name the gate replay.

## Capabilities
- Modified: `ci-fail-to-pass`.

## Impact
- A fix pull request that changes a gate check gets a `Fail-to-Pass Check` run that proves or refuses the fix. The check is not a required check of `main` (ADR 0014), so it blocks no merge.
- The replay of a gate row needs `kubectl` for the `k8s` row. The `ubuntu-26.04` runner image has `kubectl`, as the `Static Analysis Quality Gate` step of `ci.yml` uses it with no install.
- The gate modules that print their own problem lines (`ruff_config`, `construct_gate`, `startup_imports`, `swallowed_failures`) are not replayed. Issue #4596 covers them.

## Feasibility
- `src/devops_cli/ci/fail_to_pass.py`: `is_test_file` keeps only `tests/**/test_*.py`, and `changed_test_files` filters the diff with it. Thus a module of `tests/gate/k8s_checks/` never gets to the replay, and the report says `The fix changes no tests/**/test_*.py file.`
- `tests/gate/runner.py`: `main` prints `<row>: <module>.<check>[<case>] failed:` on stderr for each failed case, and `<row>: N cases, M failed` on stdout. It imports every check module before the first case, so a module that cannot import stops the run with a traceback and no summary.
- `tests/gate/k8s.py` runs the package `tests.gate.k8s_checks`, and `tests/gate/tree.py` runs `tests.gate.tree_checks`. Thus the name of the check directory less `_checks` is the gate module.
- `tests/support/paths.py` takes `REPO_ROOT` from the `tests` package. Thus a row that runs with its working directory in another tree reads the files of that tree.
- Command output: `uv run python -c "import sys; from tests.gate.k8s import main; sys.exit(main())"` in a worktree of `origin/main` printed `k8s: 107 cases, 0 failed` in 115 s with kubectl from the PATH.
- PR #4551 (`b835d3ca`) changed `k8s/otel/values.yaml` and `tests/gate/k8s_checks/otel_collector.py` and no `tests/**/test_*.py` file. With the change, `devops ci fail-to-pass --base b835d3ca~1 --head b835d3ca` named `otel_collector.check_the_trace_pipeline_deletes_gateway_key_data_before_tempo` as failed on base and passed on head. It exited 1, because `deploy_stack.check_prometheus_operator_crds_install_before_every_service_monitor` failed on both trees: both runs import the `devops_cli` of today, and that check compares a table of today's `src/` with the old manifests. The same two file changes, undone and done again on top of this branch, gave `k8s gate row: 1 of 107 cases failed on base, 0 of 107 on head` and exit 0.

## Existing Tool Considered
`git worktree` checks out the base and head trees, `pytest` replays the changed test modules, and `tests/gate/runner.py` runs the checks of a row. No tool maps a changed `tests/gate/<row>_checks/` module to its row, runs that row on two trees and compares the failed cases: that comparison is specific to the gate rows of this repository. The change builds it in `src/devops_cli/ci/fail_to_pass.py`. Cost: about 20,000 output tokens to write the code and its tests, about 2,000 tokens each month to keep and fix it, and about 2 hours of elapsed time. The change deletes no internal code.
