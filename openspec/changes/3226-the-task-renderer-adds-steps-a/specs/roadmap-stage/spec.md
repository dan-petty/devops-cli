## ADDED Requirements

### Requirement: The tuicr bullet needs a source change
The task renderer SHALL add the tuicr review bullet only when at least one task group changes a path under src/.

#### Scenario: A plan that changes no source omits the bullet
- **WHEN** A plan has groups that change no path under src/
- **THEN** The rendered tasks text holds no bullet that starts with Pending a person: review the diff in tuicr.

#### Scenario: A plan that changes source gets the bullet
- **WHEN** A plan has one group that changes src/devops_cli/roadmap/stage_change.py
- **THEN** The rendered tasks text holds the tuicr review bullet.

### Requirement: An empty workflow follow-up section is omitted
The task renderer SHALL omit the Workflow follow-up heading when it holds no bullet.

#### Scenario: No follow-up bullet leaves no section
- **WHEN** A plan has no workflow follow-up bullet
- **THEN** The rendered tasks text holds no Workflow follow-up heading.

### Requirement: The docs step needs a command or a message change
The task renderer SHALL add the devops docs generate --sync-readme step to a documentation group only when the group changes a path in the commands package or the lang package of the CLI.

#### Scenario: A document-only group omits the docs step
- **WHEN** A documentation group changes only SECURITY.md
- **THEN** The rendered task holds no devops docs generate --sync-readme step.

#### Scenario: A command change keeps the docs step
- **WHEN** A documentation group changes src/devops_cli/commands/pr.py
- **THEN** The rendered task holds the devops docs generate --sync-readme step.

### Requirement: A document task starts with the Edit verb
The task renderer MUST prepend the fixed verb Edit to a documentation text whose first word is a path.

#### Scenario: A root document gets the Edit verb
- **WHEN** A group supplies the documentation text SECURITY.md
- **THEN** The rendered task starts with Edit and names SECURITY.md.

#### Scenario: A nested document gets the Edit verb
- **WHEN** A group supplies the documentation text docs/ROADMAP_WORKFLOW.md
- **THEN** The rendered task starts with Edit and names docs/ROADMAP_WORKFLOW.md.

### Requirement: A document task keeps its own verb
The task renderer MUST keep a documentation text whose first word is a verb unchanged.

#### Scenario: An existing verb has no double verb
- **WHEN** A group supplies the documentation text Document the fix in docs/TESTING.md
- **THEN** The rendered task starts with Document and holds no Edit Document.

### Requirement: The documentation field starts with an imperative verb
The stage prompt SHALL state that the documentation field starts with an imperative verb, names each document, and is empty when the step changes no document.

#### Scenario: The prompt states the documentation rule
- **WHEN** A test reads src/devops_cli/ai/tasks/roadmap_stage_change.md
- **THEN** The prompt states the imperative verb rule, the rule that names each document, and the rule for a step that changes no document.
