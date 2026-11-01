## ADDED Requirements

### Requirement: A skip-class item is not-applicable with no model call
The check SHALL give the verdict `not-applicable`, with no model call and no search, to an item whose title has the Conventional Commit type `test`, `docs`, `refactor`, `chore`, `ci` or `perf`, and to an item whose title has the type `fix` and whose body holds the text `Traceback (most recent call last)`. The comment and the block of the body SHALL name the class: the type, or `fix-with-stack-trace`. An item of any other type, and an item with no type, SHALL NOT be a skip class.

#### Scenario: Each type is a skip class
- **WHEN** the check runs on six items whose titles have the types `test`, `docs`, `refactor`, `chore`, `ci` and `perf`
- **THEN** each check has the verdict `not-applicable`, each comment names the type, and the model received no request and no search ran

#### Scenario: The base rule of one agent run holds for non-skip items only
- **WHEN** the check runs on a skip-class item
- **THEN** no agent run happens for it, and the rule "The check of one item SHALL be one agent run" of the requirement "The agent finds facts with three tools only" holds for an item that is not a skip class

#### Scenario: A fix with a stack trace
- **WHEN** the check runs on an item titled `fix(roadmap): a crash` whose body holds `Traceback (most recent call last)`
- **THEN** the check has the verdict `not-applicable`, the comment names `fix-with-stack-trace`, and the model received no request

#### Scenario: A fix with no stack trace
- **WHEN** the check runs on an item titled `fix(roadmap): a crash` whose body holds no traceback
- **THEN** the model receives a request for the item

#### Scenario: A type that is no skip class
- **WHEN** the check runs on items whose titles have the types `feat`, `build` and `style`, and on an item whose title has no type
- **THEN** the model receives a request for each of them

#### Scenario: A skip class with an unpaired marker
- **WHEN** the body of a skip-class item holds the start marker of the block with no end marker
- **THEN** the item is skipped with a named reason and nothing is written for it

### Requirement: A non-skip item needs a search before any verdict
For an item that is no skip class, the check SHALL refuse a reply that follows no `search_web` call, and SHALL give the model one more turn to search. A second reply that follows no search SHALL end as a failed check: the job skips the item with a named reason and writes nothing for it. The check SHALL refuse a reply with the verdict `not-applicable` from the model, because the job sets that verdict for a skip class only.

#### Scenario: A reply with no search gets one more turn
- **WHEN** the model answers a `feat` item with the verdict `none` and no search, then searches, then answers with the verdict `none`
- **THEN** the model received three requests, the check is written with the query of the search, and the counter `devops_cli_firecrawl_searches_total` has a point

#### Scenario: Two replies with no search
- **WHEN** the model answers a `feat` item twice with a verdict and no search
- **THEN** the model received two requests, the item is skipped with the reason that the reply gives a verdict with no search, and nothing is written for it

#### Scenario: A not-applicable reply from the model
- **WHEN** the model searches for a `feat` item and then answers with the verdict `not-applicable`
- **THEN** the item is skipped with the reason that the job sets `not-applicable` for a skip class only, and nothing is written for it
