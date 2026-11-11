# Design

## Decisions

- **The returns are a setting.** `roadmap.stage.gate_returns` sits beside `roadmap.stage.limit` and `roadmap.stage.step_tokens`. The owner tunes it live while the stage job moves to 80% success. The default 3 comes from the sample: 8 of 10 refused items made progress at the second reply, and a refusal names one module at a time, so a plan with problems in two modules needs a third reply. `plan_stage` passes the loaded value to the planner. A planner that gets no value, as in `plan_item` of the golden set, reads the setting.
- **The row limit is a setting.** `service.max_failed_rounds` sits beside `service.github_requests_per_hour` and `service.model_call_concurrency`. `FailureLedger` reads it when the caller gives no limit, so the one ledger of the Service and a ledger of one round follow the same value. The default 6 gives the stage row about 3.7 hours of failed rounds at 37 minutes a round.
- **The wait stays in the code.** The stage spec says that no setting changes the wait, and four jobs read the one table `RETRY_AFTER`. `plan_defect` gets 1 hour, as `provider` and `ci_infra` have. The return to New after 3 refused plans on one body still limits the attempts of an item.
- **Nested limits.** A return is one more planner call in the same item. Each call keeps its tool call limit and request limit. The item wait is longer than the stage interval, and the row retry time is shorter than the `for` of the suspension alert.

## Rejected alternatives

- **Keep the default at 1 and set 3 in the ConfigMap.** The code default is what the specs and a new repository get. The owner asked for the loosening now, and a live step alone leaves the code and the docs with the old value.
- **A setting for the wait of each class.** It splits the one table of `failure.py` that four jobs read, against the stage spec. The progress-aware caps plan makes the waits adaptive later.
- **A ledger limit for each job.** One failed item fails a whole stage round, but no data shows that the other rows need another limit. The hourly request budget still limits a failing row.
