# Proposal

## Why

The stage job accepts a `criteria` entry that no person wrote, so the implement job verifies steps against invented criteria and hides that the issue gave none (#3391).

## What Changes

- `criterion_problems` in `src/devops_cli/roadmap/stage/stage_criteria.py` refuses each `criteria` entry whose text is not an acceptance criterion that a person wrote in the issue body.
- The message `stage_problem_criterion_unknown` in `src/devops_cli/lang/en/messages.py` quotes the entry and says that no person wrote it.
- `tests/roadmap/stage/test_roadmap_stage_criteria.py` covers a body with no person-written heading and a body whose only list sits in the refine block.
- `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` covers the `criteria` gate on a plan with an entry that no person wrote.
- `src/devops_cli/ai/tasks/roadmap_stage_change.md` states that the check refuses an entry that no person wrote, and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` asserts that sentence.
- The spec delta of `roadmap-stage/criteria` modifies the requirement that refuses an unmapped criterion and the requirement that the replay judges a plan with a `criteria` list.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/criteria`: An unmapped criterion is refused, The replay judges the criteria gate on plans with a criteria list

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_criteria.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_criteria.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The premise holds in the moved module: `read_file` of `src/devops_cli/roadmap/stage/stage_criteria.py` shows `def criterion_problems` building `mapped` from the entry texts and refusing only a missing criterion and a group over the count, so no line compares an entry with the person-written list.
- The test module moved with the code: the tests live in `tests/roadmap/stage/test_roadmap_stage_criteria.py`.
- The prompt exists: `src/devops_cli/ai/tasks/roadmap_stage_change.md:61` holds `An issue with no such list gets an empty list. The check refuses a reply that leaves one item out.` The empty-list rule stays and the refusal sentence joins it.
- PR #5875 (#4081) separated `ProposalGate.CRITERIA` from `_path_gate` in `stage_eval_gates.py`, and `_criteria_gate` already passes `plan.issue_body` to `criterion_problems(plan.proposal.criteria, plan.issue_body, len(plan.proposal.groups))`.
- `search_code` of `check_proposal(` shows callers passing `issue_body`: `stage.py`, `implement.py`, and `plan_check.py`.
- `docs/ROADMAP_WORKFLOW.md:386` holds the rule that a plan changing the stage prompt states the replay score before and after, so the task of group 2 holds `uv run devops roadmap eval stage --replay` with the words score, before and after.
- No call of the plan needs a checkout of the repository, a client of a service or a network.
- The checks against the real system: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_criteria.py tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, then `uv run devops roadmap eval stage --replay` with the score before and after the change.

## Existing Tool Considered

No open, maintained tool covers the need, because the rule compares a reply with the text of one issue of this repository and belongs in the existing `criterion_problems`. The change builds about 4k tokens of code to keep and fix, in about 1 hour, and deletes no internal code: `acceptance_criteria` and `criterion_problems` stay.

## Dependencies

None.
