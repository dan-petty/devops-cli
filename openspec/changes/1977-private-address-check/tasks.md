# Tasks

## 1. No committed file holds a private address or a `.lan` host

- [x] Add the invariant test and its unit cases; the tree scan fails on the 10 in-scope addresses of origin/main
  - Verification: `uv run devops ci test tests/invariants/test_committed_addresses.py`
- [x] Move the scenarios of `configured-service-urls` and `stack-credential-sync` to `192.0.2.10`, the five tests that feed them to the same address, and the `reference_extractor.py` docstring to the NAT64 form of `192.0.2.1`
  - Verification: `uv run devops ci test tests/invariants/test_committed_addresses.py tests/test_argo.py tests/test_grafana.py tests/test_k8s_credentials.py tests/test_prometheus.py tests/test_http_egress.py`
- [x] Name the check in SECURITY.md rule 8, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1977-private-address-check`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
