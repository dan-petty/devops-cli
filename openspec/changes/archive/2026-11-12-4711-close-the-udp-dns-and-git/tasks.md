# Tasks

## 1. The floor refuses UDP sends, DNS lookups and git network transports

Kind: other (test-only edits). Changes: `tests/invariants/test_hermetic_floor.py`, `tests/conftest.py`, `tests/support/bootstrap.py`.

- [x] 1.1 Write the tests first: six caught probes (`sendto`, `sendmsg`, `gethostbyname`, `gethostbyname_ex`, `gethostbyaddr`, `getnameinfo`) each fail with `network edge reached without a fake`, a loopback UDP exchange and numeric lookups pass, and `git ls-remote` of an https and an ssh remote fails with `transport '<name>' not allowed`. The probe and git tests fail on `origin/main`.
  - Verification: `$ uv run devops ci test tests/invariants/test_hermetic_floor.py`
- [x] 1.2 Guard `sendto`, `sendmsg` and the four lookups in `tests/conftest.py`, and write `protocol.allow = never` and `protocol.file.allow = user` into the `.gitconfig` of the isolated HOME.
  - Verification: `$ uv run devops ci test tests/invariants/test_hermetic_floor.py`
- [x] 1.3 Run the full suite with the new floor.
  - Verification: `$ uv run devops ci test`

## 2. Documents

Kind: other. Changes: `docs/TESTING.md`.

- [x] 2.1 Name the send and lookup guards and the git config of the isolated HOME in the floor list and in "Exists today".
  - Verification: `$ uv run devops ci --check --only docs`
