## MODIFIED Requirements

### Requirement: Prepare writes the run of the agent
When no decision ends the run, `prepare` SHALL clone the repository at the tip of the default branch. It SHALL commit the scaffold of the change folder with its date. It SHALL write the state file and an issue listing of at most 1 MiB in `state/`, and the inputs in `work/`. The listing SHALL be a list of `IssueRecord` with the number, the title, the URL and the state, and the body of the item only. A fixed text SHALL stand for the title of an issue that `trust.is_trusted` does not accept.

#### Scenario: A run that goes on
- **WHEN** `prepare` runs for a Ready item with two comments of a person and no false premise
- **THEN** the head of the clone holds the dated scaffold, and the inputs hold the body and the two comments whole

#### Scenario: A large repository
- **WHEN** the open issues of the store hold more than 1 MiB of text
- **THEN** the listing holds the body of the item only, and its size is below 1 MiB

#### Scenario: An issue of an account with no write access in the listing
- **WHEN** an active change folder of the base names a closed issue whose author has the association `NONE`
- **THEN** the record of that issue holds its number, its state and the text `(title left out: an account with no write access opened the item)` in place of its title, and the record of the item holds the title of the item

### Requirement: Prepare writes named issues with comments
The `prepare` phase SHALL write each issue that the item body names to `work/github/issues/<number>.json` before the agent phase starts. Only for an item whose author `trust.is_trusted` accepts, the file SHALL hold the title, the body and the last 3 comments that `trust.trusted_replies` keeps. For another item the file SHALL hold a null `title`, a null `body`, no comment and a `note` with one fixed line, and `prepare` SHALL NOT read the comments of that item.

#### Scenario: Two named issues
- **WHEN** a test runs `prepare` for an item whose body names #12 and #34, both of a person with write access, with a fake GitHub client that returns one comment of that person on #12
- **THEN** `work/github/issues/12.json` holds the state, title, labels, body and that comment, and `work/github/issues/34.json` exists

#### Scenario: A comment of an account with no write access
- **WHEN** the body names #12, an issue of a person with write access that holds one comment of a collaborator and one comment of an account with the association `NONE`
- **THEN** `work/github/issues/12.json` holds the comment of the collaborator and not the other comment

#### Scenario: An issue of an account with no write access
- **WHEN** the body names #12, an issue whose author has the association `NONE`, with a title, a body, a label and one comment
- **THEN** `work/github/issues/12.json` holds the number, the state, the label, a null `title`, a null `body`, no comment and the `note` "An account with no write access opened this item. Its title, its body and its comments are left out.", and `prepare` sends no request for the comments of #12

#### Scenario: A pull request of a bot
- **WHEN** the body names #56, a pull request whose author has the association `CONTRIBUTOR` and the login of the Service App's bot, `github-actions[bot]` or `dependabot[bot]`, with a comment of the Service App's bot and a comment of `github-actions[bot]`
- **THEN** `work/github/issues/56.json` holds the title and only the comment of the Service App's bot for the first two logins, and a null `title` and no comment for the third

### Requirement: Prepare writes open pull requests with paths
The `prepare` phase SHALL write each open pull request with the paths that it changes to `work/github/pulls.json`. An entry SHALL hold the title only for a pull request whose author `trust.is_trusted` accepts. For each other pull request a fixed text SHALL stand for the title, and the entry SHALL keep the number, the state, the plan mark and the paths.

#### Scenario: Two open pull requests
- **WHEN** a test runs `prepare` with a fake client that returns two open pull requests of a person with write access, one of which changes `src/app.py`
- **THEN** `work/github/pulls.json` holds both numbers and titles, and the paths of the second include `src/app.py`

#### Scenario: An open pull request of an account with no write access
- **WHEN** a fake client returns an open plan pull request whose author has the association `NONE` and an open plan pull request of the Service App's bot, and each changes `src/app.py`
- **THEN** the entry of the first holds its number, its state, the plan mark, `src/app.py` and the text `(title left out: an account with no write access opened the item)` in place of its title, and the entry of the second holds its title

### Requirement: Prepare writes files of a named pull request
The `prepare` phase SHALL write the files of each pull request that the item body names to `work/github/pull-files/<number>.json`. The file SHALL hold the patch text only for a pull request whose author `trust.is_trusted` accepts. For each other pull request, and for one whose author `prepare` could not read, the file SHALL hold the name and the status of each changed file, a null `patch` and a `note` with one fixed line.

#### Scenario: Named pull request
- **WHEN** a test runs `prepare` for an item whose body names #56, a pull request of a person with write access, with a fake client that returns one changed file with a patch
- **THEN** `work/github/pull-files/56.json` holds the path and the patch of that file

#### Scenario: A pull request of an account with no write access
- **WHEN** the body names pull request #56 of an account that has no write access, and the fake client returns one changed file with a patch
- **THEN** `work/github/pull-files/56.json` holds the name, the status and the counts of that file, a null `patch` and the `note` "An account with no write access opened this pull request. Its patch text is left out."

#### Scenario: A pull request whose author could not be read
- **WHEN** the body names pull request #56, the read of item #56 fails, and the read of its files gives one changed file with a patch
- **THEN** `work/github/pull-files/56.json` holds a null `patch` and the `note`

#### Scenario: The patch of a pull request of a bot
- **WHEN** the body names #56, a pull request whose author has the association `CONTRIBUTOR` and the login of the Service App's bot, `github-actions[bot]` or `dependabot[bot]`
- **THEN** `work/github/pull-files/56.json` holds the patch for the first two logins and a null `patch` for the third

### Requirement: Issue index is newline-delimited and bounded
The `prepare` phase SHALL write the open issues whose author `trust.is_trusted` accepts to `work/github/issue-index.jsonl` as one JSON object per line, with at most 1000 records and a body of at most 500 characters. An open issue of another account SHALL get no line.

#### Scenario: Repository with 3000 open issues
- **WHEN** a test runs `prepare` with a fake client that returns 3000 open issues of a person with write access, each with a body of 2000 characters
- **THEN** `work/github/issue-index.jsonl` holds at most 1000 lines, each body is at most 500 characters, and the file is at most 1 MiB

#### Scenario: An open issue of an account with no write access
- **WHEN** a fake client returns one open issue of a person with write access and one open issue whose author has the association `NONE`
- **THEN** `work/github/issue-index.jsonl` holds one line, with the number, the title, the labels and the body of the first issue
