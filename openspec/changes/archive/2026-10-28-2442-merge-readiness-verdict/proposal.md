# Proposal

## Why

Issue #2442, part 1 of #998: the merge-readiness rules of `devops pr check-readiness` lived inside the Typer module `src/devops_cli/commands/pr.py`, about 620 lines from `_check_mergeable_blocker` to `_evaluate_pr_blockers`. The rules printed their own warnings and information lines while they decided, so no other caller could get the verdict as data. The item rules (`_closes_one_issue` and the eight others) were private helpers of the command module, and the readiness tests patched `devops_cli.commands.pr.run_gh`, imported private names and replaced the GitHub session.

## What Changes

- New module `src/devops_cli/github/merge_readiness.py`. `assess_merge_readiness(pr_data, owner, repo_name, number, *, options, runner, session, review_root)` returns a `MergeReadiness`: the blockers, the advisories (the warnings and information lines of today), the checks still running, the review threads that block, and the grounding facts. It prints nothing and raises no `typer.Exit`. Each `gh` call goes through `runner` and each read of the GitHub session through `session`, as `GitHubRoadmapStore` takes them. `read_changed_files`, `read_closing_issues`, `closing_issues_args` and `perimeter_advisory` are public.
- New module `src/devops_cli/roadmap/grounding.py`: the item rules as public pure predicates over the `Grounding` facts (`targets_the_default_branch`, `closing_issues_were_read`, `closes_one_issue`, `closes_an_issue_of_its_repository`, `closes_an_open_issue`, `closes_an_item`, `changed_files_were_read`, `archives_its_change`, `writes_only_its_own_record`), in `GROUNDING_RULES`, with `grounding_blockers`.
- `devops pr check-readiness` reads the verdict and renders it: the advisories, then the table of the review threads that block, then the blockers or the success line. Its exit codes and its lines do not change. The thread table now prints after the advisories, not between them.
- `github/check_verdict.py`: the private `_fetch_checks_from_rest` becomes the public `read_commit_checks(owner, repo_name, head_sha, *, runner, session)`. `github/pr_monitor.py` calls it by that name.
- `github/pr_threads.py`: `list_pr_review_threads` takes an optional `runner` for its `gh` calls.
- Deleted from `commands/pr.py`: the readiness block, and `_classify_check_run`, which no code called.
- Tests: the readiness tests in `tests/test_pr_cmd.py` and all of `tests/test_pr_check_runs.py` go, with the `routed_session` fixture that replaced the GitHub session. The rules are tested in `tests/test_item_grounding.py` (a table for each rule) and `tests/test_merge_readiness.py` (the verdict over the two GitHub edges), and the command in `tests/commands/test_pr.py` (a table of exit codes and lines). The new support fixture `github_api_and_gh` serves the session over `GitHubApiFake` and sends `gh` to `process_fake`.
- No behavior a consumer observes changes, so the change has no spec delta (`skip_specs: true`). The `pr-grounding` requirements stay true as written.
- This change fits one pull request.

## Impact

- `src/devops_cli/commands/pr.py`, `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/roadmap/grounding.py`, `src/devops_cli/github/check_verdict.py`, `src/devops_cli/github/pr_threads.py`, `src/devops_cli/github/pr_monitor.py`.
- `tests/commands/test_pr.py`, `tests/test_merge_readiness.py`, `tests/test_item_grounding.py`, `tests/test_pr_cmd.py`, `tests/test_github_pr_monitor.py`, `tests/support/fakes/github.py`; `tests/test_pr_check_runs.py` is deleted.
- `docs/SELF_IMPROVEMENT.md` (where the perimeter warning lives) and `docs/TESTING.md` (the new fixture).

## Feasibility

- On origin/main 4226904e the readiness block of `commands/pr.py` ran from `_check_mergeable_blocker` to `_evaluate_pr_blockers`, and only `check_readiness` called `_evaluate_pr_blockers`. `pr ready` read its checks through `check_verdict.fetch_pr_check_verdicts`, and `pr monitor` judged with its own rules in `github/pr_monitor.py`, so moving the block changes neither. #2443 moves those two commands onto the verdict.
- The MCP tool `pr_check_readiness` is generated from the Typer command (#997) and runs it in-process through `CliRunner` (`ai/mcp/dispatcher.py`). It spawns no `devops` process, so it follows the command with no change.
- `_changes_its_task_file`, which #998 names, no longer exists: the item rules are the OpenSpec archive rules and the `priority/*` rule of ADR 0016.
- `docs/TESTING.md` allows a test to install an edge's fake "through a constructor or parameter the domain code already takes". The verdict takes `runner` and `session`. The tests use the real `run_gh` and the real session, with `process_fake` and `GitHubApiFake` at their edges.
- Two mutations of the verdict (a draft never blocks; every unresolved thread counts as replied) each made tests fail in `tests/test_merge_readiness.py` and `tests/commands/test_pr.py`.

## Existing Tool Considered

No open tool judges a pull request by this repository's own rules: one open roadmap Item, its archived OpenSpec change, and the `priority/*` label. GitHub's mergeable state, check runs and review threads stay the inputs, read through `gh` and the GitHub session (gidgethub) as before. The change moves code and builds nothing new. It deletes the readiness block of `commands/pr.py`, `_classify_check_run`, the `routed_session` fixture and `tests/test_pr_check_runs.py`.
