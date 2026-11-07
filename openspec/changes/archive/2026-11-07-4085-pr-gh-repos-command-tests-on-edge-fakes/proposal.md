# Proposal

## Why

Issue #4085 is group 2 of #3769. The tests of the `pr`, `gh` and `repos` commands patch names inside `devops_cli`. The rule of `docs/TESTING.md` is that a test doubles only an edge. #1336 turns the ratchets of #1309 into bans, and the patches block it.

An AST count at `origin/main` 74ba76b8 finds 266 string patches of a `devops_cli` name in nine files:

- `tests/commands/test_pr_cmd.py`: 84
- `tests/commands/test_gh_cmd.py`: 53
- `tests/commands/test_pr_update.py`: 51
- `tests/commands/test_repos.py`: 41
- `tests/commands/test_pr_form_check.py`: 9
- `tests/commands/test_pr_status.py`: 9
- `tests/commands/test_pr_dry_run.py`: 7
- `tests/commands/test_pr_title_labels.py`: 6
- `tests/commands/test_github_milestones.py`: 6

The patches replace `run_gh`, `check_binary`, `load_settings`, `get_repo_origin_name`, `time.sleep`, the private helpers of the commands, and the functions of the `github` package that the commands call.

## What Changes

- Each test reaches its edge through a shared double:
  - `gh` and `git` go through `process_fake`. The new fixture `gh_edge` in `tests/support/gh_process.py` records a fresh quota in the rate limiter and returns the fake. It comes with `answer_gh`, `script_gh`, `mentions`, `answer_origin` and `gh_argv`.
  - The GitHub session goes through `github_api` (`github_api_and_gh` where a command reads both ways).
  - The roadmap goes through `roadmap_store`, and the status, the labels and the form check of `pr create` run for real on it.
  - Settings go through the `config` fixture. Waits go through `clock`. An MCP tool goes through `mcp_dispatcher`.
  - The project board of `gh project reconcile` goes through `ProjectGitHub.install`, which hangs the board on `process_fake` and `github_api`. `tests/github/test_github_projects_reconcile.py` calls it too.
- A test that called a private helper (`_fallback_create_pr`, `_render_pr_list_fallback`, `_execute_update_branch`, `_get_repo_labels`) now runs the command and reads its output and the commands that `gh` received.
- A test of the mutation budget used a patched `MutationBudget`. It now builds a board that is larger than the default budget.
- A test of the cache options of `gh api` read the keyword arguments of a mocked `run_gh`. It now reads when `gh` starts again, with the clock.
- Each test keeps its node id (346 ids before and after). The behavior that each test checks does not change.
- No file under `src/` changes. The change has no spec delta, and `skip_specs: true` is set.
- Left for a later item of #3769: four tests of `tests/commands/test_repos.py` still import private helpers of `devops_cli.commands.repos` (`_current_branch`, `_resolve_workspace_file`, `_list_git_tracked_files`, `_reload_workspace`). Issue #4085 asks for no string patch, and these imports were there before. The follow-up item for private imports owns them. No ceiling is raised.
- Result: 266 string patches of a `devops_cli` name before, 0 after. No ratchet on these patches exists yet (`docs/TESTING.md`, "Floor and ratchets"), so no ceiling changes.

## Impact

- `tests/commands/` (nine files), `tests/support/gh_process.py` (new), `tests/project_reconcile_fake.py`, `tests/github/test_github_projects_reconcile.py` and `docs/TESTING.md`.

## Feasibility

Checked on `origin/main` a224adbb, 2026-11-07.

- The count of #3769 still holds in kind. A count with the `ast` module finds 266 string patches in the nine files (the grep count of the issue is lower because a patch can span lines).
- Every edge that the commands reach has a double: `gh` and `git` run through `run_subprocess`, which `process_fake` replaces (`src/devops_cli/core/process.py`). The rate limiter reads `gh api rate_limit` first, and `update_quota` records a fresh quota without a start of `gh` (`src/devops_cli/github/rate_limiter.py`).
- The commands are thin enough: no logic had to move into a domain package.
- Faults put into `src` made the migrated tests fail: `repos update` that never pulls, `repos clone` that does not reload the workspace, `pr create` that sets no Status, a REST fallback that opens a non-draft pull request, a head poll that does not wait, `update --all` that runs newest first, `gh api` that drops `--paginate` or never caches, and a reconcile budget that is not the default.

## Existing Tool Considered

`pytest` with the fakes of `tests/support/fakes/` (process, GitHub session, roadmap store, clock, MCP dispatcher) and the `config` fixture covers the need. No new tool is needed. The one new helper module, `tests/support/gh_process.py`, holds about 90 lines for the gh answers that nine files repeat. It deletes the patches of `run_gh`, `check_binary`, `get_repo_origin_name` and `time.sleep` in those files.
