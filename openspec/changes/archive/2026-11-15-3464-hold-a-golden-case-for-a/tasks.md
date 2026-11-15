# Tasks

## 1. Label the unnamed verify test of case 2576 and move the replay totals

Kind: manifest. Reads: `tests/fixtures/roadmap_eval/stage/2576-a-token-that-argo-cd-refuses/plan.json`, `tests/fixtures/roadmap_eval/stage/2576-a-token-that-argo-cd-refuses/case.json`, `src/devops_cli/roadmap/stage/stage_form.py`, `src/devops_cli/lang/en/messages.py`. Changes: `tests/fixtures/roadmap_eval/stage/2576-a-token-that-argo-cd-refuses/case.json`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py`.

- [x] 1.1 Write `test_the_replay_of_the_plan_of_2576_is_refused_for_its_unnamed_verify_test` in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, and it fails first because `tests/fixtures/roadmap_eval/stage/2576-a-token-that-argo-cd-refuses/case.json` holds no `verify_form` defect for group 1
  - Verification: `$ uv run devops ci test tests/roadmap/stage/` fails on the base
- [x] 1.2 Add one object to the defects of `tests/fixtures/roadmap_eval/stage/2576-a-token-that-argo-cd-refuses/case.json`: the type `verify_form`, the severity `major`, a where text that names group 1 and its verify, a problem and an evidence that name the recorded verify command and the empty reads and creates of the group, the gate `paths`, and the message `which runs no test module of the group`. In `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, add the test above, raise `JUDGED_BASELINE` to (83, 320), set the `VERIFY_FORM` row of the count test to (7, 0, 12), raise the count of the defects that waited for a gate to 77, and name the case in the comment above the baseline. In `tests/roadmap/stage/test_roadmap_stage_eval_command.py`, set the share line to `83 of 320 (26%)`, the JSON `defects` to judged 83 and known 320, and the `verify_form` row to (7, 0, 12)
  - Verification: `$ uv run devops ci test tests/roadmap/stage/` passes
