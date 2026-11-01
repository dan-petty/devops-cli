# Proposal

## Why

Issue #2600 asks one question. Should `devops scan complexity` and the inspection hotspots read their complexity figure from Ruff at run time, or keep the McCabe port in `src/devops_cli/core/code_metrics.py` with a stated reason?

The answer is: keep the port. Ruff is a development dependency only. Ruff gives the figure only inside a message string, and only for a function above `max-complexity`. The port is one standard-library module, and a test holds 12 figures that were taken from Ruff.

The module docstring does not state this reason yet. This change adds it, so the next reader does not ask the same question again.

## What Changes

- `src/devops_cli/core/code_metrics.py`: the module docstring gets a short paragraph. It says why the module does not call Ruff. The code does not change.
- The change has no spec delta (`skip_specs: true`). No `devops` command, option or message changes, and the figures that the two readers report stay the same.
- The change fits one pull request.
- The change deletes no code. The port stays, so the second acceptance criterion of the issue (the port goes) does not apply.

## Acceptance

| Criterion of the issue | Delivered by |
| :--- | :--- |
| The two readers get their complexity from one source that matches `ruff check --select C901`, and a test holds it. | Already true on `origin/main`. Both readers call `measure_tree`, and `tests/core/test_code_metrics.py` holds the figures (see Feasibility). The test holds 12 figures taken from Ruff and does not run Ruff. Group 1 keeps these tests green and states the reason in the module. |
| If the port goes, `core/code_metrics.py` and its samples go with it. | Does not apply. The decision is to keep the port. |

## Feasibility

All checks ran on `origin/main` with Ruff 0.16.8.

- Ruff is not a runtime dependency. A script that loads `pyproject.toml` printed `[] ['ruff==0.16.8']`: no `ruff` in `[project] dependencies`, and `ruff==0.16.8` in `[dependency-groups] dev`.
- Ruff has no structured complexity field. `ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=0' --output-format json x.py` on a function `f` with one `if` printed one entry with `"message": "`f` is too complex (2 > 0)"`. The keys are `cell`, `code`, `end_location`, `filename`, `fix`, `location`, `message`, `name`, `noqa_row`, `severity` and `url`. The number is only in `message`.
- Ruff reports only the functions above `max-complexity`. A figure for every function needs `max-complexity=0`, a Ruff process per scan, and a parse of the message string.
- Product code reads the figure in two places only. `git grep -n "code_metrics" src` prints `src/devops_cli/ai/inspection.py:28` and `src/devops_cli/security/complexity.py:15`. Both import from `devops_cli.core.code_metrics`, and both call `measure_tree`.
- The module has 119 lines, of which 89 are code. `wc -l` and `grep -v '^\s*#\|^\s*$' | wc -l` printed 119 and 89. This matches the "about 90 lines" of the issue.
- The test holds 12 figures taken from Ruff. It does not run Ruff. `tests/core/test_code_metrics.py` has one test with 12 parameters (not `tests/test_code_metrics.py`, which the issue names by its old path). A scratch script wrote each of the 11 sample sources to a file and ran the Ruff command above on it. For each function, the figure of Ruff equalled the figure of `measure_tree`. It printed `diffs 0`.
- Other product code already runs Ruff as a subprocess (`_default_ruff_block_checker` in `src/devops_cli/review/analysis.py` runs `ruff check` with `F,UP`). That code finds `ruff` on `PATH` and does not make Ruff a declared runtime dependency. It does not change the decision: the complexity scan runs for every user of `devops`, and it must not need a tool that is only a dev dependency.
- Nothing newer changed the question. `git log origin/main` for the module and its test shows #2830 (test move), #2602 (nesting removed, #1876) and #1975. No open change folder other than this one names `code_metrics` or `scan complexity`.
- `CONST_COMPLEXITY_SOURCE` in `src/devops_cli/config/constants.py` is `"mccabe (ruff C901)"`. It is the `source` field of the findings and it stays true.

## Existing Tool Considered

Ruff `C901` counts the same standard McCabe figure, and CI already enforces it at 10 with `ruff check`. The change does not use it at run time for these reasons.

- Ruff as a runtime dependency adds a native binary to every install of `devops`, for a metric that 89 lines of standard-library Python compute.
- Ruff as a subprocess needs Ruff on `PATH` where `devops scan` runs, one process per scan, and a parse of a message string, because JSON output has no number field.

The written cost of the port is: about 89 lines of code in `src/devops_cli/core/code_metrics.py`, and 12 test samples in `tests/core/test_code_metrics.py`. The test compares the port to 12 figures that were taken from Ruff. It does not run Ruff, so a later change of Ruff counting does not fail it. The cost to write this change is one docstring paragraph. The change deletes no internal code.
