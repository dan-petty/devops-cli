## Purpose
What the knowledge base manuals of devops-cli state about the libraries they describe: the repository that each manual names as the public source, and the path of the code inside it.

## ADDED Requirements

### Requirement: The harness manual names the maintained repository
The manual `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md` SHALL list `https://github.com/pydantic/pydantic-ai` in its front matter `sources` and SHALL name src/pydantic_ai_harness as the path of the code in its 'Public Git Repository' row.

#### Scenario: The front matter lists the maintained repository
- **WHEN** A test reads the front matter `sources` of the harness manual.
- **THEN** The list holds `https://github.com/pydantic/pydantic-ai` and holds no URL of the archived harness repository.

#### Scenario: The repository row names the maintained repository and path
- **WHEN** A test reads the 'Public Git Repository' row of the harness manual.
- **THEN** The row links to `https://github.com/pydantic/pydantic-ai` and its text holds src/pydantic_ai_harness.

### Requirement: No manual names the archived harness repository
The manuals under `src/devops_cli/ai/knowledge_base/devops_cli/libraries/` SHALL hold no reference to `pydantic/pydantic-ai-harness`.

#### Scenario: No manual holds the archived repository URL
- **WHEN** A test reads every manual under `src/devops_cli/ai/knowledge_base/devops_cli/libraries/`.
- **THEN** No manual holds the text `pydantic/pydantic-ai-harness`.
