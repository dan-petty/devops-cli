# Proposal

## Why

The check `Changed-Test Independence` runs each changed test file three times in one process, so its time grows with the number of changed test files. On pull request #6562 one pass took 454 s and GitHub cancelled the second pass at the job limit, so the check gave no result at all. Issue #6564 asks for a pass or fail result under the 5 min + 1 min bound of AGENTS.md rule 5, with the same tests, the same three shuffled passes and no higher timeout.

## What Changes

- `devops ci test` takes the options `--shard` and `--shards` and passes only the files of its shard to pytest, weighed by the recorded seconds that `devops ci durations` writes.
- The new `shard_paths` splits a given list of test files across the shards, and `shard_test_files` calls it for the whole suite, so both splits weigh the same recorded seconds.
- A sharded `--repeat` run passes only its shard's files to each of its passes.
- A shard that holds no file exits 0 and starts no pytest, so an empty shard never runs the whole suite.
- The job `changed-tests` is a matrix of eight shard jobs named `Changed-Test Independence (shard <n> of <total>)`, each with its own tooling cache key and a 12-minute test step under the 15-minute job limit.
- The new job `changed-tests-result`, named `Changed-Test Independence`, needs the matrix and ends red when the matrix does not succeed.
- The workflow parity allowlist of `tests/commands/test_ci.py` holds the row of the aggregate step.
- The generated page `docs/commands/ci.md` holds the two new options of `devops ci test`.
- The check keeps the same three shuffled passes over the same changed test files, and raises no timeout.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-test-shards`: The test command runs one shard of the files it selects, Each repeat pass of a shard runs the files of that shard, The workflow runs Changed-Test Independence in shards

## Impact

- Code: `src/devops_cli/core/test_selection.py`, `src/devops_cli/commands/ci.py`, `.github/workflows/ci.yml`
- Documents: `docs/commands/ci.md`
- Tests: `tests/commands/test_ci_shard.py`, `tests/commands/test_ci_repeat.py`, `tests/commands/test_ci.py`

## Feasibility

- The probes say "The path `.github/workflows/ci.yml` is a file of the staging commit.", so the workflow that holds the check is in the staged tree.
- `read_file` read lines 750-835 of that workflow, and the range holds `.github/workflows/ci.yml:757:changed-tests:`, `.github/workflows/ci.yml:758:name: Changed-Test Independence`, `.github/workflows/ci.yml:764:timeout-minutes: 15`, `.github/workflows/ci.yml:775:- name: Detect Changed Test Files` and `.github/workflows/ci.yml:804:uv run devops ci test --repeat 3 -- "${CHANGED_TESTS[@]}"`, so one job holds the check, one step lists the changed test files, and one step runs them.
- That range also holds `.github/workflows/ci.yml:794:cache-suffix: changed-tests` and `.github/workflows/ci.yml:796:compile-bytecode: "false"`, so one process runs every changed file three times and its time grows with the number of changed files.
- `read_file` read lines 2250-2345 of the test command module, and the range holds `src/devops_cli/commands/ci.py:2284:def test(`, `src/devops_cli/commands/ci.py:2296:int, typer.Option("--repeat", min=0, help=HELP.ci.repeat)` and `src/devops_cli/commands/ci.py:2325:_run_shuffled_repeats(_build_test_cmd("0", verbose, k, x, None), targets, repeat, seed)`, so the command takes no shard option and runs every pass over all of its targets.
- That range also holds `src/devops_cli/commands/ci.py:2268:if targets is None:` and `src/devops_cli/commands/ci.py:2269:print_error(MESSAGES.ci.repeat_needs_targets, prefix=False)`, so a repeat run refuses no target and a shard's file list is the one argument that narrows each pass.
- `read_file` read lines 1815-1865 of the gate command, and the range holds `src/devops_cli/commands/ci.py:1826:typer.Option("--shard", min=1, help=HELP.ci.shard),`, `src/devops_cli/commands/ci.py:1840:if shard > shards:` and `src/devops_cli/commands/ci.py:1842:MESSAGES.ci.shard_above_total.format(shard=shard, shards=shards), param_hint="--shard"`, so the gate refuses a shard above the total and the test command reuses that refusal and its help text.
- `read_file` read lines 320-400 of the selection module, and the range holds `src/devops_cli/core/test_selection.py:330:def directory_modules(directory: str, root: Path) -> list[str]:`, `src/devops_cli/core/test_selection.py:345:def recorded_durations(root: Path) -> dict[str, float]:` and `src/devops_cli/core/test_selection.py:356:def shard_test_files(shard: int, shards: int, root: Path) -> list[str]:`, so the splitter weighs the modules of the whole suite and takes no given list.
- That range also holds `src/devops_cli/core/test_selection.py:350:path = root / CONST_CI_TEST_DURATIONS_PATH` and `src/devops_cli/core/test_selection.py:372:lines = {module: line_count(module) for module in directory_modules(CONST_TESTS_ROOT_DIR, root)}`, so the recorded seconds come from the record under the root and the split covers the tests tree.
- `read_file` read lines 815-855 of the gate command, and the range holds `src/devops_cli/commands/ci.py:825:from devops_cli.core.test_selection import shard_test_files` and `src/devops_cli/commands/ci.py:843:*shard_test_files(shard, shards, _get_project_root()),`, so the gate's test row already splits the whole suite and no function splits a given list.
- `search_code` for `shard_paths` gave "No match.", so the function that splits a given list is new.
- `read_file` read lines 1-45 of the shard test module, and the range holds `tests/commands/test_ci_shard.py:22:from devops_cli.core.test_selection import directory_modules, is_test_module, shard_test_files` and `tests/commands/test_ci_shard.py:29:_SPLIT_OPTIONS = ("--splits", "--group", "--splitting-algorithm")`, so the shard cases and their imports sit in that module.
- `read_file` read lines 100-140 of the repeat test module, and the range holds `tests/commands/test_ci_repeat.py:127:result = runner.invoke(CI, ["test", "--repeat", "3", "--seed", "2", "tests/test_shared.py"])`, so a repeat case of the command goes in that module.
- `read_file` read lines 1856-1990 of the parity test module, and the range holds `tests/commands/test_ci.py:1868:allowlist: dict[tuple[str, str], str] = {`, `tests/commands/test_ci.py:1922:"Require Passing Test Shards",` and `tests/commands/test_ci.py:1966:assert len(rows) > 0, (`, so a new run step needs an allowlist row of its own.
- `read_file` read lines 30-120 of the workflow contract test module, and the range holds `tests/invariants/test_workflow_contracts.py:45:SUITE_STEP_LIMIT_MINUTES = {` and `tests/invariants/test_workflow_contracts.py:110:if "timeout-minutes" in step and not step["timeout-minutes"] < limit`, so every job needs a limit and each step limit stays under its own job limit.
- The probes say "`e78252815` has no definition at the staging commit. No commit in the history added or removed its text.", so the head of pull request #6562 is no fact of the staged tree: the 454 s pass, the 1,473 changed tests and the cancel at 21:15 are the report of that pull request, and this plan reads them as such.
- The set that the new guard covers is the changed test files of a pull request, whose count no tool of this run can read for a future head, so the count is unverified; the guard is `shard_paths`, its test `test_shard_paths_puts_each_given_file_in_one_shard` decides every file of a fixed list as in exactly one shard, and that test is the verify of the first group.
- `shard_paths` reads the given test modules and the duration record under the root, so a checkout of the repository is its precondition.
- `shard_test_files`, `recorded_durations` and `directory_modules` walk the tests tree and read the record under the root, so a checkout of the repository is their precondition.
- `_resolve_test_targets` and `_head_seed` read the checkout, and `_head_seed` runs `git rev-parse HEAD`, so a checkout of the repository is their precondition.
- `_run_shuffled_repeats` starts pytest over the checkout, so a checkout of the repository with `uv` and pytest is its precondition.
- `uv run devops docs generate` reads the checkout, so a checkout of the repository is its precondition; no call of the plan needs a client of a service or a network.
- The plan introduces no program of its own: each verify runs `uv run devops ci test` or `uv run devops ci --check`, whose rows start `uv`, `python`, `pytest`, `devops`, `actionlint` and `zizmor` from the runner image, each in the image tools list and none `NOT_IN_RUNNER`; the failure classes of a step are `test`, `lint`, `types` and `ci_infra`, and the pod settings are `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `capabilities.drop: ALL`.
- The first checks against the real system are `uv run devops ci test tests/commands/test_ci_shard.py`, `uv run devops ci test tests/commands/test_ci_repeat.py`, `uv run devops ci test tests/commands/test_ci.py tests/invariants/test_workflow_contracts.py` and `uv run devops ci --check --only actionlint,zizmor`.

## Existing Tool Considered

The open, maintained library `pytest-xdist` runs tests in parallel workers inside one job, so it gives a shard no own time bound and no matrix that GitHub shows as separate jobs. The change builds its own split instead and reuses the shard mechanism that the project keeps in `devops ci` and the GitHub Actions matrix. Written cost of the code that the project keeps: about 40k tokens to build, keep and fix, and about 2 hours of elapsed time. The change deletes no internal code.

## Dependencies

None.
