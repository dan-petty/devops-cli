# Design

## Decisions

- **The phases run inside the round (owner, #6704 option 2).** `_stage_one` runs `prepare`, the agent work and `publish` one after the other. The planner stays where it is until #6705 moves it into the agent phase, so no result of the current planner needs a file form.
- **The patch comes from the staged commit.** The agent work switches the clone to the commit that the planner read and writes the change folder there, so the patch holds only the files of the plan. `publish` applies it to the tip that `prepare` found. A tip that refuses the patch stops the item, as the conflict of the old rebase did.
- **The lease.** A re-stage pushes with a lease on `stage.sha` (#3387). A new plan pushes with an empty lease, and a resume with a lease on the kept branch that `prepare` found; a branch that holds the same tree gets no new commit.
- **The identity.** The commit keeps the identity that the clone of the job commits as, which `run.py` sets from the session, so the write makes no GitHub request.
- **The kept branch keeps its mark (#6668).** `_remove_staged` keeps `stage.pending` when it keeps the branch, and `_resumable_branches` finds it.

## Rejected alternatives

- Separate `--phase` calls in this change: the outcome would need a file form of every result of the current planner, which #6705 and the change of #6528 remove.
- A push from the clone of the job with a new remote: the clone is the folder that the planner reads, and the phases push from a new repository.
