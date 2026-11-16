# Design

## Decisions

### 1. Shared writer in steps/comment.py
Put the shared marked-comment writer in `src/devops_cli/roadmap/steps/comment.py`.
Define the public entry point as `post(target, marker, key, body)`.
Every roadmap job that writes a marked comment calls this function.

### 2. Read before write and upsert by marker and key
Read the target's comments before writing.
Find an existing comment where the body contains both the marker and the key.
If the existing comment has the same body, perform no write.
If the existing comment has different body, update it.
If no comment matches, create a new comment.

### 3. Target abstraction
Accept any target object that provides comment listing, creation, and update methods.
Provide a standard `Target` class that wraps an issue or pull request.
Allow `Target` to use a `RoadmapStore` or `GitHubClient`.

### 4. Structural test for direct callers
Add a structural test in `tests/structural/`.
Verify that no roadmap module outside `steps/comment.py` calls `comment_on_issue` or `comment_on_pull`.

## Rejected alternatives

### Keep per-job comment helpers
Rejected: Different modules keep separate rules. Reruns after stops leave duplicate comments.

### Create a new comment on every run
Rejected: Reruns after service stops leave extra comments.

### Edit the last comment by the bot
Rejected: Can edit a comment from another job or a person.
