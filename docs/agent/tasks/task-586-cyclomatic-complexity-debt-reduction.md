# Task: Ruff Enforces the Complexity Cap of 10 (#586)

**Issue**: [#586](https://github.com/dan-petty/devops-cli/issues/586)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p1-high
**Scope**: scope/cli

## Description
`AGENTS.md:14` said cyclomatic complexity ≤ 10 was strictly enforced project-wide, validated by `devops scan complexity` and the architectural invariant tests. Nothing enforced it. `pyproject.toml` did not select `C901`, `devops ci` had no complexity step, `devops scan complexity` exits 0 on a breach, and the `structural-invariants` hook only printed complexity breaches as a note.

Owner decision D1 makes Ruff's `C901` (standard McCabe) the enforced definition. It comes with an inline baseline, `RUF100` to remove a marker once its function is fixed, `PGH004` against blanket `noqa`, a ceiling on `C901` markers that may only go down, and a meta-test that pins `max-complexity` and forbids `C901` in per-file ignores. It uses no radon, no lizard and no new dependency. No function is decomposed here.

A review of the first version found committed ways past the cap that the tests missed. Ruff 0.16's own `# ruff: ignore[C901]`, `# ruff: disable[C901]` and `# ruff: file-ignore[C901]` comments hide functions without a marker. A marker or file-level exemption with a form feed or a no-break space in place of a space went uncounted. `.ignore` and `.gitignore` files drop a source from Ruff's walk. `C90` selected with `C9` ignored turns `C901` off. The rewritten nesting walk also hit Python's recursion limit on long expressions. All five are fixed here, each with tests.

## Key Changes
- **`pyproject.toml`**: `select` adds `C901`, `PGH004` and `RUF100`, and `[tool.ruff.lint.mccabe] max-complexity = 10`.
- **Baseline**: the three steps ran in order. `uv run ruff check --select C901 --add-noqa .` ran once and added 66 directives, none of them merged into an existing comment. Then `uv run ruff check --fix --fixable RUF100 .`, without `--select RUF100`, fixed the 9 stale codes. The `# nosec` comments stay, and `tests/test_ai_gateway_tune.py:338` keeps "the script under test" as a plain comment.
- **`src/devops_cli/config/constants.py`**: `CONST_COMPLEXITY_LINT_RULES` (`C901`, `PGH004`, `RUF100`) sits beside `CONST_TEST_ASSERTION_LINT_RULES`. Next to it are:
  - the key allowlists `CONST_RUFF_TOP_LEVEL_KEYS`, `CONST_RUFF_LINT_KEYS` and `CONST_RUFF_MCCABE_KEYS`, plus `CONST_RUFF_PER_FILE_IGNORE_KEYS`;
  - `CONST_RUFF_EXCLUDE`, `CONST_COMPLEXITY_CAP_ROOTS`, `CONST_RUFF_SOURCE_SUFFIXES` and `CONST_RUFF_CONFIG_FILE_NAMES`;
  - `CONST_RUFF_IGNORE_FILE_NAMES` (`.gitignore`, `.ignore`);
  - the three regexes, `CONST_RUFF_FILE_EXEMPTION`, `CONST_C901_SUPPRESSION` and `CONST_RUFF_C901_SUPPRESSION_COMMENT`. Each one takes any whitespace except a newline (`[^\S\n]`) where Ruff does. The last one matches a `ruff:` comment with any verb whose brackets name `C901`.
- **`src/devops_cli/config/defaults.py`**: `DEFAULT_C901_SUPPRESSION_CEILING = 66` sits next to `DEFAULT_MAX_COMPLEXITY`.
- **`tests/test_architectural_invariants.py`**:
  - `_complexity_cap_escapes(pyproject, project)` returns every escape it finds. `_lint_escapes` counts a cap rule as enforced only when `select` names it by its own code. `_tree_escapes` checks four things: file-level exemptions and Ruff's own `C901` suppression comments, through `_source_escapes`; nested and outranking Ruff configs; and ignore files, through `_ignore_file_escapes`. That helper matches covered sources against the root `.gitignore` with `pathspec`, a declared dependency, so no `git` process runs.
  - `_c901_suppressions` and `_c901_suppressions_over` count `C901` markers with a regex over the file text.
  - The new tests are `test_every_complexity_cap_escape_is_reported` (38 cases), `test_the_complexity_cap_has_no_escape`, `test_c901_suppressions_stay_under_the_ceiling`, `test_suppressions_over_the_ceiling_name_their_files` and `test_every_marker_spelling_ruff_honours_is_counted` (4 cases).
  - `test_filesystem_get_tools_complexity` is removed, because `C901` covers it.
- **`src/devops_cli/security/structural_invariants.py`**: the hook checks nesting only. The complexity accumulation in `_measure`, `MAX_COMPLEXITY`, the `max_complexity` parameters, `over_complex` and the note are gone. `measure` returns the nesting depth from an explicit stack, not recursion. `breaches` and `check_structural_invariants` return the breach list, and `breaches` reports a parser `RecursionError` as a file it could not parse.
- **`tests/test_structural_invariant_hook.py`**: `test_complexity_is_reported_without_blocking` is removed. `test_a_long_expression_is_measured_rather_than_overflowing` and `test_a_parser_overflow_is_reported_rather_than_raised` are added, and both run in-process.
- **`pyproject.toml` comment**: says the meta-test bans every other way past the cap, and that each of the three rules must be named by its own code.
- **`.pre-commit-config.yaml`**: the hook comment's complexity clause now says that complexity is Ruff's `C901`, run by the `ruff-check` hook. The import claim is left for #773.
- **Docs**: `AGENTS.md:14`, `CONTRIBUTING.md:13`, `docs/SDLC.md:129` and `docs/ROUTINE_TASKS.md:55` name the real enforcers. `AGENTS.md:14` also says that a function over the cap is decomposed, never suppressed, and that the meta-test rejects Ruff's own `ruff:` comments and ignore files:
  - `C901`, through `uv run devops ci` and the pre-commit ruff hook;
  - the marker ceiling test;
  - for nesting, the `structural-invariants` hook and `test_no_excessive_nesting_in_src`.

  They also say that `devops scan complexity` reports a different, in-house count and does not gate.
- **`docs/ROADMAP.md`**: not edited. #739 made it a generated view. The PR description names "Metric Provenance: radon's Cyclomatic Complexity Behind One Adapter" as superseded by D1.

## Measurements
These were taken on 321ecda (`origin/release/v0.2.25`) with ruff 0.16.8. The issue's figures are from ef21785, and the counts have moved since then.
- `C901` breaches, measured with `ruff check --no-cache --isolated --select C901 --config 'lint.mccabe.max-complexity = 10' --statistics --exit-zero src tests`: 66 (the issue had 76). With the markers in place, the same command needs `--ignore-noqa` and still prints 66. 65 are in 42 `src` files and 1 is in `tests`: `test_no_circular_imports_in_decoupled_subsystems` in `tests/test_architectural_invariants.py`.
- The in-house counter, `run_complexity_scan(src/devops_cli, max_complexity=10)`: 215 functions over 10 (the issue had 235).
- `ruff check --select RUF100 .`, which replaces the configured `select`, reports 34 unused codes before the baseline (the issue had 31). With the project's `select` plus `RUF100`, it reports exactly the 9 listed below.
- `PGH004` (blanket `noqa`): 0 hits.
- The release tip moves until this ships. If it moves before merge, the orchestrator re-runs the baseline on the new tip at ship time: `--add-noqa` once, then `--fix --fixable RUF100`. `DEFAULT_C901_SUPPRESSION_CEILING` and the counts in this file are then set to the new tip's numbers. The local `origin/release/v0.2.25` was still 321ecda at the last check.

## Acceptance Criteria
- [x] `uv run devops ci --check --no-cache` passes on the PR head, with every check reported as passing. Plain `uv run ruff check .`, the command GitHub CI runs (`.github/workflows/ci.yml:51`), prints `All checks passed!`.
- [x] The baseline removed no `noqa` code the project needs. `git diff -U0 321ecda -- src tests | grep -c '^-.*# noqa'` prints 9, and they are the issue's lines:
  - `ai/gateway_bench.py:69`, `:97` and `:100` (`S310`);
  - `ai/gateway_tune.py:432` (`S603`);
  - `tests/test_ai_gateway_tune.py:338` (`S102`);
  - `tests/test_exceptions.py:172-173` (`F401`);
  - `tests/test_sandbox_metrics.py:231`, which was `:229` at ef21785, and `tests/test_sandbox_probe.py:133` (`N802`).
- [x] The meta-test passes on the real `pyproject.toml`. Before the config change it reported `C901`, `PGH004` and `RUF100` as not enforced and `max-complexity: None, not 10`. `test_every_complexity_cap_escape_is_reported` has 38 cases, built from in-memory config dicts and `tmp_path` files: 2 complying controls and 36 escapes, one per case. The helper reports each escape alone. The first 24 escapes failed against a stub helper. The 12 added in review fail against the helpers as they were before the review, and Ruff 0.16.8 hides a complexity-13 function behind each comment spelling they use. The escapes are:
  - top-level `per-file-ignores` covering `C901`;
  - top-level `extend-ignore = ["C901"]`;
  - `include`, `extend`, `extend-exclude` and `lint.exclude`;
  - an `exclude` other than `["repos"]`;
  - `C901` unselected, `C901` ignored, and `C901` selected as `C90` with `C9` ignored. The control `C9` ignored under an exact `C901` reports nothing, and Ruff agrees;
  - `RUF100` in `extend-ignore`, and `PGH004` unselected;
  - `max-complexity` raised, `max-complexity` missing, and an extra `mccabe` key;
  - `per-file-ignores` with `C9`, `extend-per-file-ignores` with `ALL`, and `per-file-ignores` with `PGH`;
  - a file-level `ruff` exemption with and without codes, and a file-level `flake8` exemption. Each also appears with a form feed or a no-break space after the `#`;
  - Ruff's own comments naming `C901`: a trailing `ignore[C901]`, a `disable[C901]`/`enable[C901]` pair, an unpaired and unspaced `disable[E501,C901]`, a `file-ignore[C901]`, and a `disable[ C901 ]` with em spaces;
  - an `.ignore` under `src`, a `.gitignore` under `tests`, an `.ignore` beside `pyproject.toml`, and a root `.gitignore` that lists a source. In that last case, the `__pycache__/` and `*.py[cod]` lines in the same file report nothing;
  - a nested `ruff.toml`, `.ruff.toml` or `pyproject.toml`;
  - a `ruff.toml` beside `pyproject.toml`.

  No test runs the ruff binary.
- [x] The ceiling test passes, and three numbers are equal at 66:
  - `DEFAULT_C901_SUPPRESSION_CEILING`;
  - `_c901_suppressions` over `src` and `tests`: 65 + 1, in 43 files;
  - `uv run ruff check --select C901 --ignore-noqa --statistics --exit-zero .`, which prints `66 C901 complex-structure`.

  `test_every_marker_spelling_ruff_honours_is_counted` counts 1 for each of four markers: a form feed or a no-break space after the `#`, an em space after the colon, and an ASCII `noqa : E501 C901`. The regex as it was before the review counted 0 for the first three. Ruff hides the function behind all four.

  With the ceiling still at 0 after the baseline, the test failed with `66 more C901 marker(s) than DEFAULT_C901_SUPPRESSION_CEILING allows, among these files: [...]. Decompose the function the new marker sits on until Ruff no longer reports it; do not raise the ceiling.`
- [x] `test_suppressions_over_the_ceiling_name_their_files` writes, at run time, both forms `--add-noqa` produces: the plain `C901` marker on `def f(x):` and the merged `C901, N802` marker on `def do_GET(x):`. The helper counts 2 for `src/over.py`, reports an excess of 1 naming `src/over.py` at ceiling 1, and reports nothing at ceiling 2. It failed against a stub helper.
- [x] The probe sequence, with `p=src/devops_cli/_c901_probe.py`, gave the expected result at each step. The probe is deleted.

  ```text
  $ uv run ruff check $p                         -> C901 `f` is too complex (11 > 10), exit 1
  $ uv run pre-commit run ruff-check --files $p  -> ruff check....Failed (C901 `f` is too complex (11 > 10)), exit 1
  $ sed -i '1s/$/  # noqa: C901/' $p && sed -i '/x == 10/,+1d' $p
  $ uv run ruff check $p                         -> RUF100 [*] Unused `noqa` directive (unused: `C901`), exit 1
  $ uv run ruff check --fix $p; grep -c noqa $p  -> Found 1 error (1 fixed, 0 remaining). / 0
  $ rm $p
  ```

- [x] `rg -n -i complexity src/devops_cli/security/structural_invariants.py` returns nothing, and the six tests in `tests/test_structural_invariant_hook.py` pass. The old and new nesting measures agree on all 14,749 functions in `src` and `tests`.
- [x] The hook survives long expressions. With a `def f()` returning a sum of N ones, the hook as first rewritten raised `RecursionError` (exit 1) at 600 and 900 terms, where the 321ecda hook exited 0. Now it exits 0 at 450, 600, 900 and 3000 terms; the 321ecda hook also failed at 3000. `ast.parse` itself overflows near 200,000 terms, and `breaches` reports that as `could not parse`.
- [x] `rg -n C901 AGENTS.md CONTRIBUTING.md docs/SDLC.md docs/ROUTINE_TASKS.md` shows `AGENTS.md:14`, `CONTRIBUTING.md:13`, `docs/SDLC.md:129` and `docs/ROUTINE_TASKS.md:55`. `rg -n 'nothing enforces it|240 functions' .pre-commit-config.yaml src tests` returns nothing. `git diff` changes only `AGENTS.md:14` in that file and leaves `.github/pull_request_template.md` unchanged.
- [x] `uv run ruff check .` wall time, over 7 runs each:
  - with `--no-cache`: median 1.27 s before and 1.08 s after;
  - cached: median 1.14 s before and 0.94 s after.

  Both changes are under 1 s and within run-to-run noise.
- [x] Test durations, from a JUnit report covering setup, call and teardown:
  - The 47 new test items take 0.467 s together, with the file cache warm. The breakdown:
    - `test_the_complexity_cap_has_no_escape`: 0.129 s. Reading the 921 sources takes about 55 ms of that, and matching them against `.gitignore` about 27 ms.
    - `test_c901_suppressions_stay_under_the_ceiling`: 0.092 s.
    - `test_suppressions_over_the_ceiling_name_their_files`: 0.005 s.
    - The 38 escape cases: 0.174 s together, at most 0.006 s each.
    - The 4 marker-spelling cases: 0.018 s together.
    - `test_a_long_expression_is_measured_rather_than_overflowing`: 0.045 s.
    - `test_a_parser_overflow_is_reported_rather_than_raised`: 0.004 s.
  - Before the review fixes, the test step ran as `pytest -n auto --maxprocesses=8 --durations=0 --cov=src`. Before this change: 8021 passed in 144.23 s, with a `--durations` sum of 662.70 s. After it: 8047 passed in 138.62 s, with a sum of 578.79 s.
  - After the review fixes, `uv run devops ci --check --no-cache` passed all 13 checks. Its test step took 2 m 34 s, with mypy at 31 s and docs at 17 s. It prints no test count; `pytest --collect-only` collects 8074 tests.
  - The earlier difference is negative. The removed `test_complexity_is_reported_without_blocking` took 5.06 s, one hook subprocess, and `test_filesystem_get_tools_complexity` took 0.02 s. `test_structural_invariant_hook.py` went from 31.47 s to 26.73 s. The rest of the 83.9 s drop in the sum is load varying between runs.

## Trade-offs
- `devops scan complexity` keeps the in-house count (215 over 10 in `src`, against 65 for `C901`) until #773 aligns it with McCabe. It reports only and does not gate.
- The ceiling test uses `≤`, so it does not force the ceiling down when a marker goes. A PR that removes markers lowers the ceiling itself, and a raised ceiling or a new marker shows up in review as a changed line.
- The meta-test goes beyond D1's list. Besides the checks added in review (the bullets below), it does two more things:
  - A per-file ignore that covers `RUF100` or `PGH004` also counts as an escape. Without `PGH004`, a blanket `noqa` would hide `C901` with no marker to count.
  - A `ruff.toml` or `.ruff.toml` beside `pyproject.toml` is reported, because Ruff prefers it to `pyproject.toml`.

  `per-file-ignores` stays allowed for every other rule. #420 adds any new Ruff key to the allowlists in its own PR.
- The counting regex reads raw text, not comment tokens, so a string literal that looks like a marker overcounts, which fails safe. The new tests build every marker, exemption and comment text at run time, so their own source does not match.
- Ruff's own `ruff:` comments naming `C901` are banned, not counted. One `disable` covers any number of functions, so it cannot be counted one per function the way a marker is. The pattern accepts any verb (`ignore`, `disable`, `enable`, `file-ignore`) and any case. It therefore also reports spellings Ruff does not honour, such as `# RUFF: DISABLE[C901]`, which fails safe. A rule name like `[complex-structure]`, or a prefix like `[C9]` or `[ALL]`, does not hide `C901` in Ruff 0.16.8, so the pattern does not look for them. `PGH004` cannot be suppressed by a line or range comment at all: Ruff reports `RUF100` on the comment and still reports `PGH004`. `RUF104` (unmatched range comment) is not selected; the ban already covers every range comment that names `C901`.
- A cap rule counts as enforced only when `select` names it by its own code. That is stricter than Ruff: `select = ["C90"]` alone does enforce `C901`, but the test reports it. Matching Ruff's prefix redirects instead would mean copying a table Ruff can change.
- Ignore files that are not committed are out of the meta-test's reach: `.git/info/exclude`, a global gitignore, and ignore files above the project. They differ per machine and never reach the clean checkout GitHub CI lints. The root `.gitignore` is matched with `pathspec`, not with `git check-ignore`, so the tests start no process. Where `pathspec` and Ruff's `ignore` crate disagree on an edge case, the check can miss a file.
- The nesting walk uses an explicit stack, so it has no depth limit of its own. Only `ast.parse` limits how deep an input can go.
