Part of #886. Depends on sub-issue 00 (the dry-run class ratchet test).

### Problem or Motivation

The owner's dry-run rule (#412) says that a dry run makes no external request and returns the requests that the real run would make. The #886 inventory (2026-10-25, commit 1bb164bd) found 17 valkey and vault commands that do not obey it:

- 16 commands make an external request, or possibly make one, and have no request plan.
- 1 commands make no external request and need only the `no-external-request` class.

A command without a request plan either prints the generic `Would run delegated command` line under `devops --dry-run`, or fails with `No such option: --dry-run`, or prints an echo of its arguments. None of these shows the requests.

A command that makes no external request prints the generic `Would run delegated command` line under `devops --dry-run` and does not run, although running it is safe. Some of these commands have an echo-only `--dry-run` that prints only their arguments.

### Proposed Solution & Architectural Design

For each command in the table:

- **Request plan**: add `--dry-run` if it is missing. The dry run makes no external request, reads included. It returns the command's real result type, marked as a dry run, with the ordered `PlannedRequest` items (argv, stdin and env with `<placeholders>`, plus `condition` and `repeat`). Build each `PlannedRequest` from the same argument builder that the real run uses, so that the plan cannot drift from the run. Print it with `render_request_plan`. Give the command the `request-plan` class.
- **Mark only**: give the command the `no-external-request` class. `devops --dry-run <command>` then runs it normally.
- Remove an echo-only preview (`render_dry_run_result` or `@dry_run_command`) when the command gets its new dry run, with no shim.
- Remove the command's paths from `tests/fixtures/dry_run_gaps.json`.

Notes from the inventory:

- `vault audit` reads the local audit log only. The other commands reach Vault or Valkey over the network.
- A plan never holds a secret value. It names the path and uses a `<placeholder>` for the value.
- The table comes from a static walk of each callback and the functions that it calls. Check each row against the code before you change it. If a row is wrong, change the class to match the code, and record the evidence in the pull request.

| Command | `--dry-run` today | External request | Work | Evidence |
| :--- | :--- | :--- | :--- | :--- |
| `valkey backup` | yes (echo only) | yes | request plan | valkey: valkey.Valkey @ valkey.client:ValkeyClient.__init__:151 |
| `valkey cli` | no | yes | request plan | valkey: valkey.Valkey @ valkey.client:ValkeyClient.__init__:151 |
| `valkey flush` | yes (echo only) | yes | request plan | valkey: valkey.Valkey @ valkey.client:ValkeyClient.__init__:151 |
| `valkey get` | no | yes | request plan | valkey: valkey.Valkey @ valkey.client:ValkeyClient.__init__:151 |
| `valkey info` | no | yes | request plan | valkey: valkey.Valkey @ valkey.client:ValkeyClient.__init__:151 |
| `valkey keys` | no | yes | request plan | valkey: valkey.Valkey @ valkey.client:ValkeyClient.__init__:151 |
| `valkey ping` | no | yes | request plan | valkey: valkey.Valkey @ valkey.client:ValkeyClient.__init__:151 |
| `valkey set` | yes (echo only) | yes | request plan | valkey: valkey.Valkey @ valkey.client:ValkeyClient.__init__:151 |
| `valkey stats` | no | yes | request plan | valkey: valkey.Valkey @ valkey.client:ValkeyClient.__init__:151 |
| `vault audit` | no | no | mark only | - |
| `vault get` | yes (echo only) | yes | request plan | vault @ security.vault_broker:VaultSecretBroker.get_secret:283 |
| `vault leases` | yes (echo only) | yes | request plan | http: httpx2.HTTPTransport @ http.client:egress_transport:106 |
| `vault login` | yes (echo only) | yes | request plan | http: httpx2.HTTPTransport @ http.client:egress_transport:106 |
| `vault logout` | yes (echo only) | yes | request plan | http: httpx2.HTTPTransport @ http.client:egress_transport:106 |
| `vault set` | yes (echo only) | yes | request plan | http: httpx2.HTTPTransport @ http.client:egress_transport:106 |
| `vault status` | yes (echo only) | yes | request plan | http: httpx2.HTTPTransport @ http.client:egress_transport:106 |
| `vault sync` | yes (echo only) | yes | request plan | http: httpx2.HTTPTransport @ http.client:egress_transport:106 |

### Target Subsystem

HashiCorp Vault & Secret Management

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
<!-- checked-at: sha=d594b55213c3a8d118f43cc09d98045f39fc0d3f -->
## Proposed design

### Problem statement
The dry-run rule requires that a dry run makes no external request and lists the requests a real run makes. Seventeen valkey and vault commands do not obey this rule. They print a generic line, fail on --dry-run, or print only an argument echo. This item adds request plans or no-external-request marks so every command obeys the rule.

### Acceptance criteria
- Criterion 1: The change removes each command in the table from tests/fixtures/dry_run_gaps.json.
  Verification: Run the ratchet test and confirm it passes.
- Criterion 2: Each request-plan command makes no external request in both flag orders.
  Verification: Run tests with the process runner, HTTP clients, and other clients patched to fail.
- Criterion 3: Each request-plan command prints its ordered planned requests.
  Verification: Run devops  --dry-run and devops --dry-run  and check the output.
- Criterion 4: Each request-plan command with --format json or --json returns the real result type marked as a dry run.
  Verification: Run tests that parse the JSON result and check dry_run and requests.
- Criterion 5: Each request-plan command plans the same requests the real run makes, in the same order.
  Verification: Run a test that records each call from a fake runner or client and compares it with the plan.
- Criterion 6: Each mark-only command runs normally under devops --dry-run.
  Verification: Run tests with the process runner and HTTP clients patched to fail.
- Criterion 7: The change removes echo-only previews for these commands with no shim.
  Verification: Search the code for render_dry_run_result and `@dry_run_command` for these commands and confirm they are absent.
- Criterion 8: The new tests start no process and open no socket.
  Verification: Run the new tests and confirm the test guards record no process or socket reach.
- Criterion 9: The pull request records the test time.
  Verification: Check the pull request description for the recorded test time.
- Criterion 10: uv run devops ci passes.
  Verification: Run uv run devops ci.

### Key questions
- **Does this item fit one pull request?**: Yes. One pull request can deliver all 17 command changes, the fixture update, and the tests. (proposed)
- **Does this item wait on work outside this roadmap?**: No. It waits only on the roadmap sub-issue for the dry-run class ratchet test. (proposed)

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "High", "Priority": "P1-High", "Status": "In Review", "Value": "High", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "5c2c1d458e8fd432359906d6985f8fbd3db7b524e96989a2eaf8c6a33471200f", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "2c4a65e9f9443e87c01475713ab66dd251c86f46f2d7af19a23324a0e1586190"} -->
