# roadmap-author-trust Specification

## Purpose
Which authors the roadmap jobs trust: a person with write access and two bots with an exact login, the approval that an item of a bot needs from the review of refine, the retry right that no bot has, and the replies that the models of refine and of the alternatives job read. The trust check of a job is the author rule and, for an item of a bot, the approval.

## Requirements

### Requirement: A job trusts an author with write access or a bot with an exact login
The refine, stage, implement and alternatives jobs SHALL take an item only when its `author_association` is OWNER, MEMBER or COLLABORATOR, or its author login is equal to `service.github_app.bot_login` or to `github-actions[bot]`. A job SHALL NOT trust any other bot, or any other account.

#### Scenario: An item of the Service App
- **WHEN** an item's author login is `devops-cli-service[bot]` with the association CONTRIBUTOR, and `service.github_app.slug` is `devops-cli-service`
- **THEN** a refine round takes the item, and the stage, implement and alternatives jobs take it once refine's review approved it

#### Scenario: An item of github-actions
- **WHEN** an item's author login is `github-actions[bot]` with the association CONTRIBUTOR
- **THEN** a refine round takes the item, and the other jobs take it once refine's review approved it

#### Scenario: An item of another bot or of an outside account
- **WHEN** an item's author login is `dependabot[bot]`, or an account with the association NONE opened it
- **THEN** no job takes the item, and the reason of each job names the author and the association

### Requirement: A login that only resembles a trusted login is not trusted
The trust check SHALL use equality on the whole login. A login that holds the trusted login with another character before or after it, that lacks `[bot]`, or that differs in case SHALL NOT be trusted.

#### Scenario: A lookalike login
- **WHEN** an item's author login is `devops-cli-service[bot]x`, `devops-cli-service`, `DEVOPS-CLI-SERVICE[BOT]` or `github-actions[bot]2`
- **THEN** no job takes the item

### Requirement: With no App slug no item of the App is trusted
When `service.github_app.slug` is unset, `bot_login` SHALL be None, and the trust check SHALL trust no item whose author login is the login of the Service App's bot. An item with no author login SHALL NOT be trusted.

#### Scenario: No App slug
- **WHEN** `service.github_app.slug` is unset and an item's author login is `devops-cli-service[bot]`
- **THEN** no job takes the item

### Requirement: Item and IssueRecord carry the author login
`Item`, `IssueRecord` and `IssueComment` SHALL hold the login of the author, which the GitHub store reads from `user.login`. A payload with no `user` SHALL give no login.

#### Scenario: The store reads the login
- **WHEN** an issue's `user.login` is `devops-cli-service[bot]`
- **THEN** the Item of the listing, the Item that the store reads and the issue record all give that login

### Requirement: An item of a bot needs the approval of refine's review
The stage, implement and alternatives jobs SHALL take an item whose author is a bot only when its job record holds `refine.judge` `approved`. The body of the item SHALL also hash as `refine.body_hash` and `refine.section_hash` record, outside the section of refine and in it. An item of a person SHALL need no approval. The reason of a job that leaves out such an item SHALL say that no review approved its body as it is now.

#### Scenario: A bot item with no approval
- **WHEN** a Ready item of the Service App has no `refine.judge` in its job record
- **THEN** the stage and implement jobs leave it out with the reason that no review approved it, and the alternatives job does not check it

#### Scenario: A bot item with a refusal
- **WHEN** a Ready item of `github-actions[bot]` holds `refine.judge` `refused`
- **THEN** the stage and implement jobs leave it out

#### Scenario: A bot item with an approval
- **WHEN** a Ready item of the Service App holds `refine.judge` `approved`, and its body hashes as the record holds
- **THEN** the stage and implement jobs take it, and the alternatives job checks it

#### Scenario: A bot item whose body changed after the review
- **WHEN** a Ready item of the Service App holds `refine.judge` `approved`, and a person edited its body, in the section of refine or outside it
- **THEN** the stage, implement and alternatives jobs leave it out, and the reason says that no review approved its body as it is now

#### Scenario: A hash that no review wrote
- **WHEN** a round records the hashes of a body with no review, because the body is too big to refine or the model failed on it twice
- **THEN** the round clears `refine.judge`, and no job takes the item as approved

#### Scenario: An item of a person
- **WHEN** a Ready item of the owner has no `refine.judge`
- **THEN** the stage and implement jobs take it

### Requirement: A comment of a bot starts no retry
The `implement: retry` check SHALL accept only a comment whose `author_association` is OWNER, MEMBER or COLLABORATOR. A comment by the login of the Service App's bot or of `github-actions[bot]` SHALL start no retry.

#### Scenario: The App comments implement: retry
- **WHEN** a stopped item has a comment `implement: retry` by `devops-roadmap[bot]` with the association CONTRIBUTOR
- **THEN** the implement job leaves the item out as stopped

### Requirement: The models of refine and of the alternatives job read only the replies of trusted authors
Refine reads comments for the replies, the answers to a `covers` question, the stage return and the wait checks. The alternatives job gives comments to its model. These comments SHALL be those whose `author_association` is OWNER, MEMBER or COLLABORATOR, or whose author login is equal to the login of the Service App's bot. A comment of any other account, `github-actions[bot]` included, SHALL NOT reach either model.

#### Scenario: Replies of several accounts
- **WHEN** an item has replies from an account with the association NONE, from `dependabot[bot]`, from `github-actions[bot]`, from the owner and from the Service App's bot
- **THEN** the `replies` of the request to the model of refine hold the reply of the owner and the reply of the Service App's bot, in that order, and no other

#### Scenario: The alternatives job reads the same replies
- **WHEN** the same item is checked by the alternatives job
- **THEN** the `replies` of its request hold the same two replies and no other
