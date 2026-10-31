## ADDED Requirements

### Requirement: skip-class-classification
The check SHALL classify an item as a skip class when its Conventional Commit type is one of test, docs, refactor, chore, ci, or perf, or when its body is a fix of an internal defect with a stack trace and no new capability. For a skip-class item, the verdict SHALL be not-applicable with the class name as the reason, and no model call SHALL be made.

#### Scenario: Each skip class produces not-applicable without a model call
- **WHEN** The check runs on an item whose type is test, docs, refactor, chore, ci, or perf
- **THEN** The verdict is not-applicable, the comment names the class as the reason, and no model call is made

#### Scenario: A fix with stack trace and no new capability is a skip class
- **WHEN** The check runs on an item whose body is a fix of an internal defect with a stack trace and no new capability
- **THEN** The verdict is not-applicable, the comment names the class as the reason, and no model call is made

### Requirement: search-before-verdict
For a non-skip-class item, the check SHALL reject a model reply that gives a verdict with no search recorded. The check SHALL give the model one additional turn to perform a search. A second reply without a search SHALL end as a failed check for that item.

#### Scenario: A scripted model answers a feat item without a search
- **WHEN** The model returns a verdict with no search recorded for a feat item
- **THEN** The check rejects the reply, gives the model one turn to search, and a second answer without a search ends as a failed check for that item

### Requirement: firecrawl-counter-replay
The devops_cli_firecrawl_searches_total counter SHALL increase by at least 1 when the check runs on a non-skip-class item and the model performs a search.

#### Scenario: A replay of a feat item triggers a search
- **WHEN** The check runs on a feat item in a replay and the model performs a search
- **THEN** devops_cli_firecrawl_searches_total increases by at least 1
