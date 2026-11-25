## Tracking issue

This issue tracks the two parts of decision 5 in the section "Decisions".

- Part 1, #2010: the lazy-export modules import their names under `TYPE_CHECKING`, and the code that Ruff preview flags is rewritten with no setting changed.
- Part 2, no child issue: Ruff `PLR1702` at 5 replaces the `structural-invariants` hook, and the nesting figure leaves `devops scan complexity` and the spec verifier. Intake judged a separate Part 2 issue a duplicate of this issue on 2026-10-23, so Part 2 stays here, as decision 5 says.

The pull request of Part 2 closes this issue. It merges after #2010 closes, so this issue closes after its child issue.

---

## Friction

AGENTS.md line 14 enforces nesting with a second metric that the project wrote. The metric is `core/code_metrics.py` (207 lines). A pre-commit hook runs it as a script (`python3 -P src/devops_cli/core/code_metrics.py`). A nesting leg in a whole-tree test runs it again. Ruff has the rule `PLR1702` (too-many-nested-blocks). Issue #586 already showed the project count diverging from the Ruff count for complexity.

## Evidence

- Ruff 0.16.8, trial on generated functions with k nested blocks. The hook (`--max-depth 5`) fails from five nested `if`, `for`, `with` or `match`. `PLR1702` at `max-nested-blocks = 5` fails only from six. At 4 it fails from five, which matches the hook for `if`, `for` and `with`.
- `PLR1702` ignores `match`. Five nested `match` blocks passed at 4. The hook ignores the body of `try`. Five nested `try` blocks passed the hook and failed Ruff at 4.
- On `src/` the hook reports 0 at depth 5. `PLR1702` at 5 reports 0. At 4 it reports 13 functions (for example `ai/direct.py:230`, `config/settings.py:1284`, `k8s/service.py:348`).
- Three modules in `src/` use `core/code_metrics.py`: `security/complexity.py`, `ai/inspection.py` and `ai/spec/verifier.py`.
- The hook is at `.pre-commit-config.yaml:57-66`. The nesting leg is in `test_the_source_tree_keeps_its_structural_invariants` (`test_architectural_invariants.py:220-241`). The import-cycle and layer checks in that test stay.
- AGENTS.md:54 requires the owner's instruction before a threshold changes. The owner gave it (see the decision).

## Decision (owner, 2026-10-22)

Ruff `PLR1702` with `max-nested-blocks = 5` replaces the nesting hook. The value 5 is one level looser than the hook for `if`, `for` and `with`. The owner approved this change of the cap. The `structural-invariants` hook, the nesting leg of the whole-tree test and the nesting leg of `core/code_metrics.py` are deleted.

## Proposed remedy

- Set `max-nested-blocks = 5` in `[tool.ruff.lint.pylint]`. Enable `PLR1702` as the only preview rule: `preview = true`, `explicit-preview-rules = true` and a `select` that names it.
- Delete the hook, the nesting leg of the whole-tree test and `main` and `breaches` of `core/code_metrics.py` (39 lines).
- Read the three modules that use `core/code_metrics.py`. Each one takes a nesting figure from `ruff check --select PLR1702 --output-format json`, or drops the figure.
- State two gaps in the pull request. The value 5 is one level looser than the hook. Ruff does not count `match` blocks.
- Reword AGENTS.md line 14 (pair A15), docs/SDLC.md (O10, O12), CONTRIBUTING.md (O02) and docs/ROUTINE_TASKS.md (O23). Use the value 5 where the pairs show 4.

## What it deletes

- The hook, the nesting leg of the whole-tree test, `main` and `breaches`, and their tests (a share of the 377 lines of `tests/test_code_metrics.py`).
- No function needs a decomposition, because `src/` has 0 findings at 5.

## Tests

- The resolved-settings test of the dependency item (the Ruff-flags item) also asserts that `PLR1702` is enabled at 5.
- A negative control in `tmp_path`: six nested `if` blocks fail `ruff check`, and five pass.

## Dependencies

- refactor(ci): Ruff's own flags protect the complexity cap, and the configuration-escape tests and key allowlists are deleted
- docs(agents): agents and devops ai write in ASD-STE100 Simplified Technical English. Both items edit AGENTS.md.

## Acceptance criteria

- `ruff check` reports 0 findings for `PLR1702` at 5.
- The `structural-invariants` hook and its `args: [--max-depth, "5"]` are gone.
- The nesting leg of the whole-tree test and the nesting leg of `core/code_metrics.py` are gone.
- The pull request shows the results of both tools on `src/` once, as AGENTS.md line 54 requires for a replaced check.
- `uv run devops ci` passes.

Size: M.

---

## Rescope notes from the 2026-10-22 survey

A survey of the release tip `3ef69850` found that the remedy above is not complete. The check ran Ruff 0.16.8 on a scratch copy of the settings outside the repository. This section adds the facts and the decisions. The decision of the owner about the cap of 5 does not change. The body above stays as it is.

### What holds on the tip

- No part of this issue is merged. Both dependencies are merged: #1870 (PR #1892) and #1873.
- `PLR1702` with `max-nested-blocks = 5` reports 0 findings on the whole tree. The tree has no Python file outside `src/` and `tests/`.
- At 4 the rule reports 11 findings, all in `src/`. The count of 13 in the evidence above does not match the tip.
- The hook is at `.pre-commit-config.yaml:59-66`. The whole-tree test is at `tests/test_architectural_invariants.py:212-233`, and its nesting leg is `too_deep` at lines 223-228.
- `DEFAULT_MAX_NESTING_DEPTH` is at `src/devops_cli/config/defaults.py:675`.

### The premise "PLR1702 is the only preview rule" is false

`PLR1702` is a preview rule, so Ruff needs `lint.preview = true` to run it. That setting also turns on the preview behavior of stable rules. The setting `explicit-preview-rules = true` does not stop this. The help text of `ruff rule F822` documents one such change.

The scratch run used the Ruff settings of `pyproject.toml` with four changes. It set `preview = true` and `explicit-preview-rules = true`. It added `PLR1702` to `select` and set `max-nested-blocks = 5`. The same settings without preview report 0 findings. With preview they report 145 findings.

| Rule | Findings | Where |
| --- | --- | --- |
| `F822` undefined-export | 139 | 8 `__init__.py` files (next table) |
| `UP046` non-pep695-generic-class | 2 | `src/devops_cli/ai/toolsets/__init__.py:33` and `:107` |
| `RUF001` ambiguous-unicode-character-string | 2 | `src/devops_cli/output/formatters/scalars.py:209` and `tests/test_output.py:378` (the micro sign) |
| `F401` unused-import | 2 | `tests/test_exceptions.py:145` and `:146` |

The 8 lazy-export modules behind the 139 `F822` findings:

| Module | `F822` findings |
| --- | --- |
| `src/devops_cli/ai/review/__init__.py` | 33 |
| `src/devops_cli/core/__init__.py` | 32 |
| `src/devops_cli/config/__init__.py` | 26 |
| `src/devops_cli/ai/models/__init__.py` | 18 |
| `src/devops_cli/ai/rag/__init__.py` | 17 |
| `src/devops_cli/ai/benchmark/__init__.py` | 8 |
| `tests/support/fakes/__init__.py` | 4 |
| `src/devops_cli/__init__.py` | 1 |

Each of these modules serves its exports through a module-level `__getattr__`. Its `__all__` lists names that no import in the module binds, so preview `F822` reports them. Two other modules already import their names under `TYPE_CHECKING`, and Ruff reports nothing there: `src/devops_cli/security/__init__.py:8` and `src/devops_cli/telemetry/__init__.py:8`.

Ruff also prints a warning for `tests/test_review_security_tools.py:167`: "Invalid `# noqa` directive". It prints the same warning on the current settings without preview. Preview does not cause it, and it is outside this item. The line is a comment that contains the text `# noqa`.

### Two fixes for the F822 findings

**Fix A: rewrite the 8 modules with `TYPE_CHECKING` imports.**

- Each module gets an `if TYPE_CHECKING:` block that imports its exported names. The runtime stays lazy, because Python skips that block.
- The survey estimates about 200 lines. The two existing modules use 45 lines for 50 names (`security`) and 82 lines for 63 names (`telemetry`).
- A type checker then sees real types where it saw `Any`. `mypy --strict` can report new errors at the import sites. This rewrite is untested under `mypy --strict`.
- It changes no threshold and adds no suppression.

**Fix B: ignore `F822` for the 8 files with `lint.per-file-ignores`.**

- The help text of `ruff rule F822` names this fix.
- It breaks the settings guard of #1870. `tests/test_ruff_complexity_cap.py:96` requires `linter.per_file_ignores` to be `{}`.
- It breaks the ceiling `"per-file-ignores": 0` at `src/devops_cli/config/defaults.py:671`. The count adds one for each code in each pattern (`tests/test_architectural_invariants.py:1852`). One glob raises the ceiling to 1. Eight named files raise it to 8.
- It turns off a lint rule for 8 files, so it changes a quality threshold. `AGENTS.md:57` says only the user can allow this.

**Fix C: a third path found in the re-check, outside the survey.**

- A separate Ruff run that selects only `PLR1702` reports 0 findings at 5. It shows none of the 145 findings, because no other rule is selected. The scratch run in `/tmp` confirmed this.
- It needs a second Ruff configuration or extra command flags. `tests/test_ruff_complexity_cap.py:41` and `:393` pin every `ruff check` to `--config pyproject.toml` and to no other flag. That test must change.
- The pre-commit hook and the `devops ci` row (`src/devops_cli/commands/ci.py:662`) each need a second Ruff command.

The 6 other findings do not depend on this choice. Each needs its own fix:

- `UP046`: rewrite the two classes with PEP 695 type parameters. `AbstractToolset` inherits from `BaseModel`, so the rewrite needs a pydantic and mypy check.
- `RUF001`: add the micro sign to `allowed-confusables` (`pyproject.toml:131`). The other option is to print the Greek letter mu, which changes the output of `format_duration` and its test.
- `F401`: the two imports in `tests/test_exceptions.py` appear to exist for their side effect. A `# noqa: F401` marker raises the ceiling `"tests noqa: F401": 3` at `src/devops_cli/config/defaults.py:665`. A call to `importlib.import_module` needs no marker. This rewrite is untested.

### The nesting figure: `--max-indent` and `max_indentation`

`core/code_metrics.py` keeps `nesting_depth` and `max_nesting_depth` after the hook goes. Three product paths read that figure:

- `src/devops_cli/security/complexity.py:40-48` raises a finding when `fn.max_nesting_depth` is above the cap.
- `src/devops_cli/commands/scan.py:519-546` passes `--max-indent` into it. The option text is at `src/devops_cli/lang/en/help.py:1430`. The generated docs list it at `docs/CLI_REFERENCE.md:3102`, `docs/commands/scan.md:162` and `docs/MCP_TOOLS.md:2061`.
- `src/devops_cli/ai/spec/verifier.py:70-90` builds the rule `max_indentation`. The dry-run result at line 122 and `tests/test_ai_spec.py:54` and `:111` use it.

`src/devops_cli/ai/inspection.py:28` reads only the cyclomatic figure, so it needs no change.

`PLR1702` gives no depth for each function. It prints one line, "Too many nested blocks (N > M)", only for a function above the cap `M`. A function at or under the cap gets no figure. Ruff is a dev dependency only (`pyproject.toml:83`). A figure from Ruff therefore needs a Ruff subprocess in product code with the cap set to the user value.

The other path is to drop the figure. That also removes `nesting_depth`, `max_nesting_depth`, `_NESTING` (`core/code_metrics.py:24`) and `DEFAULT_MAX_NESTING_DEPTH`. It removes `--max-indent` and the rule `max_indentation` from the CLI, the MCP tool and the spec verifier.

### Decisions (owner, 2026-10-22: follow best practices)

1. **Which fix clears the 139 `F822` findings: A, B or C?**
   Decided: A. It changes no threshold and adds no suppression. It follows the pattern of `security/__init__.py` and `telemetry/__init__.py`. It keeps one Ruff configuration, pinned by #1870. Accept that Effort can rise from M to L if `mypy --strict` reports errors.
2. **How do the 6 other findings get fixed?**
   Decided: rewrite `UP046` with PEP 695 type parameters. Write the micro sign as the escape `\u00b5` in the source of `output/formatters/scalars.py` and `tests/test_output.py`, so `RUF001` has no literal to report and no lint setting changes. Replace the two test imports with `importlib.import_module` and add no `noqa` marker. The first and third fixes are untested, so the pull request proves each one.
3. **Does `devops scan complexity` keep `--max-indent`, and does the spec verifier keep `max_indentation`?**
   Decided: drop both. Ruff gives no depth for each function, and Ruff is not a product dependency. The remedy above already allows "or drops the figure". This is a public CLI and MCP change. Pre-1.0 policy allows it.
4. **Does a follow-up issue cover the hand-written McCabe port `mccabe_complexity` (`core/code_metrics.py:73`)?**
   Decided: yes, as a separate issue, not in this item. The lead files it after this item starts. Ruff `C901` enforces the same property (#586). `devops scan complexity` and `ai/inspection.py` still read the port, so its removal needs its own plan.
5. **Does the work ship as one pull request or as two parts?**
   Decided: two parts. Part 1 applies the answers to questions 1 and 2. It changes no setting and leaves the gate green. Part 2 switches on preview, deletes the hook, the test leg and the metric code, and updates the docs. Part 1 is #2010, and its own pull request closes that issue. The pull request of Part 2 closes this issue.

### Proposed addition to the acceptance criteria

- `ruff check --config pyproject.toml .` reports 0 findings with preview on, for every selected rule and not only `PLR1702`.

### Status

The issue has no milestone. It stays in the backlog until a person plans its milestone on the board. The survey found no item of v0.2.39 that depends on it. Only a person runs mutating `devops roadmap` commands while the roadmap service is suspended (#1562).

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=4da1e346a2a752bf9581aa2ab29e9637ff3e71d9 -->
## Proposed design

### Problem statement
The project enforces a nesting depth cap of 5 with a custom pre-commit hook and a 207-line metric script. Ruff's rule PLR1702 replaces that hook. This issue enables PLR1702 at max-nested-blocks = 5. It deletes the structural-invariants hook, the nesting leg of the whole-tree test, and the nesting metric code. It drops the --max-indent option and the max_indentation spec rule. It updates the documentation to reflect the new enforcement.

### Acceptance criteria
- Criterion 1: ruff check reports 0 findings for PLR1702 at max-nested-blocks = 5 on the whole tree.
  Verification: Run `ruff check --config pyproject.toml .` and confirm 0 PLR1702 findings.
- Criterion 2: The structural-invariants hook is removed from .pre-commit-config.yaml.
  Verification: Confirm .pre-commit-config.yaml has no structural-invariants hook entry and no args: [--max-depth, "5"].
- Criterion 3: The nesting leg of test_the_source_tree_keeps_its_structural_invariants is removed.
  Verification: Run `uv run devops ci test tests/test_architectural_invariants.py` and confirm the test passes without the too_deep assertion.
- Criterion 4: The functions main, breaches, nesting_depth, and the constant _NESTING are removed from core/code_metrics.py.
  Verification: Confirm src/devops_cli/core/code_metrics.py has no main, breaches, nesting_depth, or _NESTING.
- Criterion 5: The --max-indent option is removed from devops scan complexity.
  Verification: Run `uv run devops scan complexity --help` and confirm --max-indent is absent.
- Criterion 6: The max_indentation rule is removed from the spec verifier.
  Verification: Confirm src/devops_cli/ai/spec/verifier.py has no max_indentation rule.
- Criterion 7: ruff check reports 0 findings with preview on, for every selected rule.
  Verification: Run `ruff check --config pyproject.toml .` and confirm 0 findings for all selected rules.
- Criterion 8: uv run devops ci passes.
  Verification: Run `uv run devops ci` and confirm all checks pass.
- Criterion 9: The documentation references PLR1702 and does not reference the structural-invariants hook.
  Verification: Confirm AGENTS.md, docs/SDLC.md, CONTRIBUTING.md, and docs/ROUTINE_TASKS.md reference PLR1702 and do not reference the structural-invariants hook.
- Criterion 10: A negative control confirms six nested if blocks fail and five pass.
  Verification: Create a file with six nested if blocks, run ruff check, confirm it fails. Change to five, confirm it passes.

### Key questions
- **Which fix clears the 139 F822 findings: A, B or C?**: Fix A: rewrite the 8 modules with TYPE_CHECKING imports. It changes no threshold and adds no suppression. It follows the pattern of security/__init__.py and telemetry/__init__.py. (proposed)
- **How do the 6 other findings get fixed?**: UP046: rewrite with PEP 695 type parameters. RUF001: write the micro sign as \u00b5 in scalars.py and test_output.py. F401: replace the two test imports with importlib.import_module and add no noqa marker. (proposed)
- **Does devops scan complexity keep --max-indent, and does the spec verifier keep max_indentation?**: Drop both. Ruff gives no depth for each function, and Ruff is not a product dependency. Pre-1.0 policy allows the public CLI and MCP change. (proposed)
- **Does a follow-up issue cover the hand-written McCabe port mccabe_complexity?**: Yes, as a separate issue. Ruff C901 enforces the same property. devops scan complexity and ai/inspection.py still read the port, so its removal needs its own plan. (proposed)
- **Does the work ship as one pull request or as two parts?**: Two parts. Part 1 is #2010 and fixes the 145 preview findings. Part 2 is this issue and switches on preview, deletes the hook and metric code, and updates the docs. Part 2 merges after #2010 closes. (proposed)

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
#2010
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "High", "Priority": "P2-Medium", "Status": "Ready", "Value": "Medium", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "8365c1c3ded79f107955fbd519d6167b969642f4d387ffd0aa0aadc7678add5f", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "c2cb5cab0f21f894e4a7f58bbe4adc2ca2d4bcf2313e11f75d14b3a7cad5640f"} -->
