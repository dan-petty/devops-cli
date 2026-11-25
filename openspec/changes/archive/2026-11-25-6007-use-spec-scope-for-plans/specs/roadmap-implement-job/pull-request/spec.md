## MODIFIED Requirements

### Requirement: The pull request that delivers the code has the type of the issue
The job SHALL set the delivery pull request title using the Conventional Commit type selected by the changed paths. The summary SHALL come from the proposal `## Summary` section, `## What Changes`, or the issue summary. Before writing the title, the job SHALL check it with the pull request form and fall back to the issue title when invalid. The job SHALL drop undeclared scopes, and SHALL set the title when setting `Closes #<issue>`.

#### Scenario: A test-only plan
- **WHEN** the staged plan changes only paths under `tests/` and the issue title starts with `perf(roadmap):`
- **THEN** `_delivery_title()` returns a title that starts with `test(roadmap):`

#### Scenario: A proposal with a summary
- **WHEN** the archived proposal has a `## Summary` section whose first line is `pin a single registry read` and the changed paths are test-only
- **THEN** `_delivery_title()` returns `test(roadmap): pin a single registry read`

#### Scenario: A proposal without a summary
- **WHEN** the proposal has no `## Summary` section and its first `## What Changes` bullet is `- Add two regression tests`
- **THEN** `_delivery_title()` returns a title whose summary is `Add two regression tests`

#### Scenario: No usable proposal summary
- **WHEN** the proposal has no `## Summary` and no `## What Changes` section
- **THEN** `_delivery_title()` returns the title that `delivery_title(self.target.item.title, declared)` returns

#### Scenario: A Staged item
- **WHEN** the title of the issue is `fix(roadmap): the job drops a comment`, the commit of the staged branch that adds the change folder has the subject `docs(spec): plan #1 Keep the last comment of a thread`, and the job finishes the change
- **THEN** the title of the pull request becomes `fix(roadmap): Keep the last comment of a thread`

#### Scenario: An issue that states a goal and a plan that states a smaller change
- **WHEN** the title of issue 3785 is `fix(k8s): find the source of the <gpu-node> host crashes` and its plan commit has the subject `docs(spec): plan #3785 Remove the profiler exclusion of the <gpu-node> node (#5182)` (or legacy `docs(openspec): plan #3785 ...`)
- **THEN** the title of the pull request is `fix(k8s): Remove the profiler exclusion of the <gpu-node> node`

#### Scenario: A summary at the limit
- **WHEN** the item has no plan title and the summary of the title of the issue is 60 UTF-16 code units
- **THEN** the form accepts the title, and the job writes it unchanged

#### Scenario: A long summary
- **WHEN** the item has no plan title and the summary of the title of the issue is 61 UTF-16 code units
- **THEN** the job stops the item, and the title of the pull request is not written

#### Scenario: A summary of emoji over the limit
- **WHEN** the item has no plan title and the summary of the title of the issue is 40 emoji of one code point each, which is 80 UTF-16 code units
- **THEN** the job stops the item, and the title of the pull request is not written

#### Scenario: A scope that no label declares
- **WHEN** the title of the issue is `fix(floor): the job drops a comment` and `.github/labels.yml` declares no `scope/floor`
- **THEN** the title of the pull request is `fix: the job drops a comment`

### Requirement: One function decides when a draft pull request is ready
`draft_readiness` SHALL take a draft pull request, its kind (stage plan, implement, agent or person), its recorded item, its check runs and its change folder, and SHALL answer ready, wait or refuse with a reason. A stage plan is complete when its title summary and its body are not placeholders. An implement pull request is complete when every task group is ticked and the change is archived. An agent's or a person's pull request is complete when its author says so.

#### Scenario: An incomplete implement pull request is refused
- **WHEN** the function reads a pull request of kind implement whose change has one unticked task group
- **THEN** it answers refuse and the reason names that group

#### Scenario: A complete plan with passing checks is ready
- **WHEN** the function reads a pull request of kind stage plan whose title summary and body are not placeholders and whose check runs all passed
- **THEN** it answers ready

#### Scenario: A stage plan with a placeholder title summary is refused
- **WHEN** the function reads a pull request of kind stage plan whose title is `docs(spec): plan #3321 x` and whose body is not a placeholder
- **THEN** it answers refuse and the reason names a placeholder summary

#### Scenario: A stage plan with a placeholder body is refused
- **WHEN** the function reads a pull request of kind stage plan whose title summary is not a placeholder and whose body is `x`
- **THEN** it answers refuse and the reason names a placeholder body

#### Scenario: An author's pull request waits for the author
- **WHEN** the function reads a pull request of kind person or agent whose author has not said that it is complete
- **THEN** it answers wait

#### Scenario: Checks decide after completeness
- **WHEN** the function reads a complete pull request with one failed check, and another with one running check
- **THEN** it answers refuse for the first and wait for the second

#### Scenario: An extra check can refuse
- **WHEN** a test gives the function an extra check that refuses
- **THEN** it answers refuse with the reason of that check, even for a complete pull request with passing checks

### Requirement: The pull request gets the labels of the new title
For each pull request, after the job sets the title and the body, it SHALL add the `type/*` and `scope/*` labels that the new title gives, as `.github/labels.yml` on the default branch declares them. It SHALL remove each such label that the pull request holds, that the old title gave and that the new title does not give. A label of a person SHALL stay. A label that fails SHALL be named in a comment on the pull request and SHALL NOT stop the item. Rejected credentials SHALL stop it.

#### Scenario: A Staged item changes type and scope
- **WHEN** the pull request holds `type/docs` and `scope/spec` for the title `docs(spec): plan #1 keep every comment` and the job sets `fix(roadmap): the job drops a comment`
- **THEN** the pull request holds `type/bug` and `scope/roadmap` and holds neither `type/docs` nor `scope/spec`

#### Scenario: The labels of the old title are not held
- **WHEN** the pull request holds no label and the job sets a new title
- **THEN** the pull request holds the labels of the new title, and the job sent no request that removes a label

#### Scenario: A label of a person stays
- **WHEN** a person added `scope/ai` to the pull request and neither title gives it
- **THEN** the pull request still holds `scope/ai`

#### Scenario: A Planned item
- **WHEN** the job opens the draft of a Planned item with the title `fix(roadmap): the job drops a comment`
- **THEN** the pull request holds `type/bug` and `scope/roadmap`, and the job sent no request that removes a label

#### Scenario: A label is refused
- **WHEN** GitHub refuses `type/bug` for the pull request
- **THEN** a comment on the pull request names `type/bug` and the reason, and the run ends at the draft as it does without the failure

#### Scenario: A dry run
- **WHEN** `devops roadmap implement --dry-run` runs
- **THEN** the plan lists the read of the pull request, the read of `.github/labels.yml`, the request that adds a label and the request that removes one, and the run makes no request

### Requirement: The archive commit keeps its docs type
The implement job SHALL keep the title of the archive commit in the form `docs(spec): archive the change (#N)`, whatever the type and scope of the item.

#### Scenario: Archive commit of a docs item
- **WHEN** The implement job archives the change for issue 2670.
- **THEN** The archive commit title is `docs(spec): archive the change (#2670)`.
