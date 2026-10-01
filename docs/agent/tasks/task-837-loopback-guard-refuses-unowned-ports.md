# Task: The Test Network Guard Refuses Loopback Connects to Services the Test Did Not Start (#837)

**Issue**: [#837](https://github.com/dan-petty/devops-cli/issues/837)
**Status**: Done
**Milestone**: v0.2.24
**Priority**: priority/p0-critical
**Scope**: scope/cli

## Description
The session fixture `prevent_external_network_calls` (`tests/conftest.py`) claimed to keep tests off live endpoints. It blocked DNS lookups and non-loopback connects, but it passed every loopback `connect` and `connect_ex` through, and the isolated test config sends telemetry to `http://localhost:4318`. On a workstation that holds `kubectl port-forward`s, the suite therefore reached the cluster's OTLP collector, Valkey, Ollama and the other forwarded services. CI declares no `services:`, so it only ever ran the connection-refused branches.

The issue cites no introducing commit. `git log -S` finds the loopback pass-through in the first version of the guard, 2ed28d4 (v0.2.16, #161). The `localhost:4318` test endpoint dates from f36add8 (v0.2.2, #21), and the `DEVOPS_CLI_TEST_LIVE_VALKEY` switch from 838c0d7 (v0.2.21, #329).

This delivers the `docs/ROADMAP.md` entry *Loopback Socket Guard So Tests Never Reach Port-Forwarded Services*.

- The guard wraps `socket.socket.listen` and records each port the test process listens on. A loopback `connect` to any other port raises `ConnectionRefusedError(ECONNREFUSED)`, and `connect_ex` returns `ECONNREFUSED`. Non-loopback connects still raise `RuntimeError`. The refusal is the `OSError` that `ValkeyClient` and the HTTP clients already handle. The docstring says that subprocesses a test spawns are not guarded.
- The guard stays installed after the session ends. The old fixture restored the socket methods at teardown, so a connect that ran after the last fixture went out unguarded. Examples are an OTLP export that the last test queued on a `devops-otel` thread, or one that `atexit` flushes. A scratch test whose thread connected to `localhost:4318` half a second after the session ended reached the stand-in collector while the guard was still restored at teardown, and was refused once it stayed installed. While the guard was still restored at teardown, one such export reached the stand-in collector in two of five full runs with the stand-ins up.
- `EmbeddingsEngine._init_valkey` no longer checks `PYTEST_CURRENT_TEST` or `DEVOPS_CLI_TEST_LIVE_VALKEY`. Production code carries no test logic, and the guard refuses the configured Valkey in every test. `test_init_valkey_fast_probe_offline` and `test_init_valkey_fast_probe_online` keep their fake clients without the switch. `test_init_valkey_skipped_during_pytest` became `test_init_valkey_runs_without_l2_when_valkey_refuses`, which drives the real client against the refused port.
- `test_popeye_dry_run` never enabled dry-run mode, so it ran the real `popeye` binary wherever it was installed. That binary is a subprocess the in-process guard cannot cover, and with no cluster in the isolated kubeconfig it queried `localhost:8080`, which is the ArgoCD port-forward. The test now enables dry-run mode and asserts the simulated finding, as #748 did for its Trivy, Kube-linter and Pluto siblings.
- `pytest-socket` was not adopted. Its `--allow-hosts` takes hosts, not ports, and its errors subclass `RuntimeError`.

## Acceptance Criteria
- [x] A connect to a loopback port that nothing in-process listens on raises `ConnectionRefusedError`, and `connect_ex` returns `ECONNREFUSED`. `test_network_guard_refuses_loopback_services_the_test_did_not_start` (`tests/test_validation.py`) listens through the C socket type, as a port-forward in another process does, so the kernel accepts connections on a port the guard never saw opened. It checks both calls for `127.0.0.1` and `localhost` and failed against the old guard with `DID NOT RAISE ConnectionRefusedError`.
- [x] A test that starts its own server in-process can still connect to it. `test_network_guard_lets_a_test_reach_a_server_it_started` connects and gets `connect_ex() == 0`. The suite's `HTTPServer` tests (`tests/test_sandbox_metrics.py`, `tests/test_sandbox_probe.py`) pass, and the probe below counts 21 connects, all to ports the test process listened on.
- [x] The full suite passes both with the usual port-forwards running and with none. The cluster is offline, so stand-in listeners took the place of the port-forwards. They listened on the ports `devops k8s port-forward` uses (3000, 4000, 4318, 6333, 6379, 8030, 8080, 8090, 11434, 16686), answered HTTP with 200 `{}` and RESP with `+PONG`/`+OK`, and ran in a private network namespace, so no other process could reach them. With the stand-ins up, the old guard failed `test_ingest_remote_docs_blocks_ssrf`, because `127.0.0.1:8080` answered, and passed 6,507 tests. With the new guard, every test passed (6,511 in the probe run), and the stand-ins accepted no connection in any of five gate runs or the probe run. With none, `uv run devops ci` passes.
- [x] The test-step durations of `devops ci` on ext4, with the stand-ins up, are recorded below.
- [x] `rg DEVOPS_CLI_TEST_LIVE_VALKEY src tests` returns nothing.
- [x] `uv run devops ci` passes.

## Measurements
These are loopback connection attempts in one full test run, counted by a scratch plugin wrapped around the guard (`pytest -p loopback_probe -n 8 tests`, stand-ins up):

| | Reached a stand-in service | Refused | Reached an in-process server | Total |
| :--- | ---: | ---: | ---: | ---: |
| Before | 2,597 (OTLP 2,545, Valkey 24, Ollama 15, 8080 5, 4000/8030/8090/16686 2 each) | 15 | 19 | 2,631 |
| After | 0 | 5,716 (OTLP 5,562, Valkey 80, Ollama 29, others 61) | 21 | 5,737 |

After the change, the OTLP attempts double. A refused export cannot reuse a kept-alive connection, so each one tries both `::1` and `127.0.0.1`. The Valkey attempts rise because every `EmbeddingsEngine` now probes. A refused probe costs about 2.5 ms per engine, which was measured over 20 constructions.

These are the `devops ci` test-step durations on ext4 (16 cores, 8 workers, stand-ins up, private network namespace). Other agents' gates shared the machine, so the runs are listed in order with the one-minute load average at their start and end. The spread follows that load. At comparable load the two guards take the same time: 1m 48s to 1m 57s at a load of 5 to 9, and 4m 45s to 4m 47s at a load of 27 to 32.

| Run | Guard | Load | Test step |
| :--- | :--- | :--- | ---: |
| 1 | Before | not recorded | 1m 53s |
| 2 | After | 8.7 to 6.6 | 1m 57s |
| 3 | Before | 7.8 to 5.3 | 1m 48s |
| 4 | After | 4.9 to 8.6 | 2m 39s |
| 5 | After | 8.1 to 24.9 | 4m 9s |
| 6 | Before | 32 to 27 | 4m 47s |
| 7 | After | 27 to 31 | 4m 45s |

Under the old guard, a slow live service also made the suite slow. In two baseline runs, the stand-ins were slowed by per-connection process lookups. There, `test_multi_project_indexing` took 73 to 83 s and `test_ollama_embedding_model_properties_and_embed` took 37 to 46 s, waiting on the stand-in Ollama. Under the new guard, neither is among the 25 slowest tests.
