# Tests double only process edges, through seams

Tests replace only what devops-cli reaches beyond its own process: other machines, long-lived daemons, any program, the keyring and the wall clock. Everything inside the process runs for real, and no test patches a devops-cli module, function or private name. Each edge has one seam in the source tree that supplies its real implementation, and a test installs an in-memory fake through that seam. On 2026-10-07 the suite held 3,655 patch sites, 2,770 of them aimed at devops-cli internals, and 937 imports of private names. Refactors that kept behaviour still broke tests, and product code had grown branches that detect mocks or reshape modules so tests can patch them. The roadmap package showed the alternative already works: about 470 tests over an in-memory store and an injected `runner=` need about 68 patches.

## Considered Options

- **Patch at the library boundary only** (`subprocess.run`, httpx2 transports, SDK classes), with no source changes: rejected because several SDKs speak HTTP through other stacks (plain httpx, urllib3, requests) that a class swap cannot reach, and the shared HTTP pool hands out cached clients that bypass it. Patching the stdlib object itself stays as a fallback for stdlib edges.
- **Pass every client down the call graph as a parameter**: rejected as a rewrite of signatures across hundreds of modules for no gain over one seam per edge.
- **Allow internal patches with a stated reason**: rejected because exceptions accumulate until the rule means nothing.
- **freezegun for the clock**: rejected as unmaintained, and its frozen monotonic clock hangs asyncio and tenacity. time-machine fakes wall-clock reads; waiting goes through the parameters tenacity and pydantic-ai already offer. ratelimit takes only a `clock=` for its window, so its `sleep_and_retry` sleep is patched at the stdlib, the fallback for stdlib edges.

## Consequences

- An edge without a seam gets one before its tests migrate. The seams for processes (#775), the model client (#1001), the GitHub session (#983) and review tools (#772) come first.
- Every fake has a contract suite, run against the fake and against the real implementation with recorded responses or a local tool. The fakes live in `tests/support/fakes/`, one module per edge.
- The hermetic floor fails a test that reaches an edge without a fake, and resets process-wide state after every test. gh is such an edge: a test that starts a real gh would act as the developer's own login.
- Product code that detects mocks or exists only to be patched is removed, and ratchets keep internal patches, private imports and those accommodations from growing until each reaches zero.
- The decision of 2026-10-24 removes the earlier allowances for git in temporary repositories, kubectl offline renderers, bwrap with the `bwrap` mark, and `@pytest.mark.live`.
- [`docs/TESTING.md`](../TESTING.md) states the conventions that follow from this decision.

## Amendment (2026-10-24: a test of src starts no program)

The owner decided on 2026-10-24 that a test of `src/` starts no system program and does not read the host. Every test must run the same in the devcontainer and on a stock runner, with no installation and no host change on the runner.

This decision removes the following earlier allowances:
- git in temporary repositories.
- kubectl offline renderers (`kubectl kustomize` and `kubectl patch --local`).
- bwrap with the `bwrap` mark.
- `@pytest.mark.live` for live local tools.

Real child processes stay only in the contract suite of the process runner (`tests/test_process_contract.py` and the process-group tests of `core/process.py`). Every other real tool goes to a contract suite that replays recorded transcripts or to a `devops ci` row. Checks of committed files and tool configuration belong in `devops ci`. The bwrap suite is an opt-in contract suite that a person runs in the devcontainer. A test must not skip based on host state.
