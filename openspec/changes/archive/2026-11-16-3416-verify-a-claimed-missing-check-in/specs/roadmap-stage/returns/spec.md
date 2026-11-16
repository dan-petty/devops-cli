## MODIFIED Requirements

### Requirement: A false absence or a claimed missing check returns the item
The stage job SHALL return an item to New with the probe evidence when the issue body states that a cited class field is absent and the staging commit defines it, and SHALL make no model call for that item. The stage job SHALL return an item to New with the probe evidence when a plan text says that a cited call site runs no named check and the staging commit holds it, and SHALL write no branch and open no pull request for that item.

#### Scenario: The body says a field is absent while the class defines it
- **WHEN** The body says that `PullStatus` defines no `labels` and `PullStatus` at the staging commit defines `labels`
- **THEN** The stage job returns the item to New, and its comment quotes the probe line that names the file and line of `labels`

#### Scenario: The item waits on a body edit
- **WHEN** The body states that a cited class field is absent and the staging commit defines it
- **THEN** The stage job records `refine.next_step` as `edit` for the item

#### Scenario: A plan that claims a check the base holds
- **WHEN** a plan says that `_publish` runs no `title_problems` check, and the staging commit holds `title_problems` in a helper of `_publish`
- **THEN** the stage job returns the item to New, writes no branch, opens no pull request, and its comment quotes the line that names the path and the line of `title_problems`

## RENAMED Requirements

- FROM: `### Requirement: A false absence returns the item`
- TO: `### Requirement: A false absence or a claimed missing check returns the item`
