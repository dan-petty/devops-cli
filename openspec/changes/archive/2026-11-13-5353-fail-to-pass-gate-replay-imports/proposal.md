# Proposal: #5353

## Why
`devops ci fail-to-pass` runs the gate row of a changed check module on the base tree with `sys.executable -c "from tests.gate.<row> import main"` and the base tree as the working folder. The interpreter is the one of the head checkout, and its editable install names the `src/` of the head. With `-c`, Python puts the working folder first on the import path, but the package is under `src/`, so `import devops_cli` reads the head source. The base run of a gate row thus runs the head source on the manifests of the base. A fix that changes a list in `src/` and adds the manifest file that the list names, as the fix of #5306 does, then fails gate cases of check modules that the fix does not change, and the command exits 1 also when the real base passes those cases. Closes #5353.

## What Changes
- The gate row script of the replay, `CONST_FAIL_TO_PASS_GATE_ROW_SCRIPT`, puts the absolute path of `src/` in the folder that the row runs in first on `sys.path`, and then runs the script of `CONST_GATE_ROW_SCRIPT`. So the run on each tree imports `devops_cli` from the `src/` of that tree, as `pythonpath = ["src"]` of `pyproject.toml` does for the pytest replay.
- `gate_row_argv` uses the new script. The dry-run plan shows the new script in the two gate row lines.
- CONTRIBUTING.md says that each gate row run imports the code under `src/` of its own tree.
- The rows of `devops ci` keep `CONST_GATE_ROW_SCRIPT`: `uv run python` in the checkout imports the `src/` of that checkout already.

The change fits one pull request.

## Capabilities
- `ci-fail-to-pass` (modified): ADDED requirement "Each gate row run imports the source of its tree".

## Impact
- The base run of a gate row now runs the base source. A fix that changes `src/` and a gate check gets a gate replay that shows only the cases that the fix changes. After the merge, the Fail-to-Pass Check of pull request #5357 (#5306) passes on a new run whose merge commit holds this fix. A re-run of an old run uses the old merge commit and the old code (GitHub re-runs a workflow with the same `GITHUB_SHA`).
- The head run of a named head (`--head <ref>`) now imports the `src/` of the worktree of that head, not the `src/` of the checkout that runs the command.
- No setting, no dependency and no output format changes. Rollback: `git revert`. No downtime.

## Feasibility
- `git show origin/main:src/devops_cli/ci/fail_to_pass.py`: `gate_row_argv` returns `[sys.executable, "-c", CONST_GATE_ROW_SCRIPT.format(module=row)]`, and `_run_gate_row` runs it with `cwd=<tree>` and no environment of its own.
- The `.venv` of a checkout holds `_editable_impl_devops_cli.pth` (the editable install of hatchling), which holds one line: the `src/` of that checkout.
- A probe in a scratch folder with `src/devops_cli/__init__.py` and `tests/gate/probe.py`, which prints `devops_cli.__file__`, ran each script with the interpreter of the worktree: the script of `origin/main` printed the `src/devops_cli/__init__.py` of the worktree, and the new script printed the one of the scratch folder.
- The issue proposes `PYTHONPATH=<tree>/src` in the environment of the run. `run_subprocess` cannot pass it: `build_subprocess_env` raises `SecurityError` for a caller key that matches `CONST_CODE_LOADING_ENV_PATTERNS`, and that tuple holds `PYTHONPATH` (#2205, #2429). The fix keeps that refusal and puts the path in the script, which has the same result.
- The pytest replay gets the source of its tree from `pythonpath = ["src"]` of the `pyproject.toml` of the tree, which pytest puts first on `sys.path`.
- The new test reproduces the fault: on the code of `origin/main`, it failed with `probe gate row: 2 of 2 cases failed on base, 0 of 2 on head` and `A gate case of a check module that the fix does not change fails on base (probe listed.check_each_listed_manifest_exists)`, the form of the CI log of #5357.
- `uv run devops ci fail-to-pass --base origin/main --head <head of #5357>` with the fix exits 0: `k8s gate row: 1 of 114 cases failed on base, 0 of 114 on head (tests/gate/k8s_checks/host_overrides.py)`, and the failed case is `host_overrides.check_open_webui_allows_only_the_origins_of_its_ingress_hosts`.

## Existing Tool Considered
- The standard Python import system covers the need: `sys.path.insert` before the import, which is what pytest does for its `pythonpath` setting. No library is needed.
- `PYTHONPATH` in the environment of the run is the usual tool. The env refusal of `run_subprocess` blocks it, and the design records why the refusal stays.
- `uv run --directory <tree>` would sync a new environment for each tree: it is slow, and it can download packages in the replay.
- Cost to build: about 0.15M tokens to build, 0.01M tokens a quarter to keep and fix, and 1 hour.
- Internal code that the change deletes: none.
