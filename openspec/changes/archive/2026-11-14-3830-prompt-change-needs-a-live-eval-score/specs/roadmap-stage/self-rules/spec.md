## RENAMED Requirements

- FROM: `### Requirement: A plan that changes the stage prompt or a stage gate gives the eval replay task`
- TO: `### Requirement: A plan that changes the stage prompt or a stage gate gives the measure that it can move`

## MODIFIED Requirements

### Requirement: A plan that changes the stage prompt or a stage gate gives the measure that it can move
The stage job SHALL refuse a plan whose groups change `src/devops_cli/ai/tasks/roadmap_stage_change.md` unless one group task holds `uv run devops roadmap eval stage --limit <n>` or `uv run devops roadmap eval stage --case <n>` and the words `score`, `before` and `after`. The stage job SHALL refuse a plan whose groups change `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_form.py`, `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/roadmap/stage/stage_criteria.py` or `src/devops_cli/roadmap/stage/stage_eval_gates.py` unless one group task holds `uv run devops roadmap eval stage --replay` and those words. A plan that changes both the prompt and a gate module SHALL hold both commands.

#### Scenario: Prompt change without a replay task
- **WHEN** A plan changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` and no group task holds the live command with the before and after score.
- **THEN** `check_proposal` returns a problem that names the changed path and the live command.

#### Scenario: Check module change without a replay task
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_paths.py` and no group task holds the replay command with the before and after score.
- **THEN** `check_proposal` returns a problem that names the changed path and the replay command.

#### Scenario: Replay command without the score
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_change.py` and one group task holds `uv run devops roadmap eval stage --replay` but not the words `score`, `before` and `after`.
- **THEN** `check_proposal` returns a problem that asks for the before and after score.

#### Scenario: Trigger path with a replay task
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_change.py` and one group task holds `uv run devops roadmap eval stage --replay`, `score`, `before` and `after`.
- **THEN** `check_proposal` returns no problem for the eval rule.

#### Scenario: Prompt change with the replay only
- **WHEN** A plan changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` and a group task holds `uv run devops roadmap eval stage --replay` with the before and after score.
- **THEN** `check_proposal` returns a problem that names `uv run devops roadmap eval stage --limit`.

#### Scenario: Prompt change with a bounded live run
- **WHEN** A plan changes only `src/devops_cli/ai/tasks/roadmap_stage_change.md` and a group task holds `uv run devops roadmap eval stage --limit 3` with `score`, `before` and `after`.
- **THEN** `check_proposal` returns no problem for the eval rule.

#### Scenario: Prompt change with the live run but no score
- **WHEN** A plan changes only `src/devops_cli/ai/tasks/roadmap_stage_change.md` and a group task holds `uv run devops roadmap eval stage --limit 3` without the three words.
- **THEN** `check_proposal` returns a problem that names the live command and asks for the before and after score.

#### Scenario: Gate change keeps the replay
- **WHEN** A plan changes only `src/devops_cli/roadmap/stage/stage_change.py` and a group task holds `uv run devops roadmap eval stage --replay` with `score`, `before` and `after`.
- **THEN** `check_proposal` returns no problem for the eval rule.

#### Scenario: Gate change without a replay task
- **WHEN** A plan changes `src/devops_cli/roadmap/stage/stage_eval_gates.py` and no group task holds the replay command with the before and after score.
- **THEN** `check_proposal` returns a problem that names the changed path and the replay command.

#### Scenario: Both paths with one command
- **WHEN** A plan changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/roadmap/stage/stage_change.py`, and one group task holds only the replay command with the three words.
- **THEN** `check_proposal` returns a problem that names the live command.

#### Scenario: Unrelated source change
- **WHEN** A plan changes only `src/devops_cli/roadmap/stage/stage.py`.
- **THEN** `check_proposal` returns no problem for the eval rule.

## ADDED Requirements

### Requirement: The stage prompt states both commands
The stage prompt SHALL name the live command for a prompt change and the replay command for a gate change.

#### Scenario: Prompt text
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** the text holds `uv run devops roadmap eval stage --limit` and `uv run devops roadmap eval stage --replay`.

### Requirement: The workflow document states the rule
`docs/ROADMAP_WORKFLOW.md` SHALL state the live command for a prompt change and the replay command for a gate change.

#### Scenario: Workflow document rule
- **WHEN** a test reads `docs/ROADMAP_WORKFLOW.md`.
- **THEN** the text holds `uv run devops roadmap eval stage --limit` and `uv run devops roadmap eval stage --replay`.

### Requirement: The live run takes a case limit
`devops roadmap eval stage` SHALL accept `--limit <n>` and score the first n cases of the set.

#### Scenario: Live run with a limit
- **WHEN** a test calls `select_cases(cases, (), 2)` over a set of more than two cases.
- **THEN** the result holds the first two cases.
