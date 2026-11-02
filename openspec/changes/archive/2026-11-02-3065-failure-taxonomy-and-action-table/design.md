# Design

## The classifier is a function of its evidence

`classify_failure(FailureEvidence)` reads five fields: the error text, the exit status, the refusal of a tool, the name of the check, and the last message of the agent. It reads no file and makes no request. The rules are regular expressions in a fixed order, from the cause that is most sure to the one that is least sure. The order is part of the contract and is held by the table test:

1. An exit status of a signal: 137 is `oom`, and 124 and 143 are `timeout`.
2. A refusal of a tool is `refused_tool`.
3. The text, for the causes outside the code of the item: `oom`, `timeout`, `conflict`, `parser`, `provider`, `refused_tool`. The parser comes before the provider: an Ollama that cannot parse a tool call answers `ModelHTTPError` with HTTP 400, as the stop of #2747 shows.
4. The text, for the checks of the item: `types`, `lint`, `test`.
5. `premise_false` (from the text and from the message of the agent), then `plan_defect`.
6. The name of the check. A name with `image`, `duration` or `build` is `ci_infra` before any other, so "Test Job Duration" is no test.
7. Anything else is `ci_infra`.

The text of a stop decides before the message of the agent. In #2175 the stop was a `mypy` failure while the agent said that the function was already deleted; the class is `types`, because the stop is what the job must act on.

## Unknown input is ci_infra

The issue fixes 12 classes, so there is no `unknown`. A failure that no rule matches is `ci_infra`, whose default action is `retry`. Rejected: a thirteenth class `unknown` (the class list is fixed by the issue); stopping at once (a transient infrastructure error would block the item until a person reads it).

## One table, and what "taken" and "left" mean

`ACTION_BY_CLASS` is a read-only mapping. A test holds that its keys are the 12 classes. Rejected: an action branch in the job for each class (the defaults would scatter, and no test could hold that each class has one).

The job runs one action by itself: the fix round. A stop for a failed check after the rounds has taken `repair`. The action left is the default of the class, or `wait` when the default was taken already. For all other classes the action taken is `none`. Rejected: to dispatch `retry`, `change_tier`, `raise_limit`, `amend` and `return` in this change. The job has no model tier, the Service cannot write the memory limit of the Job, and a return of an item is a decision that AGENTS.md reserves with evidence; each is a change of its own (see Feasibility in the proposal).

## The record, the trace and the metric

The runner writes the class in `implement.failure` in the same write as `implement.stopped`, and a clear removes both. The trace is the Job log, which is the evidence that the Service already quotes in its report: the runner writes one line with the class and the action left. Rejected: a span attribute. The roadmap code opens no span, and the Job log is what a person reads.

The counter is `devops_cli_service_implement_failures_total` with the label `class`, not one counter for each class (12 names for one fact). The Service increments it when a round reports the Job, after the write of the Job state, so a write that fails is reported again and counted once. Rejected: a counter in the runner (the pod is not scraped).

A Job that left the item without a result has no record of its class. The round classifies the tail of the log, records the class with the stop, and names it in the report.
