## ADDED Requirements

### Requirement: A criterion of a manifest, a workflow or a config file names a command proof
The refine reply prompt `src/devops_cli/ai/tasks/roadmap_refine_reply.md` SHALL tell the model that an acceptance criterion of a manifest, a workflow or a config file names a validator command or a live check as its proof, with the phrase of the stage prompt, and never asks for a test that reads the file.

#### Scenario: The refine and stage prompts keep the phrase
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_refine_reply.md` and `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** both hold "names a validator command or a live check as its proof"
