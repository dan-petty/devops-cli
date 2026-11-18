# Proposal

## Why

A run of `devops roadmap eval verify` on #3717 stops a case with `Tool <text> exceeded max retries count of 2`, which names no tool and no limit, and the case counts as failed, so the run gives no recall and no false-alarm count and a person cannot act on the stop.

## What Changes

- Type the stop of an agent run from its messages: a call that the tools retry limit ended, a run whose tools the budget took away, an exhausted output retry and a text reply each get a reason and the name of the tool, the limit or the text.
- Cite pydantic-ai `AutoOutputSchema` (`_output.py:638-655`, which also strips Markdown fences at `_output.py:981`) for text replies that hold valid JSON findings. Keep `text_reply` only for text replies that pydantic-ai refuses.
- Name the cause in the stop message of the verification pass: the tool name and the tools retry limit of a refused call, the limit that ended the tools, the output retry limit that the run used, or the text reply that pydantic-ai refuses.
- Record `cases[].reason` in the JSON report and name the reason of each failed case in the text report of `devops roadmap eval verify`.
- Add one requirement to `roadmap-stage/verification` and one to `roadmap-stage-eval`, because the stop message of the pass and the report of a `devops` command change.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/verification`: A stopped verification run names its cause
- `roadmap-stage-eval`: The verify report names the stop reason of a failed case

## Impact

- Code: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage_verify_eval.py`
- Tests: `tests/roadmap/refine/test_roadmap_refine_investigation.py`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`

## Feasibility

- The probes confirm the paths of the premise: "The path `src/devops_cli/roadmap/stage/stage_verify_eval.py` is a file of the staging commit.", "The path `src/devops_cli/roadmap/agent_run.py` is a file of the staging commit.", "The path `src/devops_cli/config/constants.py` is a file of the staging commit." and "The path `src/devops_cli/roadmap/refine/refine_investigation.py` is a file of the staging commit."
- The earlier plan named a text reply as the cause of the stop of the issue. `read_file` of `src/devops_cli/roadmap/stage/stage_verify.py` lines 82 and 590 and of `src/devops_cli/roadmap/stage/stage_toolbox.py` line 204 showed `src/devops_cli/roadmap/stage/stage_verify.py:82:_REPLY_RETURNS: Final[int] = 1` and `src/devops_cli/roadmap/stage/stage_toolbox.py:204:output_retries=max_retries,`, so the pass sets the output retry limit to 1.
- `read_file` of `src/devops_cli/roadmap/refine/refine_investigation.py` lines 605 to 616 showed `src/devops_cli/roadmap/refine/refine_investigation.py:612:"tools": CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES,` beside the output retries, and the staged value of the constant is `src/devops_cli/config/constants.py:3378:CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES: Final[int] = 2`.
- The message of the issue names 2, which is the tools retry limit, and the archived record of that path shows the same text: `openspec/changes/archive/2026-11-02-3037-the-stage-job-plans-with-a/design.md:11:Tool 'read_file' exceeded max retries count of 2`. The observed stop is the tools retry path with the limit 2, and not the output retries with the limit 1, so the new plan names the tool of the last reply and the tools retry limit, and keeps the text reply only because the acceptance criterion names it.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_toolbox.py` lines 1012 to 1024 showed `tests/roadmap/stage/test_roadmap_stage_toolbox.py:def test_a_reply_that_calls_no_tool_of_the_run_raises_with_the_stop_reason_no_tool_call`: a call to a tool that the run does not offer ends as `StructuredOutputValidationError`, which is the class that the issue reports.
- `read_file` of `src/devops_cli/lang/en/messages.py` lines 4224 to 4228 showed `src/devops_cli/lang/en/messages.py:4225:stage_verify_stopped: str = (` with `src/devops_cli/lang/en/messages.py:4226:"The verification run stopped before it gave its findings: {reason}. The plan passed the "`, which is the text of the issue.
- `read_file` of `src/devops_cli/roadmap/agent_run.py` lines 139 to 150 showed `src/devops_cli/roadmap/agent_run.py:139:def run_error_message(stopped: AgentRunError) -> str:` and `src/devops_cli/roadmap/agent_run.py:148:hidden = _QUOTED.sub("<text>", bounded_text(first))`, which hides each quoted part, so a tool name in the message reads `<text>`.
- `read_file` of `src/devops_cli/roadmap/agent_run.py` lines 240 to 303 showed `src/devops_cli/roadmap/agent_run.py:254:limit: RunLimit | None = None` and `absorb`, which records the messages of a stopped run and treats a call to any tool that is no function tool of the run as the output tool's, so the new cause reads the last reply itself.
- `read_file` of `src/devops_cli/roadmap/stage/stage_toolbox.py` lines 173 to 270 showed `src/devops_cli/roadmap/stage/stage_toolbox.py:173:def chat_structured[M: BaseModel](`, which passes the retries to `investigate` at `src/devops_cli/roadmap/stage/stage_toolbox.py:204:output_retries=max_retries,`, and `src/devops_cli/roadmap/stage/stage_toolbox.py:241:def _stopped(result: InvestigationStopped, trace: RunTrace, schema: type[BaseModel]) -> Exception:`, which formats `src/devops_cli/roadmap/stage/stage_toolbox.py:248:else MESSAGES.roadmap.stage_verify_stopped`.
- pydantic-ai handles model output types with `AutoOutputSchema` (`_output.py:638-655`) and strips Markdown fences (`_output.py:981`), so valid JSON text replies already pass without home-grown parsing.
- `read_file` of `src/devops_cli/roadmap/stage/stage_verify_eval.py` lines 94 to 104 showed `src/devops_cli/roadmap/stage/stage_verify_eval.py:94:class CaseOutcome:` and `src/devops_cli/roadmap/stage/stage_verify_eval.py:104:error: str = ""`: the case keeps a free-text error and no typed reason.
- `read_file` of `src/devops_cli/roadmap/stage/stage_verify_eval.py` lines 212 to 345 showed `src/devops_cli/roadmap/stage/stage_verify_eval.py:283:with checkout_at(repository, case.base_commit, operation=_OPERATION) as source:`, `src/devops_cli/roadmap/stage/stage_verify_eval.py:212:def _not_run(case: StageCase, error: str = "") -> CaseOutcome:` and `src/devops_cli/roadmap/stage/stage_verify_eval.py:337:return _not_run(case, result.error_message)`.
- `read_file` of `src/devops_cli/roadmap/stage/stage_verify_eval.py` lines 440 to 505 showed the JSON field `src/devops_cli/roadmap/stage/stage_verify_eval.py:493:"error": case.error,` and the one ended line of the text report `src/devops_cli/roadmap/stage/stage_verify_eval.py:455:ended=f"verified {len(score.cases) - score.failed}, failed {score.failed}"`, which names a count and no case.
- `read_file` of `src/devops_cli/roadmap/stage/stage_toolbox.py` line 130 showed `src/devops_cli/roadmap/stage/stage_toolbox.py:130:traces: list[RunTrace] | None = None,`, so the eval reads the trace of the run of each case.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_toolbox.py` line 1000 showed `tests/roadmap/stage/test_roadmap_stage_toolbox.py:1000:def test_a_reply_of_text_that_is_no_json_names_the_root_and_the_type_json_invalid(`, so a text reply is a stop of the run today.
- Task 3.1 runs `evaluate_cases` with `ToolboxModel(Script(...).model())` and the `stage_repo` clone, as `test_roadmap_stage_verify_eval.py:730-781` does. The test reaches no network, no cluster and no real scanner.
- Each verify command runs `uv run devops ci test`; the runner image installs `uv`, `python`, `pytest` and `devops`, a failed test is the failure class `test` with the action `repair`, and the pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`.
- The live criterion needs the local `qwen3.8:27b` verification model and a network: not checked. The first checks of it are `uv run devops roadmap eval verify --case good-2739-the-subprocess-environment-guard-accepts-gh --dry-run`, which makes no model call, then the same command with no `--dry-run`.
- The first checks of the implementation are `uv run devops ci test tests/roadmap/refine/test_roadmap_refine_investigation.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py`.
- `find_issues` for `roadmap eval verify` listed open items #3956 and #4402 among others, and the context lists no overlap, no metric sender and no issue dependency, so `dependencies` is empty.

## Existing Tool Considered

pydantic-ai, the MIT-licensed harness already in use, handles model outputs with `AutoOutputSchema` (`_output.py:638-655`) and strips Markdown fences (`_output.py:981`), so valid JSON text replies already pass without home-grown parsing. It raises after its tool and output retries and holds the messages of the run; the change reuses its messages and adds no library.

## Dependencies

None.
