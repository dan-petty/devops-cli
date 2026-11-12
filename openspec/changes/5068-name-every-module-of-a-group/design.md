# Design

## Decisions

- `_unnamed_module_tests` walks the modules of `group.changes` in order and gives each module whose tests the group names nowhere, with the nearest test of `record_module_tests`. `existing_test_problems` gives one problem for each module, so the repair round gets the full list at once. The message `stage_problem_missing_module_test` stays the same: it names one group, one module and one test.
- A test that the problem of an earlier module asks for counts as named for each later module of the same group. A test of a module can also run a later module (#4467), so the repair that adds the asked test passes that later module too. The gate then asks only for the tests that one repair needs, and a repair that names every asked test passes the group.
- The rule that accepts or refuses a group does not change. The function gives no problem only when each module of the group has a named test, as before: the extra names come only from problems that the function also gives. The change adds no acceptance and no refusal; it changes only how many modules one refusal names.

## Rejected alternatives

- Give one problem for each group that lists every module and test. The problem text, its finding class (`stage_finding_classes.json`) and the findings tests read one module for each problem, so a new list message would change three places for the same information.
- Give every module with its own nearest test, with no asked test counted as named. A group that changes `follow.py` and the messages that it shows would get two problems, and the repair would add a second test that the gate does not need.
- Raise the number of stage gate returns. The returns cap the cost of a bad plan; the defect is that one refusal held only one of the problems.
