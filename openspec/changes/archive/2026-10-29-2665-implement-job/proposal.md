# Proposal

## Why

Issue #2665, the second sub-issue of #2661. The step of #2664 runs one task group of a staged change. Nothing runs the groups of a change in order, archives the change, rewrites the pull request, watches its checks or marks it ready.

`devops roadmap implement` with no `--group` is the job. It takes each Staged item that a label filter names, runs the unticked groups of its `tasks.md` with the step, regenerates the documentation, archives the change, pushes, rewrites the pull request body to close the issue, watches the checks, runs one fix step for a failed check, and marks the pull request ready when the checks pass. A person merges.

The merged step is not a security boundary. Its shell checks only the first word of a command, so `uv run python -c` still runs code, and it relies on the runner of sub-issue #2667 for the sandbox and for an environment with no credential. The job therefore refuses to run a step unless the setting `roadmap.implement.in_runner` is true. That setting is true only in the pod of a runner Job. The Service pod and a workstation keep it false, so they never run a step, whatever credential they hold. The job runs every `git push`, every pull request call and every GitHub write itself, in its own process, with the credential that the job holds. The agent shell gets none of them.

## What Changes

- `devops roadmap implement` gets the job mode. With `--group` it is the step of #2664, unchanged. Without `--group` it is the job: `[--repo] [--source] [--item N | --filter family=value]... [--limit 1] [--dry-run | --plan | --confirm]`. A new module `roadmap/implement.py` selects and plans, `roadmap/implement_run.py` writes, and `roadmap/implement_pull.py` holds the pull request calls.
- Selection. The default filter is `status=ready priority=p0-critical priority=p1-high type=bug effort=low`. The job takes a Staged item: `stage.pr` and `stage.branch` in its record, the branch on `origin`, the draft open. It leaves out an item with `implement.stopped`, an item whose author is not trusted, an item with a commit on its branch by anyone but the App, an item that is not Ready, and an item that a worktree holds. Each left-out item has a reason in the plan. `--limit` defaults to 1.
- The run of one item. Status In Progress, then rebase of the staged branch onto `origin/<default>` in a worktree that `worktrees add` takes over. Then one step for each group that has an unticked task. Then `uv run devops docs generate --sync-readme` and `uv run devops openspec archive <change>`, one commit each, and the push. Then the pull request body `Closes #N`, the why of the proposal and the `Change:` line, and one comment on the pull request with the outcome of each step. Then `monitor_pr`. A failed check runs one fix step. The second failure stops the item. Checks green and no open thread: `gh pr ready`, Status In Review, and one comment on the issue with the pull request and the spend.
- The fix step is the step of #2664 with a synthetic group, "Make check `<name>` pass". Its input is the log of the failed check, cut to `CONST_ROADMAP_IMPLEMENT_LOG_CHARS` characters from the end. It must leave `tasks.md` as it was. Its verification is the union of the verification commands of the change.
- A stop. The job comments on the item with the step, the reason and the last message of the agent, sets Status to Ready, and records `implement.stopped`. It pushes the commits of the steps that passed, so the branch keeps the work. The job never retries a stopped item. A comment `implement: retry` by a trusted author after the stop clears the record, and the next run takes the item again.
- The job record gets the keys `implement.group`, `implement.sha`, `implement.pr`, `implement.stopped` and `implement.spend`. The marker `<!-- devops roadmap implement -->` heads every comment of the job on the item.
- Small supports: `GitHubClient.get_pull_status`, `update_pull_body` and `comment_on_pull`; `IssueComment.author_association`; `parse_filters` takes the default filter as a parameter.
- A consumer observes the command, the setting and the writes, so the change carries spec deltas: a new capability `roadmap-implement-job`, and one added requirement in `roadmap-implement-step` for the fix step.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-implement-job`: which items the job takes, what it writes to git and to GitHub, and when it stops.

### Modified Capabilities

- `roadmap-implement-step`: one added requirement, "A fix step makes a failed check pass".

## Impact

- `src/devops_cli/roadmap/implement.py`, `implement_run.py`, `implement_pull.py` (new), `implement_step.py`, `stage.py`, `store.py`, `github_store.py`, `memory_store.py`, `request_plan.py`.
- `src/devops_cli/github/client.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/config/settings.py`, `constants.py`, `defaults.py`, `src/devops_cli/lang/en/messages.py`, `help.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
- `CONTEXT.md`, and the documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The merged step, read in `roadmap/implement_step.py`, gives `run_step` for a group of a checkout and `StepOutcome` with the commit, the reason and the spend. The job calls it for each group. For the fix step, `build_step_inputs` takes a synthetic group, and the exit checks keep their order. The change to the step is small, and the existing tests of the step keep their meaning.
- `worktree_add.add_worktree` takes over a staged branch when the App wrote every commit past `origin/main`. It fetches the branch, checks the authors with `git log --format=%an` against `service.github_app.bot_login`, and adds a worktree that tracks the branch. The job uses it as it is, and selects with the same author rule.
- `github.pr_monitor.monitor_pr` is a library function: it waits until no check runs, and returns the status with the failed checks, the unresolved threads, the head commit and the mergeability. Read from the source and from a run on a scripted pull request: right after a push, GitHub can still show the old head with the checks of the old head, and a head that holds no check yet reads as a pending check, so the monitor waits for it. A status whose head is not the pushed commit is not a result. The job polls again for that case.
- The failed log. A failed check item holds its `link`, `https://<host>/<owner>/<repo>/actions/runs/<run>/job/<job>`. `run_view.fetch_workflow_run_view(run, log_failed=True, job=<job>)` runs `gh run view --log-failed`. The job reads the run and the job from the path segments of the link with `urllib.parse.urlsplit`. A link with another shape gives an empty log, and the fix step then works from the check name alone.
- Marking ready needs GraphQL, which the REST client of the session does not offer. `gh pr ready` does. The job runs it through `run_gh`, which paces and classifies the call, as `devops pr ready` does.
- The environment of the agent shell. Read in `pydantic_ai/workspaces/local.py` of pydantic-ai 2.59.0: a local workspace passes `PATH`, `HOME`, `LANG`, `LC_ALL` and `LC_CTYPE` of the host, plus its own `env`. The step sets `HOME` to a scratch directory. So the shell gets none of the variables of the job, and the git configuration of the job's user, with its credential helper, is out of its reach. A process of the same user can still read `/proc/<pid>/environ` of the job. So the runner pod is the boundary, and the token it holds must be as narrow as #2667 makes it: one repository and a short life. The job writes no secret to disk.
- The comments of a person. `IssueComment` has no author today. The REST payload of a comment has `author_association`, so the change reads it. The retry comment counts only from the owner, a member or a collaborator.

## Existing Tool Considered

`devops pr monitor` (`monitor_pr`), `gh pr ready`, `devops openspec archive`, `devops docs generate`, `worktree_add.add_worktree` and the step of #2664 cover the parts of the work. The job builds only what none of them gives: the selection of a Staged item, the loop over the groups, the pull request body, the single fix step and the records. It uses `urllib.parse` for the link of a check and `textwrap` for the length of the body. It writes no parser of its own.

Cost of what the change builds, estimated: about 1,400 lines of code and tests, about 450k tokens of agent work, and two days of elapsed time. Upkeep is small: the job follows the interfaces of `monitor_pr`, the store and the step.

The change deletes no code. It moves the default filter of `parse_filters` into a parameter, and makes `priority_order` of `stage.py` public.
