# Proposal

## Why

Issue #2554 reports that `devops sandbox deploy` fails with a raw Docker API 404 when the sandbox image is not on the local engine. The default image is `python:3.14-slim`, so the first deploy on a fresh engine fails. No code pulls the image before it creates the container.

## What Changes

- Add `DockerEngineService.pull_image`. It asks the engine for the image with `images.get` and pulls it with `images.pull` only when the engine does not hold it. A failed lookup or pull raises `DockerEngineError` with the image reference and the reason.
- Call `pull_image` in `WorkloadSandboxEngine._spawn_container` (`src/devops_cli/sandbox/engine.py`), the code that `devops sandbox deploy` runs, before `create_container`.
- Teach `DockerEngineFake` the two calls (`images.get`, `images.pull`) and add a contract scenario for them, recorded from a real engine, so the fake stays true to the Engine API.
- List the image check and the pull in the dry-run plan of `devops sandbox deploy`. The dry-run rule (#412, #2251) says a dry run returns the requests that the real run makes. This change adds two requests to the real run, so the plan must list them.
- Not in this change: the workload runner (`WorkloadSandboxRunner.run` in `src/devops_cli/docker/sandbox.py`, behind `devops docker sandbox` and `devops test sandbox`) also creates a container with no pull. The issue names only `devops sandbox deploy`, so this change leaves the runner as it is.
- The change fits one pull request.
- The change adds the capability `sandbox-image-pull`, because it changes how a devops command behaves. It changes no document: no command, option or help text changes.

## Capabilities

### New Capabilities

- `sandbox-image-pull`: how `devops sandbox deploy` gets its image onto the engine: it pulls a missing image, it does not pull a local image, a failed pull names the image and the reason, and the dry run lists the image requests.

### Modified Capabilities

None. The requirement `sandbox-request-plans` of `command-dry-run-class` stays true: the dry run still prints the container creation and start requests and makes zero engine calls.

## Impact

- Code: `src/devops_cli/docker/engine.py`, `src/devops_cli/docker/sdk.py`, `src/devops_cli/sandbox/engine.py`, `src/devops_cli/sandbox/sandbox_plans.py`.
- Tests and test support: `tests/support/fakes/docker_engine.py`, `tests/support/docker_engine_scenarios.py`, `tests/docker/test_engine_contract.py`, `tests/fixtures/docker_engine/recorded_exchanges.json`, `tests/core/test_docker_engine.py`, `tests/sandbox/test_sandbox_deploy_pull.py` (new), `tests/commands/test_sandbox_dry_run.py`.
- Existing tests that must keep passing: `tests/commands/test_sandbox_lifecycle.py` (deploy over mock clients, rollback, dry run), `tests/sandbox/test_sandbox_seccomp.py` and `tests/commands/test_sandbox_logs.py` (deploy over the fake with `alpine:3`, which the fake holds), `tests/commands/test_sandbox_networking.py`.
- Code that this change reuses: `DockerEngineError` (`src/devops_cli/exceptions/docker.py`), `DockerEngineFake.fail` and `call_names` (a pull failure in a test uses `fail`), the `docker_daemon` fixture, `DEFAULT_SANDBOX_IMAGE` (`src/devops_cli/config/defaults.py`).

## Feasibility

All commands ran on 2026-11-01 in a checkout at origin/main `9f3b7010`, with docker SDK 7.2.0 and Docker Engine 29.9.2.

- No code pulls an image. `git grep -n "images\.pull\|pull_image" -- src tests` prints nothing.
- `devops sandbox deploy` runs `WorkloadSandboxEngine.deploy`. `grep -n "engine.deploy" src/devops_cli/commands/sandbox.py` prints lines 193 (dry run) and 212 (real run). `_spawn_container` in `src/devops_cli/sandbox/engine.py` calls `engine.create_container` (line 394), and `deploy` wraps any error as `Failed deploying sandbox container: ...` (line 381). That is the text in the issue.
- The workload runner is not the call site. `git grep -n "create_container" -- src` lists only `src/devops_cli/docker/sandbox.py:295` (the runner) and `src/devops_cli/sandbox/engine.py:394` (deploy). The runner serves `devops docker sandbox` and `devops test sandbox`.
- The engine answers a create with a missing image as the issue says. The call `containers.create("devops-contract-absent:never")` over the SDK printed `ImageNotFound 404 'No such image: devops-contract-absent:never'`. The recorded exchange `missing_objects` in `tests/fixtures/docker_engine/recorded_exchanges.json` holds the same 404 on `/containers/create`.
- The lookup raises a typed error for a missing image. `images.get("devops-contract-absent:never")` printed `ImageNotFound 404 'No such image: devops-contract-absent:never'`.
- A pull of an image that no registry holds raises a typed error that names the reason. `images.pull("devops-contract-absent:never")` printed `ImageNotFound 404 "pull access denied for devops-contract-absent, repository does not exist or may require 'docker login'"`. The error carries the reason, and the code adds the image reference.
- `images.pull` takes the tag from the reference. The source of `docker/models/images.py` (`ImageCollection.pull`) calls `parse_repository_tag(repository)`, uses `latest` when there is no tag, drains the pull stream, and then calls `self.get(...)`. So `images.pull("python:3.14-slim")` is enough.
- The fake lacks both calls. `grep -n '"images\.' tests/support/fakes/docker_engine.py` shows that `FakeImages` records only `images.list`, `images.build`, `images.push` and `images.prune`. `EngineImages` in `src/devops_cli/docker/sdk.py` has the same four methods. `DockerEngineFake.fail(name, error, times=)` exists and makes a named call raise.
- The contract suite requires a recorded scenario for each fake feature (`docs/TESTING.md`, "Docker engine, contract suite"). `tests/docker/test_engine_contract.py::test_the_record_is_of_the_locked_docker_sdk` fails when the scenarios and the record differ. The record is of SDK 7.2.0 and Engine 29.9.2, so a scenario recorded on this engine matches. A local engine is on this host: `/var/run/docker.sock`, `docker version` prints Engine 29.9.2.
- The dry-run plan lists requests. `plan_sandbox_deploy` in `src/devops_cli/sandbox/sandbox_plans.py` returns `POST /containers/create` and `POST /containers/<name>/start`, and `tests/commands/test_sandbox_dry_run.py` asserts `DOCKER POST /containers/create` in the output.
- Nothing newer did or removed this. `git log --oneline origin/main -5 -- src/devops_cli/sandbox/engine.py src/devops_cli/docker/engine.py` shows only #2845, #2588, #2561, #2546 and #2534, and none adds a pull. A search of the open and closed issues for "sandbox image pull" finds no other issue about it. #2603 (types for docker-py) and #2520 (sandbox logs, merged as #2546) do not touch this path.
- Dry run stays free of requests. `WorkloadSandboxEngine.deploy(cfg, dry_run=True)` returns before `_spawn_container`, so no pull call runs under a dry run.

## Acceptance

Criteria of the issue, and the group of `tasks.md` that delivers each:

- Pull a missing image before the container is created (scenario: deploy with a missing image): group 2 (`pull_image`) and group 3 (the deploy calls it).
- Skip the pull when the image is local (scenario: deploy with an existing image): group 2 and group 3.
- Name the image and the reason when the pull fails (scenario: pull fails): group 2 (the error text) and group 3 (the deploy shows it).
- Group 1 delivers no criterion by itself. It gives the tests of groups 2 and 3 a fake that answers `images.get` and `images.pull` as the engine does.
- Group 4 keeps the dry-run plan true to the real run. It is not a criterion of the issue. It follows from the dry-run rule (#412) once the real run makes two more requests.
- Pending a person: run the reproduction of the issue on a real engine without `python:3.14-slim`. Tests cannot reach a registry.

## Existing Tool Considered

docker-py 7.2.0 is a dependency already. `client.images.get(name)` checks for an image and `client.images.pull(repository)` pulls it. `containers.run` also pulls a missing image, but it starts the container. The sandbox deploy creates the container and starts it later, with a registry record and a rollback between the two, so `containers.run` does not fit. The change builds no pull logic of its own. `DockerEngineService.pull_image` is a wrapper that calls the two SDK methods and types the error. The change deletes no code.
