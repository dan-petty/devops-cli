# Design

## Decisions

- **Put the gate in `src/devops_cli/roadmap/stage/stage_eval_gates.py` as one `Gate` in `GATES`, with its own `DefectType` and `GateName`.**: The stage gate set is deterministic and replayable, so the replay reports the defect by its own name and a regression fails the golden set. `stage_specs.py`, the other file that the issue names, is a separate concern: it reads the base specs under `openspec/specs/`, so it holds no gate.
- **Read the field addition from the text of the groups: a group changes `src/devops_cli/roadmap/stage/stage_change.py` and its title, implementation or documentation names `StageProposal` with a new field.**: The staging plan holds no diff, so the text of the group is the only offline signal that the plan adds a field.
- **Require a group that changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` and names the new reply key with its rule.**: The prompt test compares the reply-key bullets with the properties of the schema of `StageProposal`, and the behavior rule is what the model reads for the new field.
- **Name the prompt file and the reply key in the problem that the gate returns.**: The model gets the problem back once, and the message must say what to add and where.
- **Add a recorded case with the defect, and keep the gate name `none` on no case.**: The replay must report the new defect as caught by the new gate, and a plan that adds the field with the prompt update must pass.

## Rejected alternatives

- **Check the plan inside `check_proposal` only.**: `replay_case` calls `run_gates(PlanUnderTest.of_case(case))`, and `_status` reads `problems.get(defect.gate, [])`, so a check outside a `Gate` gives the replay no named defect to judge.
- **Refuse every plan that changes `src/devops_cli/roadmap/stage_change.py`.**: The file holds `check_proposal`, `render_change` and `measure_groups` beside `StageProposal`, so the rule would refuse a docstring or validator edit that adds no field.
- **Reuse `DefectType.MISSING_PATH` and `GateName.PATHS`.**: `Gate(GateName.PATHS, "#3010", DefectType.MISSING_PATH, _path_gate)` runs `check_proposal`, and `_names_every_path` requires a problem that names each path of the defect: a prompt key is no path of the staged tree.
- **Reuse `DefectType.CRITERION_DROPPED` and `GateName.CRITERIA`.**: `_criteria_gate` returns `criterion_problems(plan.proposal.criteria, plan.issue_body, len(plan.proposal.groups))`, which judges the `criteria` list against the acceptance criteria and nothing about the prompt.
- **Rely on `test_the_top_level_keys_of_the_reply_are_the_fields_of_the_proposal` alone.**: That test runs in the test suite after the change is implemented, so it stops the pull request of the item and not the plan that leaves the update out.
