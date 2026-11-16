## ADDED Requirements

### Requirement: The pass names each project owner/name
Every point that `devops ai rag ingest` writes SHALL carry the project name owner/name of its repository.

#### Scenario: The pass runs outside the checkout
- **WHEN** The pass indexes the repository owner/name while the directory it runs in holds another name
- **THEN** Each written point carries owner/name in its project name and no point carries the directory name.

### Requirement: Drift compares the project that --repo names
`devops ai rag drift` SHALL compare the project that `--repo owner/name` names when the option is given, and the name of the current directory otherwise.

#### Scenario: Drift runs in a worktree
- **WHEN** The user runs `devops ai rag drift --repo owner/name` from a directory that holds another name
- **THEN** The report names the project owner/name and reads its points and its cache entries.
