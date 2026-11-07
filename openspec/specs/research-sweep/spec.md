# research-sweep Specification

## Purpose
How `devops research sweep` hands the actionable findings of the pins to roadmap intake: one candidate for each finding that no issue carries, with a digest of every finding, a gauge of open findings by severity and an alert rule for critical findings, without a model deciding what a finding is.

## Requirements

### Requirement: Actionable finding files one intake candidate
The sweep SHALL file exactly one intake candidate for each finding with severity critical or high that no issue body carries a marker for. The candidate SHALL end with the marker line `research-finding: <source id>`.

#### Scenario: First sweep of an actionable finding
- **WHEN** the sweep runs with `--confirm` on a high-severity finding and no issue body holds its marker
- **THEN** intake files one issue whose body holds the advisory ids and URLs and ends with the marker of the finding

#### Scenario: Plan without confirm
- **WHEN** the sweep runs without `--confirm` on an actionable finding
- **THEN** intake decides the candidate and no issue is written

### Requirement: Second sweep skips a filed finding
The sweep SHALL file no candidate for a finding whose marker an issue body already holds, open or closed.

#### Scenario: Second sweep of the same finding
- **WHEN** the sweep runs again on the same finding and the issue search returns its marker
- **THEN** the sweep files no candidate, calls no model, and prints one digest line that says the finding was filed before in that issue

### Requirement: Non-actionable finding stays in the digest
The sweep SHALL print a digest line and file no candidate for a finding whose severity is lower than high.

#### Scenario: Low-severity finding
- **WHEN** the sweep runs on a low-severity finding
- **THEN** the sweep prints one digest line that says the finding is not actionable and makes no intake call

### Requirement: Dry run makes no request
The sweep SHALL make no external request with `--dry-run`, and SHALL return a report of the same type as a real run with the list of requests that a real run makes.

#### Scenario: Dry run
- **WHEN** the sweep runs with `--dry-run`
- **THEN** no OSV, GitHub search, intake, metric or alert request leaves the process, and the report lists the OSV requests, the issue search and the requests of intake

### Requirement: Candidate body has public advisory data only
The sweep MUST put the advisory ids and their URLs in the candidate body, MUST NOT put a path of the inventory, a private host name or a private address there, and SHALL stop before any request when a candidate looks like it holds a secret.

#### Scenario: Finding with a private inventory path
- **WHEN** the sweep builds the candidate of a finding whose inventory file path holds a private host name and address
- **THEN** the title and the body hold the advisory id, its aliases and their URLs, and neither the host name nor the address

#### Scenario: Candidate that looks like a secret
- **WHEN** the summary of an advisory holds a token
- **THEN** the sweep raises a security error and sends no request

### Requirement: Intake keeps its duplicate flag
The sweep SHALL never drop a candidate and SHALL never close an issue. A candidate that intake skips SHALL stay in the digest with the reason, and a possible duplicate that intake flags SHALL stay in the entry.

#### Scenario: Intake skips a candidate
- **WHEN** intake skips the candidate of a finding
- **THEN** the digest line of the finding says that intake skipped it and gives the reason, and no issue is closed

### Requirement: Digest reports each finding
The sweep SHALL print a digest with one line for each finding that names its result, and a summary line.

#### Scenario: Digest with one filed and one skipped finding
- **WHEN** the sweep handles one actionable finding and one non-actionable finding
- **THEN** the digest has one line for each finding, and each line names its result

### Requirement: Gauge of open findings by severity
The sweep SHALL set the gauge `devops_cli_research_open_findings` with one value for each severity of the scale, with zero for a severity without a finding, and SHALL set no value when a lookup got no answer.

#### Scenario: Findings of two severities
- **WHEN** the sweep ends with one critical and one low finding
- **THEN** the gauge has the value 1 for critical and for low, and 0 for high, medium and info

### Requirement: Alert on critical findings
The alert rule `ResearchCriticalFindings` SHALL fire at severity critical when the last value of the critical gauge in the last 7 days is above zero, and SHALL stay quiet after a sweep set zero.

#### Scenario: Critical finding, then a clean sweep
- **WHEN** the gauge has the value 2 and a later sweep sets 0
- **THEN** the rule fires before the later sweep and is quiet after it
