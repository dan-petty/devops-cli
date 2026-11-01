## 1. Failing Tests First

- [x] 1.1 Add failing invariant test in `tests/invariants/test_hermetic_floor.py` verifying that opening paths under `/proc` or `/usr/local/share/tiktoken` fails with edge error
- [x] 1.2 Add test in `tests/invariants/test_hermetic_floor.py` verifying that `TIKTOKEN_CACHE_DIR` points to an empty directory by default and counts tokens identically
- [x] 1.3 Add test in `tests/invariants/test_hermetic_floor.py` verifying that `scanner_fake` sets `PATH` containing only the fake stand-ins and the interpreter directory

## 2. Implementation

- [x] 2.1 Implement `isolate_tiktoken_cache` in `tests/conftest.py`
- [x] 2.2 Implement fixed mounts and process table seams in `tests/conftest.py` for `ci.diagnostics` and `k8s.port_forward_daemon`
- [x] 2.3 Update `tests/k8s/test_k8s_port_forward_daemon.py` to avoid reading `/proc/self/stat`
- [x] 2.4 Update `scanner_fake` in `tests/support/fakes/scanners.py` to set hermetic `PATH` without host directories
- [x] 2.5 Install host path guard in `tests/conftest.py`
- [x] 2.6 Remove host-decided `pytest.skip` calls across the test suite

## 3. Verification

- [x] 3.1 Verify all tests in `tests/invariants/test_hermetic_floor.py` pass
- [x] 3.2 Run fast static checks and full `uv run devops ci`
- [x] 3.3 Archive OpenSpec change
