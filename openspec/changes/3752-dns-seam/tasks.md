# Tasks

## 1. The DNS seam, its fake and its contract suite

- [x] 1.1 Add the contract suite `tests/http/test_dns_contract.py` and the fake `tests/support/fakes/dns.py` with its `dns` fixture; the suite cannot run on the base, where the seam does not exist
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Add the `Resolver` Protocol, `SystemResolver` and the hook to `src/devops_cli/http/egress.py`, make `vet_addresses` and `avet_addresses` resolve through it, and reset it in the root conftest
  - Verification: `uv run devops ci test tests/http/test_dns_contract.py tests/http/test_http_egress.py`

## 2. Documents

- [x] 2.1 Describe the seam in `ARCHITECTURE.md` and the fake in `docs/TESTING.md`
  - Verification: `uv run devops ci docs`

## 3. Archive

- [ ] 3.1 Archive the change
  - Verification: `uv run devops openspec archive 3752-dns-seam`

## Workflow follow-up

- The tests that request `public_dns` or `scripted_resolver` move to `dns` with their packages in #3758, which deletes both.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
