# Proposal: #4467

## Why

Issue #4467: two stage plan gates refuse correct plans, and the refusals stop the stage job for items that have a correct plan. The module-test gate (#3414) counts a test as a test of a module when its text holds the dotted name of the module, and its search reads each dot of that name as a regex wildcard. So a plan that changes `src/devops_cli/lang/en/messages.py` must name `tests/commands/test_new.py`, which holds the path of the module in a string and runs none of it. The caller gate (#3307) reads a function name from a task text that runs across sentences and names a class, and it finds callers with no word boundary. In the 36 refused replies that the stage job stored, 18 of 34 module-test problems and 22 of 26 caller problems are false.

## What Changes

- `src/devops_cli/roadmap/stage/stage_paths.py`: `record_module_tests` counts a test of a module only when the test imports the module, a package whose `__init__.py` imports it, or another module that the plan changes and that imports it. `ast` and the import graph read the imports. The test naming convention alone no longer makes a test of a module. `changed_functions` reads only a task clause that adds a parameter, an argument or a keyword to a function, and `StagedTree.callers` finds the calls with `ast` among the files that `git grep -F -w` gives. A name that no module defines with `def` has no caller.
- `src/devops_cli/roadmap/stage/stage_overlap.py`: `grep_at` searches a fixed string (`git grep -F -w`), so a dot of a dotted name is no wildcard.
- `src/devops_cli/core/import_graph.py`: `build_import_graph` takes the names of more known modules, so a caller that parses only some files resolves `from pkg import name` to the submodule.
- `src/devops_cli/roadmap/plan_recheck.py`: the tree of the recheck reads the files at the revision of the pass, so the record of the module tests reads the imports of the tests there.
- `docs/roadmap/plan-check.md` and `docs/ROADMAP_WORKFLOW.md` state the rules.
- The change carries a spec delta because the stage job and its plan check are behavior that a consumer observes: four requirements of `roadmap-stage` change and one joins.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The path gate names every caller of a function that a task changes, Refuse a behavior group that omits the test of its module, Accept a behavior group that names the test of its module, Exempt a module that has no existing test, A test that holds the name of a module in text is no test of it

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/roadmap/stage/stage_overlap.py`, `src/devops_cli/core/import_graph.py`, `src/devops_cli/roadmap/plan_recheck.py`
- Documents: `docs/roadmap/plan-check.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_paths.py`
- The stage job refuses fewer correct plans. Of the 36 stored refused replies, the module-test and caller problems fall from 61 to 23 on the tree of `origin/main`, and 3 replies whose only problems were these gates pass. A negative-search literal with a dot now matches as fixed text in the search evidence of the stage job, because that evidence uses `grep_at` too.

## Feasibility

- The search reads dots as wildcards: `git show origin/main:src/devops_cli/roadmap/stage/stage_overlap.py` holds `listing = git(source, "grep", "-w", "-l", "-e", name, sha, operation=operation)` in `grep_at`, with no `-F`. On `origin/main`, `git grep -l -w -e 'devops_cli.lang.en.messages' -- tests` lists 24 files and `git grep -l -w -F 'devops_cli.lang.en.messages' -- tests` lists 1. `tests/commands/test_new.py:76` holds `"src/devops_cli/lang/en/messages.py": MESSAGES_FILE,`, which the regex matches.
- The record counts text, not imports: `record_module_tests` in `src/devops_cli/roadmap/stage/stage_paths.py` adds `{test for test in search(dotted) if _is_test_module(test)}` and the tests whose name carries the stem of the module (`_stem_names`). The premise of the issue says that about 30 tests import `devops_cli.lang.en`: on `origin/main` only `tests/roadmap/implement/test_roadmap_implement_amend.py` holds `from devops_cli.lang.en.messages import MESSAGES`, and 56 tests hold `from devops_cli.lang import`. The 24 files come from the regex, as the second point of the issue states. `tests/commands/test_new.py` holds `from devops_cli.lang import HELP` only inside the text of a scaffold, so `ast` reads no import there.
- The caller search has no word boundary: `StagedTree.callers` runs `git grep -n -F -- f"{name}("`, so `_fix(` matches `scan_fix(`, and it reads `asyncio.TaskGroup(` as a call of `TaskGroup`. `changed_functions` uses `\bAdd\s+.+?\s+to\s+`([A-Za-z_][A-Za-z0-9_]*)``, which runs across sentences: the reply of #3416 gave `skipped` from a clause that started three sentences before, and the reply of #3049 gave `FailureClass` from `Add `REVIEW = "review"` to `FailureClass``, an enum member.
- The measure: a replay of `record_module_tests`, `existing_test_problems` and `caller_problems` over the 36 stored replies (`<n>.refused.json` of 18 items, from 2026-11-10 and 2026-11-11) on the tree of `origin/main` gives 35 module-test and 26 caller problems before the change, the counts of the study. After the change it gives 19 and 4. The 4 caller problems that stay are true: the replies of #3407 and #3423 add the keyword `class_text` or `base_scenarios` to `check_gates` and `check_proposal` and leave out `plan_recheck.py`, `implement.py` and `plan_check.py`, which call them.
- The repository has the tool for imports: `src/devops_cli/core/import_graph.py` holds `build_import_graph` and `module_name`, and `src/devops_cli/core/test_selection.py` already maps changed sources to tests with them.
- The replay of the golden set builds `StagedTree(self.facts.tracked)` in `src/devops_cli/roadmap/stage/stage_eval_cases.py`, with no checkout and no search, so `uv run devops roadmap eval stage --replay` judges neither gate before or after the change.
- The first check against the real system is `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py`, then the replay of the stored replies and `uv run devops roadmap eval stage --replay` on the base and on the change.

## Existing Tool Considered

The fix uses tools that the repository has: `ast`, `build_import_graph` and `module_name` of `src/devops_cli/core/import_graph.py`, and `git grep -F -w`. No open tool reads the clause of a plan task that adds a parameter, so the change narrows the existing pattern of `changed_functions`. The written cost is about 4,000 tokens to keep and fix the new code, and about 3 hours of elapsed time to build and measure it.

## Dependencies

None.
