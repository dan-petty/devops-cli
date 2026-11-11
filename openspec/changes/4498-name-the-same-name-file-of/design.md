# Design

## Decisions

- **Reuse the hint of the path gate.** The path gate already states the same fact with `stage_path_same_name` and `stage_path_no_same_name`, and the spec pins these texts. The planner thus reads one wording for a wrong path in any place of the plan.
- **One function makes the hint.** `same_name_hint(tree, path)` in `stage_paths.py` holds the choice between the two texts. `_problem` and `_stale_test_path_problems` both call it, so a change to the hint changes both problems.
- **Add a `{hint}` placeholder to the existing key.** The problem always ends with a hint, as the missing-path problem does. One key and one formatting path serve both cases.
- **List each same-name file, not only one.** `StagedTree.same_name` returns at most `SAME_NAME_MAX` files, sorted. When exactly one file has the name, the hint names that file. When more have it, the planner reads each candidate, as it does for the path gate.

## Rejected alternatives

- **Add a "Did you mean" message.** A second wording for the same fact makes the planner read two forms.
- **Add a second key for the same-name case.** Two keys for one problem let a caller pick the wrong one, and the two texts can drift apart.
- **Run `git ls-files` in the check.** `StagedTree` already holds the files of the staged commit. A second read costs a git call and can see another tree.
