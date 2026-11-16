# Proposal: #5025

## Why
Roadmap jobs post marked comments across multiple sites with inconsistent rules. These sites do not share one read-before-write or upsert pattern. A restart can post duplicate comments on an item or pull request. Closes #5025.

## What Changes
Add `src/devops_cli/roadmap/steps/comment.py` with `post(target, marker, key, body)`.
The function reads existing comments on the target before writing.
It updates an existing comment that matches the marker and key.
It creates a new comment when no comment matches.
It makes no write when the body does not change.
It routes all marked comments in the roadmap through this writer.

## Capabilities
- Provides one shared writer for marked comments across all roadmap jobs.
- Enforces marker read before each comment write.
- Refuses repeated comments with the store repeat guard.
- Adds a structural test that forbids direct calls to `comment_on_issue` or `comment_on_pull`.

## Impact
- All roadmap comment sites use the shared step writer.
- Stop replays leave no extra comments on issues or pull requests.
- No module outside `steps/comment.py` calls `comment_on_issue` or `comment_on_pull`.

## Feasibility
The repository already uses the repeat guard in `src/devops_cli/roadmap/stores/comment_repeat.py`.
The GitHub client already supports comment read and update operations.

## Existing Tool Considered
No open library provides internal roadmap step comment governance. The alternatives check on issue #5025 confirmed `not-applicable` for this refactor.
