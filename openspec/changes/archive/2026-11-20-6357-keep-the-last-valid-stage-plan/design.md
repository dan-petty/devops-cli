# Design

## Decisions

- **Keep the last schema-valid plan in the caller's value: the repair round reuses `change.proposal`, the plan that `_ask_plan` returned.**: `_ask_plan` returns only a reply that the schema accepts, so a failed revision raises before the plan that the caller holds changes.
- **Reuse `roadmap.stage.gate_returns` for the schema return, and pass its used count into `_returned` as the keyword argument `used`.**: The setting already counts the returns of the planner loop, and the issue requires the schema return to count in the same budget.
- **Keep one output retry for a first plan ask and end it with the class `parser`.**: No earlier plan exists to return, and the replies spec sets one output retry for a reply that breaks the schema.
- **Re-raise the schema error when the gate returns are spent.**: `src/devops_cli/ai/client/models.py:115:class StructuredOutputValidationError(AIClientError):` gives the class `parser` through the failure taxonomy, which the issue requires for the exhausted case.
- **Carry `violation_summary` of the failed revision as the problem of the return.**: `src/devops_cli/roadmap/stage/stage_toolbox.py:310:def violation_summary(exc: StructuredOutputValidationError) -> str:` gives the count and, when the error holds them, up to three violation lines with location and type.
- **Build the retry test on `checking_replies()` and the violation test on a queued schema error that carries the violation texts.**: `tests/support/fakes/model.py:350:def chat_structured(` raises at once and fills no violation texts, while `tests/support/fakes/model.py:383:def checking_replies(self) -> ModelFakeReplies:` runs the real retry of one ask, so each test shows what it claims.
- **State the rule in the stage item of `docs/CLUSTER.md`, beside the sentence that already gives the gate returns of a refused reply.**: `docs/CLUSTER.md:48:as each reply that the checks refuse` is the sentence that gives `roadmap.stage.gate_returns` and its default of 3, so a reader of the job finds the schema return in the same place.

## Rejected alternatives

- **Add a second output retry for a first plan ask.**: No earlier plan exists to preserve, and a second retry hides a schema defect at one more model call per item.
- **Treat a first reply with no plan as a gate return.**: A gate return needs a plan to revise, and no plan exists before the first reply.
- **Add a separate setting for schema returns.**: It adds a second budget for the same planner loop and a new configuration key where `roadmap.stage.gate_returns` already counts returns.
- **End the item at once on a revision schema failure, as today.**: That loses the last schema-valid plan, which is the defect of #6357.
- **Keep the last plan in a module-level cache.**: It adds shared state to a job that runs one item at a time, and `change.proposal` already holds the value.
- **Reread the last plan from the plan record file.**: It adds file I/O and a second source of truth for a value that the caller holds in `change.proposal`.
- **Drive the retry test with two queued schema errors on the plain fake.**: `tests/support/fakes/model.py:350:def chat_structured(` raises at once, so two errors are two asks and two gate returns, and its error holds no violation texts; `tests/support/fakes/model.py:383:def checking_replies(self) -> ModelFakeReplies:` runs the real retry of one ask.
