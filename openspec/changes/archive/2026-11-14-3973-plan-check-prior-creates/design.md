# Design

## Context

`measure_groups` counts the files that a group packs by parsing the code spans of its text against the checkout. A file that a prior group of the same plan creates is not in that checkout, so a later group that changes it packs no file. The own `creates` of the later group is empty, and the current condition reports the group.

## Goals

- Accept a changed path that an earlier group of the plan creates.
- Keep the report for a path that no group creates and that does not exist.

## Decisions

- **One ordered set.** The loop adds each group's `creates` after it judges the group. The condition tests against the union of the group's own creates and the set.
- **The order of the plan is the order of the work.** The stage job runs the groups in order, so a later group sees the file of an earlier one.

## Risks

- A plan with the groups in another order is still reported. That order is a real defect: the step of the later group would start without the file.

## Tests

- A plan whose first group creates `src/devops_cli/new_module.py` and whose second group changes it gives no `group-no-files` problem.
