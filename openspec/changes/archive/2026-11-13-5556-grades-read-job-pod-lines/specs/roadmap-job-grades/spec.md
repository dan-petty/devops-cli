## ADDED Requirements

### Requirement: The report reads the result lines of the Service and the Job pods, in both forms
Each query of `devops roadmap eval grades` SHALL select the containers `service`, `stage` and `fix-plan` of the namespace `devops`, SHALL count only a line that starts with `roadmap job result: ` after the parse, and SHALL parse a JSON line by its `message` field and a plain line as it is. A plain line SHALL NOT make Loki refuse a query. The base of the queries SHALL be one constant, and each query of the dashboard row `Roadmap Job Success` SHALL start with it.

#### Scenario: A JSON line of the Service and plain lines of two Job pods
- **WHEN** Loki holds one JSON line of the Service with `job=implement`, one plain line on stderr of a fix-plan Job pod with `job=fix_plan`, and one plain line on stderr of a stage Job pod with `job=stage`
- **THEN** the report gives 1 attempt to each of `implement`, `fix_plan` and `stage`

#### Scenario: A line in the log of a runner pod
- **WHEN** Loki also holds a plain result line in the container `runner` of a Job pod
- **THEN** the report does not count that line

#### Scenario: The dashboard reads the same lines
- **WHEN** a panel of the row `Roadmap Job Success` reads the result lines
- **THEN** its query starts with the base of the report
