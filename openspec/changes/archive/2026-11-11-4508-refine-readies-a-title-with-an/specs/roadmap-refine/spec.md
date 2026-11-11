## ADDED Requirements

### Requirement: Refine leaves an item with an unlisted title type
`devops roadmap refine` SHALL NOT refine an item whose title type is not in `CONST_BRANCH_TYPES`, also with `--item`, and SHALL make no model call for it, so the item does not become Ready. The detail SHALL name the type and `invalid-title-type`. The item SHALL wait on a person when the type has no correction. The first round after a title with a listed type SHALL refine the item.

#### Scenario: A New item with a security title
- **WHEN** a round runs over a New item titled `security(ssh): verify node host keys`
- **THEN** the model records no request, the Status stays New, and the detail names `fix(security): verify node host keys` and `invalid-title-type`

#### Scenario: A type with no correction
- **WHEN** a round runs over a New item titled `wip(cli): finish the half-done work`
- **THEN** the item waits on a person, the detail names `wip`, and the model records no request

#### Scenario: The title gets a listed type
- **WHEN** the title of the security item becomes `fix(security): verify node host keys` and a round runs
- **THEN** refine refines the item and sets it Ready

#### Scenario: A person names the item with --item
- **WHEN** refine runs with `--item` for the item titled `wip(cli): finish the half-done work`
- **THEN** the model records no request, and the Status stays New

#### Scenario: The limit of a round
- **WHEN** a round with `--limit 1` runs over the `wip(cli)` item and a New item with a listed type
- **THEN** refine takes the item with the listed type

## MODIFIED Requirements

### Requirement: A round leaves an item from an account without write access to a person
Without `--item`, `devops roadmap refine` SHALL take only an item whose author the jobs trust (`roadmap-author-trust`). Any other item SHALL wait on a person with a detail line that names its author, its association and `--item` with its number. It SHALL take no place under `--limit`, and the round SHALL make no model call for it. With `--item`, refine SHALL refine the open New or Ready item that it names, whoever opened it, when its title type is listed.

#### Scenario: A round with an item from an account with no association to the repository
- **WHEN** the backlog holds a New P2 item that an account with the association NONE opened and a New P3 item that the owner opened, and refine runs with `--limit 1`
- **THEN** refine asks the model about the owner's item only, and the report shows the other item waiting on a person with the detail "The author is unknown, and its association with the repository is NONE. A refine round refines only the items that these accounts opened: the owner, a member, a collaborator, the Service App's bot and github-actions[bot]. A person refines this item with --item 1."

#### Scenario: A person names the item with --item
- **WHEN** refine runs with `--item` for that item, and the model gives a proposal that is ready
- **THEN** refine refines the item and sets it to Ready

#### Scenario: An item that a collaborator opened
- **WHEN** a member or a collaborator opened a New item
- **THEN** a round takes the item

#### Scenario: An item that a trusted bot opened
- **WHEN** the Service App's bot, or `github-actions[bot]`, opened a New item
- **THEN** a round takes the item
