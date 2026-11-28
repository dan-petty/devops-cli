## MODIFIED Requirements

### Requirement: A title holds the full summary
`stage_plan_title` (called by `staging_title`) and `delivery_title` SHALL use the full summary with no `...`, selecting the `docs(spec): plan` or `docs: plan` prefix via `plan_title_prefix(has_spec_scope)`.

#### Scenario: Long delivery summary
- **WHEN** `delivery_title` receives `feat(roadmap): a summary that is longer than the bound of the title`.
- **THEN** The returned title ends with the full summary and holds no added `...`.

#### Scenario: Staging title holds the summary
- **WHEN** `staging_title` receives item 3200 and the summary `Refuse placeholder text`.
- **THEN** The returned title is `docs(spec): plan #3200 Refuse placeholder text`.

#### Scenario: Stage title in a repository without spec scope
- **WHEN** `stage_plan_title` receives issue 166, summary `add the plan`, and `has_spec_scope=False`.
- **THEN** The returned title is `docs: plan #166 add the plan`.
