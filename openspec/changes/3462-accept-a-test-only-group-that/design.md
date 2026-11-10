# Design

## Decisions

- **Judge only an `other` group whose every changed path is a test module under `tests/`**: A helper and a fixture are no test cases, so the rule cannot ask such a group for the test function that it updates; a group with one path that is no test module is accepted, as the issue asks.
- **Publish the existing `_is_test_module` of `src/devops_cli/roadmap/stage/stage_paths.py` as `is_test_module` and import it in `src/devops_cli/roadmap/stage/stage_change.py`**: That module holds the two pytest collection patterns already, so one definition decides the test-module form for the reference record and for this rule, and no second pattern can drift from it.
- **Drop the exclusion of fixture paths from the rule**: A fixture or a data file under `tests/` matches neither pytest pattern, so the new condition already accepts a group that changes it, and the exclusion repeated the same test.
- **Keep the catalog message `stage_problem_test_only`**: It names the group and the missing test function, and a refused group still changes only test modules, so a second key would repeat the same text.
- **Keep the rule in `content_problems`**: The stage job and the replay both call `content_problems` through `check_proposal`, so one rule set judges both.
- **Add the self-acceptance case under a name of its own**: `test_content_problems_accepts_this_plans_own_proposal` already builds the #3266 plan's proposal, so a second function of that name would shadow it.
- **Rename the predicate in its own group before the rule changes**: The rename keeps behavior and has its own verify, so the behavior group of the rule imports a published name and its step stays inside the budget.

## Rejected alternatives

- **Treat every Python file under `tests/` as a test module**: `tests/support/builders.py` is a Python file under `tests/`, so that rule refuses the helper group that the issue must accept.
- **Match a `test_` substring in the implementation**: A code span that holds only `tests/roadmap/stage/test_roadmap_stage_content.py` contains `test_`, so the group would pass with no function; `_is_test_function_span` matches the last `::` segment instead.
- **Reuse `_is_test_module` of `src/devops_cli/roadmap/stage/stage_form.py`**: `src/devops_cli/roadmap/stage/stage_form.py:151:path.name.startswith(_TEST_MODULE_PREFIX)` tests only the `test_` prefix, so a file named `foo_test.py` would count as a helper and its group would pass with no test function.
- **Add the catalog message `stage_problem_test_only_no_function`**: `src/devops_cli/lang/en/messages.py:3901:stage_problem_test_only: str = (` already names the group and the missing test function, so a second key duplicates the text.
- **Update the existing `test_content_problems_accepts_this_plans_own_proposal` in place**: `tests/roadmap/stage/test_roadmap_stage_content.py:853:def test_content_problems_accepts_this_plans_own_proposal() -> None:` builds the #3266 plan's own proposal, so updating it in place would drop that self-acceptance case; the plan adds a case with a name of its own.
- **Keep the exclusion of fixture paths from the rule**: A fixture path matches neither `test_*.py` nor `*_test.py`, so the new condition already accepts a group that changes it, and the exclusion states the same form twice.

## Unchanged references

- `src/devops_cli/roadmap/stage/stage_form.py` (function definition): Its `_is_test_module` takes a `PurePosixPath` and tests only the `test_` name prefix for the form checks, so this rename leaves it as it is.
