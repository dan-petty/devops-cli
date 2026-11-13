## MODIFIED Requirements

### Requirement: The pull request that delivers the code has the type of the issue
The job SHALL set the title of the pull request of a Staged or a Planned item to the type and the scope of the issue title and the summary of the plan. Before it writes the title, the job SHALL check it with the form of the pull request and SHALL stop the item when the form refuses it. The job SHALL leave out the scope when `.github/labels.yml` on the default branch declares no label `scope/<scope>`. The job SHALL set the title in the same call that sets the body `Closes #<issue>`.

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

### Requirement: The summary of the delivery title comes from the plan
The summary of the plan SHALL be the text after `docs(openspec): plan #<issue>` and one space in the subject of the newest commit of the branch that adds `proposal.md` to a folder `openspec/changes/<issue>-<slug>/`, without the end `(#<pull>)` that a squash merge adds. The job SHALL use the whole summary of the title of the issue when that subject holds no such text, or when the form of the pull request refuses the title with the summary of the plan.

#### Scenario: A Planned item
- **WHEN** the commit on `main` that adds the change folder of item 1 has the subject `docs(openspec): plan #1 Keep the last comment of a thread (#4)`
- **THEN** the job opens the draft with the title `fix(roadmap): Keep the last comment of a thread`, and writes the same title when it finishes the change

#### Scenario: No plan title
- **WHEN** the commit that adds the change folder has the subject `fix(roadmap): plan` and the title of the issue is `fix(roadmap): the job drops a comment`
- **THEN** the title of the pull request is `fix(roadmap): the job drops a comment`, the title of the issue

#### Scenario: A plan summary that the form refuses
- **WHEN** the summary of the plan has 64 characters, and the title of the issue is `fix(roadmap): the job drops a comment`
- **THEN** the title of the pull request is `fix(roadmap): the job drops a comment`, and the job does not stop the item
