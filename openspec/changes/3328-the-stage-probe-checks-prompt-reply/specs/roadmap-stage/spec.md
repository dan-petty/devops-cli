## ADDED Requirements

### Requirement: A plan that adds a StageProposal field names the reply key of the prompt
The stage job SHALL refuse a plan that adds a field to `StageProposal` and does not change `src/devops_cli/ai/tasks/roadmap_stage_change.md` with the reply key of that field.

#### Scenario: Missing reply key
- **WHEN** A plan has a group that changes `src/devops_cli/roadmap/stage_change.py` and names a new field of `StageProposal`, and no group changes `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** The job returns a problem that names `src/devops_cli/ai/tasks/roadmap_stage_change.md` and the missing reply key, and the reply returns to the model once.

#### Scenario: Reply key and rule present
- **WHEN** A plan has a group that adds a field to `StageProposal` and another group that changes `src/devops_cli/ai/tasks/roadmap_stage_change.md` with the new reply key bullet and its rule.
- **THEN** The job returns no problem for the prompt keys.

#### Scenario: A change to the file that adds no field
- **WHEN** A plan changes `src/devops_cli/roadmap/stage_change.py` in a group whose text names no new field of `StageProposal`.
- **THEN** The job returns no problem for the prompt keys.
