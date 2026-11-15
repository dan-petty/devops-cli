# Proposal

## Why

The stage job sends the earlier plan back to the planner with the problem after a gate refuses a reply and after a review returns a finding, and the earlier change measured only the first plan request. A long earlier plan can push the return request past the limit at which the run offers no tool, and the planner then makes no tool call. #3529 asks for an offline measure of the return request and for a bound on the earlier plan.

## What Changes

- Add `src/devops_cli/roadmap/stage/stage_return.py` with `request_tokens` and `bound_previous`: the bound measures the return request as the JSON text that `_ask_plan` sends, and cuts the texts of `previous` only when that count passes `tool_stop(window)` less `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS`.
- Send both return paths through the bound: `_Refused.returned` takes the window of the run, and `_repaired` builds its request the same way, so the gate return and the review repair are measured and bounded once.
- Add the measure tests to `tests/roadmap/stage/test_roadmap_stage_window.py`: a gate return and a review repair whose earlier plan is 20,000 words long, and a return that fits, each counted as the run hook counts it at a window of 65,536 tokens and asserted under 49,152 tokens with `read_spec` offered.
- Keep the first plan request as it is: its caps, its reserve and its measure do not change, and the tests of the first request stay as they are.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/run-limits`: The return request of a plan run is measured against the tool-removal limit, The earlier plan is bounded only when the return request passes the limit

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_return.py`, `src/devops_cli/roadmap/stage/stage.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_window.py`

## Feasibility

- The premise holds: the module measures the first request only. `read_file` of `tests/roadmap/stage/test_roadmap_stage_window.py` shows one measure helper, `_first_request_tokens`, and `tests/roadmap/stage/test_roadmap_stage_window.py:113:return count_tokens(ModelMessagesTypeAdapter.dump_json(script.seen[0]).decode())` counts `script.seen[0]` only.
- Both return paths add the earlier plan and the problem: `read_file` of `src/devops_cli/roadmap/stage/stage.py` shows `src/devops_cli/roadmap/stage/stage.py:1162:return {**request.for_model(), "previous": self.reply.model_dump(), "problem": self.problem}` in `src/devops_cli/roadmap/stage/stage.py:def returned`, and `src/devops_cli/roadmap/stage/stage.py:1896:"previous": change.proposal.model_dump(),` in `src/devops_cli/roadmap/stage/stage.py:def _repaired`. `search_code` for `.returned(` gave the two call sites `src/devops_cli/roadmap/stage/stage.py:1578:ask = outcome.returned(request)` and `src/devops_cli/roadmap/stage/stage.py:1646:proposal = self._ask_plan(target, key, refused, outcome.returned(request))`.
- The probe "`_Refused` defines no field `returned` in `src/devops_cli/roadmap/stage/stage.py`." is no false premise: `returned` is a method, `src/devops_cli/roadmap/stage/stage.py:1160:def returned(self, request: StageRequest) -> dict[str, Any]:`, and this plan gives it the window of the run.
- The probe that `devops_cli.ai.context_budget.count_tokens` is no file names a dotted symbol, not a path: `src/devops_cli/ai/context_budget.py:90:def count_tokens(text: str, model: str = DEFAULT_TIKTOKEN_MODEL) -> int:` counts the tokens, and `src/devops_cli/ai/context_budget.py:128:def truncate_to_token_limit(` returns a text that already fits unchanged.
- The limit follows the window: `src/devops_cli/roadmap/refine/refine_investigation.py:404:return window - window // CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE`, and the test window `tests/roadmap/stage/test_roadmap_stage_window.py:62:WINDOW = 65536` gives the limit of 49,152 tokens that `tests/roadmap/stage/test_roadmap_stage_window.py:118:return window - window // CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE` computes.
- The staged value that the bound relies on: `src/devops_cli/config/constants.py:3429:CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS: Final[int] = 8_192`. The bound keeps that reserve of 8,192 tokens below the limit for the prompts of the run, as the first request keeps it.
- The registry finding is answered, and the plan adds no constant: `read_file` of `src/devops_cli/roadmap/stage/stage_change.py` shows `src/devops_cli/roadmap/stage/stage_change.py:2649:matched = matches(registry, task_texts, changed_paths)`, which matches the `CONST_ROADMAP_` prefix of a task text, and the declaration `tests/roadmap/test_roadmap_limit_classes.py:47:("prefix", "CONST_ROADMAP_", "tests/roadmap/test_roadmap_limit_classes.py"),` already names the path that group 1 names in its implementation text. The change adds no limit, so that test needs no new entry.
- Preconditions of the calls: `plan_stage` needs a checkout of the repository and a planner client, and the tests give the clone of the `stage_repo` fixture of `tests/support/roadmap_stage.py` and the scripted model of `tests/support/scripted_model.py`, so no test reaches a model. `ToolboxClient` runs its tools on that checkout. `count_tokens` and `truncate_to_token_limit` need the tiktoken encoding cache on disk and no network. `tool_stop` needs nothing.
- The verify is `uv run devops ci test`: `pytest` is in the runner image, a failing test has the failure class `test`, and the pod keeps `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`. The plan adds no program and names none that is `NOT_IN_RUNNER`.
- Not checked in this run: the live window of 256,000 tokens of the stage task, and the GitHub items #3477 and #3523, because the run made no `read_issue` call. The context lists no overlap, no metric sender and no issue dependency, so `dependencies` is empty.
- The first checks of the implementation: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_window.py` after group 1, and again after group 2.

## Existing Tool Considered

tiktoken, through `count_tokens` and `truncate_to_token_limit` of `devops_cli.ai.context_budget`, counts and cuts the text, and `tool_stop` of the refine investigation gives the limit; all are open, maintained and already dependencies, so the change adds no library. They lack a measure of this project's return request and a bound on the `previous` field of one request, which the change adds with about 90 lines in one module, about 6,000 tokens to build and about 4 hours of work.

## Dependencies

None.
