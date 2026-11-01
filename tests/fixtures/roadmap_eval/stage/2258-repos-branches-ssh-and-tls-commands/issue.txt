Part of #886. Depends on sub-issue 00 (the dry-run class ratchet test).

### Problem or Motivation

The owner's dry-run rule (#412) says that a dry run makes no external request and returns the requests that the real run would make. The #886 inventory (2026-10-25, commit 1bb164bd) found 24 repos, branches, ssh and tls commands that do not obey it:

- 9 commands make an external request, or possibly make one, and have no request plan.
- 15 commands make no external request and need only the `no-external-request` class.

A command without a request plan either prints the generic `Would run delegated command` line under `devops --dry-run`, or fails with `No such option: --dry-run`, or prints an echo of its arguments. None of these shows the requests.

A command that makes no external request prints the generic `Would run delegated command` line under `devops --dry-run` and does not run, although running it is safe. Some of these commands have an echo-only `--dry-run` that prints only their arguments.

### Proposed Solution & Architectural Design

For each command in the table:

- **Request plan**: add `--dry-run` if it is missing. The dry run makes no external request, reads included. It returns the command's real result type, marked as a dry run, with the ordered `PlannedRequest` items (argv, stdin and env with `<placeholders>`, plus `condition` and `repeat`). Build each `PlannedRequest` from the same argument builder that the real run uses, so that the plan cannot drift from the run. Print it with `render_request_plan`. Give the command the `request-plan` class.
- **Mark only**: give the command the `no-external-request` class. `devops --dry-run <command>` then runs it normally.
- Remove an echo-only preview (`render_dry_run_result` or `@dry_run_command`) when the command gets its new dry run, with no shim.
- Remove the command's paths from `tests/fixtures/dry_run_gaps.json`.

Notes from the inventory:

- `repos clone`, `repos clone-org`, `repos update`, `repos sync`, `branches update` and `branches sync` use GitPython (`clone_from`, `fetch`, `pull`). GitPython starts `git` itself, not through `core.process.run_subprocess`, so the process runner's dry-run guard does not stop it.
- `ssh register` and `ssh rotate` post keys to GitHub through the GitHub session. `tls enable-k8s` calls `kubectl`.
- `ssh list` has an echo-only preview today (#886 names it). Remove that `--dry-run` option with no shim when the command gets the `no-external-request` class.
- The table comes from a static walk of each callback and the functions that it calls. Check each row against the code before you change it. If a row is wrong, change the class to match the code, and record the evidence in the pull request.

| Command | `--dry-run` today | External request | Work | Evidence |
| :--- | :--- | :--- | :--- | :--- |
| `branches clean` | yes | no | mark only | - |
| `branches jira` | no | no | mark only | - |
| `branches list` | no | no | mark only | - |
| `branches sync` | no | yes | request plan | gitpython .fetch() @ git.operations:fetch_all:164 |
| `branches update` | no | yes | request plan | gitpython .fetch() @ git.operations:fetch_all:164 |
| `repos clone` | yes (echo only) | yes | request plan | manual: GitPython Repo.clone_from (git/operations.py:clone_repo) |
| `repos clone-org` | yes (echo only) | yes | request plan | manual: GitHub org listing and GitPython Repo.clone_from |
| `repos list` | yes (echo only) | no | mark only | - |
| `repos sync` | yes (echo only) | yes | request plan | gitpython .fetch() @ git.operations:fetch_all:164 |
| `repos update` | yes (echo only) | yes | request plan | gitpython .fetch() @ git.operations:fetch_all:164 |
| `repos worktrees prune` | yes | no | mark only | - |
| `repos worktrees status` | no | no | mark only | - |
| `ssh audit` | yes (echo only) | no | mark only | - |
| `ssh generate` | yes (echo only) | no | mark only | - |
| `ssh list` | yes (echo only) | no | mark only | - |
| `ssh register` | yes (echo only) | yes | request plan | http: httpx2.AsyncClient @ http.client:new_async_http_client:186 |
| `ssh rotate` | yes (echo only) | yes | request plan | http: httpx2.AsyncClient @ http.client:new_async_http_client:186 |
| `ssh status` | yes (echo only) | no | mark only | - |
| `tls ca` | yes (echo only) | no | mark only | - |
| `tls cert` | yes (echo only) | no | mark only | - |
| `tls enable-k8s` | yes (echo only) | yes | request plan | kubectl create @ commands.tls:enable_k8s_cmd:508 |
| `tls homelab` | yes (echo only) | no | mark only | manual: generates a local TLS bundle; the analyzer matched a hostname list that starts with 'argocd' |
| `tls inspect` | no | no | mark only | - |
| `tls verify` | no | no | mark only | - |

### Target Subsystem

SDLC, Git & PR Governance

### Existing Tool Considered

The work uses what the repository has: `devops_cli.dry_run.requests.PlannedRequest` and `render_request_plan` (#741), the dry-run class decorator and ratchet test from sub-issue 00, and the test guards in `tests/conftest.py` and `tests/test_roadmap_dry_runs.py`. No new dependency is necessary.

### Acceptance Criteria

- [ ] Each command in the table is out of `tests/fixtures/dry_run_gaps.json`, and the ratchet test passes.
- [ ] For each request-plan command, `devops <command> --dry-run` and `devops --dry-run <command>` make no external request and print the ordered requests. Verified by tests with the process runner, the HTTP clients and the other clients patched to fail.
- [ ] For each request-plan command with `--format json` or `--json`, the dry run returns the real result type marked as a dry run, with the planned requests. Verified by tests.
- [ ] For each request-plan command, the plan holds the requests that the real run makes, in the same order. Verified by a test that runs the real command against a fake runner or client that records each call, and compares the calls with the plan (the pattern of `tests/test_roadmap_dry_runs.py`).
- [ ] For each mark-only command, `devops --dry-run <command>` runs the command normally. Verified by tests with the process runner and the HTTP clients patched to fail.
- [ ] Echo-only previews of these commands are gone, with no shim.
- [ ] The new tests start no process and open no socket. The pull request records their time.
- [ ] `uv run devops ci` passes.


Source: https://github.com/dan-petty/devops-cli/issues/886

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=69636b6c7b754c7d8aa222c2d2d7d4cf55901772 -->
## Proposed design

### Problem statement
Twenty-four repos, branches, ssh and tls commands do not follow the dry-run rule. Some make an external request under --dry-run. Some print only an argument echo or a generic line. The change makes each dry run make no external request and show the requests that a real run would make. It also runs safe commands normally under --dry-run.

### Acceptance criteria
- Criterion 1: Each command in the issue table is out of tests/fixtures/dry_run_gaps.json.
  Verification: Run the dry-run ratchet test and confirm it passes.
- Criterion 2: Each request-plan command has the request-plan class.
  Verification: Inspect the command decorator and confirm the class is request-plan.
- Criterion 3: Each mark-only command has the no-external-request class.
  Verification: Inspect the command decorator and confirm the class is no-external-request.
- Criterion 4: Each request-plan command accepts --dry-run in both flag orders.
  Verification: Run `devops  --dry-run` and `devops --dry-run ` and confirm both succeed.
- Criterion 5: Each request-plan dry run makes no external request.
  Verification: Run the command with the process runner and HTTP clients patched to fail and confirm no request is made.
- Criterion 6: Each request-plan dry run prints the ordered PlannedRequest items.
  Verification: Run the dry run and confirm the output lists argv, stdin, env, condition and repeat in order.
- Criterion 7: Each request-plan dry run returns the real result type marked as a dry run.
  Verification: Run the command with --format json or --json and confirm the result has the dry-run mark and planned requests.
- Criterion 8: Each request-plan plan matches the real run requests in the same order.
  Verification: Run a test that records calls from a fake runner or client and compares them with the plan.
- Criterion 9: Each mark-only command runs normally under devops --dry-run.
  Verification: Run `devops --dry-run ` with the process runner and HTTP clients patched to fail and confirm it completes.
- Criterion 10: Echo-only previews of these commands are removed without a shim.
  Verification: Search the command modules for render_dry_run_result and `@dry_run_command` for these commands and confirm they are absent.
- Criterion 11: Each table row matches the code.
  Verification: Inspect each callback and its called functions and record the evidence in the pull request.
- Criterion 12: The new tests start no process and open no socket.
  Verification: Run the new tests under the test guards and confirm no process or socket reach is recorded.
- Criterion 13: The pull request records the time of the new tests.
  Verification: Read the pull request and confirm it has the test time.
- Criterion 14: The repository CI passes.
  Verification: Run `uv run devops ci` and confirm it passes.

### Key questions
- **Does this item fit one pull request?**: Yes. It changes one command group and one test fixture set. (proposed) [sources: CONTEXT.md]
- **What outside work blocks this item?**: None. It waits only on sub-issue 00, which is a dependency. (proposed)
- **Which issue must be done first?**: Sub-issue 00, the dry-run class ratchet test. (proposed)

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "High", "Owner": "Agent", "Priority": "P1-High", "Status": "Planned", "Value": "High", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "5b4c87b6e7a9ebc4d824cc95eb18df148a4f05fff0129311fd2c193bf7ff4e47", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "9c8a7b9d6cb31ecdcbe529418741b6240e082fec04a2450a2f4dc5f0e02eac4e", "stage.branch": "feat/2258-repos-branches-ssh-and-tls-commands", "stage.file_cap": null, "stage.groups": "[[\"Mark-only branches: clean, jira, list\", 7041], [\"Request-plan branches: sync, update\", 7095], [\"Mark-only repos: list, worktrees prune, worktrees status\", 7049], [\"Request-plan repos: clone, clone-org, sync, update\", 7156], [\"Mark-only ssh: audit, generate, list, status\", 7055], [\"Request-plan ssh: register, rotate\", 7111], [\"Mark-only tls: ca, cert, homelab, inspect, verify\", 7089], [\"Request-plan tls: enable-k8s\", 7102], [\"Ratchet test and full CI verification\", 6999]]", "stage.needs_split": null, "stage.pr": "2972", "stage.ready": "2972", "stage.sha": "791530ef5bf5ffec6185fa7e947f0161ce4e967d"} -->
