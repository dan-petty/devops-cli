# Design

## Context

See proposal.md for the motivation and the scope (#3751, part 5 of #1335). The fakes are the work of #775, #1315, #1316, #1318, #1320 and #3752.

## Decisions

### 1. The wait raises a typed error and the command prints it
- **Decision**: `await_workflow` raises `ArgoWorkflowTimeoutError`, a subclass of `ArgoError`. `commands/argo.py` catches that one class, prints its text and exits with 1. A failed read of the Workflow is not caught there: it ends the command as it did before.
- **Rejected**: raise the base `ArgoError`. The command would have to catch every Argo failure, and a failed read would then print through the timeout path.

### 2. The wait reads time through the clock seam
- **Decision**: `await_workflow` calls `clock.monotonic` and `clock.sleep` from `devops_cli.core.clock`. A test installs `ClockFake` with the `clock` fixture, and the wait takes no real time. The timeout and the poll interval are keyword arguments with the existing defaults.
- **Rejected**: `tenacity`. The loop has one read, one test and one sleep, and `tenacity` would wrap the same steps in a retry object.

### 3. A test changes the world while the code waits
- **Decision**: `ClockFake.after_each_sleep(action)` runs `action` after each wait. The Argo test turns the Workflow into a terminal phase after two waits, and the watcher tests edit a file or raise `KeyboardInterrupt` during a poll wait.
- **Rejected**: patch `sleep` in the test. That is the patch this change removes. A thread that edits the file in the background would make the test depend on timing.

### 4. Cloudflare matching is a public function over records
- **Decision**: `find_matching_records` takes the records and the target. `delete_dns_records` takes the client, lists the zone once and deletes through the client. The tests run it over `CloudflareClient` and the `web` fake, so the real client code and the real HTTP entry point run.
- **Rejected**: move `_resolve_client` as well. It only turns settings and a keyring secret into a client. That is wiring (the note of #3751).

### 5. The engine reads time through the clock seam
- **Decision**: `DockerEngineService` calls `clock.monotonic()` for the cache lifetime. The two tests that patched `time.monotonic` move the clock with `clock.shift`.
- **Rejected**: pass a time source to the constructor. It would add a parameter that only tests set, while the clock seam already exists for this purpose.

### 6. A host without a program is a PATH with no program in it
- **Decision**: the missing-program tests set `PATH` to an empty directory with `monkeypatch.setenv`. The code under test then fails its own lookup, and no process starts. `process_fake` answers the lookup of every program, so a test that needs a missing one cannot use it.
- **Rejected**: patch `shutil.which`. It is an internal patch of the lookup that the process fake owns.

### 7. The Podman socket constants stay in the shared fixture
- **Decision**: the tests in the engine file take the socket paths from `docker_endpoint_env`, which sets the constants for the files that share it. They patch nothing themselves.
- **Rejected**: add a constructor argument for the socket roots in this change. The fixture has users in other test files, and the change would grow beyond this item.
