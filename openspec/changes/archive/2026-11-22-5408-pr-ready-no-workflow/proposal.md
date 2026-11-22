# Proposal: #5408

## Why
Closes #5408. `devops pr ready` waits for ever, and then refuses with "A check runs: no checks reported.", when the head commit of a pull request reports no check and no check will start. #5144 fixed this for a repository whose workflows list no `pull_request` or `pull_request_target` trigger. It did not fix a repository whose workflows list the trigger with a filter that skips the pull request. On 2026-11-18 and 2026-11-22, dan-petty/homelab PR #55 and PR #97 changed only `README.md` and `.github/renovate.json`. Both workflows of that repository run on `pull_request`, but their `paths` filters match neither file, so GitHub started no check, and `pr ready` needed `--force`. The trigger check reads the event names only: a workflow that lists `pull_request` counts as one that can start a check also when its `paths`, `paths-ignore`, `branches` or `branches-ignore` filter skips the pull request.

## What Changes
- A new module `src/devops_cli/github/workflow_triggers.py` decides whether one workflow file can start a check on a pull request. It reads the `on:` key, and for each `pull_request` and `pull_request_target` event it applies the branch filter to the base branch and the path filter to the files that the pull request changes, by the rules that GitHub documents. wcmatch matches each glob. The module holds the trigger set and the YAML read that `_runs_on_pull_request` in `src/devops_cli/github/client.py` held, and that function goes.
- `GitHubClient.pull_request_workflow_at` takes the base branch and the changed files of the pull request, as a `PullRequestChange`, and asks the new module about each workflow file.
- The merge-readiness verdict reads the changed files before it judges the checks, and gives the same read to the workflow filters and to the item rules. It reads no new endpoint.
- A filter that the change cannot judge keeps the wait, as today: an unread or truncated file list, an unknown base branch, a filter value that is no list of strings, both forms of one filter, or a pattern with GitHub's `?` or `+` quantifier or with a `**` inside a path segment, which wcmatch reads otherwise.
- The no-CI line of `pr ready` and of the verdict says that no workflow can start a check on the pull request, because a workflow can run on pull requests and still skip this one.
- The `pr ready` help text, `docs/commands/pr.md` and the MCP tool listing state the new rule.
- The change alters when `devops pr ready` and `devops pr check-readiness` wait and what they print, which is observable, so it carries a spec delta.
- The change fits one pull request.

## Capabilities
- `pr-merge-readiness`: MODIFIED requirement "pr ready does not wait for checks in a repository with no CI", because a workflow that runs on pull requests can still start no check on this one.
- `pr-merge-readiness`: MODIFIED requirement "pr ready waits for checks that a workflow can start", because the wait now depends on the filters too.
- `pr-merge-readiness`: MODIFIED requirement "The verdict reads the workflow triggers at the head commit", because the verdict also reads the branch and path filters of each pull request event, and a `pull_request_target` workflow keeps the wait.
- `pr-merge-readiness`: ADDED requirement "The pull request filters of a workflow follow GitHub's rules".
- `pr-merge-readiness`: ADDED requirement "A workflow filter that cannot be judged keeps the wait".

## Impact
- `devops pr ready` marks a pull request ready with no `--force` when the filters of each workflow skip it, and `devops pr check-readiness` gives no pending-check blocker for it.
- New runtime dependency: wcmatch 12.0.4 (MIT), with its dependency bracex 3.2.4 (MIT).
- The verdict makes no new request: the compare read of the changed files moves before the check judgement.

## Feasibility
- Code: on origin/main `9dfe03e3e`, `_runs_on_pull_request` at `src/devops_cli/github/client.py:411` reads only the names under `on:`, and `pull_request_workflow_at` at `src/devops_cli/github/client.py:725` returns true for each workflow that lists `pull_request`. `git grep -n "paths-ignore\|branches-ignore" -- src/` finds nothing, so no code reads a filter.
- Real system: `devops gh api repos/dan-petty/homelab/pulls/97/files` gives `.github/renovate.json` and `README.md`. The `pull_request` events of `k8s.yml` and `lint.yml` hold only `paths` filters (`k8s/**`, `scripts/k8s-checks.py*`, `**/*.yaml`, `**/*.yml`, `ansible/**` and more) that match neither file.
- Upstream rules: the workflow syntax reference of GitHub (`content/actions/reference/workflows-and-actions/workflow-syntax.md` and the reusables `triggering-workflow-branches1`, `3`, `4` and `triggering-a-workflow-paths1`, `3`, `4`, `5` of github/docs) says: `branches` and `branches-ignore` of `pull_request` and `pull_request_target` match the branch that the pull request targets; `paths` runs the workflow when one changed file matches, and `paths-ignore` skips it when every changed file matches; the last pattern that matches decides, and a `!` pattern excludes; the two forms of one filter cannot be used together; both filters must pass; no changed file means no run; the changed files are the three-dot diff of the pull request.
- Library probe: wcmatch 12.0.4 `globmatch` with `GLOBSTAR | DOTMATCH | FORCEUNIX` gives the documented answer for 19 of the 23 example rows of the filter pattern cheat sheet. It differs on `'*.jsx?'`, `'**.js'`, `v[12].[0-9]+.[0-9]+` and `releases/**-alpha`, because GitHub reads `?` and `+` as quantifiers of the character before them and `**` as a match of any characters also inside a segment. The change judges no filter that holds such a pattern.

## Existing Tool Considered
- wcmatch (https://pypi.org/project/wcmatch, MIT, last activity 2026-11-20, maintained) matches each glob. The alternatives check of 2026-11-22 names it for the `paths`, `paths-ignore` and `branches` filters. It reads no workflow YAML and no changed-file list, so the change keeps the YAML read (PyYAML) and uses the compare read that the verdict already makes.
- Rejected: pathspec 1.1.1, already a dependency. Its gitignore rules match a pattern with no slash at each depth: `*.md` matches `docs/hello.md`, but GitHub's `'*.md'` matches only root files.
- Rejected: the `NEGATE` flag of wcmatch. It ignores the order of the patterns: `['*.md', '!README.md', 'README*']` gives no match for `README.md`, but GitHub's cheat sheet says that the last pattern includes it again.
- Not usable: `pkg/workflowpattern` of nektos/act implements GitHub's quantifier rules, but it is Go code and has no Python package.
- Build cost of the rest: about 80 lines of code (the ordered rule of `!` patterns, the two forms of each filter, the cases that keep the wait) and about 20 tests; about 90k tokens and 1.5 hours to build, and a low cost to keep, because wcmatch does the matching.
- Internal code that the change deletes: `_runs_on_pull_request` and `_PULL_REQUEST_TRIGGERS` in `src/devops_cli/github/client.py`, which move into the new module.
