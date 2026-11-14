## ADDED Requirements

### Requirement: A stage change states its eval evidence
A pull request that changes `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage_criteria.py`, `src/devops_cli/roadmap/stage_eval_gates.py` or `src/devops_cli/roadmap/stage_move.py` SHALL state the stage eval evidence in its body, and the readiness verdict SHALL block the merge when it does not.

#### Scenario: A stage change with no evidence is not ready
- **WHEN** a pull request changes `src/devops_cli/roadmap/stage_change.py` and its body holds no stage eval evidence
- **THEN** the verdict holds one blocker of the kind `stage_eval` that names the path and the command

#### Scenario: A replay with two numbers is ready
- **WHEN** a pull request changes `src/devops_cli/roadmap/stage_eval_gates.py` and its body holds `uv run devops roadmap eval stage --replay` with a number before and after
- **THEN** the verdict holds no blocker

#### Scenario: A live run with one model and two scores is ready
- **WHEN** a pull request changes `src/devops_cli/roadmap/stage_move.py` and its body holds `uv run devops roadmap eval stage --model <name>` and a score before and after
- **THEN** the verdict holds no blocker

### Requirement: The evidence holds a number beside each word and one model
The stage eval evidence SHALL hold a number beside `before` and beside `after`, and a live run SHALL name exactly one model in a `--model` flag. A body with no number, one number, two different models, or a `--model` flag with no name SHALL be refused.

#### Scenario: One number is refused
- **WHEN** the body holds the replay command and a number after `before` but none after `after`
- **THEN** `stage_eval_problems` names the missing number

#### Scenario: Two models are refused
- **WHEN** the body holds two live commands with two different `--model` names
- **THEN** `stage_eval_problems` names more than one model

#### Scenario: A model flag with no name is refused
- **WHEN** the body holds `--model` with no name
- **THEN** `stage_eval_problems` names the flag
