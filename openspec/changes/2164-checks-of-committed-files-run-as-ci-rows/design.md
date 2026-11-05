# Design

## Decisions

- **A check is a function that asserts, and a runner calls it.** The moved checks keep their bodies. `tests/gate/runner.py` imports each module of a package, calls each `check_*` function, expands its `pytest.mark.parametrize` marks with the public mark API of pytest, gives it `tmp_path` and the fixtures the row names, and prints the failures with the last frames of the trace. A failed assert or `pytest.fail` is a failure; any other exception is a failure with a longer trace. Evidence: 81 cases of the `k8s` row pass in 5 s, and each case that was a pytest test keeps its name.
- **The code of the rows lives in `tests/gate/`, not in `tests/support/`.** `tests/support/bootstrap.py` imports, at the start of each pytest process, every support module that imports pytest or another support module (`_may_hand_pytest_a_plugin`). The first try put the check modules in `tests/support/`, and each pytest worker then imported `devops_cli.main` and all the checks for nothing. `tests/gate/` is not walked. `tests/invariants/test_source_tree.py` reserves the directory.
- **Rows with an existing tool join the row of that tool.** Ruff configuration checks go to `lint` and `ast-grep test` with the construct gate checks go to `constructs`, as `also_cmds` (the field exists: `security` uses it). Each `also_cmds` command is a process of its own, and the row passes when all exit 0.
- **The construct gate check takes the tracked files as a list.** The check of the committed files needs to know which files git tracks. `tracked_files()` runs `git ls-files` once for the row; the cases of the pytest file give the list. The cases that made a git repository in a temporary directory go: they tested `git ls-files`.
- **One scan checks all rules.** The old tests ran `ast-grep scan` 42 times, once for each rule and tree. The row writes one file for each violation in its tree and one in the other tree, scans once, and compares the rule ids reported for each file with the table.
- **The Ruff behavior tests go, and the probe stays.** The tests that built a project with a weakened `pyproject.toml` or a nested configuration file tested Ruff. The settings check names a weakened cap, and the invocation test (kept in pytest, it starts no program) pins `--config pyproject.toml` on every `ruff check`. A probe of three functions with the real table keeps the two scenarios of `lint-nesting-cap`: five nested blocks fail, four pass, and complexity 11 fails.
- **The startup row runs four probes at a time.** Each probe is one fresh interpreter. A module that one argv imports stays in `sys.modules`, so two argvs cannot share an interpreter. `-X importtime` stays: paired runs of #2369 show a ratio of 0.97 to 1.02. The row prints the CPU time of the probes (`RUSAGE_CHILDREN`), which is the figure that #2369 asks for, because the wall time moves with the load of the host.
- **The `tests/`-parsing invariants share one parse.** The row passes `parse_source_trees`, `parse_test_trees` and `parse_repo_trees` of `tests/support/trees.py` as fixtures. Each is made once, and the file cache of `parse_python_file` parses each file once. The test `test_every_source_file_is_parsed_at_most_once` stays in pytest for `parsed_source_trees`.
- **Tests that start a program on a temporary tree stay.** The tests of `check_argocd_gate`, of the image pins and of `deploy-stack` render a tree that the test builds, to test the behavior of `src/`. They check no committed file, and the issue limits itself to committed files and configuration. `conftest.py` keeps its allowance of `kubectl kustomize` for them.

## Existing code to reuse or keep passing

- `CheckSpec.also_cmds` and the executor of `devops ci`; the `git` and `test-settings` rows as the model of a row that runs a `python -c` command.
- `tests/support/trees.py`, `tests/support/paths.py`, `tests/support/fakes/process.py`.
- Tests that must keep passing: `tests/commands/test_ci.py`, `tests/commands/test_ci_dry_run.py`, `tests/roadmap/test_roadmap_runner_tools.py`, `tests/invariants/`.

## Rejected alternatives

- **Run the moved files as pytest in a row.** Rejected: the criterion says no pytest test starts `kubectl`, and each worker would render again.
- **Keep the checks in `tests/support/`.** Rejected: measured above; each pytest process imports them.
- **Render every kustomization in a parallel prefetch.** Rejected: the whole row runs in 5 s with lazy renders.
- **Cut `-X importtime` from the startup probes.** Rejected by #2369: the ratio with and without the flag is noise, and the flag gives the slowest imports for the failure message.
