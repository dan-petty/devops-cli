## MODIFIED Requirements

### Requirement: AGENTS.md keeps the safety rules inline

`AGENTS.md` SHALL keep each safety rule inline: never commit or push to `main`, never `--no-verify`, never lower a security or quality threshold, never run bare `gh`, only a person merges and changes secrets, settings and hardware, and the whole private-data rule with its placeholders.

#### Scenario: A safety rule leaves AGENTS.md
- **WHEN** `git grep -n -e "Never commit or push to" -e "Never use" -e "Never lower a security or quality threshold" -e "Never run bare" -e "Only a person" -e "Never commit a secret" -- AGENTS.md` runs
- **THEN** the output holds each of the six texts

### Requirement: The draft rule gives the duty to mark a draft ready
Rule 6 of `AGENTS.md` and rule 6 of the `AGENTS.md` that `devops ai agents` generates SHALL tell an agent to always mark a draft pull request ready when the checks pass and no agent work remains. `CONTRIBUTING.md` SHALL say what agent work is, and the `devops-pr-ci` skill SHALL give the same condition with `devops pr ready` in each skill root.

#### Scenario: Rule 6 holds the duty
- **WHEN** `git grep -n "no agent work remains" -- AGENTS.md src/devops_cli/templates/AGENTS.md.j2` runs
- **THEN** the command prints the line of rule 6 of each file

#### Scenario: The routed documents give the condition
- **WHEN** `git grep -l "no agent work remains" -- CONTRIBUTING.md .agents/skills .claude/skills .kilocode/skills` runs
- **THEN** the command prints `CONTRIBUTING.md` and the `devops-pr-ci/SKILL.md` of each skill root
