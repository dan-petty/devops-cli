# Design

## Decisions

- **The criteria come from one list: the top-level items under a heading `Acceptance criteria` in the part of the issue body before the refine block.**: A person writes this list. The refine block holds the same criteria again in other forms (`- Criterion N: ... Verification: ...`, `### Requirement:`), and asking for each form would ask for one criterion two or three times. A body with no such heading has no criterion, and the check finds no problem.
- **The parser is `markdown-it-py`, not a regular expression.**: CONTRIBUTING.md asks for a standard parser. A nested item is no criterion.
- **A criterion is the source text of its item, with the task-list mark removed and the white space collapsed to single spaces. An entry matches when its text, collapsed the same way, is equal.**: Code spans and links stay as written, so the model copies them from the issue. The collapse removes line breaks of a wrapped item.
- **`criterion_problems(criteria, issue_body, group_count)` is a pure function that `check_proposal` appends to its problems, with `issue_body` as a keyword with an empty default.**: It follows `path_problems` (#3010). The default keeps every other caller working, and an empty body has no criterion.
- **The job passes the whole `item.body`.**: The body sent to the model is cut to a token limit, and the check must not depend on the cut.
- **A problem quotes the exact text to copy.**: A reply goes back once. The retry then copies the text instead of guessing it.
- **Each entry holds `criterion`, `group` and `reason`. `group` is a number from 1 or `pending-person`. `reason` is required and not blank for `pending-person`, and optional for a number.**: The schema refuses the entry with no reason, as the client sends a reply that breaks the schema back before the checks. A number above the count of groups is a problem of the check.
- **`criteria` defaults to an empty list.**: An issue with no list needs no entry.
- **A split gives the `criteria` again, and the job checks them after the split.**: A split replaces groups and moves the numbers of the later ones, so the numbers of the first reply are stale.
- **`tasks.md` gets a `## Criteria` section before `## Workflow follow-up`, as plain bullets with no box.**: It is no group (`parse_task_groups` ignores a heading that is not `<n>. <title>`) and no task, so archive has nothing to tick. A plan with no criterion has no section.
- **The replay gate `criteria` judges a plan only when its `criteria` key is present. The dropped-criterion defects of the recorded cases get the gate `none`.**: A recorded plan was never asked for the mapping. Adding a hand-written `criteria` list to a recorded plan would test the list and not the plan. The run of the model (`devops roadmap eval stage`) passes the issue body, so the gate judges every first reply of the model there.

## Rejected alternatives

- **Fuzzy or semantic matching of criterion text.**: The text comes from the same issue body, so a similarity library or a model call adds cost and a source of drift that an exact match avoids.
- **Match by index, first criterion to first entry.**: The model may reorder or skip entries, and an index cannot tell a skip from a reorder.
- **Annotate each group's task list with its criteria instead of a separate section.**: It clutters the task list and hides which tasks belong to which criterion.
- **Read the refine block as the source of the criteria.**: It has two forms and a `Verification:` line in each entry, so no exact text is stable. The human list is the one list that the issue template asks for.
- **Add `criteria` to the recorded `plan.json` files so that the gate catches the dropped-criterion defects.**: The lists would be written by hand to fit the defects, and the replay would then test the hand-written list.
- **Make `issue_body` a required argument of `check_proposal`.**: It breaks every caller in `tests/roadmap/test_roadmap_stage_plan.py` for no gain.
