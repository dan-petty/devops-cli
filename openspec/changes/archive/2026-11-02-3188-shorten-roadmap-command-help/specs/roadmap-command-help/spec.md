## Purpose
The help of the long `devops roadmap` job commands: how long it is and where the rest of the description lives. `devops roadmap --help` lists each command with the start of its help, so a long help hides the list. The long description of each job is in one page under `docs/roadmap/`.

## ADDED Requirements

### Requirement: The help of a job command is a short summary that names its page
The help of each of the commands `devops roadmap intake`, `refine`, `alternatives`, `stage`, `implement` and `inbox` SHALL be a summary of at most three sentences. It SHALL name the page `docs/roadmap/<command>.md`, and that page SHALL exist in the repository. The help of an option is not part of this requirement.

#### Scenario: The summary is short
- **WHEN** the help of each of the six commands is split into sentences
- **THEN** none has more than three sentences

#### Scenario: The page exists
- **WHEN** the help of one of the six commands is read
- **THEN** it names `docs/roadmap/<command>.md` for that command, and the file is in the repository
