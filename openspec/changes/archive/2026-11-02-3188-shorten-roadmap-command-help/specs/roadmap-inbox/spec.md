## ADDED Requirements

### Requirement: A listing takes one request for each 100 rows
The inbox SHALL read each of its three listings, the open issues, the open pull requests and the repository labels, with one request for each 100 rows. A run SHALL send one request for each 100 open issues and pull requests, one for each 100 open pull requests, one for each 100 labels, one for `.github/labels.yml`, and one for the newest commit of that file when the labels differ.

#### Scenario: The requests of a run
- **WHEN** the plan of the inbox is read
- **THEN** it holds three listings that repeat for each page, one read of the labels file, and one read of the newest commit of that file that only differing labels make
