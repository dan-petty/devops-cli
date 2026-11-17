## ADDED Requirements

### Requirement: Jinja2 renders a task prompt with context
`load_task_prompt` SHALL render a task prompt through one cached Jinja2 `SandboxedEnvironment` when the caller passes a context.

#### Scenario: A prompt takes a context value
- **WHEN** A caller passes a value for a prompt that holds `{{ value }}`.
- **THEN** The returned text holds the value in place of the marker.

### Requirement: A missing value raises
The environment MUST raise `jinja2.UndefinedError` when a prompt names a value that the caller's context does not hold.

#### Scenario: A prompt names an unset value
- **WHEN** A caller passes a context that holds another value but not `missing` to a prompt that holds `{{ missing }}`.
- **THEN** `load_task_prompt` raises `jinja2.UndefinedError`.

### Requirement: A prompt read with no context keeps its markers
`load_task_prompt` MUST return the stripped file text without rendering when the caller passes no context.

#### Scenario: The call-budget and GitHub prompts keep their markers
- **WHEN** A test loads `roadmap_stage_tools.md` and `benchmark_embedding_eval_pairs.md` with no context.
- **THEN** The texts hold `{{plan_calls_advised}}` and `${{ github.workflow }}-${{ github.ref }}`, and no `UndefinedError` is raised.

### Requirement: The implement step prompt gets its tables
The implement step prompt SHALL get its three tables through context.

#### Scenario: The implement step prompt gets its tables
- **WHEN** The code builds the implement step prompt for devops-cli.
- **THEN** The text holds the table rows that the caller passes as context.

### Requirement: The implement step prompt matches today's output
The rendered implement step prompt MUST equal the output of the `str.replace` filling of today for devops-cli.

#### Scenario: Compare with today's output
- **WHEN** A test renders the implement step prompt for devops-cli with the new loader.
- **THEN** The text equals the `str.replace` output of the three tables.

### Requirement: fill_prompt is removed
The source MUST NOT hold `fill_prompt` or `PROGRAMS_PLACEHOLDER`.

#### Scenario: Search the source
- **WHEN** A search runs `git grep -n 'fill_prompt\|PROGRAMS_PLACEHOLDER' src`.
- **THEN** The search gives no match.

### Requirement: Prompt version covers the context
`stage_plan_record.prompt_version` SHALL hash the raw template text and the context values.

#### Scenario: Two contexts give two versions
- **WHEN** Two calls hash the same prompt with different context values.
- **THEN** The two prompt versions differ, and a call with no context does not raise.

### Requirement: No new template dependency
The change MUST NOT add a template dependency, and Jinja2 stays at version 3.1.6.

#### Scenario: Read the dependency list
- **WHEN** A test reads the project dependency list.
- **THEN** Jinja2 3.1.6 is present and no template library is added.
