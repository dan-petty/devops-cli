# Design

## Decisions

- **Add the rule inside `check_proposal` in `src/devops_cli/roadmap/stage_change.py`, and not as a new gate in `stage_eval_gates.py`.**: The stage job calls `check_proposal` through `stage.py`, and the replay calls it through the `paths` gate in `stage_eval_gates.py`. One function gives the job and the replay the same answer.
- **Trigger the rule on the stage prompt and each module that holds a check `check_proposal` calls**: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage_criteria.py` and `src/devops_cli/roadmap/stage_eval_gates.py`. The workflow rule names the prompt and the checks that `check_proposal` and the gates it calls hold. These six files are those checks.
- **Require the exact command `uv run devops roadmap eval stage --replay` and the words `score`, `before` and `after` in one group task.**: The rule needs a replay and a stated score, and one group task keeps the command with its result. The check stays offline and its problem text names what is missing.
- **Read the task text of the group: its title, test, implementation, documentation and verify.**: The rendered `tasks.md` holds these fields, so the model can satisfy the check in the plan it writes.
- **Put the tests in `tests/roadmap/test_roadmap_stage_form.py`.**: That module already tests `check_proposal` rules with a staged tree and needs no model, no git and no network.
- **Add one replay case and state the counts and the score.**: The golden set holds no plan that changes a trigger path, so the rule changes no recorded verdict until a case exercises it. The case records the defect of a plan that changes a check and holds no replay task, and the pull request states the `paths` counts and the score of the same model before and after.
- **Give this plan the replay task that the rule asks for.**: Its group 1 changes `src/devops_cli/roadmap/stage_change.py`, a trigger path, so group 3 holds `uv run devops roadmap eval stage --replay` with the score before and after. The new rule then accepts the plan that adds it.

## Rejected alternatives

- **Add a new `Gate` entry in `GATES` in `src/devops_cli/roadmap/stage_eval_gates.py` and nothing else.**: `stage.py` calls `check_proposal` directly, and `stage_eval_gates.py` calls `run_gates` only from `stage_eval_run.py`. A new gate alone would not refuse a plan in the stage job.
- **Add the check only to the stage job in `src/devops_cli/roadmap/stage.py`.**: The replay runs `check_proposal` through the `paths` gate, so the replay would judge a different rule and the two would drift.
- **Trigger the rule on the prompt and `stage_change.py` only.**: `check_proposal` calls `form_problems`, `path_problems` and `criterion_problems`, so a change of `stage_form.py`, `stage_paths.py` or `stage_criteria.py` changes a check of the stage job and would escape the rule.
- **Trigger the rule on every path under `src/devops_cli/roadmap/`.**: Most roadmap modules are no stage gate. The workflow rule names `check_proposal` and the gates it calls, so a wider trigger would refuse unrelated plans.
- **Accept any task text that mentions an evaluation.**: Such a task can pass with no replay command and no score, which is the gap the issue reports.
- **Add the rule without a replay case or a score.**: The workflow rule requires a measure of a changed gate, and the golden set holds no case that exercises the new rule. Without a case and a stated score, the change has no evidence that the rule catches a plan and refuses no good one.
