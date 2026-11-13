## MODIFIED Requirements

### Requirement: The agent instructions separate the two model kinds

The `ask-jev` skill SHALL state that a decision model answers a closed choice on short evidence and that a generative model writes text or uses tools. It SHALL tell an agent to ask a model only when no file or deterministic check can answer. The "Where to look" table of `AGENTS.md` SHALL route a closed question for a model to the `ask-jev` skill.

#### Scenario: An agent reads the rule
- **WHEN** an agent with a closed question for a model reads the row "ask a model a closed question" of `AGENTS.md`
- **THEN** the row links the `ask-jev` skill
- **AND** the skill names the decision model, the generative model and the evidence rule, and it tells the agent to ask only when no file or deterministic check can answer

## ADDED Requirements

### Requirement: AGENTS.md holds only the rules that every task needs

`AGENTS.md` SHALL hold the rules that every task needs, the safety rules and the "Where to look" table. A rule for some tasks only SHALL live in the document that owns that task, and the table SHALL route to that document. `CONST_AGENTS_MD_MAX_CHARS` SHALL be at most 4,500, and `AGENTS.md` and the file that `devops ai agents` writes SHALL fit it.

#### Scenario: AGENTS.md grows past its cap
- **WHEN** a change makes `AGENTS.md` longer than `CONST_AGENTS_MD_MAX_CHARS`, or sets the constant above 4,500
- **THEN** the character budget test of `tests/invariants/test_agents_md.py` fails
