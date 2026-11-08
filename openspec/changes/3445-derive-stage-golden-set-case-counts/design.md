# Design

## Decisions

- **Keep `EVALUATED_PULLS` as the single statement of the intended reviewed pulls and compare the fixtures with it.**: The comparison keeps the guard against an accidental removal of a reviewed case, which counts derived from the fixtures alone cannot catch.
- **Derive the total as `len(EVALUATED_PULLS) + len(good)` and derive the good count from the loaded cases.**: No literal count remains, so a new reviewed case needs one edit, its pull in `EVALUATED_PULLS`.
- **Put the reviewed-set comparison and the count derivation in the module-level helper `check_case_counts`.**: The main test and the new test call one copy of the check, so the two cannot drift apart.
- **Have the new test copy the case folders to `tmp_path` and add a reviewed case with a new pull there.**: The check runs offline over a temporary set and the committed fixtures stay unchanged.
- **Rename the count test to `test_the_set_holds_the_reviewed_plans_and_the_good_ones`.**: The old name states 49 and 5, which pins the counts that the change derives.
- **Leave the comment block above `EVALUATED_PULLS` and the module docstring as they are.**: They describe the cases and their history and state no count that the change derives, so they need no edit.

## Rejected alternatives

- **Derive every count from the fixtures alone and drop `EVALUATED_PULLS`.**: The fixtures alone cannot tell an accidental removal of a reviewed case from an intended one, so the guard that the issue keeps would be lost.
- **Keep the literal counts and edit them in each plan that adds a case.**: The plan of #3436 for #3411 added a case and named only one test file, and no prompt or gate refused it, so the count test would have failed.
- **Duplicate the count assertions in the new test instead of extracting a helper.**: Two copies of the check drift apart, and the new test would not exercise the check that the main test runs.
