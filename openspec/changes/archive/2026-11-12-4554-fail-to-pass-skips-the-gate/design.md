# Design

## Decisions
- **Row from the check directory.** A changed module directly under `tests/gate/<row>_checks/`, other than `__init__.py`, belongs to the gate module `tests.gate.<row>`. `tests/gate/k8s.py` runs `k8s_checks` and `tests/gate/tree.py` runs `tree_checks`, so no table needs an update for a new row that uses the runner.
- **Base tree with the head's tests.** The base run uses the tree that the pytest replay uses: the merge base as a detached worktree with the `tests/` of the head on it. Thus the check code of the head reads the manifests and source files of the base.
- **Head tree.** For `HEAD`, the head run uses the working tree, so a fix that is not committed counts. For a named head, it uses a detached worktree of that head, so both runs use the check code of the same head.
- **Same interpreter on both trees.** Each run is `python -c "import sys; from tests.gate.<row> import main; sys.exit(main())"` with the interpreter of the command and the tree as its working directory, as `devops ci` runs the row. Both runs import the same `devops_cli`, so a check that takes its cases from a constant has the same cases on both trees.
- **Compare the failed case IDs.** The command reads the `<row>: <case> failed:` lines and the `<row>: N cases, M failed` summary of each run. A case of a changed module that fails on the base and is no failure on the head proves the fix, when the two runs count the same cases. The count refuses a fix that deletes the failing case.
- **A failure of an unchanged module refuses the replay.** It mirrors the rule of the test replay for a test that the fix does not change: a fix does not pass on a base that another change broke.
- **A run with no summary could not run.** A row run that exits with a status other than 0 or 1, or that prints no summary, refuses the replay. The report names the row, the tree, the exit status and the last lines of the output.
- **Either replay proves the fix.** The command is satisfied when no replay refuses and the test replay or the gate replay proves the fix. The report keeps the test lines as before and adds the lines of the gate rows after them.

## Rejected alternatives
- **Row from the check table of `devops ci`.** The table maps `ruff_config`, `construct_gate`, `startup_imports` and `swallowed_failures` to rows, but these modules print their own problem lines and no case IDs or summary (`tests/gate/ruff_config.py`, `tests/gate/startup_imports.py`). Issue #4596 covers them.
- **Run every row.** The `k8s` row took 115 s on one tree. Every row on two trees for one changed module takes minutes more and proves nothing more.
- **Put the `src/` of the tree first on the import path.** `tests/gate/k8s_checks/host_overrides.py` takes its cases from `CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS`. With the `src/` of each tree, a fix that adds an application changes the case count, and the base run fails to import a check that uses a name that the fix adds.
- **Compare the failed totals.** A fix that changes one failure for another keeps the same total.
- **Require the whole row to pass on the head.** A failure that the fix does not touch then refuses a valid replay.
- **Always use the working tree for the head.** With `--head feature`, the base run then holds the checks of `feature` and the head run the checks of the working tree.
- **Start the workflow for `tests/gate/**` or `k8s/**`.** A change to a gate module that is not a check package, or to a manifest only, has no check that the command can replay, so the check fails with no proof.
