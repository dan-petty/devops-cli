## ADDED Requirements

### Requirement: A title repeats no word and no issue number
When the summary of a title starts with a word and an issue number (`<word> #<number>`), the rules SHALL give a problem if the first word after the number is that word, and a problem if the text after the number holds the same number. The comparison of the word SHALL ignore case. A later use of the word SHALL NOT be a problem.

#### Scenario: A repeated leading word
- **WHEN** the title is `docs(openspec): plan #2950 plan alternatives coverage telemetry`
- **THEN** the rules find one problem, and its text names the word `plan`

#### Scenario: A repeated issue number
- **WHEN** the title is `docs(openspec): plan #2950 Add coverage for #2950`
- **THEN** the rules find one problem, and its text names `#2950`

#### Scenario: A title with a new leading word
- **WHEN** the title is `docs(openspec): plan #2950 Add alternatives coverage telemetry`
- **THEN** the rules find no problem

#### Scenario: A later use of the word
- **WHEN** the title is `docs(openspec): plan #3200 Refuse placeholder and cut plan text`
- **THEN** the rules find no problem
