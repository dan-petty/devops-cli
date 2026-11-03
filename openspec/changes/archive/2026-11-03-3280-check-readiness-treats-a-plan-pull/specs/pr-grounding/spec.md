## ADDED Requirements

### Requirement: A plan pull request is judged by the rules of a plan
A pull request whose title is `docs(openspec): plan #<issue> <summary>` SHALL be judged by the rules of a plan and not by the rules of a delivery, and the verdict SHALL hold no blocker that asks for a closing issue or an archived folder.

#### Scenario: A valid plan is ready
- **WHEN** the title is `docs(openspec): plan #3183 add plan-check`, the body has the line `Plans #3183`, and the pull request adds `openspec/changes/3183-add-plan-check/proposal.md`
- **THEN** the verdict has no grounding blocker and sends no closing-issues request.

### Requirement: A plan body names its issue with one Plans line
The body of a plan pull request MUST hold exactly one line `Plans #<issue>` that names the issue of its title.

#### Scenario: The Plans line is missing
- **WHEN** a plan pull request for issue 3183 has no `Plans #3183` line
- **THEN** the verdict has one grounding blocker that names the `Plans #` form and none that asks for an archived folder.

### Requirement: A plan body uses no closing keyword
The body of a plan pull request MUST NOT hold a closing keyword before an issue reference.

#### Scenario: The plan body closes its issue
- **WHEN** a plan pull request for issue 3183 has the lines `Plans #3183` and `Closes #3183`
- **THEN** the verdict has one grounding blocker that names the closing keyword.

### Requirement: A plan adds the active change folder of its issue
A plan pull request MUST add at least one file under `openspec/changes/<issue>-<slug>/` for the issue of its title.

#### Scenario: The plan adds no change folder
- **WHEN** a plan pull request for issue 3183 changes only `docs/notes.md`
- **THEN** the verdict has one grounding blocker that names the missing active change folder.

### Requirement: A plan changes no living spec
A plan pull request MUST NOT change a path under `openspec/specs/`.

#### Scenario: The plan changes a living spec
- **WHEN** a plan pull request for issue 3183 adds `openspec/changes/3183-add-plan-check/proposal.md` and changes `openspec/specs/pr-grounding/spec.md`
- **THEN** the verdict has one grounding blocker that names the path.
