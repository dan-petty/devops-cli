# Proposal

## Why

The verification pass of the stage job checks a plan for form and reads only the start of each cited file. It makes one model call with no tool. So it misses a false premise, a broken task order and a verify command that proves nothing, unless the cited text shows the defect. The review of 2026-11-01 found such defects that no gate caught (#3039).

## What Changes

- The verifier of each plan runs as an agent. It has the read-only tools of the planner, and it reads the repository to check the paths, the premise, the scope against the criteria, the task order, the spec delta and the verify commands.
- The verifier gets no planner message. Its request holds the issue, the plan and the read results only.
- The request and the run of the verifier use the window of the task `verification`, the model that serves them. The request stays `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS` below the point where the run offers no more tools, so the verifier can read.
- A quote from a tool answer of the run counts as evidence, as a quote from the issue, the plan or a cited file does.
- The findings `task_order` and `verify_form` return the plan to the planner, as the other return types do.
- The job repairs a plan up to two rounds. The planner gets each open finding of the round. A plan with an open finding after the last round stays in draft with the label `plan/needs-fix`, and the issue receives a comment with the evidence. The comment lists the findings of each round.
- The review of refine uses the same prompt with no tool. The tool rules go to a second prompt that only an agent run loads, and that review keeps the open types that it had: a `task_order` or `verify_form` finding on a proposal is advice, because a proposal has no task groups.
- `plan_stage` and `evaluate_cases` take only the model of an agent run, so the old pass with no tool is gone from them. The eval gives `read_spec` the OpenSpec tool, as the job does, and `--model` keeps the rest of the task.
- The message and the comment of a stage run name the review run where it is the review that ran.
- The reads of the verifier appear in the comment of the staged item.
- The metrics of the tool calls give a verifier run its own value of the label `row`, `stage_verify`, so its reads do not hide a tool that the planner does not use.
- `devops roadmap eval verify` prints the recall floor of 90% of the blocker and major defects, and whether the recall meets it.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: the verification pass runs with the read-only tools, returns a plan up to two repair rounds, and returns the findings `task_order` and `verify_form`.
- `roadmap-stage-eval`: the verify command runs the tool-capable pass and prints the recall floor.
- `roadmap-refine`: the review names its open types, which do not include `task_order` and `verify_form`.

## Impact

- Code: `src/devops_cli/roadmap/stage_verify.py`, `src/devops_cli/roadmap/stage_toolbox.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/roadmap_eval_verify.py`, `src/devops_cli/roadmap/stage_verify_eval.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/refine_judge.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/tool_metrics.py`, `src/devops_cli/telemetry/instruments.py`
- Prompts: `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify_tools.md`
- Documents and manifests: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `docs/TELEMETRY.md`, `k8s/README.md`, `k8s/monitoring/prometheus-values.yaml`
- Tests: `tests/roadmap/test_roadmap_stage_verify.py`, `tests/roadmap/test_roadmap_stage_verification.py`, `tests/roadmap/test_roadmap_stage_verify_eval.py`, `tests/roadmap/test_roadmap_refine_trust.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `tests/roadmap/test_roadmap_stage_toolbox.py`

## Feasibility

The premise holds at `origin/main` commit `d254410c`. The plan of the item was made at `ce689f43`, and the code that it cites is unchanged.

- `src/devops_cli/roadmap/stage_verify.py`, function `verify`: one call to `client.chat_structured` with the schema `Verification`. The call has no tool. Checked with `git show origin/main:src/devops_cli/roadmap/stage_verify.py`.
- `src/devops_cli/roadmap/stage_toolbox.py`, method `ToolboxClient.chat_structured`: a schema other than `StageProposal` goes to the inner client with no tool.
- `src/devops_cli/roadmap/stage_verify.py`, constants `RETURN_TYPES` and `OPEN_TYPES`: neither holds `TASK_ORDER` nor `VERIFY_FORM`. The enum `DefectType` in `src/devops_cli/roadmap/stage_eval_cases.py` holds both.
- `src/devops_cli/roadmap/stage.py`, method `_Planner._verified`: one branch returns the plan once, and the second review does not return it again.
- `src/devops_cli/roadmap/stage_verify_eval.py`, function `render_verify`: the report holds no floor line.
- `docs/ROADMAP_WORKFLOW.md`, line 282: the recall floor is 90% of the defects of the severities `blocker` and `major`.
- The first body of the issue asked that a failing plan opens no pull request. Commit `#3264` (archived change `2026-11-04-3264-the-stage-marks-a-plan-ready`) keeps the draft with `plan/needs-fix`, and the module docstring of `stage_verify.py` says so. This change follows the code, and the criterion of the issue now states this outcome.

## Existing Tool Considered

The open library that covers the need is pydantic-ai, which the planner already uses. The function `investigate` in `src/devops_cli/roadmap/refine_investigation.py` runs an agent with tools, a `RunTrace` and a context window. This change reuses `investigate`, the read tools of `StageTools` and `RunTrace`, and adds no library.

The open tool `github/spec-kit` (MIT, last activity 2026-11-03) covers a read-only analysis of a spec, a plan and tasks. It has no bounded repair loop, no pipeline gate that keeps a draft closed, no recall floor on a known-defect set and no isolation from the planner reasoning. So it does not cover the need as written.

Written cost of the delta, from the issue: about 300,000 tokens to build, keep and fix, and about two days of elapsed time.

The change deletes the single-return branch of `_Planner._verified`, which the repair loop replaces. It deletes no module.
