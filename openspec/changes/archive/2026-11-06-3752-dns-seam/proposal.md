# Proposal

## Why

The DNS lookup of the egress check cannot be replaced (#3752, part 1 of #1314). `vet_addresses` calls `socket.getaddrinfo`, and `avet_addresses` calls `anyio.getaddrinfo`. A test that needs a name to resolve patches `socket.getaddrinfo` itself, through `public_dns` or `scripted_resolver`. Each lookup of the egress check now passes through these two functions, because #2437 deleted `_resolve_host_ips`. So one seam under them can serve every test of the egress check.

## What Changes

- `src/devops_cli/http/egress.py` gets a resolver seam: the `Resolver` Protocol, `SystemResolver` as the one place that supplies the real lookup, and `install_resolver`, `get_resolver` and `reset_resolver`. `vet_addresses` and `avet_addresses` resolve only through it. The checks, the errors and the timeout they have today do not change.
- `tests/support/fakes/dns.py` adds `DnsFake` and the `dns` fixture. The fixture installs the fake through the seam, also answers `socket.getaddrinfo` from it, and restores the real resolver at teardown. The root conftest keeps the reset of the seam in its list of process-wide resets.
- `tests/core/test_dns_contract.py` adds the contract suite. It runs each case over the fake and over `SystemResolver`.
- `tests/http/test_egress_resolver.py` holds what the vetting functions do with the seam. Four tests of `tests/http/test_http_egress.py` that patched `socket.getaddrinfo` for the egress check use the `dns` fixture.
- `docs/TESTING.md` and `ARCHITECTURE.md` name the seam.
- The change alters no behavior that a consumer observes: the resolver makes the same call as before, and the new code is test support. So it has no spec delta and sets `skip_specs: true`.
- The change fits one pull request.
- Not in this change: the move of the other test files that request `public_dns` or use `scripted_resolver`, and of the direct `socket.getaddrinfo` callers. Part 3 of #1314 moves them with their packages and then deletes `public_dns` and `ScriptedResolver`. The HTTP entry point and fake are part 2.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Source: `src/devops_cli/http/egress.py`.
- Tests: `tests/support/fakes/dns.py`, `tests/core/test_dns_contract.py`, `tests/http/test_egress_resolver.py`, `tests/http/test_http_egress.py`, `tests/conftest.py`.
- Documents: `docs/TESTING.md`, `ARCHITECTURE.md`.

## Feasibility

- On `origin/main` (44d9196d), `git grep -n "_resolve_host_ips" -- src tests` finds nothing. The only lookups of the egress check are `socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)` in `vet_addresses` and `anyio.getaddrinfo(...)` in `avet_addresses` (`src/devops_cli/http/egress.py`). So the premise holds, and the seam goes under these two functions, not in `core/validation.py` as the first text of #1314 said.
- `anyio.getaddrinfo` calls `socket.getaddrinfo` in a worker thread. A test that patches `socket.getaddrinfo` reaches the async lookup too, so the stdlib fallback of the fixture serves both. The existing test `test_a_slow_async_lookup_times_out_as_a_connect_timeout` patched it that way and passed.
- `anyio.fail_after(0)` around `anyio.getaddrinfo("localhost", ...)` raised `TimeoutError` in 17 of 20 runs, not in all (run with `uv run python -I`). So the contract suite makes the real lookup slow with a stdlib stand-in that blocks, and gives the timeout 0.05 s.
- A sync `socket.getaddrinfo` has no timeout, and the code has none today. The seam keeps that: only the async lookup takes a timeout.
- `tests/support/bootstrap.py` registers every module of `tests.support` that holds a fixture, so the new fake module needs no list to edit.

## Existing Tool Considered

No library covers this need: dnspython resolves names itself and would replace the system resolver (`/etc/hosts`, `nsswitch`) that the code relies on. A Protocol with one real implementation and one install hook follows the keyring seam (`src/devops_cli/config/os_keyring.py`). The code stays on `socket.getaddrinfo` and `anyio.getaddrinfo`. Cost: about 60,000 tokens to build the seam, the fake, the suite and the documents, about 5,000 tokens a year to keep them, and about 3 hours elapsed.

The change deletes the patches of `socket.getaddrinfo` in four tests of `tests/http/test_http_egress.py`. It keeps `public_dns` and `ScriptedResolver`, which part 3 of #1314 deletes when their last user moves.
