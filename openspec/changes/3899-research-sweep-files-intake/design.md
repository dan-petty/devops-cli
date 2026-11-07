# Design

## Context

`devops research advisories` (#3898) returns the advisories that affect the pins. Nothing sends them to a person. Roadmap intake already takes candidates from `survey` and from the review hand-off, and it owns the duplicate flag.

## Goals / Non-Goals

**Goals:**
- One candidate for each actionable finding, once, with the marker in its body.
- A digest that shows every finding and its result.
- A gauge by severity and one alert rule on the existing route.

**Non-Goals:**
- The exploited flag and the end-of-life date. See "Not in this change" in the proposal.
- A schedule. A person or a job starts the command.
- A new alert path.

## Decisions

- **Decision: Call intake in process.**
  *Choice:* `intake_candidate` with a `NewCandidate`, as `review intake` does.
  *Rejected alternative:* A `devops roadmap intake` subprocess. It adds a shell boundary, hides the duplicate flag and makes the test slower.
- **Decision: The marker is an HTML comment with a source id; one search reads all markers.**
  *Choice:* `<!-- research-finding: pypi:pkg@1.0:GHSA-... -->`. The sweep searches the phrase `research-finding` and reads the ids from the bodies. Any issue that carries the id settles the finding, open or closed.
  *Rejected alternative:* A local cache. It loses state on a new host and files duplicates. A label on the issue adds a second source of the same fact.
- **Decision: The id holds the pinned version.**
  *Choice:* A new pin of the same package is a new finding, and the advisory that still affects it is filed again.
  *Rejected alternative:* An id of package and advisory. A fix to a version that is still affected would stay silent.
- **Decision: An allowlist builds the body.**
  *Choice:* Public advisory fields and no inventory path. `NewCandidate.refuse_secrets` runs before any request.
  *Rejected alternative:* Copy the finding text and the locations. A path can hold a private host name.
- **Decision: The gauge is not set when a lookup failed.**
  *Choice:* A count that is not complete is not recorded. The command exits with 1 after it prints.
  *Rejected alternative:* Record the partial count. A zero would end the alert for a finding that was not read.
- **Decision: Only critical findings alert.**
  *Choice:* `ResearchCriticalFindings` reads the last value of the gauge of the last 7 days. The sweep runs when a person or a job starts it, so a rule on a fresh sample would be quiet most of the time. A sweep that sets zero ends the alert.
  *Rejected alternative:* An alert on high findings. The issue asks for critical or exploited.
- **Decision: A dry run returns a report of the same type.**
  *Choice:* `SweepReport` with `dry_run` true, no entry and the requests of a real run. The findings come from OSV, so a dry run cannot know them.
  *Rejected alternative:* Run intake and roll back. It sends requests and can leave a candidate.
