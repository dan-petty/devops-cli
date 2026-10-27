# Design

## Decision

`prune_worktrees` decides in two phases. The first phase decides every entry and reads GitHub; the second phase removes. A failed read in the first phase ends the run before any removal.

For each entry, in order:

1. The main worktree stays, even with `--force`.
2. With `--force`, the entry is removable and no later check runs.
3. A locked entry stays, with the lock reason.
4. An entry whose dirty count is unknown stays. An entry with uncommitted paths stays.
5. The entry is removable when `GET /repos/{repo}/commits/{tip}/pulls` returns a pull request with `merged_at` set and `head.sha` equal to the tip. The reason names the pull request. Any other answer keeps the entry: "no merged pull request has this commit as its head". HTTP 422 means that GitHub does not know the commit, which is the state of a commit that was never pushed, so it also keeps the entry. Any other failure of the read raises the error of the GitHub session.

The second phase runs `git worktree remove` (with `--force` under `--force`) only under `--confirm`. A non-zero exit of git becomes a `failed` item that carries the message of git, and the directory stays. The command exits 1 when any item failed.

`--dry-run` makes no external request. It decides steps 1 to 4 from git alone and returns the report with one `would check` item and one planned request for each entry that reaches step 5, and prints the plan with `render_request_plan`. This is the same layout as `roadmap intake --dry-run`.

The repository name for the requests is the `origin` remote, read with `get_repo_origin_name`. A checkout without a GitHub origin ends the run with an error that names the cause.

`GitHubClient.get_commit_pulls` is the one new GitHub call. It returns each pull request as `number`, `merged_at` and `head_sha`.

`worktrees status` loses the `contained` field. The field answered "is another ref at or after the tip", which does not mean that the work is merged, and `status` makes no GitHub request, so it cannot answer the real question. Its `dirty` field is `null` when `git status` fails.

## Rejected alternatives

- **Keep "contained" and add a minimum age.** A new worktree and a pushed branch stay "contained" for any age, and an old squash-merged branch stays uncontained. The four checked squash-merged tips are not in `origin/main`, so age does not change the result. Rejected.
- **Match the branch with `GET /repos/{repo}/pulls?state=closed&head={owner}:{branch}`.** This call is documented, but it needs a branch name, so a detached worktree cannot match, and a branch that was renamed after the push cannot match. The SHA call needs only the tip. Rejected.
- **Use `git cherry origin/main <branch>`.** It compares patch ids, and a squash that joins several commits has a different patch id. Rejected.
- **Skip the read for a worktree with no commit of its own.** A branch that was merged with a fast-forward has no commit of its own and a merged pull request, so the rule would keep it for ever. One rule for every entry is simpler. Rejected.
- **Keep the `shutil.rmtree` fallback behind `--force`.** The fallback hides the refusal of git, which is how a lock protects a worktree. Rejected.
