# Proposal

## Why

A stage revision run that breaks the reply schema ends the item with the class `parser` and loses the last schema-valid plan, which caused 8 of 11 stage failures over 24 h (#6357). The stage must keep that plan, send the violations back to the planner as one gate return, and count that return against `roadmap.stage.gate_returns`.

## What Changes

- The repair round of `src/devops_cli/roadmap/stage/stage.py` catches the schema error of its revision ask and asks again with the last schema-valid plan as `previous`, up to `roadmap.stage.gate_returns` times.
- The problem of that request is `violation_summary` of the error, so the planner reads the violation count and, when the error holds them, up to three violation lines with their location and error type.
- Each schema return adds 1 to `self._returns`, so the attempt record reports one more gate return, and `_returned` starts its count at the returns that the schema failure used, through the keyword argument `used`.
- When the returns are spent, the error re-raises, so the item ends with the failure class `parser` and the job opens no pull request.
- A first plan ask and its check returns keep today's behavior, because no earlier plan exists to return.
- Four tests in `tests/roadmap/stage/test_roadmap_stage_repair_return.py`: the output retry through `checking_replies()`, the exhausted budget, the violation text of a queued schema error, and a first reply with no earlier plan.
- `docs/CLUSTER.md` states the schema return of a revision, its place in the gate return budget, and the class `parser` of the exhausted case.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/replies`: A revision schema failure keeps the last valid plan, A reply that breaks the schema returns once, A toolbox run keeps the return rules of a broken reply

## Impact

- Code: `src/devops_cli/roadmap/stage/stage.py`
- Documents: `docs/CLUSTER.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_repair_return.py`

## Feasibility

- The `probes` section says, word for word: "The path `src/devops_cli/roadmap/stage/stage.py` is a file of the staging commit.", and `src/devops_cli/roadmap/stage/stage.py:995:_REPLY_RETURNS: Final[int] = 1` sets the single output retry of the stage client.
- The body cites line 991 for `_REPLY_RETURNS` of the stage client, and the staged line is 995: `src/devops_cli/roadmap/stage/stage.py:995:_REPLY_RETURNS: Final[int] = 1`. The value is 1, as the body says.
- `read_file` of lines 2010 to 2033 showed the first ask: `src/devops_cli/roadmap/stage/stage.py:2010:def _ask_plan(` logs the violations, keeps the refused reply at `src/devops_cli/roadmap/stage/stage.py:2032:self._keep_refused(target, key, refused, exc)` and re-raises at `src/devops_cli/roadmap/stage/stage.py:2033:raise`.
- `read_file` of lines 2205 to 2219 showed the revision ask with no handler around it: `src/devops_cli/roadmap/stage/stage.py:2216:revised = self._ask_plan(target, key, self._refused, again)`, so a revision that breaks the schema ends the item.
- `read_file` of lines 1865 to 1935 showed the gate return budget and its count: `src/devops_cli/roadmap/stage/stage.py:1882:returns = 0`, `src/devops_cli/roadmap/stage/stage.py:1910:if returns >= self._gate_returns:` and `src/devops_cli/roadmap/stage/stage.py:1929:self._returns += 1`.
- `search_code` for the setting's assignment gave `src/devops_cli/roadmap/stage/stage.py:1536:gate_returns=self._returns,`, so one more `self._returns` is one more gate return of the attempt record.
- The default of `roadmap.stage.gate_returns` is 3: `src/devops_cli/config/defaults.py:953:DEFAULT_ROADMAP_STAGE_GATE_RETURNS: int = 3`, and the setting reads it at `src/devops_cli/config/settings.py:1386:gate_returns: Annotated[int, Variable()] = Field(`.
- The schema error is `src/devops_cli/ai/client/models.py:115:class StructuredOutputValidationError(AIClientError):`, and `src/devops_cli/roadmap/stage/stage.py:2898:failure_class=failure_class_of(exc),` gives the failure class from it, which the failure taxonomy maps to `parser`.
- The problem text of the return is `src/devops_cli/roadmap/stage/stage_toolbox.py:310:def violation_summary(exc: StructuredOutputValidationError) -> str:`, which gives the count, the stop reason and at most three violation lines.
- The plain fake raises at once and keeps no violation texts: `tests/support/fakes/model.py:350:def chat_structured(` builds the error at `tests/support/fakes/model.py:376:violations=exc.error_count(),`, and `tests/support/fakes/model.py:383:def checking_replies(self) -> ModelFakeReplies:` runs the real retry of one ask through `src/devops_cli/ai/client/structured.py:186:class StructuredOutputMixin:`.
- A queued exception is raised as given, so a test can hand the error its violation texts: `tests/support/fakes/model.py:606:raise candidate`, and `src/devops_cli/ai/schema_reflection.py:38:class ViolationText(BaseModel):` is the item that the error carries.
- `tests/support/builders.py:154:def make_stage_proposal(**overrides: Any) -> StageProposal:` builds the reply of a test, and `src/devops_cli/roadmap/stage/stage_change.py:429:model_config = ConfigDict(` makes an unknown key such as `dependences` an `extra_forbidden` violation.
- `tests/roadmap/stage/test_roadmap_stage_gate_extension.py:270:assert attempt.gate_returns == 4` shows the attempt count that a test reads, and `tests/roadmap/stage/test_roadmap_stage_repair_return.py:170:assert (RoadmapStageConfig().gate_returns, model_fake.call_count) == (3, 1 + 1 + 3)` shows the default of 3 returns.
- `plan_stage` needs a checkout of the repository and a client of the model, and the tests give `stage_repo` and `model_fake`, so no test reaches a network, a cluster or a scanner.
- `_ask_plan` needs a client of the model; the test passes `model_fake.checking_replies()`, so no test reaches a network.
- The verify commands `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_repair_return.py` and `uv run devops ci docs` need `uv`, `python`, `pytest` and `git`, which the image holds as runner tools and `NOT_IN_RUNNER` does not list; a failing test run is the failure class `test`, and the pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`.
- The first checks against the real system are `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_repair_return.py`, which fails on the base because the revision ask has no handler at `src/devops_cli/roadmap/stage/stage.py:2216:revised = self._ask_plan(target, key, self._refused, again)`, and `uv run devops openspec check`.
- The premise holds at the staged commit: the revision ask at `src/devops_cli/roadmap/stage/stage.py:2216:revised = self._ask_plan(target, key, self._refused, again)` has no handler for the schema error, so a revision that breaks the schema ends the item. The Loki counts, the item numbers and the failure rates of the body are not checked by this run.
- `find_issues` for the setting and the failure class, and for the module and the constant, named no open item but this one, so the plan depends on no other item.

## Existing Tool Considered

The alternatives check of 2026-11-19 records the verdict none and names no tool, and no open, maintained tool or library covers the schema-retry policy of the stage planner loop: the need is stage-internal control flow that keeps the last valid reply and maps schema violations onto the gate return budget. The change builds its own code in the stage module, at a cost of about 30k tokens to build, keep and fix, and 8 hours. It deletes no internal code.

## Dependencies

None.
