## ADDED Requirements

### Requirement: Stage criteria stop at job block markers
`acceptance_criteria` in `src/devops_cli/roadmap/stage/stage_criteria.py` SHALL end an open `Acceptance criteria` heading at any top-level job block marker (`block_marker_of`), so Covers and Lacks items inside an alternatives block do not become criteria or trigger missing-criterion refusals in `criterion_problems`.

#### Scenario: Alternatives block follows a person's criteria list
- **WHEN** `acceptance_criteria(body)` reads a body with two items under `Acceptance criteria` followed by `<!-- devops-roadmap-alternatives:start -->` and a `Lacks:` list
- **THEN** `acceptance_criteria(body)` returns only the two person items and `criterion_problems` does not require mapping the `Lacks:` items
