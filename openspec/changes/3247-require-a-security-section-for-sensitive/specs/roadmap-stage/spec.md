## ADDED Requirements

### Requirement: A security trigger needs a security section
The proposal check SHALL refuse a plan that names a security trigger and holds no non-blank `security` text, and SHALL name the matched path or word in the refusal.

#### Scenario: A plan changes SECURITY.md with no security text
- **WHEN** `check_proposal` receives a proposal whose group changes `SECURITY.md` and whose `security` field is empty
- **THEN** it returns a problem that names `SECURITY.md` and asks for a non-blank `## Security` section

#### Scenario: A task names a trigger word with no security text
- **WHEN** `check_proposal` receives a proposal whose task text names `credential` and whose `security` field is empty
- **THEN** it returns a problem that names `credential`

#### Scenario: A plan with security text passes
- **WHEN** the same proposal holds non-blank `security` text
- **THEN** it returns no security problem

#### Scenario: A plan with no trigger needs no security text
- **WHEN** `check_proposal` receives a proposal whose Changes, group paths and task texts name no trigger
- **THEN** it returns no security problem

### Requirement: The security triggers are a fixed list of paths and words
The trigger paths MUST be the named constant `SECURITY_TRIGGER_PATHS` with a docstring, and every entry MUST be a path of the repository.

#### Scenario: The trigger paths exist
- **WHEN** a test resolves each entry of `SECURITY_TRIGGER_PATHS` from the repository root
- **THEN** every entry is a file or a directory of the commit

#### Scenario: A trigger path is missing
- **WHEN** an entry of `SECURITY_TRIGGER_PATHS` names no file and no directory
- **THEN** the test fails

### Requirement: The design file holds the security section
`render_change` SHALL write a non-blank `security` field as a `## Security` section of `design.md`, and SHALL write no such section when the field is blank.

#### Scenario: A plan with security text is rendered
- **WHEN** `render_change` renders a proposal whose `security` field holds non-blank text
- **THEN** `design.md` holds a `## Security` section with that text

#### Scenario: A plan with no security text is rendered
- **WHEN** `render_change` renders a proposal whose `security` field is empty
- **THEN** `design.md` holds no `## Security` section

### Requirement: The stage prompt names the security rule
The stage prompt MUST name the `security` key, the `## Security` section and the security trigger.

#### Scenario: The prompt and the reply agree
- **WHEN** a test reads `roadmap_stage_change.md` and the fields of `StageProposal`
- **THEN** the prompt names `security` and the trigger, and the keys of the reply are the fields of the proposal
