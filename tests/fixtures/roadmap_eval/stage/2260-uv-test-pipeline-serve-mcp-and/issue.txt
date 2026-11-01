Part of #886. Depends on sub-issue 00 (the dry-run class ratchet test).

### Problem or Motivation

The owner's dry-run rule (#412) says that a dry run makes no external request and returns the requests that the real run would make. The #886 inventory (2026-10-25, commit 1bb164bd) found 14 uv, test, pipeline, serve, mcp and ci fail-to-pass commands that do not obey it:

- 12 commands make an external request, or possibly make one, and have no request plan.
- 1 commands change local state, make no external request and have no `--dry-run`.
- 1 commands make no external request and need only the `no-external-request` class.
- Already done, not in scope: `ci`, `ci test`, `ci coverage`, `ci lint`, `ci format`, `ci typecheck`, `ci audit`, `ci security`, `ci actionlint`, `ci docs`, `ci uv-check`, `ci lockfile`, `ci build`, `ci outdated`, `ci devcontainer`, `ci deps`, `ci maintain`, `ci run`, `ci mutate`.

A command without a request plan either prints the generic `Would run delegated command` line under `devops --dry-run`, or fails with `No such option: --dry-run`, or prints an echo of its arguments. None of these shows the requests.

A command that makes no external request prints the generic `Would run delegated command` line under `devops --dry-run` and does not run, although running it is safe. Some of these commands have an echo-only `--dry-run` that prints only their arguments.

### Proposed Solution & Architectural Design

For each command in the table:

- **Request plan**: add `--dry-run` if it is missing. The dry run makes no external request, reads included. It returns the command's real result type, marked as a dry run, with the ordered `PlannedRequest` items (argv, stdin and env with `<placeholders>`, plus `condition` and `repeat`). Build each `PlannedRequest` from the same argument builder that the real run uses, so that the plan cannot drift from the run. Print it with `render_request_plan`. Give the command the `request-plan` class.
- **Local preview**: add `--dry-run`. The preview prints the change and writes nothing. Give the command the `no-external-request` class.
- **Mark only**: give the command the `no-external-request` class. `devops --dry-run <command>` then runs it normally.
- Remove an echo-only preview (`render_dry_run_result` or `@dry_run_command`) when the command gets its new dry run, with no shim.
- Remove the command's paths from `tests/fixtures/dry_run_gaps.json`.

Notes from the inventory:

- `uv run` and `pipeline` run other commands; their requests depend on those commands. Decide, with evidence, whether a pass-through command can list a plan, or whether it needs a different design. If it cannot be built as the rule says, return it with the evidence (rule 2).
- `serve` and `mcp serve` start a server. A server makes requests only when a client calls it. Their dry run lists what the server would bind and start.
- These groups each have fewer than 5 commands that need work, so they join here.
- The table comes from a static walk of each callback and the functions that it calls. Check each row against the code before you change it. If a row is wrong, change the class to match the code, and record the evidence in the pull request.

| Command | `--dry-run` today | External request | Work | Evidence |
| :--- | :--- | :--- | :--- | :--- |
| `ci fail-to-pass` | yes (echo only) | unclear | request plan | manual: git worktree of the base ref and pytest; a missing base ref can need a fetch |
| `mcp export-schemas` | no | no | local preview | - |
| `mcp serve` | no | unclear | request plan | manual: starts an MCP server; its tools make requests only when a client calls them |
| `mcp tools` | no | no | mark only | - |
| `pipeline` | yes (echo only) | unclear | request plan | manual: runs configured pipeline stages; requests depend on the stages |
| `serve` | no | unclear | request plan | manual: starts an HTTP server (uvicorn.run); requests depend on the routes called |
| `test load` | yes (echo only) | yes | request plan | manual: k6 load test against service URLs |
| `test profile-memory` | yes (echo only) | yes | request plan | http .send() @ http.broker:HttpClientBroker.arequest:141 |
| `test run` | yes (echo only) | unclear | request plan | uv run @ commands.test_cmd:run_test_cmd:162 |
| `test sandbox` | yes (echo only) | yes | request plan | docker-sdk: docker.DockerClient @ docker.engine:DockerEngineService.client:416 |
| `uv lock` | no | yes | request plan | manual: uv lock reads the package index |
| `uv python-install` | no | yes | request plan | manual: uv python install downloads a Python build |
| `uv run` | no | unclear | request plan | manual: pass-through command; uv can sync first |
| `uv sync` | no | yes | request plan | manual: uv sync reads the package index |

### Target Subsystem

SDLC, Git & PR Governance

### Existing Tool Considered

The work uses what the repository has: `devops_cli.dry_run.requests.PlannedRequest` and `render_request_plan` (#741), the dry-run class decorator and ratchet test from sub-issue 00, and the test guards in `tests/conftest.py` and `tests/test_roadmap_dry_runs.py`. No new dependency is necessary.

### Acceptance Criteria

- [ ] Each command in the table is out of `tests/fixtures/dry_run_gaps.json`, and the ratchet test passes.
- [ ] For each request-plan command, `devops <command> --dry-run` and `devops --dry-run <command>` make no external request and print the ordered requests. Verified by tests with the process runner, the HTTP clients and the other clients patched to fail.
- [ ] For each request-plan command with `--format json` or `--json`, the dry run returns the real result type marked as a dry run, with the planned requests. Verified by tests.
- [ ] For each request-plan command, the plan holds the requests that the real run makes, in the same order. Verified by a test that runs the real command against a fake runner or client that records each call, and compares the calls with the plan (the pattern of `tests/test_roadmap_dry_runs.py`).
- [ ] For each local-preview command, `--dry-run` prints the change and writes nothing. Verified by tests with the writer patched to fail.
- [ ] For each mark-only command, `devops --dry-run <command>` runs the command normally. Verified by tests with the process runner and the HTTP clients patched to fail.
- [ ] Echo-only previews of these commands are gone, with no shim.
- [ ] The new tests start no process and open no socket. The pull request records their time.
- [ ] `uv run devops ci` passes.


Source: https://github.com/dan-petty/devops-cli/issues/886

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=69636b6c7b754c7d8aa222c2d2d7d4cf55901772 -->
## Proposed design

### Problem statement
The dry-run rule says a dry run makes no external request. It also says a dry run lists the requests a real run would make. Fourteen uv, test, pipeline, serve, mcp and ci fail-to-pass commands do not obey this rule. This item adds request plans, local previews, or no-external-request classes for these commands.

### Acceptance criteria
- Criterion 1: Each command in the table is out of tests/fixtures/dry_run_gaps.json.
  Verification: Run the ratchet test and confirm the 14 paths are absent.
- Criterion 2: Each request-plan command accepts --dry-run in both flag orders.
  Verification: Run tests with patched clients and confirm no request occurs.
- Criterion 3: Each request-plan command prints the ordered requests under dry run.
  Verification: Run the command and confirm the plan appears in the output.
- Criterion 4: Each request plan is built by the same argument builder as the real run.
  Verification: Inspect the code and run the plan equality tests.
- Criterion 5: Each request-plan command with --format json or --json returns its real result type.
  Verification: Run tests and confirm the result is marked as a dry run.
- Criterion 6: Each request-plan command lists the requests that the real run makes.
  Verification: Run a test that compares recorded calls with the plan.
- Criterion 7: Each local-preview command prints the change and writes nothing.
  Verification: Run tests with the writer patched to fail.
- Criterion 8: Each mark-only command runs normally under devops --dry-run.
  Verification: Run tests with patched clients and confirm the command runs.
- Criterion 9: No echo-only preview remains for these commands.
  Verification: Inspect the command code and run the dry-run tests.
- Criterion 10: Each table row is checked against the code before change.
  Verification: Inspect the code and record any class change in the pull request.
- Criterion 11: The new tests start no process and open no socket.
  Verification: Run the tests under the conftest guards and record the time.
- Criterion 12: The full CI command passes.
  Verification: Run uv run devops ci and confirm it exits 0.

### Key questions
- **Can a pass-through command list a request plan?**: Yes. It lists the delegated argv, stdin, env, condition and repeat. It uses the same argument builder as the real run. (proposed) [sources: CHANGELOG.md:1390, tests/test_roadmap_dry_runs.py]
- **What does a server dry run list?**: It lists the bind and start requests. It does not list client calls. It makes no request. (proposed)
- **Does this item fit one pull request?**: Yes. The groups each have fewer than 5 commands. They join this item. (proposed) [sources: CONTEXT.md]
- **What issue number does this item depend on?**: The body names sub-issue 00. Record the dependency as 0. (proposed)
- **How do the tests verify plan equality?**: Use the pattern in tests/test_roadmap_dry_runs.py. Run the real command against a fake runner or client. Compare the recorded calls with the plan. [sources: tests/test_roadmap_dry_runs.py]
- **How do the tests stay offline?**: Use the process and network guards in tests/conftest.py. [sources: tests/conftest.py]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "High", "Owner": "Agent", "Priority": "P1-High", "Status": "Planned", "Value": "High", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "8caa9dad661d7b16270fc1de1c49544437cf83b6eb1f67fdc51c962831a56499", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "f9725d6d6d09bd5655bb60a777578c4ca64188feded6bac5aefb6b6f552aa5c7", "stage.branch": "feat/2260-uv-test-pipeline-serve-mcp-and", "stage.file_cap": null, "stage.groups": "[[\"uv lock and uv sync dry-run request plans\", 6869], [\"uv python-install and uv run dry-run request plans\", 6872], [\"test load and test profile-memory dry-run request plans\", 6862], [\"test run and test sandbox dry-run request plans\", 6854], [\"mcp export-schemas local preview and mcp tools mark-only\", 6870], [\"mcp serve and serve dry-run request plans\", 6895], [\"pipeline and ci fail-to-pass dry-run request plans\", 6929], [\"Remove 14 paths from dry_run_gaps.json and verify ratchet test\", 6820]]", "stage.needs_split": null, "stage.pr": "2975", "stage.ready": "2975", "stage.sha": "83654b702d7c4d5b5ae5332f2390172d266d57cb"} -->
