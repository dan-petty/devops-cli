# Proposal

## Why

`main` fails one test (#3736). #3641 made `content_problems` refuse a behavior group that changes `src/devops_cli/roadmap/stage_change.py` and holds no self-acceptance test (#3404). #3732 added `test_a_stage_check_change_with_no_replay_task_is_a_problem_of_the_gate_eval_replay`. Its sample group changes `stage_change.py` and holds no such test. Each pull request passed its own checks. Merged together, the gate `content` also refuses the plan, and the test sees two gates and not only `eval-replay`.

## What Changes

- `tests/roadmap/test_roadmap_stage_gates.py`: the changed group of that test gets a task test that holds `StageProposal`, `content_problems` and `no problem`. Only the gate `eval-replay` then refuses the plan.
- The change alters no behavior that a consumer observes, because it edits one test. So it has no spec delta and sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/roadmap/test_roadmap_stage_gates.py`.
- No command, option, message or document changes.

## Feasibility

- On `origin/main` (29309f04), `uv run pytest tests/roadmap/test_roadmap_stage_gates.py` fails: the gates that find a problem are `content` and `eval-replay`, and the test expects `eval-replay` only.
- `_self_acceptance_problems` in `src/devops_cli/roadmap/stage_change.py` looks for the marks `StageProposal`, `content_problems` and `no problem` in the test of a behavior group that changes `stage_change.py`. With a test that holds the three marks, the test passes.

## Existing Tool Considered

No tool applies: the change is one line of a test fixture. Cost: about 2,000 tokens to change and check, about 0 tokens to keep, and about 15 minutes elapsed. The change deletes no internal code.
