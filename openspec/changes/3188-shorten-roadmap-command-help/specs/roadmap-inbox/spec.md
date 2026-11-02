## MODIFIED Requirements

### Requirement: The inbox reads a bounded number of requests and writes none
The inbox SHALL read the open issues, the open pull requests, the repository labels and `.github/labels.yml` once, and the newest commit of that file only when the labels differ. A listing SHALL take one request for each 100 rows, so a run sends one request for each 100 open issues and pull requests, one for each 100 open pull requests, one for each 100 labels, one for the labels file, and one for the commit when the labels differ. It SHALL NOT call a model, and it SHALL write nothing to GitHub or git. Its dry-run class SHALL be `request-plan`: `--dry-run` SHALL make no request and SHALL list the reads.

#### Scenario: No write
- **WHEN** the inbox runs on a store that records writes
- **THEN** the store records no write

#### Scenario: The reads
- **WHEN** the inbox runs against a store that counts reads of open issues, open pull requests and labels
- **THEN** each is read once, and no read of every issue happens

#### Scenario: The requests of a run
- **WHEN** the plan of the inbox is read
- **THEN** it holds three listings that repeat for each page, one read of the labels file, and one read of the newest commit of that file that only differing labels make

#### Scenario: A dry run
- **WHEN** `inbox --dry-run` runs with processes and sockets refused
- **THEN** the exit status is 0, the output says that no request was made, and it lists the reads and no write
