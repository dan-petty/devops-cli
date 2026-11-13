# Design

## Decisions

### The script puts the `src/` of its working folder first on the import path
`CONST_FAIL_TO_PASS_GATE_ROW_SCRIPT` is `import os, sys; sys.path.insert(0, os.path.abspath('src'))` followed by `CONST_GATE_ROW_SCRIPT`. The replay runs the row with the tree as the working folder, so the path is the `src/` of the tree. It goes before the empty entry that `-c` adds for the working folder, and before `site-packages`, where the `.pth` file of the editable install adds the `src/` of the checkout that runs the command. The path is absolute when the run starts, so a check that changes the working folder later does not change where `devops_cli` comes from. The argv stays the same for each tree, so the dry-run plan keeps its form and needs no new placeholder.

### The rows of `devops ci` keep their script
A row of `devops ci` runs `uv run python -c` in the checkout, and `uv run` uses the environment of that checkout, whose editable install names the same `src/`. The change does not touch that script, so the rows of the gate stay as they are.

### The test runs a real gate row
The floor allows a real `python` child in a test with `@pytest.mark.live("python")`. The fixture `head_source_interpreter` writes a checkout with a gate row `probe` and the real `tests/gate/runner.py`, and the base tree that the git fake adds. It answers each gate row run with a real child of `sys.executable`, in the environment that `build_subprocess_env` gives, plus `PYTHONPATH=<head>/src`. That entry comes after the working folder and before `site-packages`, as the editable install of a checkout does, so the child finds the head source unless the script puts the tree source first. The check module `listed`, which the fix does not change, asserts that each manifest of the list in `src/` exists under `k8s/`. With the head source on the base tree it fails, as the four unchanged cases of #5357 failed.

## Rejected alternatives

- **`PYTHONPATH=<tree>/src` in the `env` of `run_subprocess`.** Rejected: `build_subprocess_env` refuses a caller override of `PYTHONPATH` with `SecurityError` (`CONST_CODE_LOADING_ENV_PATTERNS`, #2205, #2429). An exception for this caller would weaken a security control, which only the owner can allow.
- **The path as an argument (`sys.path.insert(0, sys.argv.pop(1))` and `<tree>/src` in the argv).** Rejected: the plan of `--dry-run` would need a placeholder for the working tree of `HEAD`, which `plan_fail_to_pass` does not know, and the result is the same.
- **`uv run --directory <tree> python -c ...`.** Rejected: uv syncs a new environment for each tree, which is slow, writes a `.venv` in the tree, and can download packages.
- **The same change in `CONST_GATE_ROW_SCRIPT`, for the rows of `devops ci` too.** Rejected: the rows already import the source of their checkout through `uv run`, and the change would change the gate for no gain in this issue.
- **A test that compares the argv only.** Rejected: it shows the text of the script, not where the child imports `devops_cli` from. The live test shows the import itself.
