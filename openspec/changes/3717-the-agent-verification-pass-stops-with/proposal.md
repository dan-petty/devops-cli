# Proposal

## Why

The verification eval pass of #3717 ends a case with `Tool <text> exceeded max retries count of 2`, so the case gives no recall and no false-alarm count, and the report names no cause; a model that replies in text instead of calling the output tool loses the findings that it wrote.

## What Changes

- Type the stop of a verification run from its messages: a text reply, a refused tool call, an exhausted output retry and an exhausted budget each get a reason and a message.
- Give the findings that a text reply holds, with the existing `_repair_and_validate_payload` parser, so a model that answers in text loses nothing.
- Record `cases[].reason` in the JSON report and name the reason of each failed case in the text report of `devops roadmap eval verify`.
- Add two requirements to `roadmap-stage/verification` and one to `roadmap-stage-eval`, because the report of a `devops` command changes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/verification`: A text reply that holds the findings gives them, A stopped verification run names its cause
- `roadmap-stage-eval`: The verify report names the stop reason of a failed case

## Impact

- Code: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage_verify_eval.py`
- Tests: `tests/ai/client/test_roadmap_agent_run.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`

## Feasibility

- The probes confirm the files of the premise: "The path `src/devops_cli/roadmap/stage/stage_verify_eval.py` is a file of the staging commit.", "The path `src/devops_cli/roadmap/agent_run.py` is a file of the staging commit." and "The path `src/devops_cli/ai/client/structured.py` is a file of the staging commit."
- The masked message reaches the report: `src/devops_cli/roadmap/agent_run.py:148:hidden = _QUOTED.sub("<text>", bounded_text(first))` hides each quoted part, and `src/devops_cli/roadmap/stage/stage_toolbox.py:250:message = template.format(reason=result.message)` puts the masked text into the error.
- The error text is the one of the issue: `src/devops_cli/lang/en/messages.py:4226:"The verification run stopped before it gave its findings: {reason}. The plan passed the "`.
- The eval keeps no typed reason: `src/devops_cli/roadmap/stage/stage_verify_eval.py:104:error: str = ""` and `src/devops_cli/roadmap/stage/stage_verify_eval.py:337:return _not_run(case, result.error_message)`.
- A text reply is a stop of the run today: `tests/roadmap/stage/test_roadmap_stage_toolbox.py:1003:client = _client(checkout, Script(ModelResponse(parts=[TextPart("I will write the plan.")])))` and `tests/roadmap/stage/test_roadmap_stage_toolbox.py:1000:def test_a_reply_of_text_that_is_no_json_names_the_root_and_the_type_json_invalid(`.
- The parser exists and has its own test: `src/devops_cli/ai/client/structured.py:103:def _repair_and_validate_payload[T: BaseModel](` and `tests/ai/client/test_ai_client_structured.py:def test_repair_and_validate_payload`.
- The retry limit is the staged value: `src/devops_cli/config/constants.py:3378:CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES: Final[int] = 2`, read at that line with its comment `src/devops_cli/config/constants.py:3377:# The retries the model gets for a tool call or an answer that breaks its schema.`.
- `src/devops_cli/roadmap/stage/stage_verify_eval.py:283:with checkout_at(repository, case.base_commit, operation=_OPERATION) as source:` needs a checkout of the repository, and the eval pass makes it for each case already.
- `src/devops_cli/roadmap/stage/stage_toolbox.py:def review` needs a client of the `stage_review` model, and `src/devops_cli/roadmap/refine/refine_investigation.py:def investigate` needs a client of a model.
- The plan decides each cause that the issue names: a text reply gives `text_reply`, a refused tool call gives `refused_tool_call`, and a run with no budget gives `budget_exhausted`; the observed stop gives `output_retries_exhausted`, and the stops that the pass already names keep `output_cut`, `invalid_arguments`, `schema_broken`, `window_starved` and `model_error`.
- The live criterion needs a network and the local `qwen3.8:27b` verification model: not checked.
- The first check is `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py`.
- The first check of the live premise is `uv run devops roadmap eval verify --case good-2739-the-subprocess-environment-guard-accepts-gh --dry-run`, which makes no request, then the live `uv run devops roadmap eval verify --case good-2739-the-subprocess-environment-guard-accepts-gh` with the local model.
- The verify commands run `uv` and `pytest`, which the runner image installs with `python` and `git`; the failure class of a failed test is `test` with the action `repair`; the pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`.
- The tests double only the model and the checkout, and reach no network, no cluster and no real scanner.
- The related items #3039 and #3688 are no dependency: #3039 added the pass, and #3688 holds another fault of the same eval; the Dependencies section of the body says None.
- The probes left `output_retries`, `text_reply`, `output_retries_exhausted`, `refused_tool_call`, `budget_exhausted`, `run_error_message` and `CaseOutcome` unprobed; this run read `src/devops_cli/roadmap/stage/stage_verify_eval.py:class CaseOutcome`, `src/devops_cli/roadmap/agent_run.py:def run_error_message` and `src/devops_cli/config/constants.py:3378:CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES: Final[int] = 2`.
- The scenario "The output retries are exhausted" names the reason `output_retries_exhausted`, and the test of the second group names it: `test_a_text_reply_that_holds_the_findings_gives_them` in `tests/roadmap/stage/test_roadmap_stage_toolbox.py` asserts that an exhausted output retry raises with `output_retries_exhausted` and names the limit 2.

## Existing Tool Considered

pydantic-ai, the MIT-licensed harness already in use, runs the verification agent and raises the stop after its output retries; the change reuses its messages and the repository's `_repair_and_validate_payload` parser and adds no library.

## Dependencies

None.
