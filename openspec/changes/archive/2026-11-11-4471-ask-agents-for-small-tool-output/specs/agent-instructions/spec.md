## ADDED Requirements

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
