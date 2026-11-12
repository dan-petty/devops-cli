# Design

## Decisions

- One module, `roadmap/job_result.py`, holds the form of the line, the intended results of each job (`SUCCESS_RESULTS`) and the classes of an infrastructure cut (`INFRA_CLASSES`). A test checks that each intended result is a value of the result enum of its job. The module imports no job module, so each job imports it with no cycle.
- The line puts `success` and `infra` in the line itself, so one Loki query gives the ratio of all jobs by `roadmap_job`, and the rule of each job stays in code.
- The fields come in a fixed order, and a value that holds another character than a letter, a digit, `_`, `-` or `.` becomes `other`. So the line holds no issue text, and a `regexp` parser reads it.
- The query extracts the label `roadmap_job`, because the stream already has the label `job`.
- The existing lines of `round_log.py` stay: `implement attempt` holds the runner digest, and the dashboard reads only the new line.
- `stage`: the planner keeps the counts of each item in `attempts`, and `emit_stage_results` logs the tried items in item order. A skipped item is no attempt. `gate_returns` counts in the loop of `_returned`, so a return of a repair round counts too.
- `implement`: the result is `implement.result` of the record, which the Service clears when it makes a Job. A Job with no result is `stopped`. The seconds run from `status.startTime` to the time of the condition Complete or Failed, which `ClusterJob.ended` reads.
- `refine_judge`: `judge` logs only a review that calls the model, so a kept approval is no attempt. `judge` gets `repo` as a keyword.
- `alternatives`: `AlternativesWriter` gets the repository as an argument. `CheckFailure.failure_class` holds the class of a failed model call, so the share of the provider cuts shows.
- `intake`: the line comes from `_count_candidate`, at the same points as the counter. A new candidate names the issue that intake filed.
- The 80% rule: a ratio of 0.80 or more with 30 attempts or more at 3 daily checks in a row. A Wilson upper bound under 0.80 ends a hold. The values come from the plan of the owner rule (`OWNER-REQUIREMENTS` item 8).

## Rejected alternatives

- A Prometheus counter for each job: a label cannot hold the counts of each attempt, and the ratio of the issue was due before the counter fixes (#4684, #4703) reached the cluster. Recording rules on counters can come later.
- A free-form `reason` text in the line: it can hold issue text. The line holds the code of the error instead.
- Change the `implement attempt` line into the new line: an open pull request of #4703 changes the lines next to its call in `implement_submit.py`, and the line holds the runner digest.
- A count `extensions` of 0 in each line now: no cap extension exists yet, and a count that is always 0 tells nothing. The change that adds an extension adds the count.
