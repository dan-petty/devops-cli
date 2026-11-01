# Proposal

## Why

Issue #2258 (part of #886) says that 24 `branches`, `repos`, `ssh` and `tls` commands do not obey the dry-run rule of #412. The rule says that a dry run makes no external request and lists the requests that a real run would make.

Today these commands do one of three things under a dry run:

- `devops --dry-run <command>` prints only `Would run delegated command` (the commands without a `--dry-run` option).
- `devops <command> --dry-run` prints a JSON echo of the arguments (the commands with an echo-only preview).
- `devops branches sync --dry-run` fails with `No such option: --dry-run`.

None of these shows the requests. This change fixes all 24 commands and removes each one from `tests/fixtures/dry_run_gaps.json`.

## What Changes

The issue sorts the 24 commands into 9 request plans and 15 mark-only commands. The check below (see Feasibility) shows that one row is wrong: `repos worktrees prune` makes GitHub requests, so it is a request plan. The result is 10 request plans and 14 mark-only commands.

- Request plans (10): `branches sync`, `branches update`, `repos clone`, `repos clone-org`, `repos sync`, `repos update`, `repos worktrees prune`, `ssh register`, `ssh rotate` and `tls enable-k8s`.
  - Each carries `@dry_run_class("request-plan")` and declares `--dry-run`.
  - Each dry run makes no external request and prints the numbered requests with `render_request_plan`.
  - The argv of each planned request comes from the same function that the real run calls. This function is new for all of them except `repos worktrees prune`, which already has a plan (`plan_prune`) and needs only its class.
  - The new functions sit in `src/devops_cli/git/git_plans.py` (new), `src/devops_cli/github/ssh_plans.py` (new) and `src/devops_cli/crypto/tls_plans.py` (new). The argv builders they share with the real run sit in `src/devops_cli/git/operations.py`, `src/devops_cli/github/client.py`, `src/devops_cli/github/ssh.py` and `src/devops_cli/crypto/ssh_keys.py`.
- Mark-only commands (14): `branches clean`, `branches jira`, `branches list`, `repos list`, `repos worktrees status`, `ssh audit`, `ssh generate`, `ssh list`, `ssh status`, `tls ca`, `tls cert`, `tls homelab`, `tls inspect` and `tls verify`.
  - Each carries `@dry_run_class("no-external-request")`.
  - A command that only reads (`branches list`, `repos list`, `repos worktrees status`, `ssh audit`, `ssh list`, `ssh status`, `tls inspect`, `tls verify`) runs normally under `devops --dry-run`. It has no `--dry-run` option.
  - A command that writes local state (`branches jira`, `ssh generate`, `tls ca`, `tls cert`, `tls homelab`) keeps or gets a `--dry-run` that prints one `Would ...` line and writes nothing. `branches clean` keeps its own `--dry-run`, which is a real local preview. See design decision 4 for the reason.
- The 13 calls of `render_dry_run_result` in `commands/repos.py`, `commands/ssh.py` and `commands/tls.py` are deleted, with no shim.
- The 24 entries leave `tests/fixtures/dry_run_gaps.json`. The ratchet test `tests/invariants/test_dry_run_class_ratchet.py` stays as it is.
- The change alters what a person observes (a command, an option and a message), so it carries a spec delta in the capability `command-dry-run-class`.
- The change fits one pull request. It has eight task groups. Each group is one implementation step.

## Capabilities

### Modified Capabilities

- `command-dry-run-class`: six ADDED requirements, one request-plan requirement and one no-external-request requirement for each of the families `git-workspace` (`branches` and `repos`), `ssh` and `tls`.

## Acceptance

The acceptance criteria of #2258, from the issue body, and the group that delivers each one:

- Each command is out of `tests/fixtures/dry_run_gaps.json` and the ratchet test passes: groups 1 to 7 each remove their commands. Group 8 checks that no entry of the four families is left but `repos worktrees add`, which the issue does not list.
- For each request-plan command, `devops <command> --dry-run` and `devops --dry-run <command>` make no external request and print the ordered requests: groups 1, 2, 3, 5 and 7. Each test runs both forms on fakes (`git_fake`, `process_fake`, `github_api`).
- For each request-plan command with `--format json` or `--json`, the dry run returns the real result type with the planned requests: only `repos worktrees prune` has such an option. It already returns `WorktreePruneReport` with `requests`, and `test_prune_dry_run_makes_no_request_and_lists_the_requests` (`tests/git/test_repos_worktrees.py`) checks it. Group 2 keeps that test. No other request-plan command has `--format` or `--json`, so no task adds one.
- For each request-plan command, the plan holds the requests of the real run in the same order, checked against a fake that records each call: groups 1, 2, 3, 5 and 7 add the test. For `repos worktrees prune` the existing tests `test_prune_without_confirm_reads_github_and_removes_nothing` and `test_prune_dry_run_prints_the_request_plan` compare the same request.
- For each mark-only command, `devops --dry-run <command>` runs the command normally: groups 1, 2, 4 and 6 for the read-only commands and for `branches clean`. The five commands that write local state print a `Would ...` line and write nothing. This is the one change from the literal text of the criterion. Design decision 4 gives the evidence.
- Echo-only previews of these commands are gone with no shim: groups 2 to 7 delete the calls, and group 8 checks with `git grep`.
- The new tests start no process and open no socket: the hermetic floor fails a test that reaches an edge without a fake, and every new test uses a fake. The pull request records the run time of the new tests: group 8 prints it, and the pull request description holds it. The description is not a file of the repository.
- `uv run devops ci` passes: the required checks of CI on the pull request. Group 8 runs the checks that this change touches (tests, docs, `openspec check`).

## Impact

- Code: `src/devops_cli/commands/branches.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/commands/ssh.py`, `src/devops_cli/commands/tls.py`, `src/devops_cli/git/operations.py`, `src/devops_cli/git/git_plans.py` (new), `src/devops_cli/github/client.py`, `src/devops_cli/github/ssh.py`, `src/devops_cli/github/ssh_plans.py` (new), `src/devops_cli/crypto/ssh_keys.py`, `src/devops_cli/crypto/tls_plans.py` (new), `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/commands/test_branches.py`, `tests/commands/test_repos.py`, `tests/git/test_repos_worktrees.py`, `tests/crypto/test_ssh.py`, `tests/commands/test_tls_cmd.py`, `tests/fixtures/dry_run_gaps.json`. The new tests join these files. Each file already holds the tests of its commands and the fixtures that they need.
- Documents: `docs/commands/branches.md`, `docs/commands/repos.md`, `docs/commands/ssh.md`, `docs/commands/tls.md`, `docs/CLI_REFERENCE.md` and the README table. Group 8 regenerates them, because `branches update`, `branches jira` and `repos worktrees prune` change their options, and `repos list`, `ssh audit`, `ssh list` and `ssh status` lose `--dry-run`.
- Code the change reuses: `PlannedRequest`, `render_request_plan` (`src/devops_cli/dry_run/requests.py`), `dry_run_class` (`src/devops_cli/dry_run/decorator.py`), `plan_prune` (`src/devops_cli/git/worktree_inventory.py`), `CONST_GITHUB_SSH_KEY_ENDPOINT_SCOPES` and `CONST_VSCODE_CLI` (`src/devops_cli/config/constants.py`), the `local_read` flag of `run_subprocess`, and the fakes `git_fake`, `process_fake` and `github_api` (`tests/support/fakes/`).
- Tests that must keep passing, because they pin the real run:
  - `tests/commands/test_repos.py` patches `fetch_all`, `pull_tracking`, `clone_repo`, `sync_from_repos`, `_reload_workspace` and `iter_workspace_repos` in `devops_cli.commands.repos`. The commands must keep calling these names with the same arguments.
  - `tests/commands/test_tls_cmd.py` patches `devops_cli.commands.tls.run_subprocess` and asserts the exact argv of `tls enable-k8s`. The command must keep calling `run_subprocess` with the same argv.
  - `tests/git/test_git_operations.py`, `tests/git/test_ssh_host_keys.py` and the recorded git transcripts of `tests/support/git_scenarios.py` pin the git calls of `fetch_all`, `pull_tracking` and `clone_repo`: the arguments and their order do not change.
  - `tests/github/test_github_ssh.py` pins the two POST requests of `register_key_on_github` and its follow-up read on HTTP 422.
  - `tests/git/test_repos_worktrees.py` pins `repos worktrees status` and `repos worktrees prune`.
  - `tests/commands/test_all_commands_help_dryrun.py` runs `devops --dry-run repos list`, `devops --dry-run repos sync` and `devops --dry-run tls homelab` and expects exit status 0.
  - The specs `git-sync` (a failed repository is reported and the exit status is not 0) and `repos-worktrees-prune` (dry run and preview) stay true.
- Code the change deletes: the 13 `render_dry_run_result(...)` calls of the three command modules, the two tests that pin the echo output (`test_repos_commands_dry_run` and the `repos list` lines of `test_repo_origin_lru_caching` in `tests/commands/test_repos.py`), and the echo tests of `tests/commands/test_tls_cmd.py`.

## Feasibility

Every check below ran on 2026-11-01 in a worktree of `origin/main` (`2ae37724`). Commands were run with `uv run`.

- The premise holds for 24 commands. A script over `_COMMAND_SPECS` (using `_collect_reachable_commands` of `tests/invariants/test_dry_run_class_ratchet.py`) prints `class=None` and `gap=True` for each of the 24 paths of the issue table. It also lists `repos worktrees add` with `gap=True`. The issue does not list that command, and this change leaves it alone.
- The echo-only previews exist. `uv run devops repos list --dry-run` prints a JSON block with `"action": "list_cloned_repositories"`. `uv run devops ssh list --dry-run` prints `"action": "audit_ssh_keys"`. `git grep -c "render_dry_run_result(" -- src/devops_cli/commands/{repos,ssh,tls}.py` prints 4, 5 and 4.
- The generic line exists. `uv run devops --dry-run branches sync` prints `Would run delegated command: devops branches sync`. `uv run devops branches sync --dry-run` prints `No such option: --dry-run`. `uv run devops --dry-run tls inspect /tmp/x.crt` prints the generic line.
- The issue is wrong about GitPython. It says that `repos clone`, `repos clone-org`, `repos update`, `repos sync`, `branches update` and `branches sync` use GitPython and that the process runner does not see it. `grep -c -i gitpython pyproject.toml` prints 0. `git grep -n -E "^(import git|from git )" -- src` prints nothing. `src/devops_cli/git/operations.py` runs every git command through `run_subprocess` (`_git` at line 197, `clone_repo` at line 240, `fetch_all` at line 254, `pull_tracking` at line 279). `docs/TESTING.md` says the same: git has one seam, the process runner. So the dry-run guard of the runner does see these calls, and the tests use `git_fake`, not a patch of GitPython. The evidence strings `gitpython .fetch() @ git.operations:fetch_all:164` in the issue are out of date.
- The issue is right that no plan can drift only if one builder serves both. Today no builder exists. `fetch_all`, `pull_tracking`, `clone_repo`, `register_key_on_github` and `enable_k8s_cmd` build their argv inline (`operations.py` lines 244, 254 to 295; `commands/tls.py` lines 497 to 526). `render_dry_run_result` is the only dry-run code of these commands. So each request-plan group splits the argv out of the runner. The split keeps every call, its arguments and its order (see Impact for the tests that pin them).
- The runner does not make a plan by itself. In a dry run, `run_subprocess` returns a `PlannedProcessResult` for each call that is not a `local_read` (`src/devops_cli/core/process.py` line 624). `_git` passes `quiet=True`, and `fetch_all` drops the result, so nothing prints. No code collects these results, and GitHub REST calls do not go through the runner. So each command needs its own plan.
- The `local_read` reads can run in a dry run. `_remotes`, `current_branch` and `_tracking_remote` pass `read=True`, which sets `local_read`. They read the local repository and make no external request. So the plan of `branches sync` and `repos sync` reads the remotes, the current branch and the tracking remote with them. It lists one `git fetch --prune <remote>` per real remote and one `git pull <remote> <branch>`.
- One row of the table is wrong: `repos worktrees prune`. The table says "external request: no". `prune_worktrees` calls `get_github_session().client.get_commit_pulls(...)` for each worktree that local state does not decide (`src/devops_cli/git/worktree_inventory.py`, `merged_pull`, line 481). The run without `--confirm` makes these requests: `test_prune_without_confirm_reads_github_and_removes_nothing` (`tests/git/test_repos_worktrees.py` line 543) asserts `github_api.requested == [request]`. The command already has a working dry run: `plan_prune` returns `would check` items and the request lines, and `uv run devops repos worktrees prune --dry-run` printed `would check ... (the merged pull request of its tip is read)` for each worktree that needs a read. So the class is `request-plan`, and the command needs only its decorator. The issue allows this change: "If a row is wrong, change the class to match the code".
- `branches clean` has a working preview, not an echo. Its `--dry-run` calls `delete_merged_branches(repo_dir, dry_run=dry_run)` and prints `would delete` (`src/devops_cli/commands/branches.py`, `clean`). It uses neither `render_dry_run_result` nor `@dry_run_command`. The issue asks to remove only echo-only previews, so the option stays. `tests/commands/test_branches.py::test_branches_commands` runs `clean --dry-run` and pins it.
- The mark-only recipe of the issue ("process runner patched to fail") cannot hold. `branches list`, `branches clean`, `repos list` and `repos worktrees status` read git through `run_subprocess(..., local_read=True)`. So the tests use the fakes of `docs/TESTING.md`: `git_fake` answers the local reads, and the test asserts that no call has `local_read` false and that `github_api.sent` is empty.
- Four mark-only commands write local state, and the table does not say so. A scratch script ran `branches jira PROJ-2 --repo <repo>` with the dry-run state on. The command printed `Created and checked out: feature/PROJ-2` and created no branch (`git branch` showed only `main`), because the runner turns `git checkout -b` into a plan result. `generate_ed25519_key` opens the private key with `os.open(..., O_WRONLY | O_CREAT | O_TRUNC)` (`src/devops_cli/crypto/ssh_keys.py` line 211). `tls ca`, `tls cert` and `tls homelab` call `generate_ca_certificate`, `generate_server_certificate` and `generate_homelab_tls_bundle`, which write key and certificate files (`src/devops_cli/crypto/tls_certificates.py`, `os.open` at line 53). Design decision 4 sets the result.
- The `ssh` key calls use the GitHub session, not `httpx2.AsyncClient`. `register_key_on_github` calls `session.rest("POST", endpoint, ...)` for each key of `CONST_GITHUB_SSH_KEY_ENDPOINT_SCOPES` (`/user/keys`, then `/user/ssh_signing_keys`). On HTTP 422 it reads the listing of that endpoint with `session.paginate`. Then `_configure_git_signing` runs `git config --global` three times, and `git -C <cwd> config --local` three times when the working directory is a repository (`configure_git_signing`, `src/devops_cli/crypto/ssh_keys.py` line 307). Issue #891 moved these calls onto the session. The plan of `ssh register` and `ssh rotate` lists all of them.
- `tls enable-k8s` runs four kinds of call for each namespace: `kubectl get namespace`, a conditional `kubectl create namespace`, `kubectl create secret tls ... --dry-run=client -o yaml`, and `kubectl apply -f -` with the rendered YAML on stdin (`src/devops_cli/commands/tls.py` lines 497, 502, 523 and 526). Line 508, which the issue cites, is only the start of the render command. The plan lists all four for each namespace. The command first generates the homelab bundle in `--tls-dir` when `tls.crt` or `tls.key` is missing. That is a local write and no request, so the plan prints it as a note.
- Existing plan code cannot serve `tls enable-k8s`. `plan_k8s_create_tls_secret` and `plan_k8s_enable_tls` in `src/devops_cli/k8s/manifest_plans.py` plan `kubectl create secret tls` with no `--dry-run=client -o yaml` render and no `apply`, and `plan_k8s_enable_tls` takes a stack, not a namespace list. Both belong to the command `k8s enable-tls` (#2239). This change leaves them alone.
- Nothing newer did or removed this work. `git log --format='%h %cs %s' -4 -- src/devops_cli/commands/{ssh,tls,repos,branches}.py` lists #2935 (owner label), #2818 and #2799 (tests over fakes), and #2675 (`worktrees add`). None changes a dry run. `uv run devops gh api 'search/issues?q=repo:dan-petty/devops-cli+dry-run+ssh+register+in:title,body+is:issue'` finds #2258 as the only open item for these commands. The sibling items that the search lists (#2234 to #2252) are closed. `openspec/changes/` holds no other change for these four command files. Change `2260` plans other commands (`uv`, `test`, `pipeline`, `serve`, `mcp`, `ci fail-to-pass`) and ADDS requirements with other names in the same capability.
- The dry-run rule, `PlannedRequest`, `render_request_plan` and `dry_run_class` exist and are in use: `git grep -c "@dry_run_class(" -- src/devops_cli/commands` counts 366 uses in 52 command modules.
- The merged siblings set the pattern for commands that write local state. The base spec says "`workspace add`, `workspace generate`, and `workspace remove` SHALL provide local previews under `--dry-run` without modifying workspace files" and "`devcontainer init` and `devcontainer update` SHALL provide local previews under `--dry-run`". Change `2260` does the same for `test profile-memory` and `mcp`.

## Existing Tool Considered

The change uses what the repository has. `PlannedRequest` and `render_request_plan` (#741) show the plan. `dry_run_class` and the ratchet test (#2230) classify the commands. `git_fake`, `process_fake` and `github_api` fake the three edges that these commands reach, as `docs/TESTING.md` requires. No new dependency is necessary. No open tool prints a plan for `git`, the GitHub session and `kubectl` calls that these commands build, so each family gets a small plan module, as the merged siblings did (`tf_plans.py`, `docker_plans.py`, `devcontainer_plans.py`).

The cost of the build: about 150,000 tokens for the eight groups, about 5,000 tokens a year to keep the plan modules in step with the commands (the shared builders make drift a test failure), and about one working day of elapsed time.

The code that the change deletes is listed under Impact.
