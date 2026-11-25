## MODIFIED Requirements

### Requirement: The stage context lists an overlapping pull request
The stage context builder SHALL list each open pull request that changes a path that the item body cites, with its number, title, state and the shared paths. For a pull request whose author `trust.is_trusted` does not accept, or whose author GitHub does not give, a fixed text SHALL stand for the title. The read of the open pull requests SHALL get the author of each in the same request, and only an author of the type `Bot` SHALL count as a bot.

#### Scenario: A fake pull request changes a cited path
- **WHEN** A test gives the builder a fake client that holds pull request 3173 of a person with write access, which changes `docs/TELEMETRY.md`, and an item body that cites `docs/TELEMETRY.md`.
- **THEN** The context holds one entry with number 3173, its title, its state and `docs/TELEMETRY.md`.

#### Scenario: A fake pull request changes a path that no item body cites
- **WHEN** A test gives the builder a fake client that holds pull request 3173, which changes `docs/TELEMETRY.md`, and an item body that cites only `src/devops_cli/roadmap/stage/stage.py`.
- **THEN** The context holds no overlap entry.

#### Scenario: A pull request of an account with no write access
- **WHEN** A test gives the builder a fake client that holds pull request 9, a plan pull request whose author has the association `NONE`, which changes `src/app.py`, and an item body that cites `src/app.py`.
- **THEN** The context entry holds number 9, the state, the plan mark, `src/app.py` and the text `(title left out: an account with no write access opened the item)` in place of the title.

#### Scenario: A pull request with no author
- **WHEN** A test gives the builder a fake client that holds one pull request with no author fields and one pull request with the association `NONE` and no author.
- **THEN** Each pull request holds the fixed text in place of its title.

#### Scenario: The author type of a bot
- **WHEN** A test gives the builder a fake client that holds a plan pull request whose author has the association `CONTRIBUTOR`, and the author is of the type `Bot` with the login of the Service App or `github-actions`, of the type `Bot` with another login, or of the type `User` with the login of one of the two bots.
- **THEN** The pull request holds its title for the two bots, and the fixed text for each other author, and each holds the plan mark.

#### Scenario: The author comes in the same request
- **WHEN** A test gives the builder a fake client that holds one open pull request.
- **THEN** The builder makes one request, and that request asks for `authorAssociation` and for the type and the login of the author.

### Requirement: The request lists the declared issue dependencies
The stage request SHALL hold `issue_dependencies` with one entry for each blocker that the Dependencies section of the item body names (the rule of `roadmap-refine/waits`), in the order of the body. An entry SHALL hold `number` and, when the store holds the issue, `title`. A fixed text SHALL stand for the title of an issue that `trust.is_trusted` does not accept. The request SHALL omit the key when the body declares no dependency.

#### Scenario: Two declared dependencies
- **WHEN** the body names `#2` and `#3` as blockers in its Dependencies section, and the store holds both as items of a person with write access with a title
- **THEN** the request holds `[{"number": 2, "title": "..."}, {"number": 3, "title": "..."}]`

#### Scenario: An issue that the store lacks
- **WHEN** the body names `#99` and the store holds no issue 99
- **THEN** its entry is `{"number": 99}` with no `title` key

#### Scenario: No dependency in the body
- **WHEN** the body has no Dependencies section
- **THEN** the request holds no `issue_dependencies` key

#### Scenario: A dependency of an account with no write access
- **WHEN** the body names `#2` as a blocker in its Dependencies section, and the store holds issue 2 with an author of the association `NONE`
- **THEN** the entry of `#2` holds the number and the text `(title left out: an account with no write access opened the item)` as its `title`
