## ADDED Requirements

### Requirement: The draft rule gives the duty to mark a draft ready
Rule 6 of `AGENTS.md` and rule 6 of the `AGENTS.md` that `devops ai agents` generates SHALL tell an agent to always mark a draft pull request ready when the checks pass and no agent work remains. `CONTRIBUTING.md` SHALL say what agent work is, and the `devops-pr-ci` skill SHALL give the same condition with `devops pr ready` in each skill root.

#### Scenario: Rule 6 holds the duty
- **WHEN** the invariant test reads rule 6 of `AGENTS.md` and rule 6 of the `AGENTS.md` generated for devops-cli
- **THEN** each holds "Always mark it ready" and "no agent work remains"

#### Scenario: The routed documents give the condition
- **WHEN** the invariant test reads `CONTRIBUTING.md` and `devops-pr-ci/SKILL.md` in `.agents/skills`, `.claude/skills` and `.kilocode/skills`
- **THEN** `CONTRIBUTING.md` says what agent work is, and each skill copy holds "Always run `uv run devops pr ready <number>`" with "no agent work remains"
