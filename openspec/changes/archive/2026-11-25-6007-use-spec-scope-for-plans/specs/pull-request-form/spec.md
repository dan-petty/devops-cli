## MODIFIED Requirements

### Requirement: A plan body has the Plans line and no closing keyword
`devops pr create` SHALL judge the body of a pull request whose title is `docs(spec): plan #<issue> <summary>` or legacy `docs(openspec): plan #<issue> <summary>` by the form of a plan: exactly one line `Plans #<issue>` that names the issue of the title, no closing reference, and a `Change:` line with the active change folder of the same issue. The command SHALL NOT ask a plan body for a `Closes` line.

#### Scenario: A plan body in the form opens a draft
- **WHEN** the title is `docs(spec): plan #3236 revise scope` and the body has the line `Plans #3236` and the line `Change: \`openspec/changes/3236-x/\``
- **THEN** the command opens a draft pull request.

#### Scenario: A plan body that closes its issue opens nothing
- **WHEN** the body of that plan has the lines `Plans #3236` and `Closes #3236`
- **THEN** the command prints that a plan closes no issue and opens nothing.

#### Scenario: A delivery title keeps the Closes rule
- **WHEN** the title is `feat(pr): check the form` and the body has no `Closes` line
- **THEN** the command prints that the body has no `Closes` line and opens nothing.

### Requirement: A title repeats no word and no issue number
When the summary of a title holds a word and an issue number (`<word> #<number>`), the rules SHALL give a problem if the first word after the number is that word, and a problem if the text after the number holds the same number. The word SHALL be the last word before the number. The comparison SHALL ignore case and the marks around the word. A later use of the word SHALL NOT be a problem.

#### Scenario: A repeated leading word
- **WHEN** the title is `docs(spec): plan #2950 plan alternatives coverage telemetry`
- **THEN** the rules find one problem, and its text names the word `plan`

#### Scenario: A repeated issue number
- **WHEN** the title is `docs(spec): plan #2950 Add coverage for #2950`
- **THEN** the rules find one problem, and its text names `#2950`

#### Scenario: A title with a new leading word
- **WHEN** the title is `docs(spec): plan #2950 Add alternatives coverage telemetry`
- **THEN** the rules find no problem

#### Scenario: A later use of the word
- **WHEN** the title is `docs(spec): plan #3200 Refuse placeholder and cut plan text`
- **THEN** the rules find no problem

#### Scenario: A repeat with a colon, a dash or a word before
- **WHEN** the title is `docs(spec): plan #2950: plan x`, `docs(spec): plan #2950 - plan x` or `docs(spec): fix plan #2950 plan x`
- **THEN** the rules find one problem that names the word `plan`

#### Scenario: A number that only starts with the same digits
- **WHEN** the title is `docs(spec): plan #2950 add #29501`
- **THEN** the rules find no problem
