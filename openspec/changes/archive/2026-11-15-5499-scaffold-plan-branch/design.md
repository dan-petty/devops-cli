# Design: #5499

## Decisions

### 1. Scaffold step module and command
- **Decision**: Add `src/devops_cli/roadmap/steps/scaffold.py` and `devops roadmap step scaffold --item <n> --kind plan`. It writes one JSON result line with `job=scaffold` and one of `created`, `resumed`, `adopted`, or `held`.
- **Rejected**: A private function in `stage.py`. It cannot be executed standalone by a person or an agent.
- **Rejected**: A flag on `devops roadmap stage`. It conflates scaffold branch setup with planning.

### 2. Git refs API for branch creation
- **Decision**: Use `POST /repos/{owner}/{repo}/git/refs` via `create_ref` on `GitHubClient` with the latest commit SHA of `origin/main`.
- **Rejected**: A placeholder commit. Issue #5499 explicitly forbids placeholder commits.
- **Rejected**: `git push origin <sha>:refs/heads/<branch>`. Requires git clone and write access rather than the single GitHub API call.

### 3. Reuse `issue_holder` for foreign commits
- **Decision**: Reuse `issue_holder` to identify branches containing commits from a person or agent.
- **Rejected**: Re-implementing author detection in scaffold, which could diverge from `devops repos worktrees add`.

### 4. Branch naming
- **Decision**: Keep the plain branch form `<type>/<issue>-<slug>` using `branch_name` and `parse_branch`.
- **Rejected**: Candidate `-<i>` suffixes. Issue #5533 owns candidate branch extensions.

### 5. Orphan branch cleanup
- **Decision**: Remove deletion of App-only branches for Ready items in `_orphans`.
- **Rejected**: Keeping deletion of App-only branches for Ready items. Deletes checked plans after 1 hour.
- **Rejected**: Removing orphan cleanup completely. Non-Ready items and closed items still require cleanup.
