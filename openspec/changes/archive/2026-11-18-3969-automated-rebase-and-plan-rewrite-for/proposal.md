# Proposal

## Why

A merged plan is judged again by `devops roadmap plan-recheck`, and the mechanical rewrite of `plan_rewrite` can repair it on the default branch. An open plan pull request lives on its own branch, so a new plan rule strands it: the branch keeps the old format and an engineer must rebase it, edit it and push it by hand (#3969). The scope comments of 2026-11-11 add one rule: the pass pushes only when the rewrite changes the plan, never only to catch up with the default branch.

## What Changes

- `devops roadmap plan-recheck` gains the option `--branches`, which reads each open draft plan pull request whose base is the default branch.
- A new pass computes the mechanical rewrite of each branch head with `rewrite_plan`, judged against the default-branch tree.
- A branch whose rewrite changes no file gets no rebase and no push, so a branch that only fell behind is left alone.
- A rewritten branch is rebased in a temporary detached worktree, validated with the plan reader, the gates and the OpenSpec check, committed once and pushed with `--force-with-lease`.
- A rebase conflict aborts the rebase and pushes nothing; a rewritten plan that fails a check is not committed; each case records its reason.
- The push runs the pre-push hook `branch-current`, and the push event starts the checks of the pull request, so the pass dispatches no workflow.
- The dry run lists the reads of the pass, and the docs describe the option and the no-push rule.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-plan-recheck`: Plan-recheck processes the open plan branches, A branch is rebased only to apply a rewrite, Plan-recheck pushes a rewritten branch once with a lease, A conflict leaves the open plan branch unchanged, A rewrite that fails a check is not pushed, Plan-recheck writes nothing

## Impact

- Code: `src/devops_cli/roadmap/plan_branches.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/roadmap/plan-recheck.md`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`
- Tests: `tests/roadmap/test_roadmap_plan_branches.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py`

## Feasibility

- `probes`: The path `src/devops_cli/roadmap/plan_rewrite.py` is a file of the staging commit. The path `src/devops_cli/roadmap/plan_recheck.py` is a file of the staging commit. The mechanical rewrite that the issue cites is `rewrite_plan` and `write_rewrite` in `src/devops_cli/roadmap/plan_rewrite.py`.
- `probes`: The path `tasks.md` is no file at the root of the staging commit. The issue means the file of one change folder, which `rewrite_plan` rewrites; no root file is planned.
- `probes`: The path `ci.yml` is no file at the root of the staging commit. These files of the commit are candidates: `.github/workflows/ci.yml`, `tests/fixtures/research/advisories/github_repo/.github/workflows/ci.yml`, `tests/fixtures/research/repo/.github/workflows/ci.yml`. The repository workflow is `.github/workflows/ci.yml`.
- The premise is confirmed: `src/devops_cli/commands/roadmap.py:def plan_recheck_cmd` registers the command with `--source`, `--branch`, `--json`, `--dry-run` and `--confirm`, and `src/devops_cli/roadmap/plan_rewrite.py:def write_rewrite` writes the rewrite to the working tree of `--source` and makes no commit. The option `--branches` does not exist at the staged commit.
- The push gate that #4670 delivered is a pre-push hook, not a function: `search_code` for `def push_branch` found only `tests/support/roadmap_stage.py:84:def push_branch(self, branch: str, *, author: str = "Person") -> None:`, and `docs/SDLC.md:321:**Current Branch at Every Push**: Immediately before each push to GitHub, the first push included, fetch` states the rule that the pass meets by rebasing before the push.
- The scope comments of 2026-11-11 answer the body: the pass pushes only when the rewrite changes the plan, pushes through that hook, and never rebases a branch only to catch up. The two tests that the comments ask for are `test_only_the_base_moved_pushes_nothing` and `test_a_rewrite_pushes_exactly_once` in `tests/roadmap/test_roadmap_plan_branches.py`.
- `src/devops_cli/roadmap/steps/fix_plan.py:def _push` already rebases a rewritten plan onto the latest default branch and pushes it with a lease, and `src/devops_cli/roadmap/clone_git.py:def checkout_at` gives the detached worktree; the pass reuses both patterns and adds no new git program.
- `src/devops_cli/roadmap/plan_check.py:def is_plan` and `src/devops_cli/roadmap/plan_check.py:def read_pull` select the plan pull requests, as `src/devops_cli/roadmap/stage/plan_drift.py:def run_plan_drift` does for the drift row.
- Precondition of `store.open_pulls()` of `src/devops_cli/roadmap/stores/store.py:def open_pulls`: a client of GitHub, because it reads the open pull requests of the repository.
- Precondition of `read_pull(reads, repo, number)`: a client of GitHub, because it reads the title and the body of the pull request.
- Precondition of `default_branch(source, operation=...)` and `checkout_at(source, head, operation=...)`: a checkout of the repository, because they read `refs/remotes/origin/HEAD` and run `git worktree add`.
- Precondition of `git(tree, "fetch", ...)` and `git(tree, "rebase", ...)`: a checkout of the repository; of `git(tree, "push", ...)`: a checkout of the repository, a network and the login of the remote.
- Precondition of `rewrite_plan(root, files, tree)` and `write_rewrite(source, rewrites)`: a checkout of the repository, because they read and write its files.
- Precondition of `validate_change(tool, source, folder, files)`: the `openspec` program of the image and a checkout of the repository; of `recheck_plans(source, store, tool=..., branch=...)`: a checkout of the repository and a client of GitHub through the store.
- The groups introduce no new command program: `uv run devops ci test` runs `pytest` from the image (RUNNER_TOOLS holds `pytest`), and `uv run devops ci docs` runs the docs row. The failure classes are `test` and `lint`, and the pod settings that apply are `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false` and `capabilities.drop: ALL`.
- First checks against the real system: `uv run devops roadmap plan-recheck --help` lists the options that the command has at the staged commit; `uv run devops roadmap plan-recheck --source <clone> --json` judges the default branch of the clone and pushes nothing; `git -C <clone> ls-remote --heads origin` before and after shows the same heads; `uv run devops ci test tests/roadmap/test_roadmap_plan_recheck.py tests/commands/test_roadmap_plan_recheck_cmd.py` passes.
- Not checked: whether the push event starts `.github/workflows/ci.yml` for a branch head. The pass dispatches nothing, and the checks of the pull request read the new head.
- `references` for `plan-recheck` found 55 files and 154 lines; the change edits the command, the help, the messages, the request plan, the docs and the two test modules that the groups name.

## Existing Tool Considered

30k tokens to build and 4 hours, then 6k tokens a year to keep: cli/cli (MIT, maintained) updates a pull request branch with `gh pr update-branch`, but the alternatives check of 2026-11-09 records that it applies no mechanical rewrite and validates no plan, so the change builds the rewrite pass in `src/devops_cli/roadmap/plan_branches.py`. The change deletes no internal code.

## Dependencies

None.
