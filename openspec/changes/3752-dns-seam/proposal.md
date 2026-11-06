# Proposal

## Why

Issue #3752 is part 1 of #1314. The DNS lookup of the egress check cannot be replaced. `vet_addresses` calls `socket.getaddrinfo` and `avet_addresses` calls `anyio.getaddrinfo` (`http/egress.py`), so a test that needs a name to resolve patches `socket.getaddrinfo` itself, through `public_dns` or `scripted_resolver`. docs/TESTING.md asks each edge for one seam, one fake and one contract suite.

## What Changes

- `http/egress.py` gains the `Resolver` Protocol, `SystemResolver` (the real lookup) and the hook `get_resolver`, `set_resolver` and `reset_resolver`. `vet_addresses` and `avet_addresses` resolve only through it.
- `tests/support/fakes/dns.py` adds `FakeResolver` and the `dns` fixture. The fixture installs the fake through the hook, removes it at teardown, and also answers `socket.getaddrinfo` from the same fake until the direct callers use the seam.
- `tests/http/test_dns_contract.py` adds the contract suite over the fake and the real resolver, and tests of the egress checks over the fake.
- The root conftest resets the resolver after each test.
- `ARCHITECTURE.md` and `docs/TESTING.md` describe the seam and the fake.
- This change alters no behavior a consumer observes, so it sets `skip_specs: true`.
- This change fits one pull request. The suite goes in `tests/http/`, the mirror directory of `http/egress.py`, not in `tests/core/` as the issue first said, because `_resolve_host_ips` left `core/` with #2437.
- The 44 test files that request `public_dns` and the 29 that use `scripted_resolver` move to `dns` with their packages in #3758, which then deletes both. The two coexist until then because those tests still patch `socket.getaddrinfo`.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `src/devops_cli/http/egress.py`: the resolver seam.
- `tests/support/fakes/dns.py`, `tests/http/test_dns_contract.py`: the fake, the fixture and the suite.
- `tests/conftest.py`: one reset entry.
- `ARCHITECTURE.md`, `docs/TESTING.md`: the seam.

## Feasibility

- `src/devops_cli/http/egress.py` is the only source module that resolves a name for the egress checks: `git grep -n getaddrinfo src/` finds `vet_addresses`, `avet_addresses` and one numeric-host check in `core/validation.py`. #2437 removed `_resolve_host_ips`, so the seam fits under `vet_addresses`.
- `anyio.getaddrinfo` and `socket.getaddrinfo` take the same arguments, so one Protocol covers both.
- The floor answers `localhost`, IP literals and numeric hosts, and refuses an unknown name with `socket.gaierror(EAI_NONAME)`. The real side of the contract suite therefore makes no DNS query. The timeout case has a real side too: it blocks `socket.getaddrinfo`, the stdlib edge below `anyio`, so the real async lookup outlasts a timeout of 0.05 s with no race. A timeout of zero is not reliable: it timed out in 288 of 300 tries. The suite passes over both sides.

## Existing Tool Considered

No open tool covers it: the alternatives check of #1314 (2026-10-29) found none. The seam follows the keyring seam (`config/os_keyring.py`): a Protocol, the real implementation and a hook. The change deletes no code. The cost to build, keep and fix the seam, fake and suite is about 40,000 tokens and half a day.
