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
- **WHEN** the title of the issue is `fix(roadmap): the job drops a comment`, the commit of the staged branch that adds the change folder has the subject `docs(openspec): plan #1 Keep the last comment of a thread`, and the job finishes the change
- **THEN** the title of the pull request becomes `fix(roadmap): Keep the last comment of a thread`

#### Scenario: An issue that states a goal and a plan that states a smaller change
- **WHEN** the title of issue 3785 is `fix(k8s): find the source of the <gpu-node> host crashes` and its plan commit has the subject `docs(openspec): plan #3785 Remove the profiler exclusion of the <gpu-node> node (#5182)`
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

## ADDED Requirements

### Requirement: Type label follows title
The implement job SHALL set the pull request's `type/*` label from the delivery title and remove any stale `type/*` label.

#### Scenario: A test-only plan on a `type/infra` issue
- **WHEN** the implement job updates a pull request whose current title is `perf(roadmap): cache registry_table in stage eval replay` and the delivery title is `test(roadmap): pin a single registry read`
- **THEN** the pull request has `type/test` and does not have `type/infra`
