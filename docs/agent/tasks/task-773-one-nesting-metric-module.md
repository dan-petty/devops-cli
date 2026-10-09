# Task: One nesting metric module shared by the pre-commit hook and the scanner (#773)

**Issue**: [#773](https://github.com/dan-petty/devops-cli/issues/773)
**Status**: Done
**Milestone**: v0.2.30
**Priority**: priority/p2-medium
**Scope**: type/refactor, scope/ci

## Description

Before this change the nesting metric was computed three times: by `security/complexity.py`'s `_ComplexityVisitor` (the scanner, which also counted complexity), by `security/structural_invariants.py` (the pre-commit hook), and by `ai/spec/verifier.py`'s `_get_ast_depth`. The copies disagreed. The hook counted the function body as depth 0 and the scanner as depth 1, so 5 nested ifs passed the hook and failed CI. The scanner's complexity was an in-house count: 244 functions in `src/` over 10, where Ruff's `C901` finds 54, and 5 of Ruff's 54 were missed. The hook kept its own copy because importing the scanner loaded every scanner and pydantic-ai. A parity test (`test_the_metric_matches_the_projects_own_scanner`) existed only to show that the hook and scanner copies agreed.

`src/devops_cli/core/code_metrics.py` is now the one copy. It uses only the stdlib and imports nothing from `devops_cli`:

- `nesting_depth(func)` is the hook's explicit-stack walk with the function body at depth 1. It walks statements only, since an expression can hold no nesting block and no def.
- `mccabe_complexity(func)` is a port of Ruff's `get_complexity_number`, split into per-construct helpers.
- `measure_tree(tree)` returns a `FunctionComplexity` for each function in source order.
- `breaches(path, max_depth)` checks nesting only. A file it cannot read or parse is reported as a breach, including a parser overflow: a `RecursionError`, or the `MemoryError` a long unary chain (`- - - ... 1`) raises.
- `main(argv)` is the hook's entry point. It takes a required `--max-depth` and the file paths.

It has two adapters:

- **The hook** (`python -m devops_cli.core.code_metrics`) works from argv and writes to stderr.
- **`devops scan complexity`** (`run_complexity_scan`, which MCP `scan_complexity` runs too) turns the results into `Finding`s.

The inspection hotspots, `devops ai spec`'s indentation rule and the single whole-tree test also read the module.

## Decisions

- **Depth origin 1.** The function body is depth 1. CI, the authoritative gate (ADR 0004), already counted this way in `test_no_excessive_nesting_in_src`. It matches AGENTS.md's "< 6 indentation levels", the issue amendment's "nothing blocks them" for the depth-6 test functions, and `ai/spec/verifier.py`. The hook was the lenient copy, with origin 0.
  - At the boundary, 4 nested ifs are depth 5 and pass, and 5 nested ifs are depth 6 and fail.
  - The nesting node set is unchanged: If, While, For, AsyncFor, ExceptHandler, With, AsyncWith, Assert and Match. A nested def is measured on its own.
- **Complexity follows Ruff `C901`** (standard McCabe), which is what the issue amendment asked for. The amendment's fallback, Ruff's JSON output, was not needed, because the port agrees with Ruff on every function.
  - `assert`, `with`, conditional expressions and boolean operands add nothing.
  - A closure adds 1 plus its own count to the function that defines it, and is also reported on its own.
  - A trailing irrefutable, unguarded `match` case subtracts 1.
  - A `try` adds 1 per handler, plus 1 when it has an `else`.
- **The whole-tree test covers `src/` only**, which keeps the gate fast. The commit hook checks every staged `.py` file, `tests/` included. Under origin 1 exactly six test functions sat at depth 6; this change flattens them.
- **Thresholds are hook arguments.** `.pre-commit-config.yaml` passes `--max-depth 5`, and `test_the_commit_hook_runs_this_module_at_the_default_cap` pins the entry and args to `DEFAULT_MAX_NESTING_DEPTH`.
- **One parse helper.** `_parse_src()` in `tests/test_architectural_invariants.py` is a plain function that reads `src/devops_cli` once, located from the test file rather than the working directory, with no cache: exactly one test calls it, and #848 extends that same test.

## Acceptance Criteria

- [x] A fresh-subprocess hook run leaves no `devops_cli.security` or `devops_cli.security.*` module, and no `pydantic_ai`, in `sys.modules` (`test_the_hook_loads_no_scanner_and_no_pydantic_ai`). The module's own imports are stdlib only.
- The amendment's "imports nothing from `devops_cli.config`" holds for the module's own imports only. `python -m devops_cli.core.code_metrics` first runs the package inits. `devops_cli/__init__.py` imports `devops_cli.config.metadata`, and with it pydantic and the `devops_cli.config` barrel (`commands`, `constants`, `defaults`, `env` and `options`). `devops_cli/core/__init__.py` imports `core.cli`, and with it typer and 16 `devops_cli.exceptions` modules. A hook run loads 269 modules, and took 0.43 s against 0.07 s for an interpreter importing only the module's stdlib imports (medians of 5, load average about 12). #776 removes the config barrel. Making `devops_cli/__init__.py` and `devops_cli/core/__init__.py` lazy is outside this item: moved to a follow-up issue, not yet filed.
- [x] The (file, function) pairs the scanner flags at 10 are the pairs Ruff `C901` flags: 54/54 in `src/`, 0/0 in `tests/`. With `ruff check --ignore-noqa --select C901 --config lint.mccabe.max-complexity=0` (ruff 0.16.8), all 18,000 functions in the tracked `src/` and `tests/` files on this branch get the same value from both, with no key or value difference. Without charging closures to the function that defines them, `src/` would give 48. The six it would miss are `ai/ext_langchain.py:24` and, in `ai/harness/`, `agents.py:377`, `memory.py:629`, `planning.py:440`, `shell.py:371` and `workflow.py:262`.
- [x] A function with 4 asserts inside a `with` scores 1. `test_complexity_is_ruffs_c901_count` holds 12 fixtures, each value read once from Ruff and hard-coded.
- [x] The depth origin is fixed, with boundary fixtures at depths 5 and 6 (`test_the_function_body_is_depth_one`). On all 18,000 functions, the new depth equals the old hook depth plus 1.
- [x] The parity test is deleted, with the rest of `tests/test_structural_invariant_hook.py`. Its fixture tests now run in-process through `main([...])` in `tests/test_code_metrics.py`.
- [x] Exactly one whole-tree test remains, `test_the_source_tree_keeps_its_structural_invariants`, which parses `src/devops_cli` once through `_parse_src()`.
- [x] The test-step `--durations` difference is negative. Each pair below was run back to back with `-n 0`, on the exported base (`edd2578`) and then on this branch:
  - **Pair 1** (load average about 17 for both runs):
    - Before: 60.9 s of call time. The parity test took 25.8 s, the three hook subprocess spawns 9.5, 9.1 and 11.3 s, and `test_no_excessive_nesting_in_src` 5.3 s.
    - After: about 5.1 s. `test_the_source_tree_keeps_its_structural_invariants` took 4.7 s and the import-check subprocess 0.3 s.
    - Difference: about −55.8 s.
  - **Pair 2** (load average falling from 18 to 10):
    - Before: 31.7 s of call time, 42.9 s wall.
    - After: 3.9 s of call time, 11.1 s wall.
    - Difference: −27.8 s of call time.
  - The whole-tree test costs what the one it replaces did (3.47 s against 3.48 s in pair 2): most of it is parsing `src/`. The saving comes from deleting the parity test and the three hook subprocess spawns.
- [x] One hook run over one file (`python -m`, without `uv run`'s own start-up) takes 0.58 s instead of 8.45 s, the medians of 5 interleaved runs each at a load average of about 18. At a load of about 5 it was 0.2 s against 3.0 s.
- [x] No new dependency: `pyproject.toml` and `uv.lock` are untouched.
- [x] `changelog.d/773.md` exists, and `CHANGELOG.md` and `docs/ROADMAP.md` are untouched.

## Stale References in the Issue

- `ai/benchmark/suite.py`, which the amendment lists as a consumer, does not exist. `ai/benchmark` holds no complexity caller.
- The amendment also lists "#593 PR2's content-taking entry". #593 is closed, and its work now sits in #873, which runs `C901` itself through Ruff, so no source-taking entry is added. Inspection and the whole-tree test already hold trees, and the hook holds paths.

## Out of Scope

- `elif` and `assert` each count as a nesting level, as before: an `elif` is an `If` in the outer `If`'s `orelse`.

## Deliverables

- [x] `src/devops_cli/core/code_metrics.py`: `FunctionComplexity`, `nesting_depth`, `mccabe_complexity`, `measure_tree`, `breaches` and `main`. Every function in it stays at C901 ≤ 10 and nesting ≤ 5 with no `# noqa`. It is not added to `devops_cli.core`'s exports.
- [x] `src/devops_cli/security/complexity.py`: only `run_complexity_scan` and `_evaluate_function_findings` remain. It parses each file in its own `try`, skips a file it cannot read or parse (`OSError`, `SyntaxError`, `ValueError`, `RecursionError` or `MemoryError`, not any exception) and calls `measure_tree`. `_ComplexityVisitor`, `FileComplexityReport` and `analyze_file_complexity` are deleted. The public signature is unchanged, so `commands/scan.py` and MCP `scan_complexity` need no edit.
- [x] `src/devops_cli/ai/inspection.py` uses `measure_tree` instead of the private `_ComplexityVisitor`.
- [x] `src/devops_cli/ai/spec/verifier.py`: `_get_ast_depth` and `_check_ast_indentation` are deleted. Violations are the functions whose `max_nesting_depth` exceeds `DEFAULT_MAX_NESTING_DEPTH`, and the detail string formats that constant instead of a literal 5. `test_the_indentation_rule_counts_nesting_as_the_commit_hook_does` (`tests/test_ai_spec.py`) pins the change: an `except` handler opens a level, and a `try` body does not.
- [x] `src/devops_cli/security/structural_invariants.py` is deleted. `.pre-commit-config.yaml` runs `uv run python3 -m devops_cli.core.code_metrics` with `args: [--max-depth, "5"]`, and the comment above the hook says what it loads.
- [x] `tests/test_code_metrics.py` is new. `tests/test_scan_complexity.py` moves to `measure_tree`, and its closure test is flipped to `[("inner", 3, 2), ("outer", 4, 1)]`. In `tests/test_architectural_invariants.py`, `_parse_src()` and the whole-tree test replace `test_no_excessive_nesting_in_src`. `tests/test_structural_invariant_hook.py` is deleted.
- [x] The six test functions at depth 6 are flattened with guard clauses, comprehensions or one combined `with`, so the hook passes them:
  - `test_no_bare_generic_exceptions_in_refactored_modules` (`tests/test_architectural_invariants.py`)
  - `test_github_workflows_caching_configuration` (`tests/test_ci.py`)
  - `test_entry_toggle_ast_invariants` (`tests/test_cli_startup_imports.py`)
  - `_extract_images_from_yaml` (`tests/test_k8s_valkey_stack.py`)
  - `test_rich_imports_confined_to_output_submodule` (`tests/test_output.py`)
  - `test_telemetry_tracing_instrumentation` (`tests/test_sandbox_metrics.py`)

  The hook passes every tracked `.py` file.
- [x] `AGENTS.md`, `CONTRIBUTING.md` and `docs/SDLC.md` drop the "in-house count" claim and name the new test. `uv run devops docs check` reports the generated docs up to date.
