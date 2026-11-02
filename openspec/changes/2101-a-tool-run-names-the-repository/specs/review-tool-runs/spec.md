## ADDED Requirements

### Requirement: ToolRun repository_uri field
A ToolRun SHALL have a repository_uri field of type str | None. It SHALL hold the `remote.origin.url` setting of the checkout that holds the tree, with the userinfo removed, when that setting is an absolute URI with a host. It SHALL be None when the checkout has no `origin` remote, when the remote is not an absolute URI with a host, when the tree is outside any checkout, and when the direct executor cannot read the checkout.

#### Scenario: Remote with credentials
- **WHEN** a checkout has a remote whose URL contains user:password@
- **THEN** repository_uri holds the URL with the userinfo removed

#### Scenario: Remote with a user name
- **WHEN** a checkout has the remote `ssh://git@example.com/a/b.git`
- **THEN** repository_uri is `ssh://example.com/a/b.git`

#### Scenario: Remote that is not an absolute URI
- **WHEN** a checkout has the remote `git@example.com:a/b.git`, or the remote `/srv/a.git`
- **THEN** repository_uri is None

#### Scenario: No remote
- **WHEN** a checkout has no remote configured
- **THEN** repository_uri is None

#### Scenario: Tree outside any checkout
- **WHEN** a tree is outside any git checkout
- **THEN** repository_uri is None and the record is made

#### Scenario: Checkout that git cannot read
- **WHEN** the direct executor runs a tool over a checkout that git cannot read
- **THEN** repository_uri is None and the record is made
