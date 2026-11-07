## REMOVED Requirements

### Requirement: The check is off without a public repository and a key
**Reason**: The check is off without a configured search provider, no longer without a Firecrawl key, and its scenarios name the provider.
**Migration**: The requirement "The check is off without a public repository and a search provider" holds the rule.

## ADDED Requirements

### Requirement: The check is off without a public repository and a search provider
The check SHALL be off when the repository is private, when its visibility cannot be read, or when no search provider is configured. The plan SHALL say why, and the run SHALL make no model call, no search and no write.

#### Scenario: A private repository
- **WHEN** the repository is private
- **THEN** the plan says that the check is off because the repository is private, and no search runs

#### Scenario: No search provider
- **WHEN** the repository is public and no search provider is configured
- **THEN** the plan says that no search provider is configured, and no search runs

## MODIFIED Requirements

### Requirement: A dry run makes no request
`devops roadmap alternatives --dry-run` SHALL make no request, and SHALL print the requests a run makes, with the exact `gh` command of each GitHub request, the URL of the request of the first configured search provider and the URL of each PyPI request.

#### Scenario: A dry run
- **WHEN** the command runs with `--dry-run`
- **THEN** it exits 0 after it makes no GitHub, model, search or PyPI request, and its output lists the requests a run makes

### Requirement: A non-skip item needs a search before any verdict
For an item that is no skip class, the check SHALL refuse a reply that follows no `search_web` call, and SHALL give the model one more turn to search. A second reply that follows no search SHALL end as a failed check: the job skips the item with a named reason and writes nothing for it. The check SHALL refuse a reply with the verdict `not-applicable` from the model, because the job sets that verdict for a skip class only.

#### Scenario: A reply with no search gets one more turn
- **WHEN** the model answers a `feat` item with the verdict `none` and no search, then searches, then answers with the verdict `none`
- **THEN** the model received three requests, the check is written with the query of the search, and the counter `devops_cli_web_searches_total` has a point

#### Scenario: Two replies with no search
- **WHEN** the model answers a `feat` item twice with a verdict and no search
- **THEN** the model received two requests, the item is skipped with the reason that the reply gives a verdict with no search, and nothing is written for it

#### Scenario: A not-applicable reply from the model
- **WHEN** the model searches for a `feat` item and then answers with the verdict `not-applicable`
- **THEN** the item is skipped with the reason that the job sets `not-applicable` for a skip class only, and nothing is written for it
