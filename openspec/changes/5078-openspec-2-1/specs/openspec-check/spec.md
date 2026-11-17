## ADDED Requirements

### Requirement: Each run takes a scratch home
Each `openspec` run of `devops openspec check` SHALL set `XDG_CONFIG_HOME` and `HOME` to the one scratch directory of the gate, so that OpenSpec reads no profile of the person and writes no file under the home of the person.

#### Scenario: every_run_takes_its_configuration_directory_as_its_home
- **WHEN** the gate runs over a tree with no change and no spec, and `HOME` names the home of the person
- **THEN** every `openspec` run has one `HOME`, which is its `XDG_CONFIG_HOME` and not the home of the person

### Requirement: The skill check reads the layout of OpenSpec 2
The skill check of `devops openspec check` SHALL read the skills in `.agents/skills/openspec-*` and through each link `.claude/skills/openspec-*`, and SHALL require no skill in `.kilocode/skills`.

#### Scenario: a_tree_whose_claude_skills_link_to_the_shared_copy_passes_the_gate
- **WHEN** each `.claude/skills/openspec-*` folder of a tree with no change is a link to its folder in `.agents/skills`, and the tree has no `.kilocode/skills`
- **THEN** the gate reports no problem

## MODIFIED Requirements

### Requirement: The gate reads the version of the command on PATH
`devops openspec check` SHALL run `openspec --version` before its other checks and SHALL report one problem naming the printed version, the locked version, the command path and `uv run devops install-tools --tool openspec --only-missing` when the printed version differs from the tools lock.

#### Scenario: An older command replaces the skill advice
- **WHEN** the `openspec` command on PATH prints `1.14.3`, the tools lock pins another version, and a committed skill differs from a regeneration
- **THEN** the output holds `1.14.3`, the locked version and `uv run devops install-tools --tool openspec --only-missing`, holds no `regenerate`, and the gate ran no `openspec update --force`

#### Scenario: The locked command keeps the skill check
- **WHEN** the `openspec` command on PATH prints the version that the tools lock pins and a committed skill differs from a regeneration
- **THEN** the output holds the skill path and `uv run devops openspec regenerate`
