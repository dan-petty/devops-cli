## MODIFIED Requirements

### Requirement: A security trigger needs a security section
The proposal check SHALL refuse a plan that names a security trigger and holds no non-blank `security` text, and SHALL name the matched path or word in the refusal. A trigger word SHALL match as a word, with an optional plural ending, and SHALL NOT match inside a longer word.

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

#### Scenario: A trigger word inside a longer word is no trigger
- **WHEN** `check_proposal` receives a proposal whose task text says "Add a regression test" and whose `security` field is empty
- **THEN** it returns no security problem

#### Scenario: A trigger word as a whole word is a trigger
- **WHEN** `check_proposal` receives a proposal whose task text says "Change the egress policy of the pod" and whose `security` field is empty
- **THEN** it returns a problem that names `egress`
