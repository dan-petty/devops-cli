## ADDED Requirements

### Requirement: The tuicr bullet needs a source change
The task renderer SHALL add the tuicr review bullet only when at least one task group changes a path under `src/`.

#### Scenario: A plan that changes no source omits the bullet
- **WHEN** a plan has groups that change no path under `src/`
- **THEN** the rendered `tasks.md` holds no bullet that starts with `Pending a person: review the diff in tuicr`.

#### Scenario: A plan that changes source gets the bullet
- **WHEN** a plan has one group that changes `src/devops_cli/roadmap/stage_change.py`
- **THEN** the rendered `tasks.md` holds the tuicr review bullet.

### Requirement: An empty workflow follow-up section is omitted
The task renderer SHALL write the `## Workflow follow-up` heading only when it holds a bullet.

#### Scenario: No follow-up bullet leaves no section
- **WHEN** a plan has no workflow follow-up bullet
- **THEN** the rendered `tasks.md` holds no `## Workflow follow-up` heading.

### Requirement: A document task starts with the Edit verb
The task renderer MUST prepend the fixed verb `Edit` to a documentation text whose first word is a path, and MUST write that path in a code span. A path is a word that holds `/` or ends in a dot and letters.

#### Scenario: A root document gets the Edit verb
- **WHEN** a group supplies the documentation text `SECURITY.md`
- **THEN** the rendered task starts with `Edit` and names `SECURITY.md` in a code span.

#### Scenario: A nested document in a code span gets the Edit verb
- **WHEN** a group supplies the documentation text `` `docs/TESTING.md` and `docs/SDLC.md` ``
- **THEN** the rendered task reads `Edit` followed by the two paths in code spans.

### Requirement: A document task keeps its own verb
The task renderer MUST keep a documentation text whose first word is not a path unchanged.

#### Scenario: An existing verb has no double verb
- **WHEN** a group supplies the documentation text `Document the fix in `docs/TESTING.md``
- **THEN** the rendered task starts with `Document` and holds no `Edit Document`.

### Requirement: The documentation field starts with an imperative verb
The stage prompt SHALL state that the `documentation` field starts with an imperative verb, names each document in a code span, and is `null` when the step changes no document.

#### Scenario: The prompt states the documentation rule
- **WHEN** a test reads the stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the prompt states the imperative verb rule, the rule that names each document, and the `null` rule for a step that changes no document.

## MODIFIED Requirements

### Requirement: A task group renders the tasks of its kind
A `behavior` group SHALL render `n.1` as its failing test, `n.2` as its implementation, and `n.3` as its documentation when `documentation` is set. An `other` group SHALL render `n.1` as its implementation with its `verify` or its `process`, and `n.2` as its documentation when `documentation` is set. A task with a command SHALL write it on a line `- Verification: ` under the task, as a code span that `step_files` reads. A group with no `documentation` SHALL render no documentation task. A documentation task SHALL end with the command `uv run devops docs generate --sync-readme` only when the group changes a path under `src/devops_cli/commands/` or `src/devops_cli/lang/`.

#### Scenario: A deletion that keeps behavior
- **WHEN** an `other` group deletes a definition and its `verify` is a `git grep` that must print nothing
- **THEN** its first task names the deletion, the line under it holds the `git grep` and says "passes", and no task asks for a test or says "fails on the base"

#### Scenario: A manual check
- **WHEN** an `other` group has a `process`
- **THEN** its first task holds the steps of the process, and it has no `Verification:` line

#### Scenario: A behavior group
- **WHEN** a `behavior` group has a `test`
- **THEN** its first task is the test, and the line under it holds the `verify` command and says "fails on the base"

#### Scenario: The step reads the command
- **WHEN** the text that `group_text` writes for a group with a `verify` is parsed with `parse_task_groups`
- **THEN** `verification_commands` of the parsed group holds the `verify` of the group

#### Scenario: A group with documentation
- **WHEN** a group has a `documentation` task and changes `src/devops_cli/commands/pr.py`
- **THEN** its last task holds the command that regenerates the documents, and its `Verification:` line holds `uv run devops ci docs`

#### Scenario: A group that changes a document only
- **WHEN** a group has a `documentation` task and changes only `SECURITY.md`
- **THEN** its last task holds the documentation text with no regeneration command, and its `Verification:` line holds `uv run devops ci docs`
