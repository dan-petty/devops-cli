# Design: Hermetic Floor Host Independence

## Architecture and Seams

### 1. Tokenizer Cache Floor Isolation
- Add an autouse fixture `isolate_tiktoken_cache` in `tests/conftest.py`.
- Point `TIKTOKEN_CACHE_DIR` and `DATA_GYM_CACHE_DIR` to an empty directory within the test `tmp_path`.
- When an encoding cannot be found in the empty cache, `_get_tiktoken_encoding` gracefully falls back to the deterministic character heuristic count across all hosts.

### 2. Mounts and Process Table Seams
- In `tests/conftest.py`, point `devops_cli.ci.diagnostics._PROC_MOUNTS` to a fixed mounts file in `tmp_path` so callers without explicit `mounts_text` never read `/proc/mounts`.
- In `tests/conftest.py`, point `devops_cli.k8s.port_forward_daemon._PROC_ROOT` to a fixed `/proc` directory structure in `tmp_path` so port forward liveness checks never inspect the host process table.
- Update `tests/k8s/test_k8s_port_forward_daemon.py` to obtain process start ticks from the isolated fixture rather than reading `/proc/self/stat`.

### 3. Hermetic PATH in `scanner_fake`
- In `tests/support/fakes/scanners.py`, set `PATH` to `[str(fake.bin_dir), str(Path(sys.executable).parent)]`.
- Prevent discovery of unrecorded host binaries.

### 4. Hermetic File Open Guard
- Wrap `io.open` in `tests/conftest.py` with an edge guard that checks file access.
- Reject access to `/proc` and `/usr/local/share/tiktoken`.
- Allow paths under the repository root, the Python virtualenv/interpreter directory, and the test's `tmp_path`.
- Record and fail tests that breach the hermetic filesystem boundary.

### 5. Host-Decided Skips Removal
- Remove `pytest.skip` blocks for symlink creation, non-UTF-8 paths, and `/proc` availability across the test suite.
