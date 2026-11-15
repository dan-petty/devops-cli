# Design: #5020

## Decisions

### 1. One open step module and command
- **Decision**: Add `src/devops_cli/roadmap/steps/open.py` with `open_or_update(request)` and `devops roadmap step open`. It returns the pull request number and one result of `created`, `updated`, or `unchanged`.
- **Rejected**: Leaving pull request creation duplicated across `stage.py`, `implement_run.py`, and `pr.py`.

### 2. Lookup existing open pull request first
- **Decision**: Query the open pull requests matching head and base branches using `GitHubClient.find_open_pull`. When found, update only the fields that differ (title, body, labels).
- **Rejected**: Unconditionally calling `create_draft_pull` and handling 422 errors. A direct lookup prevents unintended side effects and respects API quotas.

### 3. One retry on refused text
- **Decision**: When GitHub refuses text on the first creation attempt, retry once with form-checked text (#3599).
- **Rejected**: Failing immediately without retrying form-checked text.
- **Rejected**: Multiple retries or calling an LLM model, which adds unbounded latency and cost.

### 4. Status writer and marks
- **Decision**: For delivery pull requests, write In Progress status via `status_sync.write_status`. Record `<kind>.pr` in the item record and upsert marked comment if provided.
- **Rejected**: Setting status labels directly, which violates the architectural invariant of #5018.

### 5. Sweep recovery and refusals
- **Decision**: Support sweep recovery when the branch head matches `checked_sha` in the record and no open pull request exists for that head and base, spending at most 3 requests. Refuse second open pull request for an issue, and refuse heads with `[skip ci]` in the commit message.
- **Rejected**: Allowing multiple open pull requests for the same issue.

## Rejected alternatives
- Adding another script or wrapper around `gh pr create`: Subprocess wrappers obscure error handling and fail to provide typed programmatic return values.
