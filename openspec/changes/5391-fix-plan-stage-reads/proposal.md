# Proposal: #5391

## Why

The step `fix-plan` can fail the Feasibility trace gate on a citation that a run read (#5391). On 2026-11-13 the fix-plan Job on plan pull request #5390 (item #5272, head 8d08977ffff4, image 0.127.0) ended `failed` at the step `gate`, before the review of the head, with the class `plan_defect`: 4 plan calls, 3 gate returns, 2,365,095 tokens and 25 minutes. The reason was "The Feasibility section states that `src/devops_cli/roadmap/decision_step.py 50 215` was read, but the run did not read it", and the same problem for three more files.

Two defects cause this:

- `_Planner.revise` sets no trace facts of the run that wrote the head (`self._kept_facts = None`), and that run is not in the process. So the gate judges each Feasibility sentence of each reply of the repair with the reads of the repair only. A sentence that the reply keeps from the head is refused when the repair did not read its file again.
- The gate takes the path of a span `read_file <path> <start> <end>` as the whole text after the tool name. The claimed path `src/devops_cli/roadmap/decision_step.py 50 215` matches no read path, so the gate refuses the claim also when the run read the file. Its return tells the planner to read a path that is not a file, so a gate return cannot fix it.

Closes #5391.

## What Changes

- The trace gate gets `judged`, the Feasibility sentences that the trace gate of an earlier run passed, and does not judge them again. `check_gates`, `check_proposal` and `gate_arguments` take it, and `feasibility_sentences` gives the sentences of a plan in the form that the gate reads.
- `_Planner.revise` gives the sentences of the plan of the head as `judged`. A sentence that a reply adds or changes is judged with the reads of the plan runs of the repair, so a citation of a file that no run of the repair read stays refused. The stage job gives no `judged`, so its gate does not change.
- `_citation` removes one or two line numbers after the path of a span that starts with a toolbox tool name, as in `read_file path 50 215`. The refusal names the path without the line numbers. A word that is no toolbox tool keeps its numbers in the path.
- The change has a spec delta: the stage job and the step `fix-plan` refuse fewer plans, and the text of a refusal changes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/trace-gate`: The trace gate reads the path of each citation form
- `roadmap-stage/fix-plan`: The trace gate of a repair judges only the sentences that the repair adds or changes

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/steps/fix_plan.py`
- Tests: `tests/roadmap/steps/test_roadmap_fix_plan_trace.py`, `tests/roadmap/stage/test_roadmap_stage_trace_repair.py`, `tests/roadmap/stage/test_roadmap_stage_trace_spans.py`, the head of #5390 in `tests/fixtures/roadmap/plan_heads/5390-8d08977ffff4/`
- Documents: `docs/roadmap/stage.md`
- Release: the fix-plan Job runs the code of the runner image, so the fix needs a release. The `fix` commit makes release-please propose a patch release. After the merge and the release, the next fix-plan attempt on #5390 runs on the new image. The record of #5272 holds 1 attempt on the head 8d08977ffff4, and the step allows 2.

## Feasibility

- The premise is confirmed in the source at `origin/main` (4ef7c6f11, release 0.127.0). `src/devops_cli/roadmap/stage/stage.py:def revise` sets `self._kept_facts = None`, and its docstring says: "No trace of the run that made `proposal` is in the process, so the trace gate judges only the replies of this repair." `_trace_facts` then gives only the facts of the plan runs of the repair. So question 1 of the issue has the answer: the step builds its trace facts from its own runs only.
- The gate returns of question 2: the return text names the claimed path, and the planner has `read_file` in the toolset `base` (`src/devops_cli/roadmap/stage/stage_tools.py`), but the named path was `src/devops_cli/roadmap/decision_step.py 50 215`. A probe with the code of `origin/main` showed the cause: `check_proposal` with a trace that holds a read of `src/devops_cli/sample.py` refuses "`read_file src/devops_cli/sample.py 50 215` confirms gap 2" and names `src/devops_cli/sample.py 50 215`. It accepts `read_file src/devops_cli/sample.py`, `read_file("src/devops_cli/sample.py", 50, 215)` and `read_file src/devops_cli/sample.py:50-215`. `_citation` removes only the tool name, and `_CITATION_PATH` reads no line numbers after a space.
- The Job log in Loki (pod `fix-plan-5390-wnpj5`, 2026-11-13) holds the attempt line with 4 such refusals: `decision_step.py 50 215`, `constants.py 3915 3935`, `decision_point.py 398 432` and a fourth that the log cuts. Each range holds a line that the head cites (`decision_step.py:207`, `constants.py:3928`, `decision_point.py:413`), so the repair read a window around each citation and wrote the call in its Feasibility section. The log holds no tool arguments, so the reads of the repair are not proven. The attempt ended at the gate with the class `plan_defect`, not at a limit of the run (`limit_reached` or `output_cap`), and its 4 plan calls used 2,365,095 tokens. So the budget did not stop a read: the gate refused each reply on a path that is not a file.
- The head of #5390 (`git show 8d08977ffff4`) has 38 Feasibility lines. With no read of the repair, the trace gate of `origin/main` refuses its sentences that claim a `read_file` (the test `test_the_sentences_of_the_head_of_5390_pass_with_no_read_of_the_repair`).
- The stage job writes the facts of the stage run only to its plan file (`roadmap/stage/<owner>/<repo>/<number>.json`), and it deletes that file when it stages the item (`_stage`). So no record of the reads of the stage run exists when the step runs. The step stops a branch that holds a commit of another author than the clone identity (`_branch_reason`), so the trace gate of a Service run passed each sentence of the head: the stage job, or an earlier attempt of the step.
- A step-level test with a scripted toolbox planner gives the failure of #5390 on `origin/main`: "The change fails its checks, also after a second try: The Feasibility section states that `src/devops_cli/sample.py` was read, but the run did not read it."
- `uv run devops roadmap eval stage --replay` on the branch: 82 of 319 defects caught by a gate, 0 missed, and 6 of 6 good plans accepted. The replay gives no trace facts and no `judged`, so the change of the trace gate does not change it.

## Existing Tool Considered

No open tool reads the trace facts or the Feasibility claims of this project's plans. The change adds one pattern to `_citation` and one parameter to the trace gate, and reuses `_sentences`, the split that the gate already uses. Cost: about 150,000 tokens to build, 5,000 to keep and 2 hours elapsed. The change deletes no internal code.
