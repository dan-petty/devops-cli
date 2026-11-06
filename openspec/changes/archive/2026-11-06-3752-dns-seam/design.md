# Design

## Context

#1314 gives each edge one seam in `src`, one fake and one contract suite. This change does it for the DNS lookup of the egress checks. #1314 splits into three parts; this is part 1 (#3752).

## Decisions

### The seam sits in `http/egress.py`, under `vet_addresses`

After #2437, `vet_addresses` and `avet_addresses` are the only lookups of the egress checks, so the seam belongs where the lookup happens. `Resolver` has a sync `lookup(host, port)` and an async `alookup(host, port, timeout)`. The hook is `set_resolver`, which returns the resolver it replaces, with `get_resolver` and `reset_resolver`, in the shape of `set_keyring_edge` and `reset_keyring_edge`.

- Rejected: `core/dns.py`, the place the issue first named. #2437 deleted the DNS code of `core/validation.py`, so no caller is left there.
- Rejected: patching `socket.getaddrinfo` in the fixture only. It cannot cover `anyio.getaddrinfo`, and TESTING.md allows a stdlib patch only as a fallback where no seam exists.

### The timeout belongs to the resolver

`SystemResolver.alookup` applies `anyio.fail_after(timeout)` and raises `TimeoutError`, and `avet_addresses` maps that to `httpcore2.ConnectTimeout`. A fake can then stall a name without a clock.

### The fixture also answers `socket.getaddrinfo`

Direct callers of `socket.getaddrinfo` remain outside the egress checks (`core/validation.py` keeps one numeric-host check, and other packages call it). Until they move, the `dns` fixture answers the stdlib call from the same fake, and leaves calls with `AI_NUMERICHOST` to the lookup it replaces.

### The suite lives in `tests/http/`

The seam is in `http/`, and docs/TESTING.md asks `tests/` to mirror the package tree.

- Rejected: `tests/core/`, named by the issue before #2437 moved the seam.

### `public_dns` and `scripted_resolver` stay for now

The 73 files that use them still patch `socket.getaddrinfo` and `httpcore2` dials. They move with their packages in #3758, which deletes them. The `dns` fixture can already do all they do.
