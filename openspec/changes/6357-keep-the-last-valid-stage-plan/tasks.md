# Tasks

## 1. Return a revision schema failure to the planner with the last valid plan

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/ai/client/models.py`, `src/devops_cli/ai/schema_reflection.py`, `tests/support/fakes/model.py`, `tests/roadmap/stage/test_roadmap_stage_repair_return.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_repair_return.py`.
Adds: `_schema_failure`

- [ ] 1.1 First in `tests/roadmap/stage/test_roadmap_stage_repair_return.py`, write `test_a_revision_that_breaks_the_schema_returns_the_last_valid_plan` for the scenario `A revision schema failure returns the last valid plan`: pass `model_fake.checking_replies()` as the planner and answer `make_stage_proposal()`, then the text `json.dumps(json.loads(make_stage_proposal().model_dump_json()) | {"dependences": []})` twice, then `make_stage_proposal(summary="Repaired")`; assert `(plan.ready[0].proposal.summary, model_fake.call_count) == ("Repaired", 4)` and `plan.attempts[0].gate_returns == 1`. Write `test_the_last_gate_return_of_a_revision_schema_failure_ends_as_parser` for the scenario `The last gate return leaves the parser class`: answer `make_stage_proposal()` and then `_schema_failure()` four times with the default `roadmap.stage.gate_returns` of 3; assert `plan.ready == ()`, `plan.failed[0].error == "StructuredOutputValidationError"` and `plan.attempts[0].gate_returns == 3`. Write `test_the_return_of_a_revision_schema_failure_names_the_violations` for the scenario `The planner sees the revision schema violations`: answer `make_stage_proposal()`, a `_schema_failure(ViolationText(loc="dependences", type="extra_forbidden", message="Extra inputs are not permitted"))` and `make_stage_proposal(summary="Repaired")`; assert that `dependences (extra_forbidden)` is in the `problem` of the third request of `model_fake.calls`. Write `test_a_first_reply_with_no_earlier_plan_ends_as_parser`: pass `model_fake.checking_replies()` and answer the broken text twice; assert `plan.ready == ()`, `plan.failed[0].error == "StructuredOutputValidationError"` and `plan.attempts[0].gate_returns == 0`. Add the helper `_schema_failure(*texts: ViolationText) -> StructuredOutputValidationError`, which imports `ViolationText` from `devops_cli.ai.schema_reflection` and builds the error with `violations=len(texts)`, `violation_texts=texts` and `stop_reason="validation"`, and widen the `model` parameter of `_plan` in that module to `ModelFake | ModelFakeReplies`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_repair_return.py` fails on the base
- [ ] 1.2 In `_repaired` of `src/devops_cli/roadmap/stage/stage.py`, replace the single revision ask with a loop: start `problem = return_problem(open_)` and `used = 0`, and keep `floor = len(self._toolbox_traces())`; in each turn ask with `self._ask_plan(target, key, self._refused, bound_previous(request, change.proposal.model_dump(), problem, self._window))` inside a `try`; on the schema error, re-raise when `used >= self._gate_returns`, else add 1 to `used` and to `self._returns`, set `problem = violation_summary(exc)`, call `raise_if_service_stops`, and ask again; when an ask returns, pass the revision to `self._returned` with the keyword argument `used=used`. Add the keyword parameter `used: int = 0` to `_returned` and start it with `returns = used` instead of `returns = 0`, so the schema returns and the check returns share `roadmap.stage.gate_returns` and one log line reports the total. Leave the first plan ask and its call site unchanged, because `_ask_plan` already keeps a refused reply in the refused file
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_repair_return.py` passes

## 2. State the revision schema return in the stage item of the cluster document

Kind: other. Reads: `docs/CLUSTER.md`. Changes: `docs/CLUSTER.md`.

- [ ] 2.1 In the stage item of `docs/CLUSTER.md`, beside the sentence that gives a reply which breaks the rule `roadmap.stage.gate_returns` returns, state that a revision reply that breaks the reply schema after its output retry goes back to the planner with the last schema-valid plan and its violations, that this return counts against `roadmap.stage.gate_returns`, and that the item ends with the class `parser` when the returns are spent
  - Verification: `$ uv run devops ci docs` passes
- [ ] 2.2 Edit `docs/CLUSTER.md` to state the schema return of a revision, its count in the gate returns, and the class `parser` of the exhausted case
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
