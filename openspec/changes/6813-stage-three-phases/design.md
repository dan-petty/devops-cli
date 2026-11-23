# Design

## Decisions

- **The pattern of implement.** The phases are functions on `RunFolders` (`stage_job_phases.py`), and `run_stage_job` runs them in one process with the state of `prepare` in memory and the outcome of the agent in `out/`, as `implement_round` does. `prepare_stage_job`, `run_stage_agent` and `publish_stage_job` run one phase each, and the command calls them for `--phase`.
- **The planner does not change.** `plan_stage` splits into `begin_stage` (the reads, the writes that need no model and the move of the clone), `store_reads` (the reads of the planner from the store) and `plan_targets` (the planner). The agent phase calls `plan_targets` with `PlannerReads` that `prepare` read, so it holds no store.
- **The GitHub reads of the planner follow the credential of the process.** `--phase all` holds the App key, so `read_issue`, `find_issues` and the reads of the pull requests read GitHub as before. An agent phase of its own holds no credential, so each of these reads answers that GitHub cannot be read, as a failed read does (#3240). The planner of #6705 has none of these tools.
- **`prepare` decides what needs GitHub.** The CI job-time premise reads GitHub before the plan call, so `prepare` reads it, and a premise that decides the item ends the Job in `prepare` with the attempt that the planner would count. The planner read the comments of the item, the titles of its dependencies and the paths of the open plans in its plan, so an error of `ITEM_ERRORS` in these reads fails the item in `prepare` (`item_failure`), as `_plan_each` fails it.
- **`begin` in `prepare`, `settle` in `publish`.** `prepare` writes the removals and the rejections before the plan, as the round does. `StageWriter.resume` gives `publish` the writes of `begin`, so `settle` and the check-in see the whole round.
- **The clone of the agent has no blobs.** `prepare` clones with `--filter=blob:none` and checks out the staged commit, so the clone holds each blob of that commit, and the planner reads that commit only. This is the clone form of the stage Job (#5483).
- **The outcome is data.** `publish` reads the state file and the outcome with `read_run_file`, masks each text of the outcome, takes the target from the state file, and refuses a change with a file outside its change folder. The trace of the outcome keeps no text of the tool answers, which `publish` does not read.
- **The ends of a phase of its own.** The agent phase writes the end of the time budget and an error that gives no result as outcomes, and `publish` gives them the ends of `run_stage_job`. A SIGTERM in the agent phase exits with the status of its class and writes no check-in: the Service checks in for the Job.

## Rejected alternatives

- A model of each result type by hand: `TypeAdapter` gives the JSON form of the dataclasses, and #6705 changes the results.
- The GitHub reads of the planner only in `--phase all`, by a flag: the agent phase would differ between the two forms of the Job, and the credential of the process gives the same effect with no new option.
- A full clone in `prepare`: it downloads the whole history, and the planner reads one commit.
- A change of the CronJob: #6814 changes the template after a release holds this change.
