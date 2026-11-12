## ADDED Requirements

### Requirement: The code graph walk skips each ignored folder
`devops ai ast graph` SHALL list the files of its folder in one walk. The walk SHALL NOT list `.git`, a folder that git ignores, or a folder in one of them.

#### Scenario: A folder that .gitignore names
- **WHEN** the graph is built for a folder that holds `.git`, a `.gitignore` that names `vendor/`, a Python file in `vendor/pkg/` and a Python file at the top
- **THEN** the walk lists only the top folder, and the graph indexes only the file at the top
