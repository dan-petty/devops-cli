# Tests double only process edges, through seams

Tests replace only what devops-cli reaches beyond its own process: other machines, long-lived daemons, programs other than git, bwrap and kubectl's offline renderers, the keyring and the wall clock. Everything inside the process runs for real, and no test patches a devops-cli module, function or private name. Each edge has one seam in the source tree that supplies its real implementation, and a test installs an in-memory fake through that seam. On 2026-10-07 the suite held 3,655 patch sites, 2,770 of them aimed at devops-cli internals, and 937 imports of private names. Refactors that kept behaviour still broke tests, and product code had grown branches that detect mocks or reshape modules so tests can patch them. The roadmap package showed the alternative already works: about 470 tests over an in-memory store and an injected `runner=` need about 68 patches.

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
- git and bwrap run for real inside temporary directories; bwrap tests are skipped only where bwrap is missing. kubectl's offline renderers, `kubectl kustomize` and `kubectl patch --local`, also run for real: they read only files and reach no cluster, and no maintained renderer exists to fake them with (added on 2026-10-20 by #1725).
- [`docs/TESTING.md`](../TESTING.md) states the conventions that follow from this decision.
