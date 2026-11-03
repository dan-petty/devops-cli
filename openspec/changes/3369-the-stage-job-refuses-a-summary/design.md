# Design

## Decisions

- **Count the summary with `summary_length` and compare it to `SUMMARY_MAX_CHARS` from `src/devops_cli/roadmap/pull_form.py`.**: The same limit and the same count decide the pull-request form and the `Semantic PR title` check, so the gate and the delivery title agree. The count is in UTF-16 code units, so an emoji counts as two.
- **Check the summary length in `_Judge._title` after the type check and before the slug check.**: A title with no Conventional Commit type keeps its existing reason, and a valid short title still gets the slug check.
- **Add a `stage_left_title_long` message in `src/devops_cli/lang/en/messages.py`.**: It matches the other `stage_left_title_*` reasons and names the length of the issue title and the limit, as `stage_title_long` does for the plan title.
- **Keep the cut in `delivery_title` in `src/devops_cli/roadmap/stage_change.py`.**: An item staged before this check, or whose title a person edits later, still gets a delivery title that the implement job can use.
- **Put the new cases in `tests/roadmap/test_roadmap_stage_title.py`.**: That module holds the title rules, the `staging_title` tests and the `delivery_title` tests. The module named in the issue, `tests/roadmap/test_roadmap_stage.py`, is no file of the staging commit.
- **Add one requirement to `roadmap-stage` and leave its existing requirements unchanged.**: The new rule stands on its own, so no living requirement is rewritten and the archive keeps every scenario that the capability holds today.

## Rejected alternatives

- **Count the summary with `len` and a new constant in `stage.py`.**: `summary_length` in `src/devops_cli/roadmap/pull_form.py` counts an emoji as two UTF-16 code units, as the `Semantic PR title` pattern does. `len` counts code points, so a summary with an emoji could pass at 61 units, and a second constant could drift from `SUMMARY_MAX_CHARS`.
- **Check the length only in `staging_title`.**: `staging_title` runs after the plan run, so the implement job would still start on an overlong issue title and pay the model calls before the cut.
- **Reuse the message `stage_title_long`.**: That message names the summary of the plan, not the summary of the issue title, so its text would name the wrong subject.
- **Remove the cut in `delivery_title`.**: `delivery_title` in `src/devops_cli/roadmap/stage_change.py` is called by `src/devops_cli/roadmap/implement_run.py`, so an item staged before this check, or a title a person edits later, would fail at delivery.
- **Put the new cases in `tests/roadmap/test_roadmap_stage.py`, as the issue body names it.**: `probes` reports that `tests/roadmap/test_roadmap_stage.py` is no file of the staging commit and that no commit in the history deleted or renamed it.
- **Rewrite the existing requirement "The job leaves out the items it must not stage" with `modified`.**: The current requirement holds seven scenarios, such as "Items that are left out" and "The change is archived". A `modified` block replaces the whole requirement, so it would drop them.
