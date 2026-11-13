## MODIFIED Requirements

### Requirement: The agent instructions separate the two model kinds

The `ask-jev` skill SHALL state that a decision model answers a closed choice on short evidence and that a generative model writes text or uses tools. Rule 7 of `AGENTS.md` SHALL allow a `devops ai` call only when no file or deterministic check can answer, and SHALL link the `ask-jev` skill.

#### Scenario: An agent reads the rule
- **WHEN** an agent that wants to call a model reads rule 7 of `AGENTS.md`
- **THEN** the rule allows one `devops ai` call at a time, only when no file or deterministic check can answer
- **AND** the rule links the `ask-jev` skill, which names the decision model, the generative model and the evidence rule

## ADDED Requirements

### Requirement: AGENTS.md holds only the rules that every task needs

`AGENTS.md` SHALL hold the rules that every task needs, the safety rules and the "Where to look" table. A rule for some tasks only SHALL live in the document that owns that task, and the table SHALL route to that document. `CONST_AGENTS_MD_MAX_CHARS` SHALL be at most 4,500, and `AGENTS.md` and the file that `devops ai agents` writes SHALL fit it.

#### Scenario: AGENTS.md grows past its cap
- **WHEN** a change makes `AGENTS.md` longer than `CONST_AGENTS_MD_MAX_CHARS`, or sets the constant above 4,500
- **THEN** the character budget test of `tests/invariants/test_agents_md.py` fails

#### Scenario: The premise check finds a replaced item
- **WHEN** an agent finds that newer issues or code replace the item that it works on
- **THEN** rule 2 of `AGENTS.md` tells it to close the item as not planned

### Requirement: AGENTS.md keeps the safety rules inline

`AGENTS.md` SHALL keep each safety rule inline: never commit or push to `main`, never `--no-verify`, never lower a security or quality threshold, never run bare `gh`, only a person merges and changes secrets, settings and hardware, and the whole private-data rule with its placeholders.

#### Scenario: A safety rule leaves AGENTS.md
- **WHEN** a change removes a safety rule from `AGENTS.md`, such as the private registry or the device path of the private-data rule
- **THEN** the safety rule test of `tests/invariants/test_agents_md.py` fails
