## MODIFIED Requirements

### Requirement: Plan-check checks the title of the pull request
The command SHALL report a problem when the pull request title is not of the form `docs(spec): plan #<issue> <summary>`, or when the text after the colon is longer than `SUMMARY_MAX_CHARS`.

#### Scenario: A wrong title is reported
- **WHEN** the pull request title is `feat(roadmap): add plan-check`
- **THEN** the output names the title rule and the exit code is 1.

#### Scenario: A title in the staging form passes
- **WHEN** the pull request title is the title that `staging_title` builds for the issue
- **THEN** the command reports no title problem.
