# Tasks

## 1. Give the replay's paths gate the issue body

Reads: `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `src/devops_cli/roadmap/stage/stage_criteria.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`. Changes: `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.

- [ ] 1.1 In `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, build the good case with `_with_criteria(good, [])`: the `paths` gate names the criteria `First.` and `Second.` of `ACCEPTANCE_BODY`. With both entries mapped, the `paths` gate names no criterion, and a case with no `criteria` key and the same body finds no criterion problem at the `paths` gate
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` fails on the base
- [ ] 1.2 In `src/devops_cli/roadmap/stage/stage_eval_gates.py`, pass `issue_body=plan.issue_body if plan.mapped else ""` to `check_proposal` in `_path_gate`, and state that rule in its docstring. Run `uv run devops roadmap eval stage --replay` and state the score before and after the change
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes

## 2. Refuse a criteria entry that no person wrote

Reads: `src/devops_cli/roadmap/stage/stage_criteria.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_criteria.py`. Changes: `src/devops_cli/roadmap/stage/stage_criteria.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_criteria.py`.

- [ ] 2.1 In `tests/roadmap/stage/test_roadmap_stage_criteria.py`, write a test with a body whose only `Acceptance criteria` heading sits in the refine block and a reply that holds one criterion of that block: `criterion_problems` returns one problem that quotes the copied text. Add a second test with the same body and an empty `criteria` list: `criterion_problems` returns no problem
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_criteria.py` fails on the base
- [ ] 2.2 In `src/devops_cli/roadmap/stage/stage_criteria.py`, make `criterion_problems` add `MESSAGES.roadmap.stage_problem_criterion_unknown` for each entry whose `_one_line` text is not in `acceptance_criteria(issue_body)`, after the problems for a missing criterion. Add `stage_problem_criterion_unknown` to `src/devops_cli/lang/en/messages.py`: it quotes the entry, says that no person wrote it in the issue body, and says to copy the text of a top-level item under the heading `Acceptance criteria` or to give an empty list. Run `uv run devops roadmap eval stage --replay` and state the score before and after the change
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_criteria.py` passes

## 3. State the refusal in the stage prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [ ] 3.1 Add to the `criteria` bullet of `src/devops_cli/ai/tasks/roadmap_stage_change.md` that the check refuses an entry whose text is not one of the person-written criteria, beside the rule that an issue with no such list gets an empty list. Assert both sentences in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Run `uv run devops roadmap eval stage --replay` and state the score before and after the change
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes
- [ ] 3.2 Edit `src/devops_cli/ai/tasks/roadmap_stage_change.md` so the `criteria` bullet states that the check refuses an entry that no person wrote
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
