# Proposal: #4529

## Why

Issue #4529: the caller gate (#3307) of the stage plan check does not refuse a plan that adds a parameter to a function and leaves out a caller of that function. PR #4490 (#4467) made `changed_functions` read a function name only when the added part of the clause holds the word `parameter`, `argument` or `keyword`. The most frequent task form, Add `x` to `fn` or Add `x: T = d` to `fn`, holds none of these words, so the gate reads no function and reports no missing caller. Closes #4529.

## What Changes

- `src/devops_cli/roadmap/stage/stage_paths.py`: `changed_functions` also reads a clause whose added part is one code span, alone or after `the`, that `ast` reads as the parameters of a `def`, as `known` or `sampling: CallSampling | None = None`. A decorator, an option and a constant in capitals are no parameter. The `def` filter of `calling_files` drops a class or an enum, as before.
- `tests/roadmap/stage/test_roadmap_stage_paths.py`: the refused-caller test uses the plain form Add `probes` to `check_proposal` again. The table of task texts gets the true forms of the archived tasks and the false forms of a decorator, an option and a span with other words. A new test keeps a field of a model free of a caller problem.
- `docs/ROADMAP_WORKFLOW.md` states the rule.
- The change carries a spec delta, because the stage plan check is behavior that a consumer observes: one requirement of `roadmap-stage` changes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The path gate names every caller of a function that a task changes

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_paths.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_paths.py`
- The stage job refuses again a plan that adds a parameter in the plain form and leaves out a caller. Over the 924 archived `tasks.md` files, the gate reads 58 function names (the rule before #4490 read 75, `main` reads 35), and each of the 23 new reads is a true parameter addition. On the 36 stored refused replies the caller problems stay at 4, all true, so no false refusal that #4490 removed comes back.

## Feasibility

- The premise holds on `origin/main` (7234d718). The probe of the issue (`changed_functions` on one task text) gives `[]` for Add `known` to `build_import_graph`, Add `sampling: CallSampling | None = None` to `_retry_chat_dispatch`, Add `facts_source` to `plan_item` and Add `probes` to `check_proposal`, and `['build_import_graph']` only when the text says the keyword `known`.
- `calling_files` already returns no file for a name that no module under `src/` defines with `def`, so a class such as `StageProposal` or `FailureClass` stays out of the gate when the clause reads it.
- `ast.parse` reads `def _(<span>): pass` with no error only for a parameter list. `@dry_run_class("request-plan")` and `--take-ownership` give a `SyntaxError`; `REVIEW = "review"` parses, and the capitals rule (PEP 8 names constants in capitals) drops it.

## Existing Tool Considered

The standard library `ast` decides the parameter shape of a code span, as `ast` already reads the calls of `calling_files`. No regex for type annotations is written.
