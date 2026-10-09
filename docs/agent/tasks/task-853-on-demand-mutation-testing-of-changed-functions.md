# Task: On-Demand Mutation Testing of Changed Functions (#853)

**Issue**: [#853](https://github.com/dan-petty/devops-cli/issues/853)
**Status**: Done
**Milestone**: v0.2.32
**Priority**: priority/p3-low
**Scope**: type/feature, priority/p3-low, scope/cli, scope/ci

## Description

Coverage shows that the tests run the code, not that they check it. `devops ci mutate [PATHS]
[--changed] [--base REF]` runs mutmut 3.8.0 on chosen functions and shows each mutant no test
killed, with its diff, then the killed, survived, timeout and no-tests counts. It prints no score,
exits 0 whatever survives, and is neither a `devops ci` stage nor a `ci.yml` step.

`devops_cli.ci.mutate` picks the functions with `ast`. mutmut mutates the functions at a module's
top level and those directly in a top-level class, a decorated class's methods included, and
leaves out any function with a decorator other than one bare `staticmethod` or `classmethod`, and
`__new__`, `__getattribute__` and `__setattr__` (`file_mutation.py`, `_skip_node_and_children`,
`NEVER_MUTATE_FUNCTION_NAMES`). With `--changed`, a function is selected when the working tree's
syntax tree of it differs from the one at the merge base with `--base` (default `main`; item
branches pass their release branch), or the base lacks it; an untracked file under `src` that git
does not ignore counts as added. A `--base` that names no commit is an error, not an empty
selection. PATHS alone select every mutable function in the files they name or hold; with
`--changed`, they narrow the changed ones.

## Key Changes

- `pyproject.toml`: `mutmut==3.8.0` in the dev group (the lock adds libcst 1.9.0, mutmut 3.8.0 and
  setproctitle 1.3.8), and a `[tool.mutmut]` table: `source_paths`, `pytest_add_cli_args = ["-n",
  "0"]` (mutmut appends it after addopts, so it overrides `-n logical`), the test selection, and
  `also_copy` for the top-level entries the tests read.
- `.gitignore`: `/mutants/`, so neither git nor the CI cache fingerprint sees mutmut's tree.
- `src/devops_cli/ci/mutate.py`: `mutmut_module`, `mutable_functions`, `changed_functions`,
  `select_targets`, `MutationTarget` and `tally`, with stdlib `ast`, `fnmatch` and `Counter` and
  the existing git helpers. It never imports mutmut, which is a dev dependency.
- `src/devops_cli/commands/ci.py`: the `mutate` command. It runs `uv run mutmut run <globs>`
  through `_run` with a 4-hour timeout, reads `mutmut results --all true` and runs
  `mutmut show <mutant>` for each survivor through the `run_subprocess` seam. `--dry-run` lists
  the three requests and starts no mutmut process; it still reads git locally to select the
  functions, with no external request.
- `config/constants.py`: mutmut's naming (`x_`, `xǁ`, `ǁ`, `__mutmut_`), the decorators it mutates,
  the names it never mutates and the statuses the report counts. `config/defaults.py`: `DEFAULT_CI_MUTATE_TIMEOUT_SECONDS`.
- `lang/en/help.py` and `lang/en/messages.py`: the command's help and messages.
- `tests/test_ci_mutate.py` and two tests in `tests/test_architectural_invariants.py`.
- Docs: `docs/CLI_REFERENCE.md`, `docs/commands/ci.md` and the README matrix (generated), a row in
  `docs/cheatsheets/ci_and_quality.md` and in the knowledge base's CLI command reference.

## Design Notes

**The globs.** Each function is run with two globs, `<module>.<mangled>__mutmut_*` and
`*<module>.<mangled>`, where `<mangled>` is `x_<function>` or `xǁ<Class>ǁ<method>`. mutmut matches
the globs against its mutants and, for the clean test run before it mutates, against its test
stats, which are keyed by the function's name alone (`tests_for_mutant_names`); when no glob
matches a stats key it runs the whole selected suite. The first glob matches only the function's
own mutants and no stats key; the second matches only its stats key, and starts with `*` because
mutmut reads a name without one as a mutant's. A single `<module>.<mangled>*` would also select a
function whose name the target's is a prefix of (`x_run` selects `x_run_all`). When no selected
function gives mutmut a mutant (a body of only `...`, say), mutmut fails with "nothing matches",
on a first run only after its stats pass; the help says so.

**Fork mode, the network guard and the tripwire.** mutmut runs the suite in its own process and
forks one worker a mutant. The conftest network guard is a session fixture that is never undone,
so the workers inherit it, and each worker's pytest session installs it again on top. The #749
tripwire runs, but its repository root is `mutants/`, where git tracks no file, so its
tracked-file check has nothing to compare; its worker-HOME isolation still applies. A full run
in fork mode completed the stats, clean-test, forced-fail and mutant steps, so the default
`process_isolation` (fork) is kept.

**Which tests run inside `mutants/`.** The suite runs from `mutants/`, whose `src` holds mutmut's
generated code, with no git checkout and no `.venv`. A test is left out only when it reads `src`
as data (it sees the generated code, or scans the 475 MB tree), relies on git tracking the
checkout, or relies on its `.venv`. Whole modules of source-tree invariants are ignored
(`test_architectural_invariants`, `test_public_export_surface`, `test_docs`,
`test_docs_source_argv_collector`, `test_ai_task_loader`), and single tests elsewhere are
deselected: the Rich-import scan, the missing-header hallucination check that reads a provider
module, and the span caller test, which records mutmut's trampoline as its caller (generated
code); the kustomization, run-store commit and forbidden-constructs tests (git); and the
sandbox-binary test (`.venv`). The PR-head review test is deselected too: without the checkout's
git origin it fetches `refs/pull/7/head` from GitHub. A serial run of the rest of the suite from
`mutants/` took 20 minutes.

**Measured.** Generating the tree mutated 549 files into 195,936 mutants in 506 s with 8
processes at a load average of about 25, and `mutants/` is 475 MB. On the first run, mutmut then
runs the selected suite once, serially, to learn which tests cover which function. A later run
over `ci/mutate.py` itself made 135 mutants in 3 min 26 s: 117 killed, 18 survived.

## Acceptance Criteria

- [x] A unit test maps a fixture diff to the expected globs, which it builds with mutmut's own
  `get_mutant_name` and `mangle_function_name`, and asserts that the run argv disables xdist
  through `[tool.mutmut].pytest_add_cli_args`:
  `test_changed_functions_map_to_the_globs_mutmut_names`,
  `test_mutate_runs_mutmut_serially_on_the_changed_function_globs`.
- [x] `git check-ignore mutants/x` succeeds, and `test_gitignore_keeps_mutants_out_of_the_tree`
  matches it with the gitignore rules.
- [x] Neither the `devops ci` stage list nor `ci.yml` contains a mutate step:
  `test_mutate_is_no_gate_step`.
- [x] The pragma check fails on a fixture that uses the pragma:
  `test_a_no_mutate_pragma_is_reported`; `test_no_source_line_exempts_itself_from_mutation`
  passes on `src`.
- [x] Each new unit test takes at most 1 s.
- [x] `uv lock --check`, `uv audit` and `devops docs check` pass.
- [x] The key question is answered: the guard and the tripwire behave in fork mode (above).
- Pending a person: on a quiet machine, the first-run and incremental wall times of
  `rm -rf mutants && time uv run devops ci mutate --changed --base release/v0.2.32`, then the same
  command again without `rm -rf mutants`.

## Deliverables

- [x] `devops ci mutate [PATHS] [--changed] [--base REF] [--dry-run]`.
- [x] mutmut 3.8.0 in the dev group with its `[tool.mutmut]` table, and `/mutants/` ignored.
- [x] The invariant that no line under `src` carries a `no mutate` pragma.
- [x] `changelog.d/853.md`.
- [x] Two existing test-isolation bugs fixed, because mutmut's first run executes the whole suite serially in one process and stops at the first failure (owner decision, 2026-10-09: folded into this item):
  - `tests/conftest.py`'s autouse `isolate_vault_token` now clears every ephemeral CI secret (`_EPHEMERAL_CI_SECRETS.clear()`), not only the Vault key. A secret `tests/test_config_commands.py` stored through `DEVOPS_CLI_HEADLESS_AUTH` leaked into `tests/test_embedding_benchmark.py` in serial order (`uv run pytest -n 0 tests/test_config_commands.py tests/test_embedding_benchmark.py` failed 1 of 30); xdist hid it. This is one slice of #1310 (reset all process-wide state after every test).
  - `tests/test_ssh.py::test_crypto_ssh_keys_devcontainer_config_resolution` uses `monkeypatch.delenv("DEVOPS_CLI_CONFIG")` instead of patching `os.environ.get` process-wide, which broke mutmut's own `os.environ.get` call during its stats pass.
  - With both, the real first run over the final selection finished with exit 0 (133 mutants: 126 killed, 7 survived).
