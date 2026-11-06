# Tasks

## 1. The resolver seam and its fake (behavior)

- [x] 1.1 Write the contract suite `tests/http/test_dns_contract.py` and the vetting tests `tests/http/test_egress_resolver.py` first. They fail on the base, because the seam does not exist.
  Verification: `uv run pytest tests/http/test_dns_contract.py tests/http/test_egress_resolver.py`
- [x] 1.2 Add `DnsFake` and the `dns` fixture in `tests/support/fakes/dns.py`.
  Verification: `uv run pytest tests/http/test_dns_contract.py`
- [x] 1.3 Add `Resolver`, `SystemResolver`, `get_resolver`, `install_resolver` and `reset_resolver` to `src/devops_cli/http/egress.py`, and make `vet_addresses` and `avet_addresses` resolve only through them. Add the reset to the process-wide resets of `tests/conftest.py`.
  Verification: `uv run pytest tests/http/test_dns_contract.py tests/http/test_egress_resolver.py tests/invariants`

## 2. Tests of the egress check use the fake (test-only edits)

- [x] 2.1 In `tests/http/test_http_egress.py`, give the four tests that patched `socket.getaddrinfo` for the egress check the `dns` fixture.
  Verification: `uv run pytest tests/http/test_http_egress.py`
- [x] 2.2 Check that the move kept the behavior of the egress check.
  Verification: `uv run pytest tests/http tests/core`

## 3. Documents (documents)

- [x] 3.1 Name the seam, the fake, the fixture and the contract suite in `docs/TESTING.md`, and the seam in `ARCHITECTURE.md`.
  Verification: `uv run devops ci --check --only docs`
- [x] 3.2 Check that the change folder is valid.
  Verification: `uv run devops openspec check`

## Workflow follow-up

- Part 2 of #1314 builds the HTTP entry point and fake. Part 3 moves the other users of `public_dns` and `scripted_resolver` and the direct `socket.getaddrinfo` callers to the `dns` fixture and the seam with their packages, and then deletes `public_dns` and `ScriptedResolver`.
- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
