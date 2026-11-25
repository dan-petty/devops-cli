## MODIFIED Requirements

### Requirement: Refine guide names the cycle step
The refine guide SHALL name the dependency cycle step in its list of next steps and state that only an open dependency outside a cycle makes an item wait.

#### Scenario: Guide text check
- **WHEN** `git grep -n -i "cycle" -- docs/roadmap/refine.md` runs
- **THEN** the command prints the line of the cycle step in the list of next steps, and the line of the rule that only an open dependency outside a cycle makes an item wait
