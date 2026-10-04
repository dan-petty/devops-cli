# Task: Item closure summaries and automatic release cut (`devops roadmap close`) (#743)

**Issue**: [#743](https://github.com/dan-petty/devops-cli/issues/743)
**Status**: Done
**Milestone**: v0.2.26
**Priority**: priority/p1-high
**Scope**: type/feature, scope/release, priority/p1-high

## Description

`devops roadmap close` is the closure job. One run reads every pull request merged into the current release's branch, closes each item they deliver with a two-part summary, and, once the release holds no open item, cuts it through #982's shared `cut_release`. The cut writes no changelog section: fragments reach `main` uncollected (owner decision, #1103).

- **Store slice**: `RoadmapStore.merged_pull_requests(base)` returns `MergedPullRequest` records (number, URL, body, labels, milestone, merge commit, head commit, changed paths). The GitHub adapter reads `repos/{repo}/pulls?state=closed&base=…` and each merged pull request's `files` listing a full page at a time, failing closed on any page; the in-memory adapter adds `merge_pull_request`. Its existing `job_writes()` log is what tests read.
- **Closure** (`src/devops_cli/roadmap/close.py`): closing keywords are parsed by `extract_linked_issues` with the repository, so `Part N of #M`, keywords in code or quotes, other repositories' issues and pull request numbers close nothing. The comment is a fixed template: the pull request link and merge commit, the first section of the body quoted and capped at `DEFAULT_ROADMAP_CLOSE_SUMMARY_CHARS`, the changed-file count, each check run at the head commit with its bucket, and the Acceptance Criteria of each `docs/agent/tasks/task-<N>-*.md` the pull request changed, read at the merge commit (or "No task file"). Markdown sections are found with markdown-it-py, task-file names with `PurePosixPath.full_match`.
- **The cut**: the current release is the lowest open Release. It is cut when it has no open item, at least one item closed as completed, and no release pull request open or merged: `chore/cut-vX.Y.Z` into the default branch with label `release` and its milestone. `cut_release` gains an `edits` hook that the job uses to write `docs/ROADMAP.md` (`render_roadmap`) on the cut branch before the commit; it is called with `draft=False`, `sync_docs=False` and the default branch as base. Completed items with no `changelog.d/<N>.md` on the release branch are listed, and the cut still happens.
- **Modes**: `--confirm` writes; no flag or `--plan` reads and prints each closing with its comment and the cut or what holds it, ending with the GraphQL spend line; `--dry-run` makes no request and lists the requests a run makes (`close_requests`), built with the store's argument builders, `pr_checks_args`, `milestone_issues_args`, `milestone_pull_requests_args` and `_build_release_pr_command`. The MCP mirror `roadmap_close` takes `plan` or `dry-run` only.
- **Removed**: `devops gh issues close-merged`, its help strings, and the sweep functions in `github/issue_closure.py`. `extract_linked_issues` and `strip_non_prose` stay.

## Acceptance Criteria

**Store slice**
- [x] The contract suite reads merged pull requests: `tests/test_roadmap_store_contract.py::test_merged_pull_requests_are_the_ones_merged_into_the_branch_with_their_paths`.
- [x] A three-page listing returns every merged pull request with its files, and a failed page or files listing raises: `tests/test_roadmap_github_store.py::test_merged_pull_requests_read_every_page_with_each_ones_files`, `::test_a_failed_merged_pull_request_page_raises_and_returns_no_part` (pages 1 to 3), `::test_a_failed_files_listing_raises`.

**Closure** (`tests/test_roadmap_close.py`)
- [x] `Closes #1` closes #1 as completed with one comment holding the link, merge commit, first section, file count, check buckets and the task file's Acceptance Criteria: `::test_a_merged_pull_request_closes_its_issue_with_a_two_part_comment`.
- [x] `Part 1 of #N`, a code block, a quote, inline code, another repository and a pull request number close nothing: `::test_these_bodies_close_nothing`.
- [x] No task file gives "No task file"; a changed task file is quoted: `::test_a_pull_request_without_a_task_file_says_so` and the first test.
- [x] Five merged pull requests close five issues, the oldest included: `::test_five_merged_pull_requests_close_five_issues_including_the_oldest`.
- [x] An already-closed issue gets no comment and a second run writes nothing: `::test_a_closed_issue_gets_no_comment_and_a_second_run_writes_nothing`.
- [x] A failed merged-PR, issue or check-run read exits non-zero, names it, never says nothing to close, and leaves the issue open: `::test_a_failed_read_exits_non_zero_naming_it_and_the_issue_stays_open`.

**When to cut**
- [x] Held by an open item (listed), an open release PR, a merged one, and nothing delivered; cut when all are closed, with a closed unmerged release PR and a PR from another head ignored, and the lowest open release chosen: `::test_when_to_cut`, `::test_no_open_release_holds_with_no_release`.

**Cut mechanics**
- [x] From a clone on another branch, `chore/cut-v0.2.26` is pushed with the remote `release/v0.2.26` tip as parent; `release/v0.2.26` and `main` don't move; the commit changes exactly `docs/ROADMAP.md`, `pyproject.toml`, `src/devops_cli/__init__.py` and `uv.lock`; `gh pr create` gets base `main`, head `chore/cut-v0.2.26`, title `feat(release): v0.2.26`, label `release`, milestone `v0.2.26`, no `--draft`; a completed item without a fragment is named; `gh` never gets `pr merge` or `pr review`: `::test_the_cut_pushes_the_cut_branch_from_the_release_tip_and_opens_a_ready_pr`.
- [x] After the release PR closes unmerged and another item merges, the next run rebuilds the cut from the new tip with the new fragment uncollected and `CHANGELOG.md` identical to the tip: `::test_a_cut_after_an_unmerged_release_pr_rebuilds_from_the_new_tip`.
- [x] The cut names the missing fragments and the fragments present: `::test_the_cut_names_the_branch_base_title_and_missing_fragments`.

**Dry run and preview**
- [x] A run without `--confirm` prints each closing with its comment and the cut, writes nothing, changes no git ref and runs no `gh`: `::test_a_run_without_confirm_previews_and_changes_nothing`.
- [x] `--dry-run` makes no request and lists the reads, the closes and the cut's git and `gh` commands, with no `--draft`: `::test_the_dry_run_lists_the_closes_and_the_cut_without_a_request`, `::test_the_dry_run_command_makes_no_request_and_names_the_cut_files`, and `close` added to `tests/test_roadmap_dry_runs.py`'s jobs (entry-point probe).
- [x] `roadmap_close` takes `plan` or `dry-run` only: `tests/test_fastmcp_contracts.py::test_the_roadmap_tools_are_registered_and_migrate_only_previews`.

**Removal, docs and gate**
- [x] `rg -n "close-merged|close_issues_for|get_issue_states|list_merged_pull_requests" src tests docs -g '!docs/ROADMAP.md' -g '!docs/agent/tasks/**'` finds nothing; the parser tests stay in `tests/test_gh_issue_closure.py`.
- [x] `docs/ROUTINE_TASKS.md` (Cadence C and its table row) and `docs/SDLC.md` describe the cut as `devops roadmap close`, with `release prepare --create-pr` as the manual fallback; `docs/MCP_TOOLS.md` lists `roadmap_close`; `uv run devops docs check` passes.
- [x] Fragment only: `changelog.d/743.md`; `CHANGELOG.md` and `docs/ROADMAP.md` are untouched. Every new test runs offline in under 1 s.
- Pending a person: once every item of the current release is closed, `uv run devops roadmap close --plan -R dan-petty/devops-cli`, then `--confirm` from a clean clone; `gh pr view <n> --json headRefName,baseRefName,labels,milestone,isDraft` shows head `chore/cut-vX.Y.Z`, base `main`, label `release`, milestone `vX.Y.Z`, `isDraft: false`; `git fetch origin && git show --stat origin/chore/cut-vX.Y.Z` lists the files above (plus the service image tag #982 bumps), the PR's checks pass, and `gh issue view <item> --comments` shows one two-part comment on each item closed in that run.
- Pending a person: close #778 as not planned if it is still open (superseded by this command).

## Decisions and deviations

- **Preview vs dry run**: per #412, `--dry-run` makes no request, so it lists requests, not issues; the issues with their comments, the fragments and the missing ones are in `--plan` (and a run without `--confirm`).
- **Release items come from the issue listing**, not the board: the cut predicate reads each issue's milestone, state and close reason from the REST listing it already reads to find closable issues, so it spends no GraphQL points; open items holding the cut are listed by number and title, without their board Status.
- **Release PR predicate**: the cut requires head `chore/cut-vX.Y.Z`, base the default branch, label `release` and the milestone. The store's shared `is_release_pull_request` keeps no head test so a renamed Release keeps its pull request (reprioritize); its docstring now names the cut branch.
- **Fragments present** are read per completed item (`changelog.d/<N>.md` at the release branch through `repository_file`), not by listing the directory.
- **Unreadable check runs hold the cut** as well as their issues, so a run never cuts with a delivery unclosed.
- **`cut_release(edits=…)`**: the one addition to #982's function, run after the bump and before the commit.
