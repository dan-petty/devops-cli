# Design

## Decisions

- **Name the moved function `resolve_trace_spans_or_latest` and keep it in `telemetry/waterfall.py`.**: `resolve_trace_spans` is the sibling that it calls, and `ui/waterfall_modal.py` and the engine call that one. A new `last` argument on `resolve_trace_spans` would change two other callers, which want no fallback. The moved function drops the clause `or not trace_id` of the old code: it never changes the result, because `resolve_trace_spans` already reads the latest buffered trace when no id is given.
- **Give the engine and the collector a `cgroup_root`, with the host mount as the default.**: The constructor of the engine already takes a `registry` for the same reason. A setting would need a README row and a name for a value that no user changes, and an environment variable would be read by code that only a test sets. The parameter is `None` by default and the code uses `/sys/fs/cgroup`.
- **Create the incident file with `os.open(..., 0o600)` and drop the `chmod` of the file.**: A `chmod` that fails after `os.replace` cannot be made to happen on a test filesystem, so its branch had a test only through a patch of `os.chmod`. The file is private from its creation, so there is no window in which others can read it, and the branch is not needed. The directory `chmod` stays as it was.
- **Register a sandbox in the real registry and in the Docker fake, in one fixture.**: Every command and engine test needed "a sandbox that is running". The fixture gives the container the name of the instance, so `script_exec`, `script_run` (logs) and `script_stats` take the instance id.
- **Keep the two seam sites.**: `socket.getaddrinfo` in `failed_lookups` shows that no name is looked up, and `socket.socket` in the TCP timeout test raises a timeout that no loopback listener gives without a wait. #1314 replaces both. Every other DNS answer comes from `scripted_resolver`, which wraps the same seam.
- **Move the shared Prometheus servers and `engine_stats_frame` to `tests/support/sandbox.py`.**: Four files use the HTTP server and the stats frame. A test file may not import another test file, so the support module holds them.
- **Test the CIDR branch of the public whitelist through `model_construct`.**: The validator refuses a public IPv6 CIDR (#3776). The branch is the builder's rule, and `model_construct` skips only the validators of the model.
- **Split the lifecycle, metrics and networking files in commits of their own.**: A commit that only moves tests reads as a move, and the commit that changes the tests after it reads as an edit.

## Rejected alternatives

- **Patch `os.chmod` with `monkeypatch`.**: It is a patch site, and #1336 turns every patch site into a ban.
- **Read the cgroup root from an environment variable.**: The variable would exist for tests only, so the module would be shaped so that a test can patch it (docs/TESTING.md, "Doubles").
- **Fix the IPv6 CIDR defect in this change.**: It is a behavior change with its own spec delta and its own issue (#3776). A second fix in a test migration hides both.

## Out of scope

- `tests/sandbox/test_sandbox_seccomp.py`, `test_sandbox_tool_executor.py`, `tests/telemetry/test_sandbox_traces.py` and `test_k8s_ipv6_and_proxy_boundaries.py`. #1336's ban finds any site that remains in them.
- The two seam sites. #1314 replaces them.
