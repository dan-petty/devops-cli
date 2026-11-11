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
