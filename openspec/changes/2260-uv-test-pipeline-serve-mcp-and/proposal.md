# Proposal

## Why

Issue #2260 is part of #886. The dry-run rule (#412) says that a dry run makes no external request and prints the requests that the real run would make. Fourteen commands break the rule today. Under `devops --dry-run <command>`, eight of them print only `Would run delegated command`, because they have no `--dry-run` option and no dry-run class. Six have a `--dry-run` option that prints an echo of the arguments. Two of the echoes invent a result: `test load` prints `simulated_metrics`, and `pipeline` prints `SIMULATED_SUCCESS`.

## What Changes

- Eleven commands print a request plan under `--dry-run` and start nothing: `uv lock`, `uv sync`, `uv python-install`, `uv run`, `pipeline`, `test load`, `test run`, `test sandbox`, `mcp serve`, `serve` and `ci fail-to-pass`. Each one gets the `request-plan` class and a `--dry-run` option where it has none. The plan comes from the same function that builds the argument list of the real run.
- `ci fail-to-pass` shares one callback with `format fail-to-pass` and `lint fail-to-pass`. The class goes on the callback, so these two paths leave the gap list too. The gap list loses 16 paths, not 14.
- `test profile-memory` is not a request-plan command. Its built-in targets run in memory, and a custom target runs user code. It gets the `no-external-request` class and a local preview that runs nothing and writes nothing.
- `mcp export-schemas` gets a local preview: it prints what it would export and writes nothing. `mcp tools` gets the `no-external-request` class and runs as it is.
- The echo-only previews of these commands go. Nothing replaces them but the new dry runs.
- `WorkloadSandboxRunner.build_dry_run_details` has no caller after `test sandbox` changes. It goes, with the tests that call only it.
- The tests that name the old echo, or that use `serve` as the example of a command with no dry run, change in the group that breaks them.
- The change adds requirements to the existing `command-dry-run-class` capability. It adds no capability.
- The change fits in one pull request: ten groups, each of them small.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-dry-run-class`: ADDED requirements `uv-request-plans`, `pipeline-request-plans`, `test-request-plans`, `test-profile-memory-local-preview`, `mcp-local-preview`, `mcp-tools-no-external-request`, `server-request-plans` and `ci-fail-to-pass-request-plans`. No existing requirement changes.

## Impact

- Code: `src/devops_cli/commands/uv.py`, `src/devops_cli/commands/pipeline.py`, `src/devops_cli/commands/test_cmd.py`, `src/devops_cli/commands/mcp.py`, `src/devops_cli/commands/serve.py`, `src/devops_cli/commands/ci.py` (the `fail_to_pass` command only), `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/git/operations.py` (two argument builders), `src/devops_cli/ai/mcp/server.py` (the `sse` bind check), `src/devops_cli/docker/sandbox.py` (one deleted method) and `src/devops_cli/lang/en/messages.py` (two preview messages).
- Code reused, not rebuilt: `PlannedRequest` and `render_request_plan` in `src/devops_cli/dry_run/requests.py`, `dry_run_class` in `src/devops_cli/dry_run/decorator.py`, `prepare_tool_cmd` in `src/devops_cli/core/process.py`, `build_k6_cmd` and `build_dagger_cmd` in `src/devops_cli/config/commands.py`, `plan_docker_sandbox` in `src/devops_cli/docker/docker_plans.py`, `pytest_replay_argv` in `src/devops_cli/ci/fail_to_pass.py`, `_planned_request_for_cmd` in `src/devops_cli/commands/ci.py`.
- Tests that change: `tests/commands/test_uv.py`, `tests/commands/test_load_and_pipeline.py`, `tests/commands/test_test_runner.py`, `tests/commands/test_workload_sandbox.py`, `tests/commands/test_sandbox_lifecycle.py`, `tests/commands/test_sandbox_networking.py`, `tests/commands/test_memory_profiler.py`, `tests/ai/mcp/test_mcp.py`, `tests/server/test_server.py`, `tests/ci/test_fail_to_pass.py`, `tests/core/test_main_dry_run.py`, `tests/invariants/test_dry_run_class_ratchet.py` and `tests/fixtures/dry_run_gaps.json`.
- Tests that must stay green: `tests/commands/test_sandbox_lifecycle.py::test_sandbox_dry_runs_refuse_invalid_workspaces` and `::test_docker_and_test_sandbox_dry_runs_make_no_request` (#1383), `tests/commands/test_docker_dry_run.py`, `tests/invariants/test_dry_run_class_ratchet.py::test_mcp_exposure_table_no_external_request_read_only`, `tests/roadmap/test_roadmap_run.py` (`serve --service`).
- New test file: `tests/support/dry_run_stub.py` (new; a stub app for the proxy tests).
- Spec: `openspec/specs/command-dry-run-class/spec.md` (by archive).
- This change has a spec delta because it adds a command option (`--dry-run`) and changes command output.

## Acceptance

| Criterion of the issue | Delivered by |
| :--- | :--- |
| 1. The commands of the table leave `tests/fixtures/dry_run_gaps.json`, and the ratchet test passes | Groups 1 to 9 each remove their paths. Task 10.3 checks that none is left. |
| 2. Each request-plan command accepts `--dry-run` in both orders and makes no request | Groups 1, 2, 3, 4, 7, 8 and 9 |
| 3. Each request-plan command prints the ordered requests | Groups 1, 2, 3, 4, 7, 8 and 9 |
| 4. Each plan comes from the argument builder of the real run | Groups 1, 2, 3, 4, 7, 8 and 9. Each has a test that compares the recorded calls of the real run with the plan. |
| 5. A request-plan command with `--format json` or `--json` returns its real result type | None applies. No request-plan command of this item has `--format` or `--json`. Only `test profile-memory` has them, and it is a local preview (group 5). |
| 6. The plan holds the requests that the real run makes | Groups 1, 2, 3, 4, 7, 8 and 9 (the same comparison tests as criterion 4) |
| 7. A local preview prints the change and writes nothing | Group 5 (`test profile-memory`) and group 6 (`mcp export-schemas`) |
| 8. A mark-only command runs normally under `devops --dry-run` | Group 6 (`mcp tools`) |
| 9. No echo-only preview remains | Each group removes its echoes. Task 10.2 checks it with `git grep`. |
| 10. Each table row is checked against the code, and a class change is recorded | Done in `## Feasibility` and in `design.md`. Two rows change: `test profile-memory` and `ci fail-to-pass`. The pull request text repeats the two. |
| 11. The new tests start no process and open no socket, and the pull request records their time | Each test uses the process fake and the patched clients. The pull request comment records the `--durations` output of the verify commands. This is a pull request step, not a file of the change. |
| 12. `uv run devops ci` passes | Task 10.4 |

## Feasibility

Checked on 2026-11-01 against `origin/main` at commit `4734035c`, with the commands below.

1. The 14 commands exist and are in the gap list. `PYTHONPATH=. uv run python` with `_collect_reachable_commands()` of `tests/invariants/test_dry_run_class_ratchet.py` gives, for each of them, its callback, whether it declares `--dry-run`, and its class. All 14 have class `None`. Eight declare no `--dry-run`: `mcp export-schemas`, `mcp serve`, `mcp tools`, `serve`, `uv lock`, `uv python-install`, `uv run` and `uv sync`. Six declare it, and print the echo: `ci fail-to-pass`, `pipeline`, `test load`, `test profile-memory`, `test run` and `test sandbox`.
2. One callback serves three paths. The same script prints `devops_cli.commands.ci fail_to_pass` for `ci fail-to-pass`, `format fail-to-pass` and `lint fail-to-pass`. The class sits on the callback, so the ratchet test demands that all three leave the gap list: `Command 'x' has dry-run class ... but is still listed`. The first plan missed this. No other path of this item shares a callback.
3. Today's output. `uv run devops uv lock --dry-run` prints `No such option: --dry-run`. `uv run devops --dry-run uv lock`, `--dry-run mcp tools` and `--dry-run serve` print `Would run delegated command: devops <command>`. `uv run devops test load --dry-run` prints a JSON echo with `"action": "execute_k6_load_test"` and a `simulated_metrics` object. `uv run devops pipeline --dry-run` prints `"status": "SIMULATED_SUCCESS"`.
4. The line numbers in the issue table are stale. `commands.test_cmd:run_test_cmd:162` is now a line of the target selection. The `uv run` call is later in the same function. The symbols are right: `run_test_cmd` runs `run_subprocess(["uv", "run", *test_args])`. The sources of the issue to read are `tests/roadmap/test_roadmap_dry_runs.py` (the plan comparison pattern) and `tests/invariants/test_dry_run_class_ratchet.py`. `tests/test_roadmap_dry_runs.py` does not exist (`git cat-file -e origin/main:tests/test_roadmap_dry_runs.py` fails).
5. Nothing newer did or removed the work. `git log --since=2026-10-25` on the six command files and on `src/devops_cli/ci/fail_to_pass.py` shows no commit that adds a dry run or deletes a command. The newer commits are #2589 and #2353 (fail-to-pass replay), #2588 (sandbox seccomp option), #2515 and #2354 (Service). Open issues: #2258 plans four other command groups, and no open issue plans these 14 commands. Sibling plans touch the same gap file and the same spec but name other paths and other requirement names.
6. `test profile-memory` makes no external request. `src/devops_cli/telemetry/memory_profiler.py` runs the `http-pool` target against `httpx2.ASGITransport(app=_dummy_app)`, an in-memory transport. The `fastmcp` target calls `list_mcp_tools()`. `uv run devops test profile-memory http-pool --iterations 2 --format json` prints `"initial_sockets": 0` and `"final_sockets": 0`. The issue row (`http .send()`) is wrong for the built-in targets. A target `module:function` runs a function of the user, so a dry run cannot run it. The class is `no-external-request`, with a local preview.
7. `ci fail-to-pass` makes no network request either. `git grep -n "fetch\|pull\|clone" -- src/devops_cli/ci/fail_to_pass.py` finds only a docstring line. A missing base ref raises `GitOperationError` through `_verify_commit`; the command never fetches. The real run starts `git merge-base`, two `git rev-parse --verify`, `git diff --name-status`, `git ls-files --others`, `git worktree add`, `git archive`, `python -m pytest`, `git worktree remove` and `git worktree prune`. It is a request-plan command like `ci mutate`, which is `request-plan` on main for the same reason (it starts local processes). The test `test_fail_to_pass_dry_run_and_no_changed_tests` in `tests/ci/test_fail_to_pass.py` says the dry run starts no git call, so the plan uses placeholders for `<merge-base>`, `<tree>` and `<changed test files>`.
8. `uv run` and `pipeline` can list a plan. The real run passes one list to one process: `_run(["uv", "run", *ctx.args])` in `src/devops_cli/commands/uv.py`, and `build_dagger_cmd(...)` in `src/devops_cli/commands/pipeline.py`. The plan holds that one request. What `uv run` or `dagger call` does inside is not a request of devops-cli, so the plan does not list it. The resolver inserts `--dry-run` right after the command path (`_build_forwarded_args` in `src/devops_cli/core/command_resolver.py`), so `devops --dry-run uv run -- pytest` gives `uv run --dry-run -- pytest` and the tokens after `--` reach the plan unchanged.
9. The uv argument list needs `prepare_tool_cmd`. `DefaultProcessRunner.prepare_cmd` calls `prepare_tool_cmd`, which adds `--preview-features malware-check,check-command` after `uv` (`src/devops_cli/core/process.py`). The plan must apply it, as `_planned_request_for_cmd` in `src/devops_cli/commands/ci.py` does, or the plan drifts from the run.
10. `test sandbox` already has a model. `docker sandbox` in `src/devops_cli/commands/docker.py` builds its plan with `plan_docker_sandbox` and `WorkloadSandboxRunner.declared_controls()`, and it checks the workspace first. `test sandbox` has the same runner and the same flow. The tests of #1383 (`test_sandbox_dry_runs_refuse_invalid_workspaces`) pin the workspace check for both commands.
11. A server start is not a request. `run_mcp_server` calls `mcp.run(...)`, and `serve` calls `uvicorn.run(...)`. Neither makes an outbound request when it starts (the `FastAPI` app of `create_app` has no lifespan; only `serve --service` starts a manager, which polls GitHub). A dry run that only marks them would start a blocking server under `devops --dry-run`, so they need `--dry-run`. The plan names the bind and the start.
12. Existing tests that the change would break, found by `git grep`: `tests/core/test_main_dry_run.py` (two tests) and `tests/invariants/test_dry_run_class_ratchet.py::test_lazy_proxy_dry_run_no_external_request_execution` use `serve` as the example of a command with no `--dry-run`. `tests/commands/test_test_runner.py::_changed_run` parses the old JSON echo. `tests/commands/test_load_and_pipeline.py`, `tests/commands/test_memory_profiler.py` and `tests/ci/test_fail_to_pass.py` assert the echo text. The first plan named none of them. The groups below update each one.
13. No command of this item has `--format` or `--json` except `test profile-memory` (`git grep -n -E '"--json"|"--format"'` on the six command files finds lines 494 and 498 of `src/devops_cli/commands/test_cmd.py` only). Criterion 5 of the issue does not apply to a request-plan command here.

## Existing Tool Considered

No new tool is needed. The change uses what the repository has: `PlannedRequest` and `render_request_plan` (#741), the `dry_run_class` decorator and the ratchet test (#2230), the process fake in `tests/support/fakes/process.py`, and the plan builders of the groups that were delivered before (`src/devops_cli/docker/docker_plans.py`, `src/devops_cli/commands/ci.py`). The change deletes the echo-only previews of these commands and `WorkloadSandboxRunner.build_dry_run_details`.
