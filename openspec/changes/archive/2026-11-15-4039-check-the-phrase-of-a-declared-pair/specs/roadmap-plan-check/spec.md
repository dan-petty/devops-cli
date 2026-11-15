## ADDED Requirements

### Requirement: Plan-check reports a divergent declared phrase
`folder_problems` SHALL read each `("<document>", "<phrase>")` pair of `tasks.md` as a declared phrase, and SHALL report one problem for each code span of `proposal.md`, `tasks.md` or a `specs/*/spec.md` file that shares at least four consecutive words with a declared phrase and is not equal to it. The problem SHALL name the span, the declared phrase and the file. A plan that declares no pair SHALL report no phrase problem.

#### Scenario: A declared pair with no variant
- **WHEN** `tasks.md` declares a pair and no artifact quotes a variant of it
- **THEN** `phrase_problems` returns an empty list

#### Scenario: The variant of pull request #3963
- **WHEN** `proposal.md` holds `from references or from a probe line` and `tasks.md` declares `from a tool of the plan run or from a probe line`
- **THEN** `phrase_problems` returns one problem that names both spans and the proposal file

#### Scenario: A variant in a spec delta
- **WHEN** a scenario of a `specs/*/spec.md` file holds a variant
- **THEN** the problem names that file

#### Scenario: An unrelated span and a plan with no pair
- **WHEN** a code span shares fewer than four consecutive words with every declared phrase, or the folder declares no pair
- **THEN** `phrase_problems` returns an empty list

#### Scenario: The command reports the divergence
- **WHEN** `devops roadmap plan-check` reads a change folder with a divergent variant
- **THEN** its output holds the problem with the declared phrase, the span and the file
