# Design

## Decisions

### Check comment author against session login
`post()` and `post_pr_review_comment()` retrieve the active GitHub session login (`get_github_session().login`) and verify that an existing marked comment was written by that same login.

### Fall back to creating a new comment
When an existing marked comment was written by a different author or carries no author, the writer leaves the comment untouched and creates a new comment.

### Support both store comments and client comments
The comment author resolution supports `IssueComment` from `GitHubClient` (`.author`), `IssueComment` from `RoadmapStore` (`.author_login`), and dictionary comment representations.

## Rejected alternatives

### Filter inside caller functions
Rejected: Many callers invoke `post()`. Centralizing the check inside `post()` guarantees all current and future callers enforce the restriction.

### Use a static bot login configuration
Rejected: The active identity is dynamic (GitHub App installation token or personal token). Using `session.login` dynamically matches the actual author of the write.
