# agent-instructions Specification

## Purpose
The agent instructions tell an agent when to use a decision model and when to use a generative model. The example service configurations state that the two model kinds are separate.

## Requirements

### Requirement: The agent instructions separate the two model kinds

`AGENTS.md` SHALL state that a decision model answers a closed choice on short evidence and that a generative model writes text or uses tools. It SHALL link the `ask-jev` skill.

#### Scenario: An agent reads the rule
- **WHEN** an agent reads rule 13 of `AGENTS.md`
- **THEN** the rule names the decision model, the generative model, the link to the skill and the evidence rule

### Requirement: The skill gives the use of each model kind

The `ask-jev` skill SHALL give the tasks that fit a decision model, the tasks that need a generative model and the separate settings of the two kinds. It SHALL say how a workflow names another decision model.

#### Scenario: An agent chooses the model kind
- **WHEN** an agent reads the skill before a model call
- **THEN** the skill names a closed question as a decision-model task and text, tools, the repository or a long document as a generative-model task

### Requirement: The example configurations separate the settings

The example configurations SHALL state that `ai.model` and `ai.tasks.*.model` name generative models and that a workflow names a decision model separately. They SHALL NOT add a setting key that the release does not read.

#### Scenario: An operator reads the example
- **WHEN** an operator reads the AI section of `config.example.yaml` or the Service ConfigMap
- **THEN** the comments state the two model kinds and the separate decision-model setting

### Requirement: The skill copies agree

The skill copies under `.claude/skills`, `.agents/skills` and `.kilocode/skills` SHALL hold the same text.

#### Scenario: A copy differs
- **WHEN** one copy changes and another does not
- **THEN** the skill identity test fails

### Requirement: The agent instructions ask for small tool output

`AGENTS.md` SHALL hold a rule that asks an agent to search before it reads, to read only the lines that it needs, and to ask each command for less output. The rule SHALL name `git diff --stat`, `--jq`, `--limit` and a Loki `limit`, and it SHALL tell the agent to keep error lines, `file:line` and failed test IDs. `AGENTS.md` SHALL stay within `CONST_AGENTS_MD_MAX_CHARS`.

#### Scenario: An agent reads the rule for tool output
- **WHEN** an agent reads the rule "Keep tool output small" of `AGENTS.md`
- **THEN** the rule names the search before a read, the example commands and the facts that a short output keeps
- **AND** `AGENTS.md` has no more characters than `CONST_AGENTS_MD_MAX_CHARS`

### Requirement: A pointer stub says how its tool gets AGENTS.md

A pointer stub that `devops ai agents` writes with an import line SHALL say that the line loads `AGENTS.md` into the context of the tool and that the tool does not read it again. A pointer stub without an import line SHALL tell its tool to read `AGENTS.md`.

#### Scenario: A stub with an import line
- **WHEN** `devops ai agents` writes `CLAUDE.md` or `GEMINI.md`
- **THEN** the stub holds its import line and says that this line loads `AGENTS.md` into the context, so the tool does not read it again
- **AND** the stub does not say "Read that file."

#### Scenario: A stub without an import line
- **WHEN** `devops ai agents` writes `.github/copilot-instructions.md`
- **THEN** the stub says "Read that file." and does not say that the tool must not read `AGENTS.md`

### Requirement: A generated AGENTS.md names only the detected toolchain and checks

`devops ai agents` SHALL name a toolchain only for a manifest of the project (`pyproject.toml`, `Cargo.toml`, `package.json` or `go.mod`), and a check to run before a push only for a pre-push hook of the project. It SHALL name a local hook with `args` by its `id`, because its `entry` alone is not its command. It SHALL render the `fail-to-pass` sentence only for a Python project, and the OpenSpec sentence only when `openspec/config.yaml` exists.

#### Scenario: A folder holds only Cargo.toml
- **WHEN** `devops ai agents` writes the `AGENTS.md` of a folder that holds only `Cargo.toml`
- **THEN** the file names Rust
- **AND** it holds no "Python", "uv", "pytest", "ruff" or "mypy"

#### Scenario: A folder has no manifest and no hooks
- **WHEN** `devops ai agents` writes the `AGENTS.md` of a folder with no manifest and no pre-push hook
- **THEN** the file has no toolchain line and no check line

#### Scenario: devops-cli keeps its check line
- **WHEN** `devops ai agents` renders the template for devops-cli
- **THEN** the check line names the three pre-push hooks of `.pre-commit-config.yaml`, `branch-current` by its `id`

#### Scenario: The OpenSpec sentence needs the config file
- **WHEN** a project has no `openspec/config.yaml`
- **THEN** the generated `AGENTS.md` does not name OpenSpec

### Requirement: The model path has its own system prompt

The model path of `devops ai agents` SHALL send the `AGENTS.md` task as its system prompt, with the detected toolchains, pre-push checks and documents. It SHALL NOT send a review persona. The project context SHALL hold each detected manifest.

#### Scenario: The model writes the file of a Rust project
- **WHEN** `devops ai agents` calls the model for a folder with `Cargo.toml` and a pre-push hook
- **THEN** the system prompt names the hook command and holds no review persona
- **AND** the user message holds the `Cargo.toml` text

### Requirement: The template keeps the rule titles of AGENTS.md

A test SHALL compare the rule titles of the template, rendered for devops-cli, with the rule titles of `AGENTS.md`, less a named list of the rules that only devops-cli has. A rule title that only `AGENTS.md` adds SHALL fail the test.

#### Scenario: A rule is added only to AGENTS.md
- **WHEN** `AGENTS.md` gets a rule title that the template and the named list do not hold
- **THEN** the rule-title test reports that title

### Requirement: The style rules ask for the bottom line in the first line

`src/devops_cli/ai/tasks/style_ste100.md` SHALL ask for the bottom line in the first line of a reply, with each gate that still applies. A gate is any hold, blocker, review, person step, merge order or deployment step. The request that `with_style_request` adds to the system prompt of a model call SHALL hold this rule.

#### Scenario: A model call carries the first-line rule
- **WHEN** `with_style_request` builds the system prompt of a model call
- **THEN** the prompt asks for what to do or not do, the real state and each gate in the first line
- **AND** the prompt tells the model not to start with "done", "green" or "ready" while a gate applies
- **AND** the prompt asks a reply with many items to say in the first line which item to act on now and which item to hold
