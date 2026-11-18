## ADDED Requirements

### Requirement: The pass names each project owner/name
`devops ai rag ingest` SHALL name the project of every point that it writes `owner/name`, from the repository list and never from the name of the directory that the command runs in.

#### Scenario: The pass runs outside the checkout
- **WHEN** The pass indexes the repository owner/name while the directory that it runs in holds another name
- **THEN** Each written point carries owner/name in its project name and no point carries the directory name.
