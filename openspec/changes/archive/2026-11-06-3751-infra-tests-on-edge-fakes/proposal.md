# Proposal

## Why

Issue #3751 is part 5 of #1335, which is part of #1307. Seven test files of the Docker, Terraform, watcher and Argo CRD code reach their edges through patches (62 patch sites and 2 private imports). Two rules that are domain logic still sit in `src/devops_cli/commands/`: the wait for an Argo Workflow and the match of Cloudflare DNS records. The CLI tests reach them through patches of private names.

The shared fakes exist for every edge these files need: the process runner, the keyring, the Docker engine, the Kubernetes API, the HTTP entry point, DNS, the clock and the MCP dispatcher. So each patch can go, and the two rules can move into their packages behind public functions.

## What Changes

- Argo: `argo/workflows.py` holds `await_workflow(service, name, namespace, *, timeout, poll_interval)`. It polls through the clock seam (`devops_cli.core.clock`) and raises the new `ArgoWorkflowTimeoutError` (`ARGO_WORKFLOW_TIMEOUT`, a subclass of `ArgoError`) when the budget ends. `commands/argo.py` loses `_await_workflow` and its `time` calls. It catches the error, prints it and exits with 1, as before. `argo/crd.py` loses the alias `_is_not_found`; its callers use the public `is_not_found_error`.
- Cloudflare: `cloudflare/dns.py` holds `find_matching_records` and `delete_dns_records` (with the result type `DnsDeletion`). `commands/cloudflare.py` loses `_resolve_dns_target_names`, `_record_matches_filter`, `_find_matching_records` and `_execute_dns_deletions`. It calls `delete_dns_records` and renders the result.
- Docker: `docker/engine.py` reads the monotonic time through `devops_cli.core.clock`, so a test moves the cache lifetime with the `clock` fixture and patches no `time` name.
- Fakes (test support only): `ClockFake.after_each_sleep` runs a hook after each wait, so a test changes the world while the code under test waits. `ProcessCall.extra_allowed_env` records the variables a caller lets the child inherit. `DockerEngineFake.script_every_run` scripts the run of each container that has no script of its own. The fake Kubernetes API objects get `fail(method, error)` to raise an API server refusal for one method.
- Tests, seven files of the issue (each at its mirror path):
  - `tests/argo/test_argo_crd.py` runs on the `cluster` fixture. `tests/argo/test_workflows.py` is new.
  - `tests/tf/test_tf_cost.py` becomes `tests/tf/test_cost.py` (the functions of `tf/cost.py`, on `process_fake`). Its command cases move to `tests/commands/test_tf_cost.py` and its MCP cases to `tests/ai/mcp/test_tf_cost_tools.py`. `tests/tf/test_tf_analysis.py` runs its commands through `cli`.
  - `tests/watchers/test_watchers.py` waits on `clock` and reads no private state.
  - `tests/ai/mcp/test_docker_cosign.py` becomes `tests/docker/test_cosign.py` (the runner, on `process_fake` and `keyring_store`) and `tests/commands/test_docker_cosign.py` (the commands).
  - `tests/commands/test_workload_sandbox.py` runs on `docker_daemon`. The runner cases move to `tests/docker/test_sandbox.py`.
  - `tests/core/test_docker_engine.py` runs on `dns`, `clock` and `cli`, then splits by behaviour into `tests/docker/test_engine_endpoint.py`, `test_engine_connection.py`, `test_engine_projection.py`, `test_engine_containers.py`, `test_engine_facts.py`, `test_engine_networks.py` and `test_engine_build_cache.py`, and `tests/commands/test_docker_cache.py`.
  - `tests/cloudflare/test_dns.py` is new. The two DNS delete cases that test the matching rule leave `tests/commands/test_cloudflare_commands.py`.
- Not changed: item 6 of #1335 (the Argo CD, PromQL and Grafana API calls) and the other cases of `tests/commands/test_cloudflare_commands.py`. The `docker_endpoint_env` fixture still sets the Podman socket path constants of `docker/engine.py`. That fixture is shared with other files.
- This change alters no behavior a consumer observes: no command, option, message or request changes. It has no spec delta, and `skip_specs: true` is set. The new error class is raised only inside the Argo wait, and the command prints the same text and exits with 1 as before.
- This change fits one pull request.

## Impact

- `src/devops_cli/argo/` (`workflows.py` new, `crd.py`), `src/devops_cli/cloudflare/dns.py` (new), `src/devops_cli/docker/engine.py`, `src/devops_cli/exceptions/argo.py`, `src/devops_cli/exceptions/__init__.py`, `src/devops_cli/commands/argo.py` and `src/devops_cli/commands/cloudflare.py`.
- `docs/ERRORS.md` (one new row).
- `tests/support/fakes/` (`clock.py`, `process.py`, `kubernetes.py`, `docker_engine.py`), and the test files above.
- `openspec/changes/2554-devops-sandbox-deploy-fails-with-a/`, which names `tests/core/test_docker_engine.py`.

## Feasibility

Checked on `origin/main` 235a807c, 2026-11-06. The premise of #3751 holds; the tree had moved, so each claim was read again.

- The patch sites of the seven files, counted with an AST pass over `patch`, `patch.object`, `patch.dict`, `monkeypatch.setattr`, `monkeypatch.setitem` and `monkeypatch.delattr`, are 35, 12, 3, 1, 0, 9 and 2: 62 in all. The private imports are `_parse_verification_output` and `_is_not_found`: 2. Module-level `CliRunner()` sits in four files. The counts match the issue.
- The Argo wait is `_await_workflow` in `commands/argo.py` and the Cloudflare rule is the four helpers in `commands/cloudflare.py`. `git grep` finds no other caller. The Cloudflare client already uses the HTTP entry point, so the rule needs no new seam.
- `process_fake` answers the program and the PATH lookup, `keyring_store` holds the keys, `docker_daemon` is the engine, `cluster` is the Kubernetes API, `dns` answers the host name, `clock` stops time, and `mcp_dispatcher` records the MCP command. Each was read in `tests/support/fakes/` and used by the new tests.
- `_parse_verification_output` is reached through `CosignRunner.verify_image`, so a test of the public call covers it. It is not dead code, and it stays.
- Two patch sites need a product change or a fixture. `docker/engine.py` called `time.monotonic()` directly: it now calls the clock seam. The Podman socket path constants are set by the shared `docker_endpoint_env` fixture, so the tests in the engine file read the paths from that fixture and patch nothing.
- Environment: a test that needs a root-free permission check (`test_endpoint_podman_rootful_skipped_when_inaccessible`) skips when the user is root, because root opens any path.

## Existing Tool Considered

The fakes of #775, #1315, #1316, #1318, #1320 and #3752 cover every edge: `ProcessFake`, `FakeKeyring`, `DockerEngineFake`, `FakeCluster`, `ClockFake`, `DnsFake` and `DispatcherFake`. `pytest` is the runner. `tenacity` is in the project, but it would not shrink the wait loop: the loop reads the Workflow, tests its phase and sleeps, and `tenacity` would add a retry wrapper around the same three steps. So the loop stays a plain function on the clock seam. The change builds two small domain functions (`await_workflow`, `find_matching_records` with `delete_dns_records`) by moving code that exists. The estimated cost is about 350,000 tokens to build, about 15,000 tokens a year to keep, and about 2 days. The change deletes the private helpers `_await_workflow`, `_resolve_dns_target_names`, `_record_matches_filter`, `_find_matching_records`, `_execute_dns_deletions` and the alias `_is_not_found`, and the 62 patch sites.
