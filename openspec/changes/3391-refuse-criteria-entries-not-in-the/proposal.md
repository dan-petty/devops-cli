# Proposal

## Why

The stage job accepts a `criteria` entry that no person wrote, so the implement job verifies steps against invented criteria and hides that the issue gave none (#3391).

## What Changes

- `criterion_problems` in `src/devops_cli/roadmap/stage/stage_criteria.py` refuses each `criteria` entry whose text is not an acceptance criterion that a person wrote in the issue body.
- The message `stage_problem_criterion_unknown` in `src/devops_cli/lang/en/messages.py` quotes the entry and says that no person wrote it.
- `src/devops_cli/roadmap/stage/stage_eval_gates.py:def _path_gate` gives `check_proposal` the issue body of a plan that has a `criteria` list, and no body for a plan that has none.
- `tests/roadmap/stage/test_roadmap_stage_criteria.py` covers a body with no person-written heading and a body whose only list sits in the refine block.
- `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` covers the `paths` gate on a plan with a `criteria` list and on a recorded plan with none.
- `src/devops_cli/ai/tasks/roadmap_stage_change.md` states that the check refuses an entry that no person wrote, and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` asserts that sentence.
- The spec delta of `roadmap-stage/criteria` modifies the requirement that refuses an unmapped criterion and the requirement that the replay judges a plan with a `criteria` list.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/criteria`: An unmapped criterion is refused, The replay judges the criteria gate on plans with a criteria list

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `src/devops_cli/roadmap/stage/stage_criteria.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_criteria.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The premise holds in the moved module. The probe says "The path `src/devops_cli/roadmap/stage_criteria.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_criteria.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it." `read_file` of `src/devops_cli/roadmap/stage/stage_criteria.py` shows `src/devops_cli/roadmap/stage/stage_criteria.py:def criterion_problems` building `mapped` from the entry texts and refusing only a missing criterion and a group over the count, so no line compares an entry with the person-written list.
- The test module moved with the code. The probe says "The path `tests/roadmap/test_roadmap_stage_criteria.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/test_roadmap_stage_criteria.py`." The plan writes the tests in `tests/roadmap/stage/test_roadmap_stage_criteria.py` and plans no code for the old path.
- The prompt exists. The probe says "The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit." `search_code` of `An issue with no such list gets an empty list` returned one hit, and the file holds `src/devops_cli/ai/tasks/roadmap_stage_change.md:46: An issue with no such list gets an empty list.` beside `The check refuses a reply that leaves one item out.` The empty-list rule stays and the refusal sentence joins it.
- The replay holds no body for the check. `read_file` of `src/devops_cli/roadmap/stage/stage_eval_gates.py` shows `src/devops_cli/roadmap/stage/stage_eval_gates.py:def _path_gate` calling `check_proposal` with no `issue_body`, while `PlanUnderTest.of_case` sets `issue_body=case.issue_body` and `mapped="criteria" in case.plan`, so a mapped recorded plan holds its body and an unmapped one is not judged.
- `search_code` of `check_proposal(` shows the callers that hold a real body, `src/devops_cli/roadmap/stage/stage.py:1126: problems = check_proposal(`, `src/devops_cli/roadmap/implement/implement.py:404: problems = check_proposal(` and `src/devops_cli/roadmap/plan_check.py:380: for message in check_proposal(`, and the replay call `src/devops_cli/roadmap/stage/stage_eval_gates.py:161: return check_proposal(` with no body. The rule therefore holds in the job and the plan check, and the replay is the one caller that group 1 repairs.
- The first review said group 1 needs group 2. The groups are now in the other order: group 1 gives `_path_gate` the issue body, group 2 adds the refusal. `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:311: assert not replay_case(_with_criteria(good, both)).refused` passes after group 1 alone, because the old rule reads a body whose two criteria the entries copy, and it still passes after group 2 for the same reason.
- The second review is right about case 3174, and the earlier line of this plan was wrong. Its one defect is pinned to no gate at `tests/fixtures/roadmap_eval/stage/3174-a-plan-with-a-placeholder-group/case.json:29: "gate": "none"`, and `_status` returns `UNJUDGED` for that gate, so the pinned counts hold through the `UNJUDGED` path and not through the `content` gate. The plan of 3174 holds `tests/fixtures/roadmap_eval/stage/3174-a-plan-with-a-placeholder-group/plan.json:64: "criteria": []` and its issue body holds three criteria, so the `criteria` gate already refuses it and the `paths` gate names the same three criteria after group 1. Its verdict is `reject`, so the replay fails nothing and no pinned count in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` changes.
- Case 3411 keeps its verdict. Its entry copies a person-written criterion: `tests/fixtures/roadmap_eval/stage/3411-a-what-changes-item-that-names/issue.txt:13: The stage check refuses a What Changes item that names a repository path` and `tests/fixtures/roadmap_eval/stage/3411-a-what-changes-item-that-names/plan.json:70: "criteria": [`. So the `paths` gate finds no unknown-entry problem for that entry and still names the missing What Changes path.
- `docs/ROADMAP_WORKFLOW.md:314: A pull request that changes the stage prompt` holds the rule that such a plan states the replay score before and after, so the task of group 3 holds `uv run devops roadmap eval stage --replay` with the words score, before and after.
- No call of the plan needs a checkout of the repository, a client of a service or a network: `criterion_problems` and `acceptance_criteria` take strings, and `_path_gate` takes a `PlanUnderTest` whose body and tree the replay reads from the recorded case files.
- The first checks against the real system: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_criteria.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, then `uv run devops roadmap eval stage --replay` with the score before and after the change.
- Pull request #3989 changed `src/devops_cli/ai/tasks/roadmap_stage_change.md` too and merged, so this plan adds the refusal sentence beside the merged changes.

## Existing Tool Considered

No open, maintained tool covers the need, because the rule compares a reply with the text of one issue of this repository and belongs in the existing `criterion_problems`. The change builds about 4k tokens of code to keep and fix, in about 1 hour, and deletes no internal code: `acceptance_criteria`, `criterion_problems` and `_path_gate` stay.

## Dependencies

- None. Pull request #3989 merged into main, so no pull request blocks this change.
