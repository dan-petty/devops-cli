## MODIFIED Requirements

### Requirement: Each call is counted
Each call of `PageFetch` SHALL add 1 to `devops_cli_roadmap_page_fetches_total` by `toolset` (`refine`, `alternatives` or `stage`) and `result` (`ok`, `refused`, `limit` or `error`).

#### Scenario: An ok call and a refused call
- **WHEN** the check fetches a page that a search returned and then asks for a URL that nothing named
- **THEN** the counter has one point with the result `ok` and one with the result `refused`, both for the toolset `alternatives`

#### Scenario: A page read of the stage planner is counted
- **WHEN** the stage planner reads a page for an ask-mode answer
- **THEN** the counter has one point with the result `ok` for the toolset `stage`
