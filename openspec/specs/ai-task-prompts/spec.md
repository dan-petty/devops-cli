# ai-task-prompts Specification

## Purpose
How the package loads a task prompt by name from its `ai/tasks/` folder, and the error that a name which is not a prompt of that folder raises.

## Requirements

### Requirement: A task prompt loads only from the tasks folder of the package
`load_task_prompt` SHALL return the text of the named file of `ai/tasks/` without the white space at its start and end. For a name that is not a file of that folder, also a name that resolves outside it, it SHALL raise `TaskPromptNotFoundError` whose message names the prompt, and SHALL NOT return an empty string.

#### Scenario: A prompt of the folder loads
- **WHEN** a caller loads `style_ste100.md`
- **THEN** it gets the text of the file, with content and without white space at its start and end

#### Scenario: A missing prompt raises
- **WHEN** a caller loads `missing.md`
- **THEN** `TaskPromptNotFoundError` is raised and its message names `missing.md`

#### Scenario: A name outside the folder raises
- **WHEN** a caller loads `../personas/devsecops/role.md`
- **THEN** `TaskPromptNotFoundError` is raised and its message names `role.md`
