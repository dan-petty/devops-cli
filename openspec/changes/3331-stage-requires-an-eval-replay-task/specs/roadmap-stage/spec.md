## ADDED Requirements

### Requirement: A plan that changes the stage prompt or a stage gate gives the eval replay task
The stage job SHALL refuse a plan whose groups change `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage_criteria.py` or `src/devops_cli/roadmap/stage_eval_gates.py` unless one group task holds the command `uv run devops roadmap eval stage --replay` and the words `score`, `before` and `after`.

#### Scenario: Prompt change without a replay task
- **WHEN** A plan changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` and no group task holds the replay command with the before and after score.
- **THEN** `check_proposal` returns a problem that names the changed path and the replay command.

#### Scenario: Gate change without a replay task
- **WHEN** A plan changes `src/devops_cli/roadmap/stage_eval_gates.py` and no group task holds the replay command with the before and after score.
- **THEN** `check_proposal` returns a problem that names the changed path and the replay command.

#### Scenario: Check module change without a replay task
- **WHEN** A plan changes `src/devops_cli/roadmap/stage_paths.py` and no group task holds the replay command with the before and after score.
- **THEN** `check_proposal` returns a problem that names the changed path and the replay command.

#### Scenario: Replay command without the score
- **WHEN** A plan changes `src/devops_cli/roadmap/stage_change.py` and one group task holds `uv run devops roadmap eval stage --replay` but not the words `score`, `before` and `after`.
- **THEN** `check_proposal` returns a problem that asks for the before and after score.

#### Scenario: Trigger path with a replay task
- **WHEN** A plan changes `src/devops_cli/roadmap/stage_change.py` and one group task holds `uv run devops roadmap eval stage --replay`, `score`, `before` and `after`.
- **THEN** `check_proposal` returns no problem for the eval replay rule.

#### Scenario: Unrelated source change
- **WHEN** A plan changes only `src/devops_cli/roadmap/stage.py`.
- **THEN** `check_proposal` returns no problem for the eval replay rule.
