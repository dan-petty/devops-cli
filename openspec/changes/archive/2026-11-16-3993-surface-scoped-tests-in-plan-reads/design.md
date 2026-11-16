# Design

## Decisions
1. **Reuse `plan_tests()`**: Stage reuses the existing `plan_tests()` function from `src/devops_cli/roadmap/implement/implement_scoped_ci.py`. This ensures stage and implement use the exact same test selector and adds no duplicate selection logic.
2. **Per-group test assignment**: Each group's planned `changes` are passed to `plan_tests()` independently so each group receives only the scoped tests relevant to its changes, keeping token counts within step budgets.
3. **Preserve existing reads**: Any files already present in `group.reads` are kept in their original order. Scoped test modules not already in `group.reads` are appended.
4. **Omit missing test paths and record plan warning**: When `plan_tests()` returns a test path that does not exist in the repository tree, omit it from `group.reads` and record a warning naming the missing path in the staged change's warnings.

## Rejected alternatives
1. **Build a new selector for stage**: Rejected because it duplicates the implement selector and can diverge over time.
2. **Assign all scoped tests to every group**: Rejected because it repeats identical test files across all groups and can exceed the group step budget.
3. **Fail staging on missing test path**: Rejected because test selection is advisory, and a stale or prospective test mapping should not block an otherwise valid plan.
