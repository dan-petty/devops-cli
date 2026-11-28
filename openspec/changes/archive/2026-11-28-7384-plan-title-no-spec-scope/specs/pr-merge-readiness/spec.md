## MODIFIED Requirements

### Requirement: Stage plan title wins a collision
When `implement.pr` and `stage.pr` hold the same pull request number, `kind_of` SHALL return `DraftKind.STAGE_PLAN` if `is_plan_title_prefix(title, has_spec_scope=has_spec_scope)` holds (`docs(spec): plan` for scoped repositories, `docs: plan` when `has_spec_scope=False`, or legacy `docs(openspec): plan`).

#### Scenario: Colliding plan title
- **WHEN** `kind_of` receives an item whose `implement.pr` and `stage.pr` equal the pull request and a title that starts with `docs(spec): plan` or legacy `docs(openspec): plan`
- **THEN** it returns `DraftKind.STAGE_PLAN`.

#### Scenario: Colliding plan title without spec scope
- **WHEN** `kind_of` receives an item whose `implement.pr` and `stage.pr` equal the pull request, the title `docs: plan #166 add the plan`, and `has_spec_scope=False`
- **THEN** it returns `DraftKind.STAGE_PLAN`.

### Requirement: Implement title keeps a collision as implement
When `implement.pr` and `stage.pr` hold the same pull request number, `kind_of` SHALL return `DraftKind.IMPLEMENT` if the title does not satisfy `is_plan_title_prefix(title, has_spec_scope=has_spec_scope)`.

#### Scenario: Colliding implement title
- **WHEN** `kind_of` receives an item whose `implement.pr` and `stage.pr` equal the pull request and a title that starts with `fix(roadmap): keep the last comment`
- **THEN** it returns `DraftKind.IMPLEMENT`.

#### Scenario: Colliding with no title
- **WHEN** `kind_of` receives an item whose `implement.pr` and `stage.pr` equal the pull request and no title is given
- **THEN** it returns `DraftKind.IMPLEMENT`.

#### Scenario: Unscoped title in a scoped repository
- **WHEN** `kind_of` receives `docs: plan #166 add the plan` with `has_spec_scope=True`
- **THEN** it returns `DraftKind.IMPLEMENT`.

### Requirement: Read draft preserves stage plan classification
`read_draft` SHALL determine `has_spec_scope` from `.github/labels.yml` on the base ref and pass it to `kind_of`, classifying matching colliding pull requests (including `docs: plan` when `scope/spec` is absent) as `DraftKind.STAGE_PLAN`.

#### Scenario: Read draft for a colliding plan
- **WHEN** `read_draft` runs for a pull request whose title starts with `docs(spec): plan` and whose number both records hold
- **THEN** the returned `Draft.kind` is `DraftKind.STAGE_PLAN`.

#### Scenario: Read draft for a colliding plan without spec scope
- **WHEN** `read_draft` runs for a pull request titled `docs: plan #166 add the plan` in a store whose `.github/labels.yml` omits `scope/spec`
- **THEN** the returned `Draft.kind` is `DraftKind.STAGE_PLAN`.
