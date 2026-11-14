# Design

## Decisions

**The kind is `group`, and the new text is the whole group.** The model sends `new` as the replacement text from the `##` heading to the next heading. `parse_task_groups` parses it, and the same parser that reads the plan judges it, so a replacement cannot use a form that the plan reader would refuse.

**Three bounds hold the replacement small.** The replacement keeps the group number, has fewer tasks than the group, and names only the paths that the group names. Each bound answers one failure of #3053: a group that is too large loses tasks, and a group that is already done cannot drop a task, so its replacement cannot hide work behind a new path.

**The stop names the group and the kind.** The reason holds the number and the title, so the service and a person know which group to replace, and it names the kind `group` of the amendment.

**The trace needs no change.** The attempt event already carries the class of the outcome, so the no-change group keeps `plan_defect` and a changed group keeps no class. A test holds both.

## Rejected alternatives

- **A new failure class.** `plan_defect` already says that the plan is at fault, and the owner decision of 2026-11-02 keeps it.
- **A replacement with no bound on the paths.** A smaller group could move its work to a new file and evade the plan.
- **A person's comment only.** The amendment frame already returns a bounded request to the model, and the issue asks for it.
