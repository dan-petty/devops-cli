## MODIFIED Requirements

### Requirement: The tool read_issue answers the state of an item
`read_issue(number)` SHALL answer the state and the labels of an item. For a closed issue it SHALL name the merged pull request that closed it, or say that none did. For a closed pull request it SHALL say whether it merged. Only for an item whose author `trust.is_trusted` accepts, it SHALL answer the title, the first 1500 characters of the body and the last 3 comments that `trust.trusted_replies` keeps, cut to 600 characters each. For another item one fixed line SHALL stand in their place.

#### Scenario: An issue closed by a merged pull request
- **WHEN** `read_issue` reads a closed issue of a person with write access whose last closing commit is in a merged pull request
- **THEN** the answer holds the state, the title, the labels and the line "Closed by merged pull request #N."

#### Scenario: A closed pull request
- **WHEN** `read_issue` reads a closed pull request that did not merge
- **THEN** the answer says that the pull request closed with no merge

#### Scenario: A comment of an account with no write access
- **WHEN** `read_issue` reads an issue of a person with write access that holds one comment of a collaborator and one comment of an account with the association `NONE`
- **THEN** the answer holds the comment of the collaborator and not the other comment

#### Scenario: Comments of other accounts after the comment of a person
- **WHEN** an issue holds one comment of a person with write access and then three comments of an account with the association `NONE`
- **THEN** the answer holds the comment of the person, and the tool makes two requests

#### Scenario: An item of an account with no write access
- **WHEN** `read_issue` reads a closed issue whose author has the association `NONE`, and the issue holds a title, a body, a label and one comment
- **THEN** the answer holds the number, the state, the label, the line of the closing pull request and the line "An account with no write access opened this item. Its title, its body and its comments are left out.", it holds no title, no body and no comment, and the tool sends no request for the comments

#### Scenario: An item of a bot
- **WHEN** the author of an issue has the association `CONTRIBUTOR` and the login of the Service App's bot, `github-actions[bot]`, `dependabot[bot]` or a login that only starts with the login of the Service App's bot
- **THEN** the answer holds the title and the body for the first two logins, and the fixed line for the other two

#### Scenario: A comment of a bot
- **WHEN** an issue of a person with write access holds a comment of the Service App's bot, a comment of `github-actions[bot]` and a comment of a deleted account
- **THEN** the answer holds only the comment of the Service App's bot

### Requirement: The tool find_issues lists open items that name the terms
`find_issues(terms)` SHALL answer at most 10 open issues and pull requests of the repository that name the terms, each as `#N state title`. A fixed text SHALL stand for the title of an item whose author `trust.is_trusted` does not accept. It SHALL take every colon and quote out of the terms, so that the search names no repository but that of the job.

#### Scenario: Open items
- **WHEN** `find_issues` gets the terms `redaction point` and GitHub finds an issue and a pull request of persons with write access
- **THEN** the answer lists both as `#N state title`

#### Scenario: A qualifier in the terms
- **WHEN** `find_issues` gets the terms `repo:other/private`
- **THEN** the search that GitHub receives holds no `repo:` qualifier except that of the repository of the job

#### Scenario: An open item of an account with no write access
- **WHEN** GitHub finds an open issue whose author has the association `NONE` and an open pull request of the Service App's bot
- **THEN** the line of the issue holds its number, its state and the text `(title left out: an account with no write access opened the item)` and not its title, and the line of the pull request holds its title
