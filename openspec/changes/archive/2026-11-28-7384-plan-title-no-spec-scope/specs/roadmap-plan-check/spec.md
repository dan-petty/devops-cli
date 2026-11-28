## MODIFIED Requirements

### Requirement: Plan-check checks the title of the pull request
The command SHALL check the pull request title with `plan_check_title_problem` against `plan_title_prefix(has_spec_scope)` using `scope/spec` in `.github/labels.yml` of `--repo`, reporting a problem unless it matches `{prefix} #<issue> <summary>` or when the summary after the colon exceeds `SUMMARY_MAX_CHARS`.

#### Scenario: A wrong title is reported
- **WHEN** the pull request title is `feat(roadmap): add plan-check`
- **THEN** the output names the title rule and the exit code is 1.

#### Scenario: A title in the staging form passes
- **WHEN** the pull request title is the title that `staging_title` builds for the issue
- **THEN** the command reports no title problem.

#### Scenario: No-scope plan title passes when scope/spec is absent
- **WHEN** `plan_check_title_problem` or `plan_check` checks `docs: plan #166 add the plan` for a repository whose `.github/labels.yml` lacks `scope/spec` (`has_spec_scope=False`)
- **THEN** `plan_check_title_problem` returns `None` and `plan_check` reports no title problem
