# Design

## Decisions

- **Put the shared definition check in the new module `src/devops_cli/roadmap/premise.py`, and import it from the stage probe and the implement job.**: A private import from `stage_probe.py` would couple the implement job to the internals of the stage probe, and a copy would be two checks to keep in step.
- **Read the branch tip of the worktree as the commit of the check.**: The branch tip holds the staged plan and the work of the earlier groups, so the check also catches a guard that an earlier group adds.
- **Detect a task that adds a guard from its text: an add verb, a word such as guard or check, and one backticked identifier.**: The rule is deterministic and needs no model call, so the test asserts it offline with a fixed tasks file.
- **Read the kind of a group from the public `group_kind` of `src/devops_cli/roadmap/plan_read.py`, and run the check for a behavior group only.**: `TaskGroup` carries no kind. The plan reader already infers the kind from a `Kind:` line or the `fails on the base` suffix of the first task, so the implement job reuses that inference. Only a behavior group adds a product guard; a document or test group would return an item for a name it never adds.
- **Return the item to New with the definition line and run no group step.**: CONTEXT.md and the failure table of `docs/ROADMAP_WORKFLOW.md` record that a false premise returns the item to New with its evidence.

## Rejected alternatives

- **Keep the premise check inside the step model and trust it to notice the defect.**: The issue shows the plan of PR #3374 for #3368 passed `check_proposal` and would pass the plan check of #3393, so only a deterministic check at the branch tip catches the duplicate guard.
- **Copy the definition lookup into the implement job and keep the stage probe as it is.**: `src/devops_cli/roadmap/stage_probe.py` already holds `_definition_pattern` and the definition branch of `_Run.identifier`; a copy makes two checks to keep in step, which the issue rejects.
- **Run the premise check for every group, whatever its kind.**: A group whose kind is not behavior adds no product guard, so the check would return an item for a document or test task that names an existing helper.
- **Add a `kind` field to `TaskGroup`, or read the kind with the private `plan_read._kind`.**: The writer drops the kind of a group from `tasks.md`, and the plan reader infers it. A second inference in `step_files.py` would duplicate the first, and `step_files.py` cannot import `stage_change.py` without a cycle. A private import would couple the implement job to the reader internals.
