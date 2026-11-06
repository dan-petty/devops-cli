# Design

## Context

See proposal.md for the reason and the scope (#3752). Every lookup of the egress check goes through `vet_addresses` or `avet_addresses` in `src/devops_cli/http/egress.py`. Both call the stdlib directly, so a test patches `socket.getaddrinfo`.

## Goals / Non-Goals

**Goals:**
- One Protocol for the lookup, one place that supplies the real one, and one hook that installs another.
- One fake, one fixture and one contract suite that holds the fake to the real lookup.

**Non-Goals:**
- Route the direct `socket.getaddrinfo` callers (`telemetry/waterfall.py`, `sandbox/probe.py`, `sandbox/models.py`, `valkey/client.py`). Their packages own that.
- Move the other test files off `public_dns` and `scripted_resolver`.
- Change the HTTP client factories or the broker.

## Decisions

### 1. The seam sits in `http/egress.py`

- **Decision**: `Resolver`, `SystemResolver`, `get_resolver`, `install_resolver` and `reset_resolver` live in `src/devops_cli/http/egress.py`, next to the two functions that use them. `install_resolver` returns the resolver it replaces.
- **Alternative considered**: a new `core/dns.py`, as the first text of #1314 said.
  - *Rejected*: that text put the seam under `core/validation.py`. #2437 deleted the DNS branches of that module, and the lookups now sit in `http/egress.py`. A second module would add an import for the one caller that exists.

### 2. The Protocol has a sync and an async method

- **Decision**: `resolve(host, port)` and `aresolve(host, port, timeout)` return `getaddrinfo` answers for stream sockets. Only the async method takes a timeout.
- **Alternative considered**: a timeout on the sync method too.
  - *Rejected*: `socket.getaddrinfo` cannot be bounded, and bounding it needs a thread of our own. The code has no such bound today.
- **Alternative considered**: answers as plain address strings.
  - *Rejected*: the vetting code reads the family, the scope id and the flow field of each answer. A string loses them, and a scoped IPv6 answer must still fail closed.

### 3. The real resolver calls the stdlib when it is called

- **Decision**: `SystemResolver` looks up `socket.getaddrinfo` and `anyio.getaddrinfo` at each call. Code and tests that still patch `socket.getaddrinfo` keep working until their package moves to the seam.
- **Alternative considered**: bind the stdlib function in `SystemResolver.__init__`.
  - *Rejected*: it would silently ignore the patches of the test files that have not moved.

### 4. The fake reads address literals with the stdlib

- **Decision**: `DnsFake` answers an address literal through `socket.getaddrinfo(..., flags=AI_NUMERICHOST)`, which makes no DNS query and reads the spellings that glibc reads (`0xa9fea9fe`). It does not parse a literal itself.
- **Alternative considered**: `ipaddress.ip_address` in the fake.
  - *Rejected*: it does not read the legacy numeric spellings that the real lookup reads (#3128), so the fake would differ from the real lookup.

### 5. The contract suite makes the real lookup slow with a stdlib stand-in

- **Decision**: the timeout case of the real side blocks `socket.getaddrinfo` on an event until the case ends, with a timeout of 0.05 s. The fake side calls `stall("localhost")`.
- **Alternative considered**: a timeout of 0 on the real side.
  - *Rejected*: it raised `TimeoutError` in 17 of 20 runs, so the case would be flaky.

### 6. `public_dns` and `scripted_resolver` stay

- **Decision**: they patch `socket.getaddrinfo`, which `SystemResolver` still reaches, so every test that uses them passes unchanged. A test uses `dns` or the old pair, never both.
- **Alternative considered**: make `public_dns` a preset of the `dns` fixture.
  - *Rejected*: a test that requests `public_dns` and then calls `scripted_resolver` would find the fake in the seam, and the fake would ignore the scripted answers. Part 3 of #1314 moves those test files and deletes both.
