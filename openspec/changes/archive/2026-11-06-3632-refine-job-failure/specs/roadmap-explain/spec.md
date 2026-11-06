## ADDED Requirements

### Requirement: Explain names a refine job failure
For a New item whose last refine round recorded the next step `failed`, `explain` SHALL say that the refine job failed, with the failed check names, and that a body edit makes refine try again. For the next step `retry`, `explain` SHALL say that the job failed and that the next round tries again.

#### Scenario: A job failure at the limit
- **WHEN** a New item records `refine.next_step` as `failed` and `refine.failed_check` as `problem_statement`
- **THEN** the refine job is `no` and the reason names `problem_statement` and a body edit

#### Scenario: A retry
- **WHEN** a New item records `refine.next_step` as `retry`
- **THEN** the refine job is `yes`
