# Tasks

## 1. Judge only the sentences that a repair adds or changes

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/steps/fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan.py`, `tests/roadmap/stage/test_roadmap_stage_trace_runs.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/steps/fix_plan.py`, `tests/roadmap/steps/test_roadmap_fix_plan_trace.py` (new), `tests/roadmap/stage/test_roadmap_stage_trace_repair.py` (new), `tests/roadmap/stage/test_roadmap_stage_trace_spans.py`, `tests/fixtures/roadmap/plan_heads/5390-8d08977ffff4/` (new).

- [x] 1.1 Write `tests/roadmap/stage/test_roadmap_stage_trace_repair.py` with the head of #5390 as a fixture: its sentences pass the trace gate with no read of the repair when they are `judged`, and a sentence that the repair adds or changes is judged on the reads of the repair. Write `tests/roadmap/steps/test_roadmap_fix_plan_trace.py`: a fix-plan attempt with a scripted toolbox planner keeps a citation that only the run of the head read (`regated`), fails on a new citation of a file that no run read, and passes when the run read that file with its lines. Add the cases of `read_file path 3915 3935` to `tests/roadmap/stage/test_roadmap_stage_trace_spans.py`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Add `feasibility_sentences` and the parameter `judged` of `_trace_problems`, `check_gates`, `check_proposal` and `gate_arguments`, set `_judged` in `_Planner.revise`, and remove the line numbers after a tool span path in `_citation`
  - Verification: `$ uv run devops ci test tests/roadmap/stage tests/roadmap/steps tests/roadmap/test_roadmap_plan_read.py tests/commands/test_roadmap_step_fix_plan.py`

## 2. Keep the golden replay

Kind: other. Reads: `src/devops_cli/roadmap/stage/stage_eval_gates.py`. Changes: none.

- [x] 2.1 Run the replay and state that every gate refuses what it must refuse and that every good plan passes
  - Verification: `$ uv run devops roadmap eval stage --replay`

## 3. Document the repair gate

Kind: other. Reads: `docs/roadmap/stage.md`. Changes: `docs/roadmap/stage.md`.

- [x] 3.1 Write the line numbers of a `read_file` span in the trace gate paragraph, and the sentences that the repair keeps in the Repair item of the fix-plan step of `docs/roadmap/stage.md`
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: `uv run devops ci fail-to-pass --base origin/main` shows that each new test fails on the base and passes on the head.
- Pending a person: after the merge and the release, the next fix-plan attempt on #5390 reaches the review of the head.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
