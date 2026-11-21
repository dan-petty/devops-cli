## MODIFIED Requirements

### Requirement: A staged item gets a branch and one commit
For each item the job SHALL make the branch `<type>/<issue>-<slug>`, where the type is the Conventional Commit type of the title and the slug comes from its summary. The job SHALL write the change folder `openspec/changes/<issue>-<slug>/` on the staged commit, and `publish` SHALL apply its patch to the tip of the default branch as one commit of the identity of the session and push it from a new repository with a lease (#6704).

#### Scenario: A Ready bug is staged
- **WHEN** the job runs with `--confirm` on a Ready P1 bug and the model gives a valid plan
- **THEN** the branch is pushed with one commit by the session identity, and the commit holds the change folder

#### Scenario: A push URL in the clone of the job
- **WHEN** the clone that the planner reads has a push URL that names another repository
- **THEN** the job pushes the branch to `origin` all the same, with one commit whose body is `Plans #<issue>.`

#### Scenario: The default branch holds a file of the change folder now
- **WHEN** the default branch gains a file of the change folder after the plan read the staged commit
- **THEN** the patch does not apply to the tip, the item stops, and the job pushes nothing
