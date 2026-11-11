# Design

## Decisions

- **Judge only an `other` group whose every changed path is a test module under `tests/`**: A helper and a fixture are no test cases, so the rule cannot ask such a group for the test function that it updates; a group with one path that is no test module is accepted, as the issue asks.
- **Reuse `is_test_module` of `src/devops_cli/core/test_selection.py` and keep the `tests/` prefix in the rule**: It is public, and the test selector, the coverage index and `devops ci test` share it. The plan check then counts a file as a test module exactly when `devops ci test` runs it as one, and the change adds no predicate.
- **Drop the exclusion of fixture paths from the rule**: A fixture or a data file under `tests/` is no test module, so the new condition already accepts a group that changes it, and the exclusion repeated the same test.
- **Keep the catalog message `stage_problem_test_only`**: It names the group and the missing test function, and a refused group still changes only test modules, so a second key would repeat the same text.
- **Keep the rule in `content_problems`**: The stage job and the replay both call `content_problems` through `check_proposal`, so one rule set judges both.
- **Add the self-acceptance case under a name of its own**: `test_content_problems_accepts_this_plans_own_proposal` already builds the #3266 plan's proposal, so a second function of that name would shadow it.

## Rejected alternatives

- **Treat every Python file under `tests/` as a test module**: `tests/support/builders.py` is a Python file under `tests/`, so that rule refuses the helper group that the issue must accept.
- **Match a `test_` substring in the implementation**: A code span that holds only `tests/roadmap/stage/test_roadmap_stage_content.py` contains `test_`, so the group would pass with no function; `_is_test_function_span` matches the last `::` segment instead.
- **Publish `_is_test_module` of `src/devops_cli/roadmap/stage/stage_paths.py` as `is_test_module`**: The package would then hold two public functions of that name with different rules, because that predicate also takes `*_test.py`, which `devops ci test` and the selector do not run as a test module. The repository holds no `*_test.py` file, so the wider pattern changes no verdict on this tree.
- **Reuse `_is_test_module` of `src/devops_cli/roadmap/stage/stage_form.py`**: It is private to the form checks and takes a `PurePosixPath`, and the public `is_test_module` of the core applies the same `test_` prefix test.
- **Add the catalog message `stage_problem_test_only_no_function`**: `src/devops_cli/lang/en/messages.py:3902:stage_problem_test_only: str = (` already names the group and the missing test function, so a second key duplicates the text.
- **Update the existing `test_content_problems_accepts_this_plans_own_proposal` in place**: `tests/roadmap/stage/test_roadmap_stage_content.py:853:def test_content_problems_accepts_this_plans_own_proposal() -> None:` builds the #3266 plan's own proposal, so updating it in place would drop that self-acceptance case; the plan adds a case with a name of its own.
- **Keep the exclusion of fixture paths from the rule**: A fixture path is no test module, so the new condition already accepts a group that changes it, and the exclusion states the same form twice.

## Unchanged references

- `src/devops_cli/roadmap/stage/stage_paths.py` (function definition): Its `_is_test_module` decides which test files the reference record holds, with the two pytest patterns, so this change leaves it as it is.
- `src/devops_cli/roadmap/stage/stage_form.py` (function definition): Its `_is_test_module` takes a `PurePosixPath` and tests only the `test_` name prefix for the form checks, so this change leaves it as it is.
