## ADDED Requirements

### Requirement: The inbox lists each item whose refine job failed at the try limit
`devops roadmap inbox` SHALL list one line for each open New item whose `refine.next_step` is `failed`. The line SHALL show the number, the age, the failed check names, the count of tries and the last error, and SHALL show no question. The inbox SHALL list no line for an item whose `refine.next_step` is `retry`.

#### Scenario: A job failure at the limit
- **WHEN** an open New item records `refine.next_step` as `failed`, `refine.failed_check` as `problem_statement`, `refine.tries` as `3` and a `refine.failure`
- **THEN** the output lists one line in the section "New items whose refine job failed", with the check, the count `3` and the error, and the line asks no question

#### Scenario: A retry
- **WHEN** an open New item records `refine.next_step` as `retry`
- **THEN** the output lists no line for it
