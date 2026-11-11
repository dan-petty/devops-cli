# Design

## Decisions

- **One read at the staged commit.** `read_stage_selection` calls `uses_openspec(source, sha)` after it reads the staged commit. The read uses the commit, not the checkout, as `declared_steps` does (#3484), so an edit on a branch cannot turn the switch.
- **A rule of the judge, not a stop of the round.** The hold is one more check of `_Judge`, after the claim check. Each item gets the reason, so the plan, the log of left-out items, the counter and `devops roadmap explain` show it with no new code. An item that is not Ready or that a person claimed keeps that reason, so the counter counts only the Ready items that the missing file holds.
- **`--item` does not overrule the hold.** A named item gets the same plan folder, and the folder is wrong in a repository without OpenSpec.
- **The missing file is a record in the outcome of the row.** `JobOutcome` is the value that a row gives to the later rows of a round (`cross_job_predicate`). `JobOutcome.missing` holds the paths, so the onboarding row of #4664 can start in the same round and needs no other store. The plan holds the same tuple in `StagePlan.missing`.
- **A new capability.** `roadmap-project-dependencies` holds the rules about a repository that lacks a project-management dependency. #4664 adds the onboarding row to it. The requirements of the hold do not go into `roadmap-stage`: that file had 81 merge conflicts in one week, and #4622 splits it.

## Rejected alternatives

- **One `git ls-tree` for the change folders and the config file.** `planned_changes_at` could list `openspec/config.yaml` with the folders. Rejected: #4629 asks for one helper that `devops pr create` (#3767) and the archive step can call with no `PlannedChanges`, and two readers of one fact are two switches. The extra read is local, one for each round and not one for each item, and takes milliseconds. The tests that count the reads of a round count the change-folder read and the config read apart.
- **Stop the round before the selection.** Rejected: then `explain` and the plan give no reason for an item, and acceptance criterion 2 of #4629 asks `explain` for the reason.
- **A gauge or a file in the Service state for the missing file.** Rejected: no reader exists, and `JobOutcome` is the record that the rows of a round already share. The counter with the reason `no_openspec` already shows the hold on the dashboards.
- **A plan kept only in the issue body.** Rejected in #4629: it is a second plan system with no user.
