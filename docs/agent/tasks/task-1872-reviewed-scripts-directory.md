# Task: The Scripts Directory May Exist and a Scratch Script in the Project Root Still Fails (#1872)

**Issue**: [#1872](https://github.com/dan-petty/devops-cli/issues/1872)
**Scope**: type/test, scope/ci
**Feasibility**: The author checked this on 2026-10-22 against the tip of `release/v0.2.39`. The old test failed as soon as a `scripts/` directory existed. With `scripts/probe.py` in the tree, it reported `([], True) == ([], False)`. `ruff check .` and `ruff format --check .` read `scripts/probe.py`. These are the two Ruff commands in `get_check_specs` of `src/devops_cli/commands/ci.py`. Ruff found 3 errors and 1 file to reformat, and it read the PEP 723 header without an error. `mypy --strict src` does not read `scripts/`. Bandit does not read it either, because `.bandit` names the targets `src,tests`. Mypy fails on a path that does not exist, with "Cannot read file 'scripts'". Bandit skips a path that does not exist and exits 0. So the mypy target cannot name `scripts` before the directory exists. The tree has no tracked `.sh` file, no `.py` file in the project root and no `scripts/` path. So the new check finds 0 strays.

## Description

The old test `test_no_stray_scripts_in_project_root` made two assertions. The project root holds no `.py` or `.sh` file. The path `scripts/` does not exist. Task 722 added both assertions. In that task, the old `scripts/` sentinel moved into the package and the `scripts/` directory was deleted. The second assertion kept reviewed automation out of the usual place for it.

- **Test.** The second assertion is deleted, so `scripts/` may exist. The first assertion stays as strict as before. A `.py` or `.sh` file in the project root fails the test. So every scratch pattern of the rule still fails there: `tmp*.py`, `scratch*.py`, `debug_*.py`, `test_*.py` and `*.sh`.
- **Helper.** The test calls `_stray_root_scripts(root)`, which has 3 lines. It takes the root as an argument, so two new tests run it on a `tmp_path` root. One test puts a helper script in `scripts/`. The other puts each scratch pattern in the root.
- **Rule.** The `AGENTS.md` bullet is now "Scratch Work Stays Untracked". It names the test that enforces it. It no longer names `<appDataDir>/brain/<conversation-id>/scratch/`, which is a path of one vendor's agent. It allows a committed helper script in `scripts/` as a PEP 723 file. It says that Ruff checks the script.
- **Requirement on the first script's pull request.** Mypy and Bandit read `src` and `tests` only. The pull request that adds the first script adds `scripts` to the mypy and Bandit targets. Mypy fails on a missing path, so that pull request adds the target and the directory together. The `AGENTS.md` bullet states this requirement. The bullet claims no more than the gate checks today.
- **Size.** `AGENTS.md` has 39,981 of 40,000 characters. It had 39,954.
- **Not in this item.** No script moves. This item removes the block and makes no move.

## Acceptance Criteria

- [x] A `scripts/` directory with a helper in it is no stray script. `test_a_reviewed_scripts_directory_is_no_stray_script` checks it. The old test failed on such a tree. The real-tree test `test_no_stray_scripts_in_project_root` passes with a `scripts/helper.py` in the worktree.
- [x] A scratch script in the project root still fails. `test_a_scratch_script_in_the_project_root_is_stray` checks `tmp_x.py`, `scratch_x.py`, `debug_x.py`, `test_x.py` and `x.sh`. A `tmp_x.py` in the real project root made the real-tree test fail with `['tmp_x.py'] == []`.
- [x] The `AGENTS.md` rule claims only what a check enforces. It stays within the 40,000-character cap, and `tests/test_agents_md_claims.py` passes.
- [x] `ruff check`, `ruff format --check`, `mypy --strict src`, `deptry src` and `uv run devops docs check` pass.

## Deliverables

- [x] `tests/test_architectural_invariants.py`: the changed test, the helper and the two new tests.
- [x] `AGENTS.md`: the rule "Scratch Work Stays Untracked".
- [x] `docs/agent/tasks/task-1872-reviewed-scripts-directory.md` and `changelog.d/1872.md`.
