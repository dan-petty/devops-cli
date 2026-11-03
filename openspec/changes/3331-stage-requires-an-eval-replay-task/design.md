# Design

## Decisions

- **Add the rule inside `check_proposal` in `src/devops_cli/roadmap/stage_change.py`, and not as a new gate in `stage_eval_gates.py`.**: The stage job calls `check_proposal` through `stage.py`, and the replay calls it through the `paths` gate in `stage_eval_gates.py`. One function gives the job and the replay the same answer.
- **Trigger the rule on the three changed paths `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/roadmap/stage_change.py` and `src/devops_cli/roadmap/stage_eval_gates.py`.**: The workflow rule names the prompt and the checks that `check_proposal` and the gates it calls hold. These three files are those.
- **Require the exact command `uv run devops roadmap eval stage --replay` and the words `score`, `before` and `after` in one group task.**: The rule needs a replay and a stated score, and one group task keeps the command with its result. The check stays offline and its problem text names what is missing.
- **Read the task text of the group: its title, test, implementation, documentation and verify.**: The rendered `tasks.md` holds these fields, so the model can satisfy the check in the plan it writes.
- **Put the tests in `tests/roadmap/test_roadmap_stage_form.py`.**: That module already tests `check_proposal` rules with a staged tree and needs no model, no git and no network.

## Rejected alternatives

- **Add a new `Gate` entry in `GATES` in `src/devops_cli/roadmap/stage_eval_gates.py` and nothing else.**: `stage.py` calls `check_proposal` directly, and `stage_eval_gates.py` calls `run_gates` only from `stage_eval_run.py`. A new gate alone would not refuse a plan in the stage job.
- **Add the check only to the stage job in `src/devops_cli/roadmap/stage.py`.**: The replay runs `check_proposal` through the `paths` gate, so the replay would judge a different rule and the two would drift.
- **Trigger the rule on every path under `src/devops_cli/roadmap/`.**: Most roadmap modules are no stage gate. The workflow rule names `check_proposal` and the gates it calls, so a wider trigger would refuse unrelated plans.
- **Accept any task text that mentions an evaluation.**: Such a task can pass with no replay command and no score, which is the gap the issue reports.
