# Proposal

## Why

A change to one of the four gate modules that print their own problem lines gets no replay, so it cites no proof (#4596). The command reports today that such a change needs no proof at all, so this change makes it need one, gives those modules one problem per line, and replays each changed module directly under `tests/gate/` with the row whose command runs it.

## What Changes

- `run_fail_to_pass` no longer reports that a fix needs no proof, and no longer returns the no-tests report, when the only change is a `.py` module directly under `tests/gate/`: it lists those modules and replays them.
- `devops ci fail-to-pass` finds the `devops ci` row whose `cmd` or `also_cmds` runs the module, and runs the module once in a worktree of the merge base, which keeps the base's own copy of the module, and once in the head tree.
- The command exits 0 when a line of the base run's standard error is on no line of the head run, and the report names the module and that line.
- The command exits 1 when the base run writes no line on standard error, when a run exits with a status other than 0 or 1, and when no `devops ci` row runs the module.
- `tests/gate/swallowed_failures.py` writes one line per problem on standard error with the prefix `swallowed failures: `.
- `tests/gate/startup_imports.py` writes each problem as one physical line, with each newline of a problem replaced by a space.
- The `paths` filter of `.github/workflows/fail-to-pass.yml` matches `tests/gate/**` and no longer `tests/gate/*_checks/**`.
- The help of `devops ci fail-to-pass`, the generated command documents and the Fail-to-Pass Evidence item of `CONTRIBUTING.md` describe the module replay and the widened filter.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-fail-to-pass`: A changed module directly under tests/gate is replayed with its row, One problem per line, A base-only problem line proves the fix, No base problem refuses the replay, The check runs only for a fix that changes the code under src or a gate check, A changed gate check is replayed with its row, A fix that changes no source code and no gate module needs no failing proof

## Impact

- Code: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/lang/en/messages.py`, `.github/workflows/fail-to-pass.yml`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/CLI_REFERENCE.md`, `docs/commands/ci.md`, `CONTRIBUTING.md`
- Tests: `tests/gate/swallowed_failures.py`, `tests/gate/startup_imports.py`, `tests/ci/test_fail_to_pass.py`

## Feasibility

- The premise of the issue is confirmed by the probes, word for word: `The path `tests/gate/ruff_config.py` is a file of the staging commit.`, `The path `tests/gate/construct_gate.py` is a file of the staging commit.`, `The path `tests/gate/startup_imports.py` is a file of the staging commit.`, `The path `tests/gate/swallowed_failures.py` is a file of the staging commit.`, `The path `.github/workflows/fail-to-pass.yml` is a file of the staging commit.` and `The path `tests/gate/__init__.py` is a file of the staging commit.`
- The `needs_proof` return of the earlier plan was a defect, and group 3 fixes it. `read_file` on `src/devops_cli/ci/fail_to_pass.py` showed the first guard `src/devops_cli/ci/fail_to_pass.py:1027:if not changed.source_files and not changed.gate_checks:` and the next one `src/devops_cli/ci/fail_to_pass.py:1036:if not changed.test_files and not changed.gate_checks:`, which returns `src/devops_cli/ci/fail_to_pass.py:1033:needs_proof=False,` in the earlier report and then a report with no outcomes at all. Group 3 widens both guards, so a change of only `tests/gate/ruff_config.py` reaches the replay.
- The report fields arrive in the order of the groups, so each group's verify passes with the groups before it. Group 3 adds a `changed_gate_modules` field of the report beside `src/devops_cli/ci/fail_to_pass.py:239:changed_gate_checks: tuple[str, ...] = ()`, and its test asserts only `needs_proof` and that field. Group 4 adds a `gate_modules` field of the report, the replay and the count in `src/devops_cli/ci/fail_to_pass.py:def satisfied`, and its test asserts `satisfied` and `refused`. Group 5 adds the messages, `_gate_module_lines`, `_gate_module_refusals` and the plan requests, and its test asserts the report text and the dry run.
- The review finding is corrected in group 5, which now updates the existing cases of `tests/ci/test_fail_to_pass.py` in the same group as the plan requests and the widened messages. `read_file` on that module showed the line-by-line plan assertions `tests/ci/test_fail_to_pass.py:1499:assert lines[7] == "git worktree add --quiet --detach '<temp-dir>/tree' '<merge-base>'"` and `tests/ci/test_fail_to_pass.py:1504:assert lines[10:] == [`, the skip tuple `tests/ci/test_fail_to_pass.py:1587:("tests/test_x.py", ("a changed gate check exists", "a module of tests/gate/")),`, and the two texts that the widened messages change: `tests/ci/test_fail_to_pass.py:762:The fix changes no tests/**/test_*.py file and adds or changes no case of` and `tests/ci/test_fail_to_pass.py:2081:it only deletes checks of tests/gate/*_checks/`. The same texts are asserted again at `tests/ci/test_fail_to_pass.py:2160:The fix changes no tests/**/test_*.py file and adds or changes no case of`.
- This run read the four modules: `tests/gate/ruff_config.py:192:print(f"ruff configuration: {line}", file=sys.stderr)`, `tests/gate/construct_gate.py:474:print(f"construct gate: {line}", file=sys.stderr)`, `tests/gate/startup_imports.py:569:print(f"startup imports: {line}", file=sys.stderr)` and `tests/gate/swallowed_failures.py:379:print(line, file=sys.stderr)`, so each prints its own problem lines and no case ID or summary.
- Two of them break the one-line rule: `tests/gate/swallowed_failures.py:361:*([format_over_ceiling_error(over)] if over else []),` gives one problem as a multi-line block, and `tests/gate/startup_imports.py:551:found, cpu_seconds = [f"{name}: exit {exc.returncode}: {exc.stderr[-400:]}"], 0.0` gives a problem that can hold a newline.
- `list_files` on `tests/gate` showed 13 modules directly under it other than `__init__.py`: charts.py, charts_render.py, configured_domain.py, construct_gate.py, k8s.py, k8s_render.py, roadmap_eval_commits.py, ruff_config.py, ruff_selection.py, runner.py, startup_imports.py, swallowed_failures.py and tree.py.
- `search_code` for `_python_check_cmd(` showed nine rows that run a module of `tests/gate/`: `src/devops_cli/commands/ci.py:917:also_cmds=[_python_check_cmd("ruff_config")],` and `src/devops_cli/commands/ci.py:1098:cmd=_python_check_cmd("k8s"),` among them, at lines 917, 1028, 1098, 1109, 1116, 1123, 1130, 1137 and 1145.
- The plan decides each of those 13 members: the nine modules above are replayed with their row, and the four helpers charts_render.py, k8s_render.py, ruff_selection.py and runner.py are no row command, so a change to one of them exits 1 and names the module. Group 4's test of `tests/gate/runner.py` verifies that decision.
- `read_file` on `src/devops_cli/ci/fail_to_pass.py` showed `src/devops_cli/ci/fail_to_pass.py:383:def is_gate_check(path: PurePosixPath) -> bool:` for a module under `tests/gate/<row>_checks/` only, and `src/devops_cli/ci/fail_to_pass.py:502:gate_checks = [path for path in paths if is_gate_check(PurePosixPath(path))]`, so a top-level gate module reaches no replay today. `src/devops_cli/config/constants.py:2625:CONST_GATE_DIR: Final[str] = "tests/gate"` is the folder that `is_gate_module` matches.
- `file_symbols` showed `src/devops_cli/ci/fail_to_pass.py:def gate_row_argv`, `src/devops_cli/ci/fail_to_pass.py:def plan_fail_to_pass`, `src/devops_cli/ci/fail_to_pass.py:def run_fail_to_pass`, `src/devops_cli/ci/fail_to_pass.py:def _plain_base_tree` and `src/devops_cli/ci/fail_to_pass.py:def _head_tree`, and `src/devops_cli/ci/fail_to_pass.py:603:return [sys.executable, "-c", CONST_FAIL_TO_PASS_GATE_ROW_SCRIPT.format(module=row)]` is the argv that the new module run reuses.
- The staged constants are `src/devops_cli/config/constants.py:2631:CONST_GATE_ROW_SCRIPT: Final[str] = (` with the value `import sys; from tests.gate.{module} import main; sys.exit(main())`, `src/devops_cli/config/constants.py:2638:CONST_FAIL_TO_PASS_GATE_ROW_SCRIPT: Final[str] = (` with the value of `CONST_GATE_ROW_SCRIPT` behind a first `sys.path.insert` of the `src/` of the tree, and `src/devops_cli/config/constants.py:2643:CONST_FAIL_TO_PASS_GATE_ROW_EXIT_STATUSES: Final[frozenset[int]] = frozenset({0, 1})` with the value `{0, 1}`.
- `src/devops_cli/commands/ci.py:894:def _python_check_cmd(module: str) -> list[str]:` builds the command of a module, `src/devops_cli/commands/ci.py:897:return ["uv", "run", "python", "-c", CONST_GATE_ROW_SCRIPT.format(module=module)]` is its argv, and `src/devops_cli/commands/ci.py:231:return [self.cmd, *self.also_cmds]` gives the commands of a row, so the row of a module is the row whose commands hold that script.
- `read_file` on `.github/workflows/fail-to-pass.yml` showed `.github/workflows/fail-to-pass.yml:19:- "tests/gate/*_checks/**"`, which matches no module directly under `tests/gate/`, and `.github/workflows/fail-to-pass.yml:4:# under src/ can make a test fail on base, and a changed check module of tests/gate/*_checks/ can` in the comment above the job.
- `references` for `tests/gate/*_checks` listed 20 files and 48 lines; outside `openspec/changes/archive/` it names `openspec/specs/ci-fail-to-pass/spec.md`, `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/lang/en/help.py:1122:A changed module under tests/gate/*_checks/ runs its gate row on `, `src/devops_cli/lang/en/messages.py:2466:adds or changes no case of tests/gate/*_checks/, so it needs no test that fails on its `, `tests/ci/test_fail_to_pass.py`, `CONTRIBUTING.md`, `docs/CLI_REFERENCE.md`, `docs/commands/ci.md` and `.github/workflows/fail-to-pass.yml`, and each of them is a change of a group or the subject of a design decision.
- `search_code` for `gate_module` returned only the existing placeholders `src/devops_cli/ci/fail_to_pass.py:611:GATE_MODULE_PLACEHOLDER = "<changed gate check module>"` and their neighbours, and `search_code` for `is_gate_module` and for `EACH_GATE_MODULE_ROW` returned no match, so `is_gate_module`, `gate_module_argv`, `gate_row_of_module`, `GateModuleRun`, `GateModuleReplay`, `_run_gate_module`, `_replay_gate_modules`, `_gate_module_lines`, `_gate_module_refusals`, `GATE_MODULE_REPLAY` and `EACH_GATE_MODULE_ROW` are new at the staged commit.
- `read_file` on `tests/ci/test_fail_to_pass.py` showed the fake `tests/ci/test_fail_to_pass.py:def _is_gate_row_run`, which already answers a `python -c` run of a gate module, and `tests/ci/test_fail_to_pass.py:180:if dest.name == "tree":`, which records only the merge-base worktree named `tree`, so group 4 records the `gate_base` worktree too. The same file holds `tests/ci/test_fail_to_pass.py:376:"changed_gate_checks": (),` in `_replay_report`, which group 3 and group 4 extend with the new report fields.
- `read_file` on `tests/ci/test_fail_to_pass.py` showed `tests/ci/test_fail_to_pass.py:2080:"The fix changes no source code (a .py file under src/ outside the knowledge base), and "`, so the case that asserts the no-source sentence is in the module that group 3 updates, and `src/devops_cli/ci/fail_to_pass.py:1181:if not report.changed_test_files and not report.changed_gate_checks:` is the reason sentence that group 5 widens.
- `read_file` on `tests/gate/swallowed_failures.py` showed `tests/gate/swallowed_failures.py:307:def format_over_ceiling_error(over_ceiling: dict[str, list[SwallowedFailureSite]]) -> str:` used by `lower_ceilings` and by `tests/invariants/test_swallowed_failures_check.py:90:assert "a.py:3: S110 (pass)" in format_over_ceiling_error(over)`, so group 1 keeps that multi-line format and adds the one-line form beside it.
- `run_fail_to_pass(root, *, base, head)` needs a checkout of the repository as its precondition: it resolves the merge base and adds worktrees with git.
- `changed_tests(root, base, head)` needs a checkout of the repository as its precondition: it runs `git merge-base`, `git diff --name-status` and `git ls-files`.
- `_add_worktree(root, revision, dest)`, `_plain_base_tree(root, merge_base, dest)` and `_head_tree(root, head, dest)` need a checkout of the repository as their precondition: each adds and removes a worktree with git.
- `_run_gate_module(tree, module)` needs a checkout of the repository at `tree` as its precondition: it starts `python -c` with `tree` as the working folder, and the script puts the `src/` of that tree first on the import path.
- `gate_row_of_module(module)` calls `get_check_specs()` and needs no checkout, no client and no network, and `plan_fail_to_pass(base, head)` makes no git call and needs no checkout.
- No verify introduces a program: each starts a `devops ci` row whose programs (`git`, `uv`, `python`, `pytest`, `ruff`, `actionlint`, `zizmor`) are runner tools of the image, so each source is the image and none is `NOT_IN_RUNNER`.
- The failure classes are `test` for a failing test, `lint` for a lint or workflow row and `ci_infra` for a row that cannot run, and the pod settings that apply are `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `capabilities.drop: ALL`.
- The plan names no row that needs a tool outside the image: the `charts` row needs `docker` and `helm`, which are `NOT_IN_RUNNER`, and no group or verify of this change runs it.
- No group creates a file, so no `creates_lines` estimate counts against the budget of a step, and the new cases go in `tests/ci/test_fail_to_pass.py`, the module that mirrors `src/devops_cli/ci/`.
- The first checks of the implementation are `uv run devops ci test tests/ci/test_fail_to_pass.py` for the new cases, `uv run devops ci --check --only swallowed-failures` and `uv run devops ci --check --only startup-imports` for the two output contracts, `uv run devops ci --check --only actionlint,zizmor` for the widened filter, and `uv run devops ci docs` for the help and the generated documents.

## Existing Tool Considered

No open, maintained tool covers a replay of a changed gate module against the base and head trees: the alternatives check of 2026-11-20 found none. The change extends `devops ci fail-to-pass`, about 250 lines over 10 files, 12k tokens to build, 5k tokens a year to keep and fix, and one day of elapsed time. It deletes no internal code.

## Dependencies

None.
