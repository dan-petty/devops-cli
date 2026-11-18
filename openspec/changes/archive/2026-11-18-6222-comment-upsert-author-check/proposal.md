# Proposal: #6222

## Why
Two in-place comment writers find existing marked comments by marker text only, not by author:
- `post()` in `src/devops_cli/roadmap/steps/comment.py` matches the first comment that holds the marker and key.
- `post_pr_review_comment()` in `src/devops_cli/ai/review/runner.py` matches the first comment that holds the review marker of the head commit.

Because the tool token can edit comments of other users, a person who quotes or copies the marker into their own comment can have that comment overwritten. This change ensures both writers edit only comments authored by the active GitHub session.

Closes #6222.

## What Changes
- `post()` in `src/devops_cli/roadmap/steps/comment.py` checks comment author login against the session login before matching an existing comment.
- `post_pr_review_comment()` in `src/devops_cli/ai/review/runner.py` checks comment author login against the session login before updating a head review comment.
- Comments with no author or authored by another login are never edited; writers post a new comment instead.

## Capabilities
- In-place roadmap comments edit only comments written by the tool account.
- In-place PR review comments edit only review comments written by the tool account.

## Impact
- Prevents accidental overwrites of user comments containing quoted marker text.
- No breaking changes for automated workflows.

## Feasibility
- `publish_pr_evidence()` in `src/devops_cli/github/pr_evidence.py` already implements this exact pattern (`comment.author == session.login`). Both writers adopt the same comparison.

## Existing Tool Considered
- GitHub REST API issue-comments endpoint via `GitHubClient` and `get_github_session()` provides the authenticated login and comment author. No external tool or library is required.
