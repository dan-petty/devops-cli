## Problem or Motivation

`tests/roadmap/test_roadmap_stage_gates.py::test_a_stage_check_change_with_no_replay_task_is_a_problem_of_the_gate_eval_replay` fails on `main` (Tests & Coverage, shard 2). Two pull requests merged in turn. #3641 made `content_problems` refuse a behavior group that changes `src/devops_cli/roadmap/stage_change.py` and holds no self-acceptance test. #3732 added the gate test, in which the sample group changes `stage_change.py` with no such test. Each pull request passed its own checks. Together they fail: the gate `content` also finds a problem, so the test sees two gates and not only `eval-replay`.

## Proposed Solution & Architectural Design

Give the changed group in that test a task test that holds `StageProposal`, `content_problems` and `no problem`, so only the gate `eval-replay` refuses the plan.

## Target Subsystem

`tests/roadmap/test_roadmap_stage_gates.py`

## Existing Tool Considered

None needed: a one-line change of a test fixture. Cost: about 2,000 tokens to change and check, about 0 to keep, and about 15 minutes elapsed.


Source: https://github.com/dan-petty/devops-cli/pull/3668

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P1-High", "Status": "In Review", "Value": "Medium"} -->
